#include <assert.h>
#include <complex.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "prn.h"

#define DoNotOptimize(value) asm volatile("" : : "r,m"(value) : "memory")

static float power(float complex *samples, int len) {
    float sum = 0;

    for (int i = 0; i < len; i++) {
        sum += pow(cabs(samples[i]), 2);
    }

    return sum / len;
}

float complex *gps_simulate(int len, int fs, int sv, float doppler) {
    assert(fs % 50 == 0);
    unsigned int block = fs / 50;

    // Generate PRN code
    float complex *code = prn_sample(sv, fs, block, 0, 0);
    int num_bits        = ceil((float)len / block);

    float complex *samples = malloc(sizeof(float complex) * len);

    srand(time(NULL));

    // Assumes rand() is 32 bits, but also this data doesn't need to be truly random
    uint32_t rand_val;
    for (int i = 0; i < num_bits; i++) {
        if (i % 32 == 0) {
            rand_val = rand();
        }

        int8_t bit = rand_val % 1;
        bit        = 2 * bit - 1;
        rand_val >>= 1;

        for (int j = 0; j < block; j++) {
            if (i * block + j == len) {
                break;
            }

            samples[i * block + j] = code[j] * bit + 0 * I;
        }
    }

    for (int i = 0; i < len; i++) {
        // Add doppler effect
        float t = i / fs;
        samples[i] *= cexpf(2 * I * M_PI * (doppler)*t);

        // Add noise

        // Create noise at unity power
        float complex noise = (float)rand() / (float)RAND_MAX + I * (float)rand() / (float)RAND_MAX;
        noise               = 2 * noise - 1 - 1 * I;
        noise /= sqrt(2.0 / 3.0);

        // TODO: scale noise
    }

    printf("Samples power: %f\n", power(samples, len));

    free(code);

    return samples;
}

int main() {
    gps_simulate(2e5, 4.092e6, 8, 0);
}
