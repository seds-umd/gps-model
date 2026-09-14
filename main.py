import click
import numpy as np
from pathlib import Path

from gps import gps_receiver

@click.command()
@click.argument("sample_file", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path))
@click.option("--fs", default=4.092e6, help="Sampling frequency", type=float)
@click.option("--width", default="8", help="Bit width of each signed I or Q sample (little endian)", type=click.Choice(["8", "16", "32"]))
def main(sample_file, fs, width):
    if not np.isfinite(fs) or fs < 1:
        raise click.BadParameter("must be finite and at least 1 sample/second", param_hint="--fs")
    data_type = np.dtype(f"<i{int(width) // 8}")
    size = sample_file.stat().st_size
    if size == 0:
        raise click.ClickException("Capture file is empty")
    if size % (2 * data_type.itemsize):
        raise click.ClickException("Capture must contain complete I/Q pairs at the selected width")

    # Map the capture and convert one chunk at a time rather than allocating
    # a second, complex copy of the entire recording.
    data = np.memmap(sample_file, dtype=data_type, mode="r")

    rx = gps_receiver.GpsReceiver(fs)

    chunk_size = int(fs)
    for i in range(0, len(data) // 2, chunk_size):
        block = data[2 * i:2 * (i + chunk_size)]
        samples = block[::2].astype(np.complex64) + 1j * block[1::2].astype(np.complex64)
        rx.process(samples)
        print(f"{int(i/fs)}s elapsed")

if __name__ == "__main__":
    main()
