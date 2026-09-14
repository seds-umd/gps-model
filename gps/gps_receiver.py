import numpy as np
from types import SimpleNamespace
from collections import deque
from itertools import islice

from . import gps, prn_gen

CODE_FREQ = 1.023e6
CODES_PER_BIT = 20
BITS_PER_WORD = 30
WORDS_PER_SUBFRAME = 10
CODES_PER_SUBFRAME = CODES_PER_BIT * BITS_PER_WORD * WORDS_PER_SUBFRAME


def gps_parity(word, last) -> int:
    """Calculate parity for GPS frames.

    Bits must be represented as 1 or -1.

    Args:
        word: List or array containing 30 bits
        last: List containing [D29*, D30*]

    Returns:
        int: 0 if invalid, otherwise inverse of D30*
    """

    word = np.array(list(word))

    if last[1] != 1:
        word[0:24] = word[0:24] * -1

    parity_idx = [
        [1, 2, 3, 5, 6, 10, 11, 12, 13, 14, 17, 18, 20, 23],
        [2, 3, 4, 6, 7, 11, 12, 13, 14, 15, 18, 19, 21, 24],
        [1, 3, 4, 5, 7, 8, 12, 13, 14, 15, 16, 19, 20, 22],
        [2, 4, 5, 6, 8, 9, 13, 14, 15, 16, 17, 20, 21, 23],
        [1, 3, 5, 6, 7, 9, 10, 14, 15, 16, 17, 18, 21, 22, 24],
        [3, 5, 6, 8, 9, 10, 11, 13, 15, 19, 22, 23, 24],
    ]

    # Shift because GPS spec is 1-indexed, python is 0-indexed
    parity_idx = [[b - 1 for b in a] for a in parity_idx]

    d25 = last[0] * np.prod(word[parity_idx[0]])
    d26 = last[1] * np.prod(word[parity_idx[1]])
    d27 = last[0] * np.prod(word[parity_idx[2]])
    d28 = last[1] * np.prod(word[parity_idx[3]])
    d29 = last[1] * np.prod(word[parity_idx[4]])
    d30 = last[0] * np.prod(word[parity_idx[5]])

    valid = np.sum(
        [
            word[24] == d25,
            word[25] == d26,
            word[26] == d27,
            word[27] == d28,
            word[28] == d29,
            word[29] == d30,
        ]
    )

    if valid == 6:
        return int(-1 * last[1])
    else:
        return 0


def decode(sbf, word, start, end, twos_comp=False, flip=False):
    """Helper function to decode data from GPS subframes.

    word, start, and end are 1-indexed to match GPS spec.

    Args:
        sbf (list): List containing bits of subframe.
        word (int): Word within subframe.
        start (int): Starting index in word (inclusive)
        end (int): Ending index in word (inclusive)
        twos_comp (bool, optional): If True, decode using two's complement. Defaults to False.
        flip (bool, optional): If True, flip endianness. Defaults to False.

    Returns:
        int: Decoded value.
    """

    if flip:
        data = int(sbf[word - 1][start - 1 : end][::-1], 2)
    else:
        data = int(sbf[word - 1][start - 1 : end], 2)
    data_len = end - start + 1

    if twos_comp and data >= 2 ** (data_len - 1):
        data = data - 2**data_len

    return data


def arr2bin(arr, t=1):
    # Convert array of bits into string of bits for easier decoding
    return "".join(["1" if c == t else "0" for c in arr])


def decode_subframe(words, position, sv):
    """Return subframe with decoded data.

    Args:
        words (list[str]): List of words in frame as string of bits.
        position (int): Sample position of start of frame.
        sv (int): SV index

    Returns:
        Subframe: Subframe of correct type based on id
    """

    id = decode(words, 2, 20, 22)

    frame_classes = {1: Subframe1, 2: Subframe2, 3: Subframe3}

    try:
        return frame_classes[id](words, position, sv)
    except KeyError:
        # TODO: decode other subframe types
        return Subframe(words, position, sv)


class Subframe:
    def __init__(self, words, position: int, sv: int):
        self.frame_data = words
        self.position = position

        self.id = decode(self.frame_data, 2, 20, 22)
        self.tow = decode(self.frame_data, 2, 1, 17)

        # Adjust TOW to be in seconds and relative to start of frame
        self.tow = (self.tow * 6 - 6) % 604800

        self.sv = sv

    def __repr__(self) -> str:
        return f"SV {self.sv}, Subframe {self.id}, ToW {self.tow}, sample {self.position}"


class Subframe1(Subframe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.week = decode(self.frame_data, 3, 1, 10)  # 20.3.3.3.1.1
        self.l2_code = decode(self.frame_data, 3, 11, 12)  # 20.3.3.3.1.2
        self.ura = decode(self.frame_data, 3, 13, 16)  # 20.3.3.3.1.3
        self.sv_health = decode(self.frame_data, 3, 17, 22)  # 20.3.3.3.1.4

        # 20.3.3.3.1.5
        self.iodc = decode(self.frame_data, 3, 23, 24) << 8
        self.iodc = self.iodc | decode(self.frame_data, 8, 1, 8)

        self.t_gd = decode(self.frame_data, 7, 17, 24, True) * 2**-31  # 20.3.3.3.1.7

        # Clock correction - 20.3.3.3.1.8
        self.t_oc = decode(self.frame_data, 8, 9, 24) * 2**4
        self.a_f2 = decode(self.frame_data, 9, 1, 8, True) * 2**-55
        self.a_f1 = decode(self.frame_data, 9, 9, 24, True) * 2**-43
        self.a_f0 = decode(self.frame_data, 10, 1, 22, True) * 2**-31

    def __repr__(self) -> str:
        s = super().__repr__() + f", Week {self.week}, IODC {self.iodc}, "
        s += f"t_oc={self.t_oc}, a_f2={self.a_f2:0.3e}, a_f1={self.a_f1:0.3e}, a_f0={self.a_f0:0.3e}"

        return s


class Subframe2(Subframe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.iode = decode(self.frame_data, 3, 1, 8)
        self.c_rs = decode(self.frame_data, 3, 9, 24, True) * 2**-5
        self.delta_n = decode(self.frame_data, 4, 1, 16, True) * 2**-43

        self.m_0 = decode(self.frame_data, 4, 17, 24) << 24
        self.m_0 = self.m_0 | decode(self.frame_data, 5, 1, 24)
        if self.m_0 >= 2**31:
            self.m_0 = self.m_0 - 2**32
        self.m_0 = self.m_0 * 2**-31

        self.c_uc = decode(self.frame_data, 6, 1, 16, True) * 2**-29

        self.e = decode(self.frame_data, 6, 17, 24) << 24
        self.e = self.e | decode(self.frame_data, 7, 1, 24)
        self.e = self.e * 2**-33
        # assert self.e >= 0 and self.e <= 0.03, f"{self.e} is not valid"

        self.c_us = decode(self.frame_data, 8, 1, 16, True) * 2**-29

        self.sqrt_a = decode(self.frame_data, 8, 17, 24) << 24
        self.sqrt_a = self.sqrt_a | decode(self.frame_data, 9, 1, 24)
        self.sqrt_a = self.sqrt_a * 2**-19
        # assert self.sqrt_a >= 2530 and self.sqrt_a <= 8192, f"{self.sqrt_a} is not valid"

        self.t_oe = decode(self.frame_data, 10, 1, 16) * 2**4
        # assert self.t_oe < 604784, f"{self.t_oe} is not valid"

        self.fit_interval = decode(self.frame_data, 10, 17, 17)
        self.aodo = decode(self.frame_data, 10, 18, 22) * 900  # seconds; 20.3.3.4.2

    def __repr__(self) -> str:
        s = (
            super().__repr__()
            + f", iode={self.iode}, c_rs={self.c_rs:0.1f}, delta_n={self.delta_n:0.3e}, M0={self.m_0:0.3f}, c_uc={self.c_uc:0.3e}, "
        )
        s += f"e={self.e:0.4f}, c_us={self.c_us:0.3e}, sqrtA={self.sqrt_a:0.1f}, t_oe={self.t_oe}"

        return s


class Subframe3(Subframe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.c_ic = decode(self.frame_data, 3, 1, 16, True) * 2**-29

        self.Omega_0 = decode(self.frame_data, 3, 17, 24) << 24
        self.Omega_0 = self.Omega_0 | decode(self.frame_data, 4, 1, 24)
        if self.Omega_0 >= 2**31:
            self.Omega_0 = self.Omega_0 - 2**32
        self.Omega_0 = self.Omega_0 * 2**-31

        self.c_is = decode(self.frame_data, 5, 1, 16, True) * 2**-29

        self.i_0 = decode(self.frame_data, 5, 17, 24) << 24
        self.i_0 = self.i_0 | decode(self.frame_data, 6, 1, 24)
        if self.i_0 >= 2**31:
            self.i_0 = self.i_0 - 2**32
        self.i_0 = self.i_0 * 2**-31

        self.c_rc = decode(self.frame_data, 7, 1, 16, True) * 2**-5

        self.omega = decode(self.frame_data, 7, 17, 24) << 24
        self.omega = self.omega | decode(self.frame_data, 8, 1, 24)
        if self.omega >= 2**31:
            self.omega = self.omega - 2**32
        self.omega = self.omega * 2**-31

        self.Omega_dot = decode(self.frame_data, 9, 1, 24, True) * 2**-43
        # assert self.Omega_dot >= -6.33e-7 and self.Omega_dot <= 0, f"{self.Omega_dot} is not valid"
        self.idot = decode(self.frame_data, 10, 9, 22, True) * 2**-43

        self.iode = decode(self.frame_data, 10, 1, 8)

    def __repr__(self) -> str:
        s = (
            super().__repr__()
            + f", c_ic={self.c_ic:0.3e}, Omega_0={self.Omega_0:0.3f}, c_is={self.c_is:0.3e}, i_0={self.i_0:0.3f}, c_rc={self.c_rc:0.2f}, "
        )
        s += f"omega={self.omega:0.3f}, Omega_dot={self.Omega_dot:0.3e}, idot={self.idot:0.3e}, iode={self.iode}"

        return s


class FrameDecoder:
    """This class takes a sample at a time and stores it in a buffer,
    looking for valid frames as it goes.
    """

    PREAMBLE = np.repeat([1 if c == "1" else -1 for c in "10001011"], CODES_PER_BIT)

    def __init__(self):
        self.reset()

    def reset(self, sv=-1):
        """Reset decoder to initial state."""

        self.sample_buffer = deque(maxlen=CODES_PER_SUBFRAME)
        self.sample_positions = deque(maxlen=CODES_PER_SUBFRAME)

        self.sv = sv

        # State
        self.preambles = deque()
        self.idx = 0

    def process_subframe(self, idx: int, inverted: bool) -> Subframe:
        """Decode samples into subframe and return values.

        Args:
            idx (int): Index where subframe starts.
            inverted (bool): If True, bits are inverted

        Returns:
            Subframe: Subframe object containing decoded values
        """

        sbf = list(islice(self.sample_buffer, idx, idx + CODES_PER_SUBFRAME))
        sbf = np.array(sbf)
        sbf = sbf.reshape((-1, CODES_PER_BIT))
        sbf = np.sum(sbf, -1)
        sbf[sbf > 0] = 1
        sbf[sbf <= 0] = -1

        assert len(sbf) == BITS_PER_WORD * WORDS_PER_SUBFRAME

        if inverted:
            sbf = -1 * sbf

        last_parity = [-1, -1]
        words = []

        for j in range(10):
            word = sbf[j * 30 : (j + 1) * 30]

            valid = gps_parity(word, last_parity)

            if valid == 0:
                print("[Decoder] Invalid frame")
                return None

            # XOR with D30* to get correct value
            words.append(arr2bin(word * valid))
            last_parity = word[-2:]

        return decode_subframe(words, self.sample_positions[idx], self.sv)

    def process(self, sample: float, sample_pos: float) -> Subframe:
        """Process a single sample. A frame is returned if found within previous samples.

        The sample_pos argument is used to keep accurate timing. It is the
        index of the exact start of the PRN code that generated a given sample.
        It should be in units of samples of the original signal.

        Args:
            sample (float): Sample
            sample_pos (float): Position of sample within data stream.

        Returns:
            Subframe: Decoded frame. If no frame is decoded, returns None.
        """

        # Digitize samples
        sample = 1 if np.real(sample) > 0 else -1

        self.sample_buffer.append(sample)
        self.sample_positions.append(sample_pos)
        self.idx += 1

        # Exit if there's not enough samples to do anything
        if len(self.sample_buffer) < 8 * 20:
            return None

        # Check for preambles
        tail = list(islice(self.sample_buffer, len(self.sample_buffer) - len(self.PREAMBLE), None))
        corr = np.sum(self.PREAMBLE * tail)
        if np.abs(corr) == 160:
            self.preambles.append(self.idx - len(self.PREAMBLE))

        # Look through past preambles and process them if an entire subframe is available
        if (
            len(self.preambles) > 0
            and self.preambles[0] <= self.idx - CODES_PER_SUBFRAME
        ):
            # Candidate indices are absolute; deque indices follow the retained window.
            absolute = self.preambles.popleft()
            i = absolute - (self.idx - len(self.sample_buffer))

            corr = np.sum(
                self.PREAMBLE * list(islice(self.sample_buffer, i, i + len(self.PREAMBLE)))
            )
            inverted = int(corr) == -160

            word = list(islice(self.sample_buffer, i, i + BITS_PER_WORD * CODES_PER_BIT))
            word = np.array(word)
            if inverted:
                word = -1 * word

            # Downsample into bits
            word = word.reshape((-1, CODES_PER_BIT))
            word = np.sum(word, -1)
            word[word > 0] = 1
            word[word <= 0] = -1

            # The preceding subframe's word 10 ends in D29=D30=0.
            valid = gps_parity(word, [-1, -1])

            if valid:
                return self.process_subframe(i, inverted)


class SampleBuffer:
    """Storage object that allows samples to be added and removed in
    different amounts.
    """

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
        self.decoder = FrameDecoder()
        self.frames = []

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

        if not np.isfinite(code_est) or not 0 <= code_est < self.fs / 1000:
            raise ValueError("code_est must lie within one C/A code period")
        self.buffer = SampleBuffer()
        self.frames = []
        self.carrier_pll.reset()
        self.code_dll.reset()

        self.sv = sv
        self.freq_est = freq_est
        self.code_est = code_est

        # Reference code sequence
        code_ref = prn_gen.generate(sv)
        code_ref = [code_ref[-1]] + code_ref + [code_ref[0]]
        self.code_ref = np.array(code_ref)

        # Loop variables
        self.carrier_phase = 0
        self.carrier_freq = freq_est
        self.code_phase = 0
        self.code_freq = CODE_FREQ
        self.sample_position = int(self.fs / 1e3 - code_est)

        self.initialized = True
        self.first = True

        self.decoder.reset(self.sv)

        if debug:
            self.debug = SimpleNamespace(
                carr_freq=[],
                carr_err=[],
                code_freq=[],
                code_err=[],
                code_phase=[],
                code_pos=[],
                iq=[],
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

        while self.buffer.count >= blksize:
            signal = self.buffer.pop(blksize)
            assert signal is not None

            # Keep track of start of block for timing
            block_start = self.sample_position

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
            carrier_err = 0.0
            if prompt != 0:
                # Costas discriminator: fold the phase modulo pi for BPSK.
                angle = np.angle(prompt)
                if angle > np.pi / 2:
                    angle -= np.pi
                elif angle < -np.pi / 2:
                    angle += np.pi
                carrier_err = angle / (2 * np.pi)
                self.carrier_freq = self.freq_est + self.carrier_pll.update(carrier_err)

            # Update code DLL
            total = np.abs(early) + np.abs(late)
            code_err = 0.0
            if total > 0:
                code_err = (np.abs(early) - np.abs(late)) / total
                self.code_freq = CODE_FREQ - self.code_dll.update(code_err)

            # Fine time
            x = code_err * (1 - self.early_late_spacing)

            # Send sample to decoder
            if prompt != 0:
                frame = self.decoder.process(prompt, block_start + x)
            else:
                # An erased code interval breaks navigation bit timing. Do not
                # concatenate the remaining halves of a frame across the gap.
                self.decoder.reset(self.sv)
                frame = None

            # TODO: do something other than print frames
            if frame:
                self.frames.append(frame)
                print(f"[Decoder SV: {self.sv}] " + str(frame))

            if self.debug is not None:
                self.debug.carr_freq.append(self.carrier_freq)
                self.debug.carr_err.append(carrier_err)
                self.debug.code_freq.append(self.code_freq)
                self.debug.code_err.append(code_err)
                self.debug.code_phase.append(self.code_phase)
                self.debug.code_pos.append(self.sample_position)
                self.debug.iq.append(prompt)

            # Update phase step and block size for next iteration
            code_phase_step = self.code_freq / self.fs
            blksize = int(np.ceil((1023 - self.code_phase) / code_phase_step))


class GpsReceiver:
    def __init__(
        self, fs: float, channels: int = 12, dec_factor: int = 8, debug: bool = False
    ) -> None:
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
        """Set PLL and DLL parameters.

        Args:
            pll_bw (float, optional): PLL bandwidth in Hz. Defaults to 25.
            pll_zeta (float, optional): PLL damping factor. Defaults to 0.707.
            pll_gain (float, optional): PLL gain. Defaults to 0.25.
            dll_bw (float, optional): DLL bandwidth in Hz. Defaults to 1.
            dll_zeta (float, optional): DLL damping factor. Defaults to 0.707.
            dll_gain (float, optional): DLL gain. Defaults to 1.
        """

        self.pll_params = (pll_bw, pll_zeta, pll_gain)
        self.dll_params = (dll_bw, dll_zeta, dll_gain)

    def process(self, samples: np.ndarray):
        """Process samples.

        Args:
            samples (np.ndarray): Samples to be processed. Should be type np.complex64.
        """

        # TODO: run acquisition continuously instead of just at start

        # Run if no satellites are currently acquired
        if np.sum(self.acquired > 0) == 0:
            # Run acquisition

            self.buffer.push(samples)

            # Coarse search uses 500 Hz bins (2 ms); fine needs 4096 outputs.
            acq_count = max(int(4096 * self.dec_factor), int(round(self.fs * .002)))

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
                results = results[: len(self.channels)]

            for i in range(len(results)):
                # Fine acquisition
                results[i][1], _ = gps.fine_acquisition(
                    samples,
                    self.fs,
                    4096,
                    self.dec_factor,
                    results[i][0],
                    results[i][2],
                    verbose=True,
                )

                sv, freq, code, _ = results[i]

                # Initialize tracking
                print(f"[Tracking] Starting tracking on SV {sv}")
                self.acquired[i] = sv
                self.channels[i].start(sv, freq, code, self.debug)

        # Run tracking normally
        for i in range(len(self.channels)):
            if self.acquired[i] > 0:
                self.channels[i].update(samples)

    def dump_frames(self):
        """Drain decoded frames in sample-position order across channels."""
        frames = []

        for chan in self.channels:
            frames.extend(chan.frames)
            chan.frames.clear()

        return sorted(frames, key=lambda frame: frame.position)
