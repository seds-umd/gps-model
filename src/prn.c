#include "prn.h"

#include <complex.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static uint8_t sv_params[][2] = {
    {-1, -1}, // SV=0 unused
    {2,  6 },
    {3,  7 },
    {4,  8 },
    {5,  9 },
    {1,  9 },
    {2,  10},
    {1,  8 },
    {2,  9 },
    {3,  10},
    {2,  3 },
    {3,  4 },
    {5,  6 },
    {6,  7 },
    {7,  8 },
    {8,  9 },
    {9,  10},
    {1,  4 },
    {2,  5 },
    {3,  6 },
    {4,  7 },
    {5,  8 },
    {6,  9 },
    {1,  3 },
    {4,  6 },
    {5,  7 },
    {6,  8 },
    {7,  9 },
    {8,  10},
    {1,  6 },
    {2,  7 },
    {3,  8 },
    {4,  9 },
};

static int prn_shift_g1(uint16_t *g1) {
    uint16_t g1_pre = *g1;

    uint8_t out = 0;
    out ^= g1_pre >> (10 - 1);
    out &= 1;

    uint8_t fb = 0;
    fb ^= g1_pre >> (3 - 1);
    fb ^= g1_pre >> (10 - 1);
    fb &= 1;

    *g1 <<= 1;
    *g1 |= fb;

    return out;
}

static int prn_shift_g2(uint16_t *g2, int sv) {
    uint16_t g2_pre = *g2;

    uint8_t out = 0;
    out ^= g2_pre >> (sv_params[sv][0] - 1);
    out ^= g2_pre >> (sv_params[sv][1] - 1);
    out &= 1;

    uint8_t fb = 0;
    fb ^= g2_pre >> (2 - 1);
    fb ^= g2_pre >> (3 - 1);
    fb ^= g2_pre >> (6 - 1);
    fb ^= g2_pre >> (8 - 1);
    fb ^= g2_pre >> (9 - 1);
    fb ^= g2_pre >> (10 - 1);
    fb &= 1;

    *g2 <<= 1;
    *g2 |= fb;

    return out;
}

// Length is always 1023
int8_t *prn_generate(int sv) {
    // Initial value is all ones
    uint16_t g1 = 0x3FF;
    uint16_t g2 = 0x3FF;

    int8_t *ca = malloc(sizeof(int) * 1023);

    for (int i = 0; i < 1023; i++) {
        uint8_t g1_out = prn_shift_g1(&g1);
        uint8_t g2_out = prn_shift_g2(&g2, sv);

        uint8_t res = g1_out ^ g2_out;

        if (res == 0) {
            ca[i] = -1;
        } else {
            ca[i] = 1;
        }

        g1 &= 0x3FF;
        g2 &= 0x3FF;
    }

    return ca;
}

float complex *prn_sample(int sv, float fs, int len, int offset_phase, float offset_samples) {
    float chip_rate        = 1.023e6;  // From GPS spec
    int8_t *prn            = prn_generate(sv);
    float complex *samples = malloc(sizeof(float complex) * len);

    for (int i = 0; i < len; i++) {
        int prn_idx = (int)(floor((i + offset_samples) * (chip_rate / fs) + 0.5) + offset_phase) % 1023;

        samples[i] = prn[prn_idx] + 0 * I;
    }

    free(prn);
    return samples;
}
