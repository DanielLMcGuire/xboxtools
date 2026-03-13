#include <stdio.h>
#include <intrin.h>
#include <string.h>
#include <stdbool.h>

typedef enum { VENDOR_INTEL, VENDOR_AMD, VENDOR_UNKNOWN } ProcessorVendor;

static ProcessorVendor get_vendor() {
    int info[4];
    char vendor[13];

    __cpuid(info, 0);
    memcpy(vendor + 0, &info[1], 4);
    memcpy(vendor + 4, &info[3], 4);
    memcpy(vendor + 8, &info[2], 4);
    vendor[12] = 0;

    if (strcmp(vendor, "AuthenticAMD") == 0) return VENDOR_AMD;
    if (strcmp(vendor, "GenuineIntel") == 0) return VENDOR_INTEL;
    return VENDOR_UNKNOWN;
}

static int max_standard_leaf() {
    int info[4];
    __cpuid(info, 0);
    return info[0];
}

static int max_extended_leaf() {
    int info[4];
    __cpuid(info, 0x80000000);
    return info[0];
}

void print_vendor(ProcessorVendor procvend) {
    if (procvend == VENDOR_INTEL) {
        puts("Vendor: Intel");
    } else if (procvend == VENDOR_AMD) {
        puts("Vendor: AMD");
    } else {
        puts("Vendor: Unknown");
    }
}

void print_brand() {
    if (max_extended_leaf() < (int)0x80000004) {
        puts("CPU: (brand string not supported)");
        return;
    }

    int info[4];
    char brand[49];

    for (int i = 0; i < 3; i++) {
        __cpuid(info, 0x80000002 + i);
        memcpy(brand + i * 16, info, 16);
    }

    brand[48] = 0;

    char *p = brand;
    while (*p == ' ') p++;

    printf("CPU: %s\n", p);
}

void print_cpu_features() {
    int info[4];

    __cpuid(info, 1);

    puts("\nCPU Feature Flags:");

    if (info[3] & (1 << 0))  printf(" FPU");
    if (info[3] & (1 << 23)) printf(" MMX");
    if (info[3] & (1 << 25)) printf(" SSE");
    if (info[3] & (1 << 26)) printf(" SSE2");
    if (info[3] & (1 << 28)) printf(" HTT");

    if (info[2] & (1 << 0))  printf(" SSE3");
    if (info[2] & (1 << 9))  printf(" SSSE3");
    if (info[2] & (1 << 19)) printf(" SSE4.1");
    if (info[2] & (1 << 20)) printf(" SSE4.2");
    if (info[2] & (1 << 28)) printf(" AVX");
    if (info[2] & (1 << 12)) printf(" FMA");
    if (info[2] & (1 << 5))  printf(" VMX");
    if (info[2] & (1 << 2))  printf(" DTES64");

    if (max_standard_leaf() >= 7) {
        __cpuidex(info, 7, 0);
        if (info[1] & (1 << 5))  printf(" AVX2");
        if (info[1] & (1 << 16)) printf(" AVX512F");
        if (info[1] & (1 << 3))  printf(" BMI1");
        if (info[1] & (1 << 8))  printf(" BMI2");
        if (info[1] & (1 << 19)) printf(" ADX");
        if (info[1] & (1 << 29)) printf(" SHA");
    }

    puts("");
}

void print_hypervisor() {
    int info[4];

    __cpuid(info, 1);
    bool hypervisor_active = (info[2] >> 31) & 1;

    puts("\nHypervisor:");
    printf("  Hypervisor state: %s\n", hypervisor_active ? "active" : "inactive");

    if (!hypervisor_active) return;

    __cpuid(info, 0x40000000);
    printf("  Max hypervisor leaf: 0x%x\n", info[0]);

    char hvvendor[13] = {0};
    memcpy(hvvendor,     &info[1], 4);
    memcpy(hvvendor + 4, &info[2], 4);
    memcpy(hvvendor + 8, &info[3], 4);
    printf("  Hypervisor vendor: %s\n", hvvendor);
}

void print_topology_intel() {
    int info[4];

    if (max_standard_leaf() >= 0xB) {
        __cpuidex(info, 0xB, 0);
        int threads_per_core = info[1] & 0xffff;

        __cpuidex(info, 0xB, 1);
        int logical_per_pkg = info[1] & 0xffff;
        int cores = (threads_per_core > 0) ? logical_per_pkg / threads_per_core : logical_per_pkg;

        printf("Cores (logical):  %d\n", logical_per_pkg);
        printf("Cores (physical): %d\n", cores);
        printf("Threads per core: %d\n", threads_per_core);
    } else {
        // old intel
        __cpuid(info, 1);
        int logical = (info[1] >> 16) & 0xff;
        printf("Logical processors: %d\n", logical);
    }
}

void print_topology_amd() {
    int info[4];

    __cpuid(info, 1);
    int threads = (info[1] >> 16) & 0xff;

    __cpuid(info, 0x80000008);
    int cores = (info[2] & 0xff) + 1;

    printf("Cores (physical): %d\n", cores);
    printf("Logical threads:  %d\n", threads);

    if (max_extended_leaf() >= (int)0x8000001E) {
        __cpuid(info, 0x8000001E);
        printf("Thread ID:        %d\n", info[0] & 0xff);
        printf("Threads per core: %d\n", ((info[1] >> 8) & 0xff) + 1);
        printf("Core ID:          %d\n", info[1] & 0xff);
        printf("Node ID:          %d\n", info[2] & 0xff);
        printf("Nodes/processor:  %d\n", ((info[2] >> 8) & 0xff) + 1);
    }
}

void print_cache_intel() {
    int info[4];

    puts("\nCache (Intel leaf 4):");

    for (int i = 0;; i++) {
        __cpuidex(info, 4, i);

        int type = info[0] & 0x1f;
        if (type == 0) break;

        int level      = (info[0] >> 5) & 7;
        int max_threads = ((info[0] >> 14) & 0xfff) + 1;
        int ways       = ((info[1] >> 22) & 0x3ff) + 1;
        int partitions = ((info[1] >> 12) & 0x3ff) + 1;
        int linesize   = (info[1] & 0xfff) + 1;
        int sets       = info[2] + 1;
        int size_kb    = (ways * partitions * linesize * sets) / 1024;

        const char *type_str = "Unknown";
        if (type == 1) type_str = "Data";
        else if (type == 2) type_str = "Instruction";
        else if (type == 3) type_str = "Unified";

        printf("L%d %s Cache: %d KB\n", level, type_str, size_kb);
        printf("  Line size: %d B, Ways: %d, Sets: %d, Shared by: %d threads\n",
               linesize, ways, sets, max_threads);
    }
}

void print_cache_amd() {
    int info[4];

    if (max_extended_leaf() >= (int)0x80000005) {
        __cpuid(info, 0x80000005);
        int l1d      = (info[2] >> 24) & 0xff;
        int l1i      = (info[3] >> 24) & 0xff;
        int l1d_line = info[2] & 0xff;
        int l1i_line = info[3] & 0xff;
        puts("\nCache (AMD legacy leaves):");
        printf("L1 Data Cache:        %d KB (line %d B)\n", l1d, l1d_line);
        printf("L1 Instruction Cache: %d KB (line %d B)\n", l1i, l1i_line);
    }

    if (max_extended_leaf() >= (int)0x80000006) {
        __cpuid(info, 0x80000006);
        int l2      = (info[2] >> 16) & 0xffff;
        int l2_line = info[2] & 0xff;
        int l3      = ((info[3] >> 18) & 0x3fff) * 512;
        int l3_line = info[3] & 0xff;
        printf("L2 Cache: %d KB (line %d B)\n", l2, l2_line);
        if (l3 > 0)
            printf("L3 Cache: %d KB (line %d B)\n", l3, l3_line);
    }

    if (max_extended_leaf() >= (int)0x8000001D) {
        printf("\nCache (AMD deterministic leaf 0x8000001D):\n");
        for (int i = 0;; i++) {
            __cpuidex(info, 0x8000001D, i);
            int type = info[0] & 0x1f;
            if (type == 0) break;

            int level       = (info[0] >> 5) & 7;
            int max_threads = ((info[0] >> 14) & 0xfff) + 1;
            int ways        = ((info[1] >> 22) & 0x3ff) + 1;
            int partitions  = ((info[1] >> 12) & 0x3ff) + 1;
            int linesize    = (info[1] & 0xfff) + 1;
            int sets        = info[2] + 1;
            int size_kb     = (ways * partitions * linesize * sets) / 1024;

            const char *type_str = "Unknown";
            if (type == 1) type_str = "Data";
            else if (type == 2) type_str = "Instruction";
            else if (type == 3) type_str = "Unified";

            printf("L%d %s Cache: %d KB\n", level, type_str, size_kb);
            printf("  Line size: %d B, Ways: %d, Sets: %d, Shared by: %d threads\n",
                   linesize, ways, sets, max_threads);
        }
    }
}

int main() {
    ProcessorVendor procvend = get_vendor();

    print_vendor(procvend);
    print_brand();

    puts("\nTopology:");
    if (procvend == VENDOR_INTEL)
        print_topology_intel();
    else if (procvend == VENDOR_AMD)
        print_topology_amd();
    else
        puts("\nunknown vendor");

    print_cpu_features();

    if (procvend == VENDOR_INTEL)
        print_cache_intel();
    else if (procvend == VENDOR_AMD)
        print_cache_amd();
    else
        puts("\nunknown vendor");

    print_hypervisor();

    return 0;
}