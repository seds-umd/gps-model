# GPS Receiver in Python

This is a Python framework for processing GPS L1 C/A signals.

Currently implemented:
* Acquisition and tracking of individual satellites
* (Partially) navigation message decoding

Planned:
* Calculating position fix
* Real time processing from SDR

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
