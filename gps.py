import numpy as np
import matplotlib.pyplot as plt
from typing import Union, List

import prn


def acquisition(
    x: np.ndarray,
    f_s: float,
    max_shift: float,
    bin_size: float,
    f_if: float = 0,
    sv: Union[int, List[int]] = None,
    verbose: bool = False,
    threshold: float = 6,
):
    """Run parallel code phase search.

    Args:
        x (np.ndarray): Samples to be processed.
        f_s (float): Sample frequency.
        max_shift (float): Maximum frequency range to search.
        bin_size (float): Maximum acceptable frequency bin size. Actual bin size will be smaller.
        sv (int, list): If set to an int or list of ints, only those satellites will be searched.
        verbose (bool, optional): Print status if True. Defaults to False.
        threshold (float): SNR threshold for detection. Defaults to 6.

    Returns:
        List of detected signals. Each entry will be a list in the format:
            [sv, frequency shift, code phase]
        Frequency shift is in Hz. Code phase is in samples.
    """

    # Number of samples for FFT to achieve bin size
    fft_n = int(2 ** np.ceil(np.log2(f_s / bin_size)))
    bin_size_actual = f_s / fft_n

    if len(x) < fft_n:
        pass  # TODO: pad with zeros to fill up to FFT size

    if verbose:
        print(f"[Acquisition] Searching {1e3*fft_n/f_s:0.2f}ms period")
        print(f"[Acquisition] {bin_size_actual:0.1f}Hz frequency bins")

    # FFT of samples is always the same so we can pre-compute it
    X = np.fft.fft(x[0:fft_n]).conj()

    # Find frequency shifts
    shift_idx = np.arange(int((f_if - max_shift) / bin_size_actual), int((f_if + max_shift) / bin_size_actual) + 1)
    shift_freq = shift_idx * bin_size_actual

    if sv == None:
        sv_range = range(1, 33)
    elif type(sv) == int:
        sv_range = [sv]
    else:
        sv_range = sv

    # Results: sv, shift, phase
    results = []

    # Iterate through all possible satellites
    for sv_idx in sv_range:
        Y = np.fft.fft(prn.sample(sv_idx, f_s, fft_n))
        Zs = np.zeros((len(shift_idx), fft_n))

        # Iterate through frequency shifts
        for i in range(len(shift_idx)):
            Z = X * np.roll(Y, shift_idx[i])
            Zs[i] = np.abs(np.fft.ifft(Z))

        # Only check first cycle of code, TODO: handle error when there are less than 1ms worth of samples
        Zs = Zs[:, 0 : int(f_s / 1e3)]
        shift, phase = np.unravel_index(np.argmax(Zs), Zs.shape)

        # Rough approximation of SNR
        snr = Zs[shift, phase] / np.mean(Zs[shift])

        # If SNR is high enough, it's probably a satellite
        if snr > threshold:
            results.append([sv_idx, shift_freq[shift], phase])

            if verbose:
                print(
                    f"[Acquisition] SV: {sv_idx}, Doppler shift: {shift_freq[shift]:0.2f}Hz, Code sample phase: {phase}/{int(f_s/1e3)}, SNR: {snr:0.1f}"
                )

    return results
