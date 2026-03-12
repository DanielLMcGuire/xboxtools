#include <stdio.h>
#include <windows.h>
#include <intrin.h>

double measure_tsc_mhz(int core) {
    LARGE_INTEGER start, end;
    unsigned __int64 tsc_start, tsc_end;
    double mhz;

    DWORD_PTR mask = 1ULL << core;
    DWORD_PTR orig_mask = SetThreadAffinityMask(GetCurrentThread(), mask);

    QueryPerformanceCounter(&start);
    tsc_start = __rdtsc();

    Sleep(100); // sleep ~100ms for measurable delta

    tsc_end = __rdtsc();
    QueryPerformanceCounter(&end);

    // restore original affinity
    SetThreadAffinityMask(GetCurrentThread(), orig_mask);

    LARGE_INTEGER freq;
    QueryPerformanceFrequency(&freq);

    double elapsed_sec = (double)(end.QuadPart - start.QuadPart) / (double)freq.QuadPart;
    mhz = (tsc_end - tsc_start) / (elapsed_sec * 1e6);

    return mhz;
}

int main() {
    int cores = 16; // adjust per thread count
    for(int i = 0; i < cores; i++) {
        double freq = measure_tsc_mhz(i);
        printf("Core %d approximate frequency: %.2f MHz\n", i, freq);
    }
}