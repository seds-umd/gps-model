import numpy as np
from types import SimpleNamespace

from . import gps, prn

CODE_FREQ = 1.023e6


class SampleBuffer:
    def __init__(self) -> None:
        self.buffer = []
        self.count = 0

    def push(self, x: np.ndarray):
        """Add samples to buffer.

        All samples must be of the same time.

        Args:
            x (np.ndarray): Samples to be added. Must be a 1D array.
        """

        self.buffer.append(x)
        self.count += len(x)

    def pop(self, n: int) -> np.ndarray:
        """Returns n samples or None if not enough are available.

        Args:
            n (int): Number of samples to return.

        Returns:
            np.ndarray: Array of n samples
        """

        if self.count < n:
            return None

        grabbed = 0
        res = []

        while grabbed < n:
            if len(self.buffer[0]) <= n - grabbed:
                # Grab entire entry if it's less than we need
                grabbed += len(self.buffer[0])
                res.append(self.buffer.pop(0))
            else:
                # If it's too much, only grab part of it
                temp = self.buffer.pop(0)
                res.append(temp[0 : n - grabbed])
                self.buffer.insert(0, temp[n - grabbed :])
                grabbed += n - grabbed

        res = np.concatenate(res)

        assert len(res) == n
        assert grabbed == n

        self.count -= grabbed

        return res


class TrackingChannel:
    def __init__(
        self, fs: float, pll_params, dll_params, early_late_spacing: float = 0.5
    ) -> None:
        self.fs = fs
        self.early_late_spacing = early_late_spacing

        self.carrier_pll = gps.PLL(pll_params[0], pll_params[1], pll_params[2], 1e-3)
        self.code_dll = gps.PLL(dll_params[0], dll_params[1], dll_params[2], 1e-3)

        self.buffer = SampleBuffer()

        self.initialized = False

    def start(self, sv: int, freq_est: float, code_est: int, debug: bool = False):
        """Initialize tracking channel.

        After initializing, the first samples to be tracked must also be the
        samples that acquisition was run on in order for the code phases to
        line up.

        Args:
            sv (int): SV to track.
            freq_est (float): Estimated frequency in Hz.
            code_est (int): Estimated code phase in samples.
            debug (bool): Store extra debugging data.
        """

        self.sv = sv
        self.freq_est = freq_est
        self.code_est = code_est

        # Reference code sequence
        code_ref = prn.generate(sv)
        code_ref = [code_ref[-1]] + code_ref + [code_ref[0]]
        self.code_ref = np.array(code_ref)

        # Loop variables
        self.carrier_phase = 0
        self.carrier_freq = freq_est
        self.code_freq = CODE_FREQ
        # self.code_phase = 1023 - code_est * self.code_freq / self.fs
        self.code_phase = 0 # TODO: start at correct phase
        self.sample_position = int(self.fs / 1e3 - code_est)

        self.initialized = True
        self.first = True

        if debug:
            self.debug = SimpleNamespace(
                carr_freq=[],
                carr_err=[],
                code_freq=[],
                code_err=[],
                code_phase=[],
                code_pos=[],
            )
        else:
            self.debug = None

    def update(self, samples: np.ndarray) -> np.ndarray:
        """Update tracking channel

        Adds samples to internal buffer. If internal buffer contains at least
        1ms of samples, those samples will be consumed by the tracking
        algorithm.

        Args:
            samples (np.ndarray): Samples to process.

        Returns:
            np.ndarray: Downsampled samples.
        """
        if not self.initialized:
            return None

        self.buffer.push(samples)

        # Throw away first few samples to line up with start of PRN code
        if self.first:
            if self.buffer.count >= self.sample_position:
                self.buffer.pop(self.sample_position)
                self.first = False
            else:
                return None

        # blksize will end up being about 1ms worth of samples
        code_phase_step = self.code_freq / self.fs
        blksize = int(np.ceil((1023 - self.code_phase) / code_phase_step))

        res_samples = []

        while self.buffer.count >= blksize:
            signal = self.buffer.pop(blksize)
            assert signal is not None

            self.sample_position += len(signal)

            # Generate code replicas
            tcode = self.code_phase + np.arange(blksize, dtype=float) * code_phase_step
            prompt_code = self.code_ref[np.ceil(tcode).astype(int)]

            tcode_early = np.ceil(tcode - self.early_late_spacing).astype(int)
            early_code = self.code_ref[tcode_early]

            tcode_late = np.ceil(tcode + self.early_late_spacing).astype(int)
            late_code = self.code_ref[tcode_late]

            # Advance code phase
            self.code_phase = tcode[-1] + code_phase_step - 1023

            # Advance carrier phase
            t = np.arange(blksize + 1) / self.fs
            phase = self.carrier_freq * 2 * np.pi * t + self.carrier_phase
            self.carrier_phase = phase[-1] % (2 * np.pi)

            # Shift to DC, remove PRN, and sum
            baseband = signal * np.exp(-1j * phase[:-1])

            prompt = np.sum(baseband * prompt_code)
            early = np.sum(baseband * early_code)
            late = np.sum(baseband * late_code)

            # Update carrier PLL
            carrier_err = np.arctan(prompt.imag / prompt.real) / (2 * np.pi)
            self.carrier_freq = self.freq_est + self.carrier_pll.update(carrier_err)

            # Update code DLL
            code_err = (np.abs(early) - np.abs(late)) / (np.abs(early) + np.abs(late))
            self.code_freq = CODE_FREQ - self.code_dll.update(code_err)

            res_samples.append(prompt)

            if self.debug is not None:
                self.debug.carr_freq.append(self.carrier_freq)
                self.debug.carr_err.append(carrier_err)
                self.debug.code_freq.append(self.code_freq)
                self.debug.code_err.append(code_err)
                self.debug.code_phase.append(self.code_phase)
                self.debug.code_pos.append(self.sample_position)

            # Update phase step and block size for next iteration
            code_phase_step = self.code_freq / self.fs
            blksize = int(np.ceil((1023 - self.code_phase) / code_phase_step))

        return res_samples


class GpsReceiver:
    def __init__(self, fs: float, channels: int = 12, dec_factor: int = 8, debug: bool = False) -> None:
        self.fs = fs
        self.debug = debug

        self.set_loop_params()

        self.channels = [
            TrackingChannel(self.fs, self.pll_params, self.dll_params)
            for _ in range(channels)
        ]

        # List of SVs that have been acquired
        self.acquired = np.zeros(channels, dtype=int) - 1

        self.buffer = SampleBuffer()

        self.out_samples = [[] for _ in range(channels)]

        # Acquisition settings
        self.dec_factor = dec_factor

    def set_loop_params(
        self,
        pll_bw: float = 25,
        pll_zeta: float = 0.707,
        pll_gain: float = 0.25,
        dll_bw: float = 1,
        dll_zeta: float = 0.707,
        dll_gain: float = 1,
    ):
        self.pll_params = (pll_bw, pll_zeta, pll_gain)
        self.dll_params = (dll_bw, dll_zeta, dll_gain)

    def update(self, samples: np.ndarray):

        # TODO: run acquisition continuously instead of just at start

        if np.sum(self.acquired > 0) == 0:
            # Run acquisition

            self.buffer.push(samples)

            acq_count = int(4096 * self.dec_factor)

            if self.buffer.count < acq_count:
                return

            samples = self.buffer.pop(self.buffer.count)

            # Coarse acquisition
            results = gps.acquisition(
                samples, self.fs, max_shift=15e3, bin_size=500, verbose=True
            )

            # Ignore extra results if we don't have enough channels:
            # TODO: sort results by highest SNR
            if len(results) > len(self.channels):
                results = results[:len(self.channels)]

            for i in range(len(results)):
                # Fine acquisition
                results[i][1], _ = gps.fine_acquisition(
                    samples,
                    self.fs,
                    4096,
                    8,
                    results[i][0],
                    results[i][2],
                    verbose=True,
                )

                sv, freq, code, _ = results[i]

                # Initialize tracking
                print(f"Starting tracking on SV {sv}")
                self.acquired[i] = sv
                self.channels[i].start(sv, freq, code, self.debug)

        # Run tracking normally
        for i in range(len(self.channels)):
            if self.acquired[i] > 0:
                out = self.channels[i].update(samples)
                self.out_samples[i].extend(out)
