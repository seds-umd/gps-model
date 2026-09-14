"""Streaming tracking must preserve state across chunks and reset on restart."""
import unittest

import numpy as np

from gps import gps_sim
from gps.gps_receiver import TrackingChannel


class StreamingReceiverTests(unittest.TestCase):
    fs = 4092000

    def make_channel(self):
        return TrackingChannel(self.fs, (25, 0.707, 0.25), (1, 0.707, 1))

    def signal(self, sv, phase, frequency, seconds=0.15):
        np.random.seed(20260914)
        return gps_sim.generate_gps(self.fs, int(self.fs * seconds), sv,
                                    doppler=frequency, sample_phase=phase)

    def assert_same_trace(self, a, b):
        for key in ['iq', 'carr_freq', 'carr_err', 'code_freq', 'code_err', 'code_pos']:
            np.testing.assert_allclose(getattr(a.debug, key), getattr(b.debug, key), atol=1e-9, rtol=0)

    def test_irregular_chunks_match_one_block(self):
        samples = self.signal(1, 37, self.fs / 4096)
        whole, chunked = self.make_channel(), self.make_channel()
        for ch in [whole, chunked]:ch.start(1, self.fs / 4096, 37, debug=True)
        whole.update(samples)
        sizes = [1, 7, 4091, 16003, 25000]
        offset, i = 0, 0
        while offset < len(samples):
            n = sizes[i % len(sizes)]
            chunked.update(samples[offset:offset+n])
            offset += n
            i += 1
        self.assertGreater(len(whole.debug.iq), 140)
        self.assert_same_trace(whole, chunked)

    def test_restart_clears_previous_signal_and_loop_state(self):
        old = self.signal(1, 37, 800)
        new = self.signal(2, 100, -1000)
        reused, fresh = self.make_channel(), self.make_channel()
        reused.start(1, 800, 37, debug=True)
        reused.update(old)
        for ch in [reused, fresh]:
            ch.start(2, -1000, 100, debug=True)
            ch.update(new)
        self.assert_same_trace(fresh, reused)

class PublicReceiverTests(unittest.TestCase):
    def test_public_receiver_honors_decimation_and_small_chunks(self):
        import contextlib
        import io
        from gps.gps_receiver import GpsReceiver
        fs = 4092000
        np.random.seed(20260914)
        samples = gps_sim.generate_gps(fs, int(fs * .1), 1, sample_phase=4090)
        for decimation in [1, 4, 8, 16]:
            with self.subTest(decimation=decimation), contextlib.redirect_stdout(io.StringIO()):
                rx = GpsReceiver(fs, channels=1, dec_factor=decimation, debug=True)
                with np.errstate(divide='raise', invalid='raise'):
                    for chunk in np.array_split(samples, 200):
                        rx.process(chunk)
                self.assertEqual(rx.acquired.tolist(), [1])
                self.assertGreater(len(rx.channels[0].debug.iq), 90)
                self.assertLess(abs(rx.channels[0].debug.carr_freq[-1]), 1)

    def test_zero_signal_does_not_poison_tracking_state(self):
        channel = StreamingReceiverTests().make_channel()
        channel.start(1, 0, 0, debug=True)
        with np.errstate(divide='raise', invalid='raise'):
            channel.update(np.zeros(4092 * 20, dtype=np.complex64))
            np.random.seed(20260914)
            samples = gps_sim.generate_gps(4092000, 4092 * 2000, 1)
            channel.update(samples)
        self.assertTrue(np.isfinite(channel.debug.carr_freq).all())
        self.assertTrue(np.isfinite(channel.debug.code_freq).all())
        self.assertGreater(np.mean(np.abs(channel.debug.iq[-20:])), 3000)

    def test_invalid_epoch_is_rejected(self):
        for phase in [-1, 4092, np.nan, np.inf]:
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'code period'):
                StreamingReceiverTests().make_channel().start(1, 0, phase)


if __name__ == '__main__':
    unittest.main()
