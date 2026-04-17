#!/usr/bin/env python

import base64
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import argparse


def _hex64(s: str) -> str:
    """Device Portal hex64 encoding: base64 over the UTF-16LE bytes."""
    return base64.b64encode(s.encode("utf-16-le")).decode()


def _pp(data):
    print(json.dumps(data, indent=2))


class Xbox:
    def __init__(self, host: str, username: str, password: str, port: int = 11443):
        self.base = f"https://{host}:{port}"
        self._auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def _req(self, method: str, path: str, params: dict = None,
             body: bytes = None, content_type: str = None) -> bytes:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", f"Basic {self._auth}")
        if body:
            req.data = body
            req.add_header("Content-Type", content_type or "application/json")

        try:
            with urllib.request.urlopen(req, context=self._ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {body.decode(errors='replace')}")

    def _get(self, path: str, params: dict = None) -> bytes:
        return self._req("GET", path, params=params)

    def _get_json(self, path: str, params: dict = None) -> dict:
        return json.loads(self._get(path, params))

    def _post(self, path: str, params: dict = None, body: bytes = None,
              content_type: str = None) -> bytes:
        return self._req("POST", path, params=params, body=body or b"",
                         content_type=content_type)

    def _delete(self, path: str, params: dict = None) -> bytes:
        return self._req("DELETE", path, params=params)

    def os_info(self) -> dict:
        return self._get_json("/api/os/info")

    def machine_name(self) -> str:
        data = self._get_json("/api/os/machinename")
        return data.get("ComputerName", str(data))

    def set_machine_name(self, name: str):
        self._post("/api/os/machinename", params={"name": name})

    def processes(self) -> dict:
        return self._get_json("/api/resourcemanager/processes")

    def system_perf(self) -> dict:
        return self._get_json("/api/resourcemanager/systemperf")

    def find_pid(self, name: str) -> list[int]:
        data = self.processes()
        return [
            p["ProcessId"]
            for p in data.get("Processes", [])
            if name.lower() in p.get("ImageName", "").lower()
        ]

    def start_app(self, package_full_name: str, app_id: str):
        self._post("/api/taskmanager/app", params={
            "appid":   _hex64(app_id),
            "package": _hex64(package_full_name),
        })

    def stop_app(self, package_full_name: str, force: bool = False):
        params = {"package": _hex64(package_full_name)}
        if force:
            params["forcestop"] = "yes"
        self._delete("/api/taskmanager/app", params)

    def stop_process(self, pid: int):
        self._delete("/api/taskmanager/process", {"pid": pid})

    def installed_packages(self, streamable_only: bool = False) -> dict:
        params = {"streamable": "true"} if streamable_only else None
        return self._get_json("/api/appx/packagemanager/packages", params)

    def install_status(self) -> dict:
        return self._get_json("/api/appx/packagemanager/state")

    def install_package(self, local_path: str, package_name: str = None):
        """Upload and install an appx package."""
        package_name = package_name or os.path.basename(local_path)
        with open(local_path, "rb") as f:
            data = f.read()
        boundary = "----XboxInstall"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{package_name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        self._post("/api/appx/packagemanager/package",
                   params={"package": package_name},
                   body=body,
                   content_type=f"multipart/form-data; boundary={boundary}")
        print(f"[+] Installed {package_name}")

    def register_network_app(self, network_share: str, username: str = None,
                             password: str = None,
                             optional_packages: list[dict] = None):
        """Register an app from a network share (loose files)."""
        main = {"networkshare": network_share}
        if username:
            main["username"] = username
        if password:
            main["password"] = password
        payload = {"mainpackage": main}
        if optional_packages:
            payload["optionalpackages"] = optional_packages
        self._post("/api/appx/packagemanager/networkapp",
                   body=json.dumps(payload).encode(),
                   content_type="application/json")

    def uninstall_package(self, package_full_name: str):
        self._delete("/api/appx/packagemanager/package",
                     {"package": package_full_name})

    def get_content_groups(self) -> dict:
        """List content groups for a streamable app in dev mode."""
        return self._get_json("/api/appx/packagemanager/contentgroups")

    def set_content_groups(self, body: dict):
        """Set content group state/percent-staged for a streamable app."""
        self._post("/api/appx/packagemanager/contentgroups",
                   body=json.dumps(body).encode(),
                   content_type="application/json")

    def dump_process(self, pid: int, out_path: str) -> int:
        """Collect a live usermode dump for pid."""
        print(f"[*] Dumping PID {pid} -> {out_path}")
        data = self._get("/api/debug/dump/usermode/live", {"pid": pid})
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] Dump saved: {len(data):,} bytes")
        return len(data)

    def dump_by_name(self, process_name: str, out_dir: str = ".") -> list[str]:
        """Find all PIDs matching name and dump each one."""
        pids = self.find_pid(process_name)
        if not pids:
            print(f"[!] No process matching '{process_name}' found")
            return []
        paths = []
        for pid in pids:
            out = os.path.join(out_dir, f"{process_name}_{pid}.dmp")
            self.dump_process(pid, out)
            paths.append(out)
        return paths

    def live_kernel_dump(self, out_path: str) -> int:
        """Collect a live full kernel dump."""
        print(f"[*] Collecting live kernel dump -> {out_path}")
        data = self._get("/api/debug/dump/livekernel")
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] Kernel dump saved: {len(data):,} bytes")
        return len(data)

    def bugcheck_dumps(self) -> dict:
        return self._get_json("/api/debug/dump/kernel/dumplist")

    def download_bugcheck_dump(self, filename: str, out_path: str) -> int:
        data = self._get("/api/debug/dump/kernel/dump", {"filename": filename})
        with open(out_path, "wb") as f:
            f.write(data)
        return len(data)

    def get_bugcheck_crash_control(self) -> dict:
        return self._get_json("/api/debug/dump/kernel/crashcontrol")

    def set_bugcheck_crash_control(self, autoreboot: bool = None, dumptype: int = None,
                                   maxdumpcount: int = None, overwrite: bool = None):
        params = {}
        if autoreboot is not None:
            params["autoreboot"] = "true" if autoreboot else "false"
        if dumptype is not None:
            params["dumptype"] = dumptype
        if maxdumpcount is not None:
            params["maxdumpcount"] = maxdumpcount
        if overwrite is not None:
            params["overwrite"] = "true" if overwrite else "false"
        self._post("/api/debug/dump/kernel/crashcontrol", params=params)

    def crash_dump_list(self) -> dict:
        return self._get_json("/api/debug/dump/usermode/dumps")

    def get_crash_control(self, package_full_name: str) -> dict:
        return self._get_json("/api/debug/dump/usermode/crashcontrol",
                              {"packageFullname": package_full_name})

    def enable_crash_control(self, package_full_name: str):
        self._post("/api/debug/dump/usermode/crashcontrol",
                   params={"packageFullname": package_full_name})

    def disable_crash_control(self, package_full_name: str):
        self._delete("/api/debug/dump/usermode/crashcontrol",
                     {"packageFullname": package_full_name})

    def download_crash_dump(self, package_full_name: str, file_name: str,
                            out_path: str) -> int:
        data = self._get("/api/debug/dump/usermode/crashdump",
                         {"packageFullname": package_full_name, "fileName": file_name})
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] Crash dump saved: {out_path} ({len(data):,} bytes)")
        return len(data)

    def delete_crash_dump(self, package_full_name: str, file_name: str):
        self._delete("/api/debug/dump/usermode/crashdump",
                     {"packageFullname": package_full_name, "fileName": file_name})

    def known_folders(self) -> list[str]:
        data = self._get_json("/api/filesystem/apps/knownfolders")
        return data.get("KnownFolders", data)

    def files(self, folder: str, subfolder: str = None) -> dict:
        params = {"knownfolderid": folder}
        if subfolder:
            params["path"] = subfolder
        return self._get_json("/api/filesystem/apps/files", params)

    def download_file(self, folder: str, filename: str, out_path: str,
                      subfolder: str = None) -> int:
        params = {"knownfolderid": folder, "filename": filename}
        if subfolder:
            params["path"] = subfolder
        data = self._get("/api/filesystem/apps/file", params)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] Downloaded {filename} -> {out_path} ({len(data):,} bytes)")
        return len(data)

    def upload_file(self, folder: str, local_path: str,
                    remote_name: str = None, subfolder: str = None):
        remote_name = remote_name or os.path.basename(local_path)
        with open(local_path, "rb") as f:
            data = f.read()
        boundary = "----XboxUpload"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{remote_name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        params = {"knownfolderid": folder, "filename": remote_name}
        if subfolder:
            params["path"] = subfolder
        self._post("/api/filesystem/apps/file", params=params, body=body,
                   content_type=f"multipart/form-data; boundary={boundary}")
        print(f"[+] Uploaded {local_path} -> {folder}/{remote_name}")

    def delete_file(self, folder: str, filename: str, subfolder: str = None):
        params = {"knownfolderid": folder, "filename": filename}
        if subfolder:
            params["path"] = subfolder
        self._delete("/api/filesystem/apps/file", params)
        print(f"[+] Deleted {folder}/{filename}")

    def rename_file(self, folder: str, filename: str, new_name: str,
                    subfolder: str = None):
        params = {"knownfolderid": folder, "filename": filename, "newfilename": new_name}
        if subfolder:
            params["path"] = subfolder
        self._post("/api/filesystem/apps/rename", params=params)
        print(f"[+] Renamed {filename} -> {new_name}")

    def etw_providers(self) -> dict:
        return self._get_json("/api/etw/providers")

    def wpr_status(self) -> dict:
        return self._get_json("/api/wpr/status")

    def wpr_start(self, profile: str):
        self._post("/api/wpr/trace", params={"profile": profile})

    def wpr_stop(self, out_path: str) -> int:
        data = self._get("/api/wpr/trace")
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] WPR trace saved: {out_path} ({len(data):,} bytes)")
        return len(data)

    def wpr_boot_trace_start(self, profile: str):
        self._get("/api/wpr/boottrace", params={"profile": profile})

    def wpr_boot_trace_stop(self, out_path: str) -> int:
        data = self._get("/api/wpr/boottrace")
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[+] WPR boot trace saved: {out_path} ({len(data):,} bytes)")
        return len(data)

    def wpr_custom_trace(self, profile_path: str) -> dict:
        """Upload a WPR profile and start tracing with it."""
        with open(profile_path, "rb") as f:
            data = f.read()
        boundary = "----XboxWPR"
        name = os.path.basename(profile_path)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        raw = self._post("/api/wpr/customtrace", body=body,
                         content_type=f"multipart/form-data; boundary={boundary}")
        return json.loads(raw)

    def wer_reports(self) -> dict:
        return self._get_json("/api/wer/reports")

    def wer_report_files(self, user: str, report_type: str, name: str) -> dict:
        return self._get_json("/api/wer/reports/files", {
            "user": user, "type": report_type, "name": name,
        })

    def wer_download_file(self, user: str, report_type: str,
                          name: str, file: str, out_path: str) -> int:
        data = self._get("/api/wer/reports/file", {
            "user": user, "type": report_type, "name": name, "file": file,
        })
        with open(out_path, "wb") as f:
            f.write(data)
        return len(data)

    def ipconfig(self) -> dict:
        return self._get_json("/api/networking/ipconfig")

    def wifi_interfaces(self) -> dict:
        return self._get_json("/api/wifi/interfaces")

    def wifi_networks(self, interface_guid: str) -> dict:
        return self._get_json("/api/wifi/networks", {"interface": interface_guid})

    def wifi_connect(self, interface_guid: str, ssid: str, key: str = None):
        params = {"interface": interface_guid, "op": "connect", "ssid": ssid}
        if key:
            params["key"] = key
        self._post("/api/wifi/network", params=params)

    def wifi_disconnect(self, interface_guid: str):
        self._post("/api/wifi/network",
                   params={"interface": interface_guid, "op": "disconnect"})

    def wifi_delete_profile(self, interface_guid: str, profile: str):
        self._delete("/api/wifi/network",
                     {"interface": interface_guid, "profile": profile})

    def battery_state(self) -> dict:
        return self._get_json("/api/power/battery")

    def power_state(self) -> dict:
        return self._get_json("/api/power/state")

    def get_active_power_scheme(self) -> dict:
        return self._get_json("/api/power/activecfg")

    def set_active_power_scheme(self, scheme_guid: str):
        self._post("/api/power/activecfg", params={"scheme": scheme_guid})

    def restart(self):
        print("[*] Sending restart...")
        self._post("/api/control/restart")

    def shutdown(self):
        print("[*] Sending shutdown...")
        self._post("/api/control/shutdown")

    def device_tree(self) -> dict:
        return self._get_json("/api/devicemanager/devices")

    def bt_paired(self) -> dict:
        return self._get_json("/api/bt/getpaired")

    def bt_available(self) -> dict:
        return self._get_json("/api/bt/getavailable")

    def bt_pair(self, device_id: str):
        self._get("/api/bt/pair", {"deviceId": device_id})

    def bt_unpair(self, device_id: str):
        self._post("/api/bt/unpair", params={"deviceId": device_id})

    def bt_discoverable(self):
        self._get("/api/bt/discoverable")

    def bt_get_radios(self) -> dict:
        return self._get_json("/api/bt/getradios")

    def bt_set_radio(self, adapter_id_b64: str, state: str):
        """state: 'On' or 'Off'. adapter_id_b64: base64-encoded adapter device id."""
        self._post("/api/bt/setradio",
                   params={"ID": adapter_id_b64, "State": state})

    def bt_connect_device(self, device_id_b64: str):
        """Connect a Bluetooth audio device. device_id_b64: base64-encoded device id."""
        self._post("/api/bt/connectdevice", params={"deviceId": device_id_b64})

    def bt_disconnect_device(self, device_id_b64: str):
        """Disconnect a Bluetooth audio device. device_id_b64: base64-encoded device id."""
        self._post("/api/bt/disconnectdevice", params={"deviceId": device_id_b64})

    def snapshot(self, out_dir: str = "xbox_snapshot"):
        os.makedirs(out_dir, exist_ok=True)

        tasks = [
            ("os_info",    self.os_info,           "os_info.json"),
            ("processes",  self.processes,          "processes.json"),
            ("systemperf", self.system_perf,        "systemperf.json"),
            ("packages",   self.installed_packages, "packages.json"),
            ("etw",        self.etw_providers,      "etw_providers.json"),
            ("wer",        self.wer_reports,        "wer_reports.json"),
            ("devices",    self.device_tree,        "device_tree.json"),
            ("ipconfig",   self.ipconfig,           "ipconfig.json"),
            ("bt_paired",  self.bt_paired,          "bt_paired.json"),
            ("bt_radios",  self.bt_get_radios,      "bt_radios.json"),
            ("wifi",       self.wifi_interfaces,    "wifi_interfaces.json"),
            ("power",      self.power_state,        "power_state.json"),
            ("battery",    self.battery_state,      "battery_state.json"),
            ("wpr",        self.wpr_status,         "wpr_status.json"),
        ]

        for label, fn, fname in tasks:
            try:
                path = os.path.join(out_dir, fname)
                with open(path, "w") as f:
                    json.dump(fn(), f, indent=2)
                print(f"[+] {label:12s} -> {path}")
            except Exception as e:
                print(f"[!] {label:12s} failed: {e}")

        try:
            self.download_file("DevelopmentFiles", "xbprobe_results.txt",
                               os.path.join(out_dir, "xbprobe_results.txt"))
        except Exception:
            pass

        print(f"\n[*] Snapshot complete: {out_dir}/")

def _cmd_info(xb, _):         _pp(xb.os_info())
def _cmd_ps(xb, _):           _pp(xb.processes())
def _cmd_perf(xb, _):         _pp(xb.system_perf())
def _cmd_packages(xb, _):     _pp(xb.installed_packages())
def _cmd_etw(xb, _):          _pp(xb.etw_providers())
def _cmd_wer(xb, _):          _pp(xb.wer_reports())
def _cmd_devices(xb, _):      _pp(xb.device_tree())
def _cmd_ipconfig(xb, _):     _pp(xb.ipconfig())
def _cmd_bt(xb, _):           _pp(xb.bt_paired())
def _cmd_bt_avail(xb, _):     _pp(xb.bt_available())
def _cmd_bt_radios(xb, _):    _pp(xb.bt_get_radios())
def _cmd_wifi(xb, _):         _pp(xb.wifi_interfaces())
def _cmd_power(xb, _):        _pp(xb.power_state())
def _cmd_battery(xb, _):      _pp(xb.battery_state())
def _cmd_wpr_status(xb, _):   _pp(xb.wpr_status())
def _cmd_snapshot(xb, _):     xb.snapshot()

def _cmd_set_name(xb, args):      xb.set_machine_name(args.name)
def _cmd_dump(xb, args):          xb.dump_process(args.pid, args.out or f"{args.pid}.dmp")
def _cmd_dumpname(xb, args):      xb.dump_by_name(args.name, args.outdir)
def _cmd_kernel_dump(xb, args):   xb.live_kernel_dump(args.out or "kernel.dmp")
def _cmd_ls(xb, args):            _pp(xb.files(args.folder, getattr(args, "subfolder", None)))
def _cmd_get(xb, args):           xb.download_file(args.folder, args.filename, args.out or args.filename)
def _cmd_put(xb, args):           xb.upload_file(args.folder, args.local_path)
def _cmd_rm(xb, args):            xb.delete_file(args.folder, args.filename)
def _cmd_mv(xb, args):            xb.rename_file(args.folder, args.filename, args.new_name)
def _cmd_install(xb, args):       xb.install_package(args.local_path)
def _cmd_uninstall(xb, args):     xb.uninstall_package(args.package)
def _cmd_wpr_start(xb, args):     xb.wpr_start(args.profile)
def _cmd_wpr_stop(xb, args):      xb.wpr_stop(args.out or "trace.etl")
def _cmd_bt_pair(xb, args):       xb.bt_pair(args.device_id)
def _cmd_bt_unpair(xb, args):     xb.bt_unpair(args.device_id)
def _cmd_wifi_nets(xb, args):     _pp(xb.wifi_networks(args.interface))
def _cmd_wifi_connect(xb, args):  xb.wifi_connect(args.interface, args.ssid, args.key)
def _cmd_wifi_disconnect(xb, args): xb.wifi_disconnect(args.interface)


def main():
    ap = argparse.ArgumentParser(description="Xbox Device Portal client")
    ap.add_argument("--host",     default="Xbox")
    ap.add_argument("--user",     default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--port",     type=int, default=11443)

    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, aliases=(), **kw):
        p = sub.add_parser(name, aliases=list(aliases), help=help_, **kw)
        p.set_defaults(func=fn)
        return p

    add("info",        _cmd_info,        "OS info",                    aliases=["os"])
    p = add("setname", _cmd_set_name,    "Set machine name")
    p.add_argument("name")

    add("ps",          _cmd_ps,          "Process list",               aliases=["procs"])
    add("perf",        _cmd_perf,        "System performance stats",   aliases=["stats"])

    add("packages",    _cmd_packages,    "Installed packages",         aliases=["apps"])
    p = add("install", _cmd_install,     "Install an appx package")
    p.add_argument("local_path")
    p = add("uninstall", _cmd_uninstall, "Uninstall a package")
    p.add_argument("package", help="Full package name")

    p = add("dump",     _cmd_dump,        "Live usermode process dump")
    p.add_argument("pid", type=int)
    p.add_argument("out", nargs="?")

    p = add("dumpname", _cmd_dumpname,   "Dump all processes matching name")
    p.add_argument("name")
    p.add_argument("--outdir", default=".")

    p = add("kdump",    _cmd_kernel_dump, "Live kernel dump")
    p.add_argument("out", nargs="?")

    p = add("ls",  _cmd_ls,  "List files in a known folder")
    p.add_argument("folder")
    p.add_argument("subfolder", nargs="?")

    p = add("get", _cmd_get, "Download a file")
    p.add_argument("folder")
    p.add_argument("filename")
    p.add_argument("out", nargs="?")

    p = add("put", _cmd_put, "Upload a file")
    p.add_argument("folder")
    p.add_argument("local_path")

    p = add("rm",  _cmd_rm,  "Delete a file")
    p.add_argument("folder")
    p.add_argument("filename")

    p = add("mv",  _cmd_mv,  "Rename a file")
    p.add_argument("folder")
    p.add_argument("filename")
    p.add_argument("new_name")

    add("etw",       _cmd_etw,        "ETW providers")
    add("wer",       _cmd_wer,        "WER reports",                aliases=["crashes"])
    add("wprstatus", _cmd_wpr_status, "WPR tracing status")

    p = add("wprstart", _cmd_wpr_start, "Start WPR trace")
    p.add_argument("profile")

    p = add("wprstop",  _cmd_wpr_stop,  "Stop WPR trace and save ETL")
    p.add_argument("out", nargs="?", help="Output path (default: trace.etl)")

    add("ipconfig",       _cmd_ipconfig,      "Network config",         aliases=["ip"])
    add("wifi",           _cmd_wifi,          "List WiFi interfaces")

    p = add("wifinetworks",   _cmd_wifi_nets,       "Scan networks on an interface")
    p.add_argument("interface")

    p = add("wificonnect",    _cmd_wifi_connect,    "Connect to a WiFi network")
    p.add_argument("interface")
    p.add_argument("ssid")
    p.add_argument("key", nargs="?")

    p = add("wifidisconnect", _cmd_wifi_disconnect, "Disconnect from WiFi")
    p.add_argument("interface")

    add("power",   _cmd_power,   "Power state")
    add("battery", _cmd_battery, "Battery state")

    add("devices", _cmd_devices, "Device tree",    aliases=["hw"])

    add("bt",       _cmd_bt,        "Paired Bluetooth devices")
    add("btavail",  _cmd_bt_avail,  "Available Bluetooth devices")
    add("btradios", _cmd_bt_radios, "Bluetooth radios/adapters")

    p = add("btpair",   _cmd_bt_pair,   "Pair a Bluetooth device")
    p.add_argument("device_id")

    p = add("btunpair", _cmd_bt_unpair, "Unpair a Bluetooth device")
    p.add_argument("device_id")

    add("snapshot", _cmd_snapshot, "Dump all state to ./xbox_snapshot/", aliases=["snap"])

    args = ap.parse_args()
    xb = Xbox(args.host, args.user, args.password, args.port)
    args.func(xb, args)


if __name__ == "__main__":
    main()
