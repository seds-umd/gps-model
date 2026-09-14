import unittest

import numpy as np

from gps import prn_gen
from gps.gps import fine_acquisition


class FineFrequencyTests(unittest.TestCase):
    def test_fft_bins_report_exact_signed_frequencies(self):
        fs, fft_n, decimation = 4092000, 4096, 8
        count = fft_n * decimation
        code = prn_gen.sample(1, fs, count)
        t = np.arange(count) / fs
        for fft_bin in [0, 1, -1, 8, -8]:
            with self.subTest(fft_bin=fft_bin):
                expected = fft_bin * fs / count
                samples = code * np.exp(2j * np.pi * expected * t)
                actual, metric = fine_acquisition(samples, fs, fft_n, decimation, 1, 0)
                self.assertAlmostEqual(actual, expected, places=8)
                self.assertGreater(metric, 8)


if __name__ == "__main__":
    unittest.main()
