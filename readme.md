# GPS Receiver in Python

This is a Python framework for processing GPS L1 C/A signals.

Currently implemented:
* Acquisition and tracking of individual satellites
* (Partially) navigation message decoding

Planned:
* Calculating position fix
* Real time processing from SDR

## Reproducible reference checks

From the repository root, after installing the requirements:

```bash
python -m unittest discover -s tests -v
```

The tests cover exact signed fine-FFT frequency bins; coarse code phases across
the full C/A epoch, including the wrap; two-second acquisition-to-tracking
convergence; irregular stream chunks; tracking restart and blank-input recovery;
the public receiver at decimation factors 1, 4, 8 and 16; navigation field boundary
values; and capture-file validation. These use seeded synthetic signals, not
live-RF sensitivity measurements or a position solution.

Coarse acquisition correlates a whole number of 1 ms C/A periods rather than
rounding to a power of two. At 4.092 Msps, a 500 Hz search bin uses 8,184 samples;
a power-of-two window splices the code and can return an incorrect phase near
the epoch boundary. Exact circular code-period correlation assumes the sample
rate is a whole multiple of 1 kHz, as in the 4 and 4.092 Msps capture settings;
other rates need resampling or separate phase-error qualification. Fine bins use `fftfreq`: spacing is
`f_s / (fft_n * dec_factor)` and DC is exactly zero.

`TrackingChannel.start` clears its previous signal, loop and decoder state and
requires a phase within one C/A period. Supply the same initial sample epoch
used by acquisition. Streaming chunk boundaries preserve tracking state.
Zero-energy correlators leave the loop estimates unchanged and skip decoder
input; this prevents NaN corruption, but does not implement a general lock-loss
detector or automatic reacquisition.

For FPGA acquisition results, frequency is a signed 12-bit bin index and code
phase refers to the front end's 4092-sample timestamp epoch. Align a capture to
that epoch before seeding the Python tracker; a phase for an unrelated block
is invalid. The standalone `gps.tracking` helper and the streaming receiver
are separate implementations; streaming lifecycle tests exercise the latter.

Navigation decoding remains partial. Corrected fields are the six-bit health
value, two's-complement negative limits, split signed 32-bit orbital fields,
and subframe-2 AODO (word 10 bits 18–22, 900 seconds per unit, excluding the
fit flag). AODO 27,900 seconds is the specification's invalid-NMCT indicator,
not an ordinary valid age. See [IS-GPS-200N](https://www.gps.gov/sites/default/files/2025-07/IS-GPS-200N.pdf),
sections 20.3.3.3.1.4 and 20.3.3.4.1–.2 and Table 20-III. Boundary tests do not
qualify the full parity/frame decoder or establish a navigation fix.

## Capture-file input

```bash
python main.py capture.iq --fs 4092000 --width 8
```

The capture must contain alternating signed I, Q integers. `--width` is 8, 16
or 32 bits per integer; multibyte integers are little-endian. The filename does
not determine width. Missing, empty or incomplete I/Q files and invalid sample
rates fail with an explanatory CLI error. The file is memory-mapped and converted
in roughly one-second chunks, retaining the final partial chunk. Use the actual
capture's sample rate; input validation does not establish RF suitability.

## Setup

Clone recursively:

```bash
git clone --recursive git@github.com:seds-umd/gps-model.git
```

Create a virtual environment and install required packages:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For better performance:

```bash
pip install mkl-fft mkl-service
```

## Generate simulated GPS data

* 60 seconds
* 8 bit IQ
* 4.092 Msps

```bash
./external/gps-sdr-sim/gps-sdr-sim -e data/brdc2570.23n -l 38.986008,-76.942566,10.0 -b 8 -d 60 -s 4092000 -o data/1/gpssim.ci16
```

Output (sv, azimuth, elevation, range, ionosphere_delay):

```
Using static location mode.
xyz =   1121575.5,  -4835955.6,   3991116.0
llh =   38.986008,  -76.942566,        10.0
Start time = 2023/09/14,00:00:00 (2279:345600)
Duration = 60.0 [sec]
03  263.0  40.1  21992642.7   5.9
04  312.6  33.2  22555628.4   6.2
09  313.0   6.2  25075733.3  10.3
16  202.7  57.1  20659221.3   4.6
26   99.6  84.0  20017697.3   3.8
27  170.3   6.5  24996606.1  13.2
28   68.2  38.7  22098657.2   5.3
29   54.8  18.4  23855962.8   7.1
31   39.2  62.4  20642429.7   4.1
32  133.1  19.6  23591461.8   8.5
```

## Example

```bash
python3 main.py data/2/GPS-L1-2022-03-27.sigmf-data --fs 4000000 --width 16
```

## Profiling

```bash
pip install snakeviz
python3 -m cProfile -o main.prof main.py data/2/GPS-L1-2022-03-27.sigmf-data --fs 4000000 --width 16
snakeviz main.prof
```
