import numpy as np
import matplotlib.pyplot as plt
from typing import Union, List

from . import prn

class PLL:
    def __init__(self, bw: float, zeta: float, gain: float, ts: float):
        """Phase locked loop

        Args:
            bw (float): Noise bandwidth
            zeta (float): Damping ratio
            gain (float): Loop gain
            ts (float): Sampling time
        """

        self.set_params(bw, zeta, gain, ts)
        self.reset()

    def set_params(self, bw: float, zeta: float, gain: float, ts: float):
        w_n = 8 * zeta * bw / (4 * zeta**2 +1)
        tau1 = gain / (w_n*w_n)
        tau2 = 2 * zeta / w_n

        self.c1 = tau2 / tau1 # derivative term
        self.c2 = ts / tau1 # proportional term

    def update(self, err):
        nco = self.last_nco + self.c1 * (err - self.last_err) + err * self.c2

        self.last_err = err
        self.last_nco = nco

        return nco

    def reset(self):
        self.last_err = 0
        self.last_nco = 0


def acquisition(
    x: np.ndarray,
    f_s: float,
    max_shift: float,
    bin_size: float,
    f_if: float = 0,
    sv: Union[int, List[int]] = None,
    verbose: bool = False,
    threshold: float = 6,
) -> List[List[Union[int, float]]]:
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
        print(f"[Acquisition] Searching {1e3*fft_n/f_s:0.2f}ms period, N={fft_n}")
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

def fine_acquisition(x: np.ndarray, f_s: float, fft_n: int, dec_factor: int, sv: int, code_phase: int, verbose: bool = False):
    """Perform fine frequency acquisition by decimation.

    Frequency resolution is `f_s/(fft_n*dec_factor)`

    Args:
        x (np.ndarray): Complex samples containing GPS signal. Must be at least `fft_n*dec_factor` long.
        f_s (float): Sampling frequency of `x`.
        fft_n (int): Length of FFT.
        dec_factor (int): Decimation factor.
        sv (int): SV number found during initial acquisition.
        code_phase (int): Code phase found during initial acquisition.
        verbose (bool, optional): Print status/debug info. Defaults to False.
    
    Returns:
        Frequency estimate.
    """

    assert len(x) >= fft_n*dec_factor, "Not enough samples provided"

    x_dec = x[0:fft_n*dec_factor] * prn.sample(sv, f_s, fft_n*dec_factor, offset_samples=code_phase)
    x_dec = np.sum(x_dec.reshape(-1, dec_factor), axis=1) # Acting as a mean but absolute value doesn't matter

    f = np.linspace(f_s/-2, f_s/2, fft_n) / dec_factor

    X = np.abs(np.fft.fftshift(np.fft.fft(x_dec)))

    freq_est = f[np.argmax(X)]

    if verbose:
        print(f"[Acquisition] Fine freq: {freq_est:0.1f} Hz, +-{f_s/(fft_n*dec_factor*2):0.1f} Hz")

    return freq_est

def tracking(x: np.array, f_s: float, sv: int, freq_est: float, code_est: int, debug_results: bool = False):
    carrier_pll = PLL(6.5, 0.707, 0.25, 1e-3)
    code_dll = PLL(1, 0.707, 1, 1e-3)

    # Parameters
    ms_count = int(1e3 * len(x) / f_s)
    code_freq_basis = 1.023e6
    early_late_spacing = 0.5

    code_ref = prn.generate(sv)
    code_ref = [code_ref[-1]] + code_ref + [code_ref[0]]
    code_ref = np.array(code_ref)

    # Variables
    carrier_phase = 0
    carrier_freq = freq_est

    code_phase = 0 # units of code chips
    code_freq = code_freq_basis

    # sample_position = code_est # units of samples
    sample_position = int(f_s/1e3 - code_est)

    # Outputs
    res_samples = []

    if debug_results:
        res_carr_freq = []
        res_carr_err = []
        res_code_freq = []
        res_code_err = []
        res_code_phase = []
        res_code_pos = []

    for _ in range(ms_count):
        code_phase_step = code_freq / f_s
        blksize = int(np.ceil((1023 - code_phase) / code_phase_step))

        # Get chunk of data
        raw_signal = x[sample_position:sample_position + blksize]
        sample_position = sample_position + blksize

        # Exit if not enough samples
        if len(raw_signal) < blksize:
            break

        # Generate code replicas
        tcode = code_phase + np.arange(blksize, dtype=float)*code_phase_step
        prompt_code = code_ref[np.ceil(tcode).astype(int)]

        tcode_early = np.ceil(tcode - early_late_spacing).astype(int)
        early_code = code_ref[tcode_early]

        tcode_late = np.ceil(tcode + early_late_spacing).astype(int)
        late_code = code_ref[tcode_late]

        code_phase = tcode[-1] + code_phase_step - 1023

        # Advance phase
        t = np.arange(blksize + 1) / f_s
        phase = carrier_freq * 2 * np.pi * t + carrier_phase
        carrier_phase = phase[-1] % (2 * np.pi)

        # Shift to DC, remove PRN, and sum
        baseband = raw_signal * np.exp(-1j * phase[:-1])

        prompt = np.sum(baseband * prompt_code)
        early = np.sum(baseband * early_code)
        late = np.sum(baseband * late_code)

        # Update carrier PLL
        carrier_err = np.arctan(prompt.imag / prompt.real) / (2 * np.pi)
        carrier_freq = freq_est + carrier_pll.update(carrier_err)

        # Update code DLL
        code_err = (np.abs(early) - np.abs(late)) / (np.abs(early) + np.abs(late))
        code_freq = code_freq_basis - code_dll.update(code_err)

        # Save stuff for graphing and debugging
        res_samples.append(prompt)

        if debug_results:
            res_carr_freq.append(carrier_freq)
            res_carr_err.append(carrier_err)

            res_code_freq.append(code_freq)
            res_code_err.append(code_err)
            res_code_phase.append(code_phase)
            res_code_pos.append(sample_position)

    res_samples = np.array(res_samples, dtype=np.complex64)

    if debug_results:
        return res_samples, res_carr_freq, res_carr_err, res_code_freq, res_code_err, res_code_phase, res_code_pos
    else:
        return res_samples
