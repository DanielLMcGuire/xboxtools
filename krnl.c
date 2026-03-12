#include <windows.h>
#include <winternl.h>
#include <stdio.h>

#define SystemModuleInformation 11

typedef struct _RTL_PROCESS_MODULE_INFORMATION {
    HANDLE Section;
    PVOID MappedBase;
    PVOID ImageBase;
    ULONG ImageSize;
    ULONG Flags;
    USHORT LoadOrderIndex;
    USHORT InitOrderIndex;
    USHORT LoadCount;
    USHORT OffsetToFileName;
    UCHAR FullPathName[256];
} RTL_PROCESS_MODULE_INFORMATION;

typedef struct _RTL_PROCESS_MODULES {
    ULONG NumberOfModules;
    RTL_PROCESS_MODULE_INFORMATION Modules[1];
} RTL_PROCESS_MODULES;

typedef NTSTATUS (WINAPI *PNtQuerySystemInformation)(
    ULONG, PVOID, ULONG, PULONG);

void list_kernel_modules() {
    PNtQuerySystemInformation NtQSI = (PNtQuerySystemInformation)
        GetProcAddress(GetModuleHandleA("ntdll.dll"), 
                      "NtQuerySystemInformation");

    ULONG size = 1024 * 1024;
    RTL_PROCESS_MODULES *modules = (RTL_PROCESS_MODULES*)malloc(size);
    ULONG needed = 0;

    NTSTATUS status = NtQSI(SystemModuleInformation, modules, size, &needed);
    if (status != 0) {
        printf("NtQSI failed: %08X (needed %u bytes)\n", status, needed);
        free(modules);
        return;
    }

    printf("Loaded kernel modules (%u):\n", modules->NumberOfModules);
    for (ULONG i = 0; i < modules->NumberOfModules; i++) {
        RTL_PROCESS_MODULE_INFORMATION *m = &modules->Modules[i];
        printf("  [%3u] Base: %p  Size: %08X  %s\n",
               i,
               m->ImageBase,
               m->ImageSize,
               m->FullPathName);
    }
    free(modules);
}

void probe_device(const char *path) {
    HANDLE h = CreateFileA(path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, 0, NULL);

    if (h == INVALID_HANDLE_VALUE) {
        printf("  [!] %s - failed (%u)\n", path, GetLastError());
        return;
    }
    printf("  [+] %s - OPEN\n", path);
    // Sleep(50000);
    CloseHandle(h);
}

int main() {
    printf("=== Kernel Module Enumeration ===\n");
    list_kernel_modules();

    printf("\n=== Device Probe ===\n");
    const char *targets[] = {
        "\\\\.\\xvmctrl",
        "\\\\.\\xvioc",
        "\\\\.\\xvbus",
        "\\\\.\\XVIO",
        "\\\\.\\xvmctrl0",
        NULL
    };

    for (int i = 0; targets[i]; i++)
        probe_device(targets[i]);

    return 0;
}