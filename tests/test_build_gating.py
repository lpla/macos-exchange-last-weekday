"""Static regression checks for the deliberately narrow research build gate.

No macOS frameworks, Apple binaries, accounts, or privileged operations are used.
These checks cannot replace building and probing on each target macOS release.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "tools" / "build.sh").read_text()
SOURCE = (ROOT / "src" / "ExchangeLastWeekdayFix.m").read_text()


class BuildGateTests(unittest.TestCase):
    def test_exact_supported_intel_builds(self):
        self.assertIn("25G241|25G332)", BUILD)
        self.assertIn('[[ "$running_arch" == x86_64 ]]', BUILD)
        self.assertIn('case "$running_build" in', BUILD)
        self.assertIn('Unvalidated macOS build:', BUILD)

    def test_live_build_uses_exact_runtime_gate(self):
        self.assertIn('build_define="-DEXS_EXPECTED_BUILD=\\\"$running_build\\\""', BUILD)
        self.assertIn('"$build_define"', BUILD)
        self.assertIn('strcmp(buf, EXS_EXPECTED_BUILD) == 0', SOURCE)
        self.assertIn('if (!checkBuild()) return -5;', SOURCE)

    def test_fault_injection_and_mismatch_separate(self):
        self.assertIn('X-TEST-MISMATCH', BUILD)
        self.assertIn('EXS_LAB_TRANSIENT_FAIL_COUNT=8', BUILD)
        self.assertIn("libExchangeLastWeekdayFix.v6-mismatch.dylib", BUILD)
        self.assertIn("libExchangeLastWeekdayFix.v6-transient-test.dylib", BUILD)

    def test_build_remains_unprivileged(self):
        self.assertNotIn("sudo ", BUILD)
        self.assertNotIn("launchctl", BUILD)
        self.assertNotIn("csrutil disable", BUILD)


if __name__ == "__main__":
    unittest.main()
