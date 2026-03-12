#include <stdio.h>
#include <intrin.h>
#include <string.h>

void print_vendor() {
    int info[4];
    char vendor[13];

    __cpuid(info, 0);

    memcpy(vendor + 0, &info[1], 4);
    memcpy(vendor + 4, &info[3], 4);
    memcpy(vendor + 8, &info[2], 4);
    vendor[12] = 0;

    printf("Vendor: %s\n", vendor);
}

void print_brand() {
    int info[4];
    char brand[49];

    for (int i = 0; i < 3; i++) {
        __cpuid(info, 0x80000002 + i);
        memcpy(brand + i * 16, info, 16);
    }

    brand[48] = 0;
    printf("CPU: %s\n", brand);
}

void print_topology() {
    int info[4];

    __cpuid(info, 1);

    int threads = (info[1] >> 16) & 0xff;

    __cpuid(info, 0x80000008);

    int cores = (info[2] & 0xff) + 1;

    printf("Cores: %d\n", cores);
    printf("Threads: %d\n", threads);
}

void print_cache_sharing() {
    int info[4];

    printf("\nCache Sharing Topology:\n");

    for (int i = 0;; i++) {
        __cpuidex(info, 0x8000001D, i);

        int type = info[0] & 0x1f;
        if (type == 0) break;

        int level = (info[0] >> 5) & 7;
        int max_threads = ((info[0] >> 14) & 0xfff) + 1;

        const char *type_str = "Unknown";
        if (type == 1) type_str = "Data";
        else if (type == 2) type_str = "Instruction";
        else if (type == 3) type_str = "Unified";

        printf("L%d %s Cache shared by %d threads\n", level, type_str, max_threads);
    }
}

void print_cpu_features() {
    int info[4];

    __cpuid(info, 1);

    printf("\nCPU Feature Flags:\n");

    if (info[3] & (1 << 0)) printf("  FPU ");
    if (info[3] & (1 << 23)) printf("  MMX ");
    if (info[3] & (1 << 25)) printf("  SSE ");
    if (info[3] & (1 << 26)) printf("  SSE2 ");

    if (info[2] & (1 << 0)) printf("  SSE3 ");
    if (info[2] & (1 << 9)) printf("  SSSE3 ");
    if (info[2] & (1 << 19)) printf("  SSE4.1 ");
    if (info[2] & (1 << 20)) printf("  SSE4.2 ");
    if (info[2] & (1 << 28)) printf("  AVX ");

    printf("\n");
}

void print_l1_cache() {
    int info[4];

    __cpuid(info, 0x80000005);

    int l1d = (info[2] >> 24) & 0xff;
    int l1i = (info[3] >> 24) & 0xff;

    int l1d_line = info[2] & 0xff;
    int l1i_line = info[3] & 0xff;

    printf("L1 Data Cache: %d KB (Line Size %d)\n", l1d, l1d_line);
    printf("L1 Instruction Cache: %d KB (Line Size %d)\n", l1i, l1i_line);
}

void print_l2_l3_cache() {
    int info[4];

    __cpuid(info, 0x80000006);

    int l2 = (info[2] >> 16) & 0xffff;
    int l2_line = info[2] & 0xff;

    int l3 = ((info[3] >> 18) & 0x3fff) * 512;
    int l3_line = info[3] & 0xff;

    printf("L2 Cache: %d KB (Line Size %d)\n", l2, l2_line);

    if (l3 > 0)
        printf("L3 Cache: %d KB (Line Size %d)\n", l3, l3_line);
}

void print_deterministic_cache() {
    int info[4];

    for (int i = 0;; i++) {

        __cpuidex(info, 0x8000001D, i);

        int type = info[0] & 0x1f;
        if (type == 0) break;

        int level = (info[0] >> 5) & 7;

        int ways = ((info[1] >> 22) & 0x3ff) + 1;
        int partitions = ((info[1] >> 12) & 0x3ff) + 1;
        int linesize = (info[1] & 0xfff) + 1;
        int sets = info[2] + 1;

        int size = (ways * partitions * linesize * sets) / 1024;

        const char *type_str = "Unknown";

        if (type == 1) type_str = "Data";
        else if (type == 2) type_str = "Instruction";
        else if (type == 3) type_str = "Unified";

        printf("L%d %s Cache: %d KB\n", level, type_str, size);
        printf("  Line Size: %d\n", linesize);
        printf("  Ways: %d\n", ways);
        printf("  Sets: %d\n", sets);
    }
}

void print_raw_leaves() {
    int info[4];

    __cpuid(info, 0x40000000);
    printf("Hypervisor max leaf: 0x%x\n", info[0]);
    char hvvendor[13] = {0};
    memcpy(hvvendor, &info[1], 4);
    memcpy(hvvendor+4, &info[2], 4);
    memcpy(hvvendor+8, &info[3], 4);
    printf("Hypervisor vendor: %s\n", hvvendor);
    
    __cpuid(info, 0x40000001);
    printf("HV interface: 0x%x\n", info[0]);
    
    __cpuid(info, 0x40000003);
    printf("HV features EAX: 0x%x\n", info[0]);
    printf("HV features EBX: 0x%x\n", info[1]);
    
    __cpuid(info, 0);
    printf("Max standard leaf: 0x%x\n", info[0]);

    __cpuid(info, 0x80000000);
    printf("Max extended leaf: 0x%x\n", info[0]);
}

void print_extd_topology() {
    int info[4];

    __cpuid(info, 0x8000001E);
    printf("  Thread ID: %d\n", info[0] & 0xff);
    printf("  Threads per core: %d\n", ((info[1] >> 8) & 0xff) + 1);
    printf("  Core ID: %d\n", info[1] & 0xff);
    printf("  Nodes per processor: %d\n", ((info[2] >> 8) & 0xff) + 1);
    printf("  Node ID: %d\n", info[2] & 0xff);
}

int main() {
    print_vendor();
    print_brand();
    print_topology();
    print_cpu_features();

    printf("\nAMD Cache Leaves\n");
    print_l1_cache();
    print_l2_l3_cache();
    print_cache_sharing();
    printf("\nRaw Leaves\n");
    print_raw_leaves();

    printf("\nDeterministic Cache (0x8000001D)\n");
    print_deterministic_cache();

    printf("\nExtended topology\n");
    print_extd_topology();
}