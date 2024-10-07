import numpy as np
from gps import gps_sim, gps
import time

if __name__ == "__main__":
    fs = 4 * 1.023e6
    N = fs * 0.01
    runs = 100
    sv = np.random.randint(1, 32)

    threshold = 5.5

    powers = [-110, -120, -122.5, -125, -126, -127, -128, -128.5]

    power = -128.5
    doppler = np.random.uniform(-5e4, 5e4)
    phase = np.random.randint(1023 * 4)

    print(f"Doppler={doppler}, phase={phase}")

    results = np.zeros(len(powers))

    start = time.time()
    for i, power in enumerate(powers):
        for j in range(runs):
            samples = gps_sim.generate_gps(
                fs, N, sv, doppler, sample_phase=phase, signal_power=power
            )
            res = gps.acquisition(
                samples, fs, 1e5, 1e3, verbose=False, threshold=threshold
            )

            svs = [r[0] for r in res]

            if len(svs) == 1 and svs[0] == sv:
                results[i] += 1

        print(f"Power={powers[i]} dBm: {100*results[i]/runs:.0f}% success")

    end = time.time()

    print(f"Took {end - start:.2f} s")
