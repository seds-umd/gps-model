# GPS Receiver in Python

This is a Python framework for processing GPS L1 C/A signals.

Currently implemented:
* Acquisition and tracking of individual satellites
* (Partially) navigation message decoding

Planned:
* Calculating position fix
* Real time processing from SDR

## Tests

From the repository root, after installing the requirements:

```bash
python -m unittest discover -s tests -v
```

The tests use seeded synthetic signals, so they need no capture file and no
hardware. They cover fine-acquisition frequency bins, coarse code phase across
the whole C/A epoch, acquisition-to-tracking convergence, streaming in
irregular chunks, tracking restart, the public receiver at decimation factors
1, 4, 8 and 16, LNAV field decoding, complete-frame decoding through subframes 1 to 3,
and the capture-file CLI. They are noiseless reference checks, not a
sensitivity measurement, and there is still no position solution.

A few behaviours worth knowing when you use the model:

* Coarse acquisition correlates a whole number of 1 ms C/A periods (8,184
  samples for a 500 Hz bin at 4.092 Msps) instead of rounding up to a power of
  two, which spliced the code at the window edge and could shift the peak near
  the epoch boundary. This assumes the sample rate is a multiple of 1 kHz;
  resample other rates first.
* Fine-acquisition bins come from `fftfreq`, so DC is exactly zero and spacing
  is `f_s / (fft_n * dec_factor)`.
* `TrackingChannel.start` resets all loop and decoder state and requires a code
  phase within one C/A period, measured from the same sample epoch acquisition
  used. Chunk boundaries do not disturb tracking. A zero-energy block leaves
  the loop estimates alone and resets the frame decoder, so a frame is never
  spliced across a gap; there is no lock-loss detector or reacquisition yet.
* FPGA acquisition results give frequency as a signed 12-bit bin index and code
  phase relative to the front end's 4092-sample timestamp epoch. Align a
  capture to that epoch before seeding the Python tracker.
* Navigation decoding is still partial: no subframe 4/5 pages, no ephemeris
  consistency checks, no pseudoranges. The preamble detector expects exactly
  20 correlator samples per bit, so real bit-edge jitter is not handled yet.
  Field references are IS-GPS-200N sections 20.3.3.3.1.4 and 20.3.3.4.1-2 and
  Table 20-III.

## Capture-file input

```bash
python main.py capture.iq --fs 4092000 --width 8
```

The capture must be alternating signed I, Q integers; `--width` is 8, 16 or 32
bits per integer, little-endian. The file is memory-mapped and processed in
one-second chunks, so long captures do not need a second copy in RAM. Missing,
empty or odd-length files and bad sample rates fail with a clear error.

## Setup

Clone recursively:

```bash
git clone --recursive git@github.com:seds-umd/gps-model.git
```

Create a virtual environment and install required packages:

```bash
python3.12 -m venv venv   # 3.11 or 3.12: the pinned numpy 1.x has no wheels for newer Pythons
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
