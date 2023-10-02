# Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Generate simulated GPS data

* 5 seconds
* 8 bit IQ
* Ionospheric delay disabled

```bash
./gps-sdr-sim/gps-sdr-sim -e brdc2570.23n -l 38.986008,-76.942566,10.0 -b 8 -d 60 -i -s 2600000
```
