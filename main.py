import click
import numpy as np

from gps import gps_receiver

@click.command()
@click.argument("sample_file")
def main(sample_file):
    data = np.fromfile(sample_file, dtype=np.int8)
    data = data[::2].astype(np.complex64) + 1j * data[1::2].astype(np.complex64)

    fs = 4.092e6 # TODO: don't hard code sample rate

    rx = gps_receiver.GpsReceiver(fs)

    for i in range(0, len(data), int(fs)):
        rx.process(data[i:int(i+fs)])
        print(f"{int(i/fs)}s elapsed")

if __name__ == "__main__":
    main()
