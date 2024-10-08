#pragma once

#include <complex.h>
#include <stdint.h>

int8_t *prn_generate(int sv);
float complex *prn_sample(int sv, float fs, int len, int offset_phase, float offset_samples);
