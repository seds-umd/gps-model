import numpy as np

from . import prn_gen


def generate_gps(
    f_s: int,
    n: int,
    sv: int,
    doppler: float = 0,
    doppler2: float = 0,
    code_phase: int = 0,
    sample_phase: int = 0,
    signal_power: float = None,
) -> np.ndarray:
    """Generate a modulated baseband GPS signal. Only includes L1 C/A, not P(Y). Navigation data is just random bits.

    Args:
        f_s (int): Sampling frequency, must be greater than 2*1.023 MHz
        n (int): Number of samples to generate
        sv (int): Satellite index, between 1 and 32 inclusive
        doppler (float): Frequency shift of signal
        doppler2 (float): Derivative of frequency shift
        code_phase (int): Offset of PRN code
        signal_power (float): Power of input signal in dBm. If not given, no noise is generated. Real world minimum is -128.5 dBm.
    """

    n = int(n)

    # Generate C/A code apply to data
    block = int(f_s / 50)
    assert f_s % 50 == 0, "Sample rate must be divisible by 50"

    code = prn_gen.sample(sv, f_s, block, code_phase, sample_phase)
    num_bits = int(np.ceil(n / block))
    bits = np.random.choice([-1, 1], size=num_bits)

    samples = np.zeros(n, dtype=np.complex64)

    for i in range(num_bits):
        if n < (i + 1) * block:
            samples[i * block : n] = code[: n - i * block] * bits[i]
        else:
            samples[i * block : (i + 1) * block] = code * bits[i]

    # Add doppler offset
    t = np.arange(n) / f_s
    samples = samples * np.exp(2j * np.pi * (doppler + t * doppler2) * t)

    # Add noise
    if signal_power is not None:
        # Samples start at unity power

        # Create noise at unity power
        noise = np.random.uniform(-1, 1, n) + 1j * np.random.uniform(-1, 1, n)
        # Power is 2/3 = var(Re) + var(Im)
        noise /= np.sqrt(2/3)

        # Set noise level to correct ratio
        noise_power_dbm = -174 + 10 * np.log10(f_s)
        snr = signal_power - noise_power_dbm
        snr_ratio = 10 ** (snr / 10)
        noise /= np.sqrt(snr_ratio)

        # Add noise to samples
        samples = samples + noise

        # Normalize back to unity power
        samples = samples / np.sqrt(np.var(samples))

    return samples.astype(np.complex64)
