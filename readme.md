# Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Generate simulated GPS data

* 10 seconds, 8 bit IQ

```bash
./gps-sdr-sim/gps-sdr-sim -e brdc2570.23n -l 38.986008,-76.942566,10.0 -b 8 -d 20
```

```
Using static location mode.
xyz =   1121575.5,  -4835955.6,   3991116.0
llh =   38.986008,  -76.942566,        10.0
Start time = 2023/09/14,00:00:00 (2279:345600)
Duration = 2.0 [sec]
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
Time into run =  2.0
Done!
Process time = 0.4 [sec]
```

Columns of output: prn, az, el, distance?, ionosphere delay
