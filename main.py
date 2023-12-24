import click
import numpy as np

from gps import gps_receiver

@click.command()
@click.argument("sample_file")
@click.option("--fs", default=4.092e6, help="Sampling frequency", type=float)
@click.option("--width", default=8, help="Bit width of each I or Q sample", type=int)
def main(sample_file, fs, width):
    if width == 8:
        data_type = np.int8
    elif width == 16:
        data_type = np.int16
    elif width == 32:
        data_type = np.int32

    data = np.fromfile(sample_file, dtype=data_type)
    data = data[::2].astype(np.complex64) + 1j * data[1::2].astype(np.complex64)

    rx = gps_receiver.GpsReceiver(fs)

    for i in range(0, len(data), int(fs)):
        rx.process(data[i:int(i+fs)])
        print(f"{int(i/fs)}s elapsed")

if __name__ == "__main__":
    main()
