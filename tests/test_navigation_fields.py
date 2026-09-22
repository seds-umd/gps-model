"""LNAV field boundaries; IS-GPS-200N section 20.3.3 and signed integers."""

import unittest

from gps.gps_receiver import decode, Subframe1, Subframe2, Subframe3


def set_field(words, word, start, end, value):
    width = end - start + 1
    bits = f"{value & ((1 << width) - 1):0{width}b}"
    words[word - 1] = words[word - 1][: start - 1] + bits + words[word - 1][end:]


class NavigationFieldTests(unittest.TestCase):
    def test_aodo_excludes_fit_flag_and_is_in_seconds(self):
        for raw in [0, 1, 17, 31]:
            for fit in [0, 1]:
                with self.subTest(raw=raw, fit=fit):
                    words = ["0" * 30 for _ in range(10)]
                    set_field(words, 10, 17, 17, fit)
                    set_field(words, 10, 18, 22, raw)
                    frame = Subframe2(words, 0, 1)
                    self.assertEqual(frame.fit_interval, fit)
                    self.assertEqual(frame.aodo, raw * 900)

    def test_twos_complement_extremes(self):
        for width in [1, 8, 16, 22, 24]:
            for value in [-(1 << (width - 1)), -1, 0, (1 << (width - 1)) - 1]:
                with self.subTest(width=width, value=value):
                    bits = f"{value & ((1 << width) - 1):0{width}b}"
                    self.assertEqual(decode([bits], 1, 1, width, twos_comp=True), value)

    def test_health_uses_all_six_bits_and_not_ura(self):
        for health, ura in [(0, 15), (1, 0), (32, 0), (63, 7)]:
            with self.subTest(health=health, ura=ura):
                words = ["0" * 30 for _ in range(10)]
                set_field(words, 3, 13, 16, ura)
                set_field(words, 3, 17, 22, health)
                frame = Subframe1(words, 0, 1)
                self.assertEqual(frame.ura, ura)
                self.assertEqual(frame.sv_health, health)

    def test_split_signed_fields_at_negative_limit(self):
        for cls, field, hi, lo in [
            (Subframe2, "m_0", 4, 5),
            (Subframe3, "Omega_0", 3, 4),
            (Subframe3, "i_0", 5, 6),
            (Subframe3, "omega", 7, 8),
        ]:
            for raw in [0x80000000, 0xFFFFFFFF, 0, 0x7FFFFFFF]:
                with self.subTest(field=field, raw=raw):
                    words = ["0" * 30 for _ in range(10)]
                    set_field(words, hi, 17, 24, raw >> 24)
                    set_field(words, lo, 1, 24, raw & 0xFFFFFF)
                    expected = (raw if raw < 0x80000000 else raw - 0x100000000) * 2**-31
                    self.assertEqual(getattr(cls(words, 0, 1), field), expected)


if __name__ == "__main__":
    unittest.main()
