#include <stdio.h>
#include <intrin.h>

int main() {
    int info[4];
    for(int i = 0; ; i++) {
        __cpuidex(info, 0x8000001D, i);
        if((info[0] & 0x1f) == 0) break;
        int level = (info[0] >> 5) & 7;
        int ways = ((info[1] >> 22) & 0x3ff) + 1;
        int linesize = (info[1] & 0xfff) + 1;
        int sets = info[2] + 1;
        int size = (ways * linesize * sets) / 1024;
        printf("L%d: %d KB\n", level, size);
    }
}