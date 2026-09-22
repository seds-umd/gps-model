"""Capture-file usability checks without running a physical receiver."""

from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner
import numpy as np

spec = importlib.util.spec_from_file_location(
    "gps_cli", Path(__file__).parents[1] / "main.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CaptureCliTests(unittest.TestCase):
    def test_real_receiver_processes_a_synthetic_capture(self):
        from gps import gps_sim

        np.random.seed(20260914)
        samples = gps_sim.generate_gps(4092000, 409200, 1, sample_phase=4090)
        iq = np.empty(2 * len(samples), dtype=np.int8)
        iq[::2] = np.rint(60 * samples.real).astype(np.int8)
        iq[1::2] = np.rint(60 * samples.imag).astype(np.int8)
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory, "synthetic.iq")
            iq.tofile(capture)
            result = CliRunner().invoke(cli.main, [str(capture)])
        self.assertEqual(result.exit_code, 0, repr(result.exception))
        self.assertIn("[Tracking] Starting tracking on SV 1", result.output)

    def test_invalid_capture_and_options_fail_with_useful_messages(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "empty.iq").write_bytes(b"")
            Path(directory, "odd.iq").write_bytes(b"\x01\x02\x03")
            Path(directory, "short16.iq").write_bytes(b"\x01\x02")
            Path(directory, "good.iq").write_bytes(b"\x01\x02\x03\x04")
            cases = [
                (["missing.iq"], "does not exist"),
                (["empty.iq"], "empty"),
                (["odd.iq"], "complete I/Q"),
                (["short16.iq", "--width", "16"], "complete I/Q"),
                (["good.iq", "--width", "24"], "Invalid value"),
                (["good.iq", "--fs", "0"], "finite"),
                (["good.iq", "--fs", "nan"], "finite"),
                (["good.iq", "--fs", "inf"], "finite"),
            ]
            for args, message in cases:
                with self.subTest(args=args), patch.object(
                    cli.gps_receiver, "GpsReceiver"
                ) as receiver:
                    result = runner.invoke(
                        cli.main, [str(Path(directory, args[0])), *args[1:]]
                    )
                    self.assertNotEqual(result.exit_code, 0)
                    self.assertIn(message, result.output)
                    receiver.assert_not_called()

    def test_signed_iq_and_partial_final_chunk(self):
        runner = CliRunner()
        for width in [8, 16, 32]:
            with self.subTest(width=width), tempfile.TemporaryDirectory() as directory:
                values = np.array(
                    [-7, 3, 2, -5, 0, 1, 6, 4, -2, -3], dtype=f"<i{width // 8}"
                )
                capture = Path(directory, "capture.iq")
                values.tofile(capture)
                with patch.object(cli.gps_receiver, "GpsReceiver") as receiver:
                    result = runner.invoke(
                        cli.main, [str(capture), "--width", str(width), "--fs", "2"]
                    )
                    self.assertEqual(result.exit_code, 0, repr(result.exception))
                    chunks = [
                        c.args[0] for c in receiver.return_value.process.call_args_list
                    ]
                    self.assertEqual([len(c) for c in chunks], [2, 2, 1])
                    np.testing.assert_array_equal(
                        np.concatenate(chunks), values[::2] + 1j * values[1::2]
                    )


if __name__ == "__main__":
    unittest.main()
