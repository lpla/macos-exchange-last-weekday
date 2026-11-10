"""Portable tests of the 25G342 migration guardrails; no macOS services touched."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "upgrade_25g342.py"
SPEC = spec_from_file_location("upgrade_25g342", SCRIPT)
MOD = module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class UpgradeSafetyTests(unittest.TestCase):
    def test_known_library_hashes_are_pinned(self):
        self.assertEqual(len(MOD.OLD_SHA), 64)
        self.assertEqual(len(MOD.NEW_SHA), 64)
        self.assertNotEqual(MOD.OLD_SHA, MOD.NEW_SHA)

    def test_hash_calculation(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blob"
            path.write_bytes(b"synthetic-not-an-apple-binary")
            self.assertEqual(MOD.sha(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cancel_has_no_root_calls(self):
        with patch("builtins.input", return_value="no"):
            with patch.object(MOD, "root") as privileged:
                with patch.object(MOD, "preflight") as verification:
                    MOD.upgrade("test-only")
        privileged.assert_not_called()
        verification.assert_not_called()

    def test_launchctl_override_parser(self):
        fixture = ('"com.apple.exchange.exchangesyncd" => disabled\n'
                   '"io.lpla.exchange-last-weekday-sync" => enabled\n'
                   '"io.lpla.exchange-last-weekday-health" => enabled\n')
        with patch.object(MOD, "overrides", return_value=fixture):
            MOD.expected_override(MOD.NATIVE_ID, "disabled")
            MOD.expected_override(MOD.CUSTOM_ID, "enabled")
            MOD.expected_override(MOD.WATCH_ID, "enabled")
            with self.assertRaises(MOD.Stop):
                MOD.expected_override(MOD.NATIVE_ID, "enabled")

    def test_immutable_apple_paths_are_not_upgrade_targets(self):
        self.assertNotEqual(MOD.ACTIVE, MOD.NATIVE_PLIST)
        self.assertNotEqual(MOD.ACTIVE, Path(MOD.APPLE_BIN))
        self.assertEqual(MOD.JOURNAL.parent, MOD.BASE)
        self.assertNotEqual(MOD.JOURNAL, MOD.OLD_JOURNAL)


if __name__ == "__main__":
    unittest.main()
