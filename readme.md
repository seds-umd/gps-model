# GPS Receiver in Python

This is a Python framework for processing GPS L1 C/A signals.

Currently implemented:
* Acquisition and tracking of individual satellites
* (Partially) navigation message decoding

Planned:
* Calculating position fix
* Real time processing from SDR

## Setup

Create a virtual environment and install required packages.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Generate simulated GPS data

* 60 seconds
* 8 bit IQ
* Ionospheric delay disabled

```bash
./gps-sdr-sim/gps-sdr-sim -e data/brdc2570.23n -l 38.986008,-76.942566,10.0 -b 8 -d 60 -i -s 2600000 -o data/gpssim.ci16
```
