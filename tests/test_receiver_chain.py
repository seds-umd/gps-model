"""Deterministic single-channel acquisition and tracking; no external capture."""

import unittest

import numpy as np

from gps import gps_sim
from gps.gps import acquisition, fine_acquisition, tracking


class ReceiverChainTests(unittest.TestCase):
    def test_numpy_satellite_identifier(self):
        np.random.seed(20260914)
        samples = gps_sim.generate_gps(4092000, 10000, 1)
        candidates = acquisition(samples, 4092000, 2000, 1000, sv=np.int64(1))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], 1)

    def test_code_epoch_phases_preserve_fine_correlation(self):
        fs = 4092000
        for phase in [0, 37, 1800, 2300, 3000, 4089, 4090, 4091]:
            with self.subTest(phase=phase):
                np.random.seed(20260914)
                samples = gps_sim.generate_gps(fs, 50000, 1, sample_phase=phase)
                candidates = acquisition(samples, fs, 2000, 1000, sv=1)
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0][2], phase)
                freq, metric = fine_acquisition(
                    samples, fs, 4096, 8, 1, candidates[0][2]
                )
                self.assertEqual(freq, 0)
                self.assertGreater(metric, 2048)

    def test_acquisition_feeds_a_stable_tracking_channel(self):
        fs = 4092000
        for frequency, phase in [(0, 0), (fs / 4096, 37), (-fs / 4096, 4090)]:
            with self.subTest(frequency=frequency, phase=phase):
                np.random.seed(20260914)
                samples = gps_sim.generate_gps(
                    fs, 2 * fs, 1, doppler=frequency, sample_phase=phase
                )
                candidates = acquisition(samples, fs, 2000, 1000, sv=1)
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0][0], 1)
                coarse_phase = candidates[0][2]
                error = (coarse_phase - phase) % 4092
                self.assertLessEqual(min(error, 4092 - error), 2)
                fine_frequency, metric = fine_acquisition(
                    samples, fs, 4096, 8, 1, coarse_phase
                )
                self.assertAlmostEqual(fine_frequency, frequency, places=8)
                self.assertGreater(metric, 8)
                prompt, carrier, carrier_error, _, code_error, _, _ = tracking(
                    samples, fs, 1, fine_frequency, coarse_phase, debug_results=True
                )
                self.assertGreaterEqual(len(prompt), 1995)
                for values in [prompt, carrier, carrier_error, code_error]:
                    self.assertTrue(np.isfinite(values).all())
                self.assertLess(
                    np.max(np.abs(np.asarray(carrier[-50:]) - frequency)), 1
                )
                self.assertLess(np.mean(np.abs(code_error[-50:])), 0.1)
                self.assertGreater(np.mean(np.abs(prompt[-50:])), 0.9 * fs / 1000)


if __name__ == "__main__":
    unittest.main()
