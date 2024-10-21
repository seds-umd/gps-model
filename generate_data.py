import subprocess
import random

out_dir = "data"


class GpsSdrSim:
    def __init__(self, fs=4.092e6, bits=8, nav="data/brdc2570.23n"):
        self.fs = fs
        self.bits = bits
        self.nav = nav

        self.logs = []

        # TODO: configurable time too

    def sim_static(self, filename, dur, lat, lon, alt=0):
        cmd = [
            "./external/gps-sdr-sim/gps-sdr-sim",
            "-e",
            self.nav,
            "-l",
            f"{lat},{lon},{alt}",
            "-b",
            str(self.bits),
            "-d",
            str(dur),
            "-s",
            str(self.fs),
            "-o",
            filename,
        ]

        res = subprocess.run(cmd, stderr=subprocess.PIPE)
        log = res.stderr.decode().split("\n")

        log = [x for x in log if "Time into run" not in x]
        log = "\n".join(log)

        self.logs.append([cmd, log])

    # TODO
    def sim_orbit(self):
        pass

    def save_logs(self, filename):
        with open(filename, "w") as f:
            for log in self.logs:
                f.write(" ".join(log[0]))
                f.write("\n")
                f.write(log[1])
                f.write("\n\n")


if __name__ == "__main__":
    sim = GpsSdrSim()

    # Deterministic results
    random.seed(0x9ac27902)

    for i in range(10):
        lat = random.uniform(-90, 90)
        lon = random.uniform(-180, 180)
        alt = random.uniform(-10e3, 10e3)

        sim.sim_static(f"data/test{i}.ci16", 60, lat, lon, alt)

    sim.save_logs("data/gen.log")
