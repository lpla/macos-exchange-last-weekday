#!/usr/bin/env python3
"""Single-host, fail-closed migration from the verified 25G332 deployment to 25G342.

Runs as the logged-in Intel GUI user. Privileged changes use explicit sudo
commands. No Apple executable or system plist is modified. This updater is
experimental: run 'preflight' before 'apply'; never skip its checks.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import time

BASE = Path("/Library/Application Support/ExchangeLastWeekdayFix")
ACTIVE = BASE / "libExchangeLastWeekdayFix.dylib"
MANIFEST = BASE / "v6-installed.sha256"
MONITOR = BASE / "health-monitor"
CHECKER = MONITOR / "check-update-health.sh"
CUSTOM = Path("/Library/LaunchAgents/io.lpla.exchange-last-weekday-sync.plist")
WATCH = Path("/Library/LaunchAgents/io.lpla.exchange-last-weekday-health.plist")
NATIVE_PLIST = Path("/System/Library/LaunchAgents/com.apple.exchange.exchangesyncd.plist")
APPLE_BIN = "/System/Library/PrivateFrameworks/ExchangeSync.framework/Versions/Current/exchangesyncd"
OLD_JOURNAL = BASE / "reinstall-25G332"
JOURNAL = BASE / "upgrade-25G342"
OLD_SHA = "cd7f9b4aa78818cd4a38ffe70d08f02b188ce642ffea7ffd2655830be15c7809"
NEW_SHA = "75b240444c7f2a64eadaa7bf2a7da79663ef5b0e80049486231ae967694bf321"
CANDIDATE = Path(__file__).resolve().parents[1] / "build/experimental-25G342/libExchangeLastWeekdayFix.v6.dylib"
UID = os.getuid()
GUI = f"gui/{UID}"
CUSTOM_ID = "io.lpla.exchange-last-weekday-sync"
WATCH_ID = "io.lpla.exchange-last-weekday-health"
NATIVE_ID = "com.apple.exchange.exchangesyncd"


class Stop(Exception):
    pass


def call(*args: object, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(arg) for arg in args]
    result = subprocess.run(cmd, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise Stop(f"Command failed (exit {result.returncode}): {cmd!r}\n{result.stderr.strip()}")
    return result


def root(*args: object, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return call("/usr/bin/sudo", *args, input_text=input_text, check=check)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Stop(message)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def regular(path: Path, mode: int, *, owner: int = 0) -> None:
    require(not path.is_symlink() and path.is_file(), f"Missing or symlinked file: {path}")
    info = path.stat()
    require(info.st_uid == owner and info.st_mode & 0o777 == mode,
            f"Unexpected owner or mode on {path}: uid={info.st_uid}, mode={info.st_mode & 0o777:o}")


def directory(path: Path, mode: int) -> None:
    require(not path.is_symlink() and path.is_dir(), f"Missing or symlinked directory: {path}")
    info = path.stat()
    require(info.st_uid == 0 and info.st_mode & 0o777 == mode,
            f"Unexpected owner or mode on directory {path}")


def job_output(job: str) -> str | None:
    result = call("/bin/launchctl", "print", f"{GUI}/{job}", check=False)
    return result.stdout if result.returncode == 0 else None


def job_pid(job: str) -> int | None:
    output = job_output(job)
    match = re.search(r"^\s*pid = (\d+)\s*$", output, re.M) if output else None
    return int(match.group(1)) if match else None


def overrides() -> str:
    return call("/bin/launchctl", "print-disabled", GUI).stdout


def expected_override(label: str, state: str) -> None:
    pattern = rf'"{re.escape(label)}"\s*=>\s*{state}\b'
    require(re.search(pattern, overrides()) is not None,
            f"Unexpected launchctl override for {label}; expected {state}")


def phase() -> str:
    return root("/bin/cat", OLD_JOURNAL / "phase").stdout.strip()


def new_phase(value: str) -> None:
    require(value in {"PREPARED", "CUTOVER", "WATCH_ENABLED", "RESTORED_NATIVE", "RECOVERY_REQUIRED"},
            f"Invalid upgrade journal phase: {value}")
    root("/usr/bin/tee", JOURNAL / "phase", input_text=value + "\n")
    root("/bin/chmod", "0600", JOURNAL / "phase")


def verify_plists() -> None:
    sync = plistlib.loads(CUSTOM.read_bytes())
    watch = plistlib.loads(WATCH.read_bytes())
    require(sync.get("Label") == CUSTOM_ID, "Unexpected custom LaunchAgent label")
    require(sync.get("ProgramArguments", [None])[0] == APPLE_BIN, "Unexpected sync executable")
    require(sync.get("EnvironmentVariables", {}).get("DYLD_INSERT_LIBRARIES") == str(ACTIVE),
            "Unexpected injection location")
    require(sync.get("MachServices", {}).get(NATIVE_ID) is True, "Missing original Exchange MachService")
    require(watch.get("Label") == WATCH_ID, "Unexpected monitor label")


def preflight() -> str:
    require(UID != 0, "Run as the logged-in GUI user, not as root")
    require(call("/usr/bin/uname", "-m").stdout.strip() == "x86_64", "Intel x86_64 required")
    require(call("/usr/bin/sw_vers", "-productVersion").stdout.strip() == "26.7.3",
            "Expected macOS 26.7.3")
    require(call("/usr/bin/sw_vers", "-buildVersion").stdout.strip() == "25G342",
            "Expected build 25G342")
    require("status: disabled" in call("/usr/bin/csrutil", "status").stdout,
            "SIP must already be disabled; this program never changes SIP")
    require(NATIVE_PLIST.is_file(), "Original Apple LaunchAgent unavailable")
    directory(BASE, 0o755)
    directory(MONITOR, 0o755)
    directory(OLD_JOURNAL, 0o700)
    regular(ACTIVE, 0o755)
    regular(MANIFEST, 0o600)
    regular(CHECKER, 0o755)
    regular(CUSTOM, 0o644)
    regular(WATCH, 0o644)
    require(root("/bin/test", "-f", OLD_JOURNAL / "phase", check=False).returncode == 0,
            "Old protected journal phase missing")
    require(phase() == "WATCH_ENABLED", "Previous journal is not WATCH_ENABLED")
    require(sha(ACTIVE) == OLD_SHA, "Installed v6 binary is not the previously validated 25G332 build")
    require(root("/bin/cat", MANIFEST).stdout.strip() == OLD_SHA, "Old manifest differs from active binary")
    require(call("/usr/bin/codesign", "--verify", "-v", ACTIVE, check=False).returncode == 0,
            "Old dylib signature not valid")
    require(CANDIDATE.is_file() and not CANDIDATE.is_symlink(), "25G342 candidate missing")
    require(sha(CANDIDATE) == NEW_SHA, "25G342 candidate SHA-256 differs from verified lab artifact")
    require(call("/usr/bin/codesign", "--verify", "-v", CANDIDATE, check=False).returncode == 0,
            "Candidate signature invalid")
    checker_text = CHECKER.read_text()
    require(checker_text.count("EXPECTED_BUILD='25G332'") == 1,
            "Installed checker does not target old build as expected")
    require(checker_text.count(f"EXPECTED_SHA='{OLD_SHA}'") == 1,
            "Installed checker has an unexpected binary digest")
    require(not JOURNAL.exists() and not JOURNAL.is_symlink(),
            "Migration journal already exists: stop; do not repeat this migration")
    verify_plists()
    output = job_output(CUSTOM_ID)
    require(output is not None and job_pid(CUSTOM_ID) is not None, "Replacement sync service not running")
    require(f"path = {CUSTOM}" in output, "Replacement service was registered from another plist")
    pid = job_pid(CUSTOM_ID)
    require(call("/bin/ps", "-p", str(pid), "-o", "command=").stdout.strip() == APPLE_BIN,
            "Replacement job does not run Apple's actual Exchange executable")
    require(job_output(WATCH_ID) is not None, "Health watcher not registered")
    require(job_output(NATIVE_ID) is None, "Original Apple Exchange job unexpectedly registered")
    expected_override(CUSTOM_ID, "enabled")
    expected_override(WATCH_ID, "enabled")
    expected_override(NATIVE_ID, "disabled")
    return checker_text.replace("EXPECTED_BUILD='25G332'", "EXPECTED_BUILD='25G342'").replace(
        f"EXPECTED_SHA='{OLD_SHA}'", f"EXPECTED_SHA='{NEW_SHA}'")


def write_backup() -> None:
    root("/usr/bin/install", "-d", "-o", "root", "-g", "wheel", "-m", "0700", JOURNAL)
    for source, name, mode in [
        (ACTIVE, "old-v6.dylib", "0755"),
        (MANIFEST, "old-manifest.sha256", "0600"),
        (CHECKER, "old-check-update-health.sh", "0755"),
        (CUSTOM, "old-custom.plist", "0644"),
        (WATCH, "old-watch.plist", "0644"),
    ]:
        root("/usr/bin/install", "-o", "root", "-g", "wheel", "-m", mode, source, JOURNAL / name)
    require(root("/usr/bin/shasum", "-a", "256", JOURNAL / "old-v6.dylib").stdout.split()[0] == OLD_SHA,
            "Protected backup hash mismatch")
    new_phase("PREPARED")


def verify_process() -> int:
    pid = job_pid(CUSTOM_ID)
    require(pid is not None, "Replacement Exchange service has no running PID")
    output = call("/bin/ps", "-p", str(pid), "-o", "command=").stdout.strip()
    require(output == APPLE_BIN, f"Unexpected Exchange process command: {output}")
    mapping = root("/usr/bin/vmmap", pid).stdout
    require(str(ACTIVE) in mapping, "Candidate library is not mapped into new Exchange process")
    return pid


def wait_for_hooks(pid: int) -> None:
    for _ in range(15):
        logs = call("/usr/bin/log", "show", "--info", "--last", "10m", "--style", "compact",
                    "--predicate",
                    'process == "exchangesyncd" AND eventMessage CONTAINS "ExchangeLastWeekdayFix v6"',
                    check=False).stdout
        current = "\n".join(line for line in logs.splitlines()
                            if f"exchangesyncd[{pid}:" in line)
        if "REFUSED permanent incompatibility" in current:
            raise Stop("Candidate explicitly refused private ABI compatibility")
        if "both hooks installed" in current:
            print("HOOKS_ACTIVE for replacement PID", pid, flush=True)
            return
        time.sleep(2)
    raise Stop("Hook installation cannot be confirmed by recent logs; fail closed")


def restore_native() -> None:
    # Restore a functioning Apple daemon, not the old build-gated dylib.
    print("RECOVERY: enabling native ExchangeSync and retiring custom agents.", flush=True)
    for label in (WATCH_ID, CUSTOM_ID):
        if job_output(label) is not None:
            root("/bin/launchctl", "bootout", f"{GUI}/{label}")
        root("/bin/launchctl", "disable", f"{GUI}/{label}")
    root("/bin/launchctl", "enable", f"{GUI}/{NATIVE_ID}")
    if job_output(NATIVE_ID) is None:
        root("/bin/launchctl", "bootstrap", GUI, NATIVE_PLIST)
    root("/bin/launchctl", "kickstart", "-kp", f"{GUI}/{NATIVE_ID}")
    time.sleep(2)
    pid = job_pid(NATIVE_ID)
    require(pid is not None, "Native service not running after restoration")
    require(call("/bin/ps", "-p", str(pid), "-o", "command=").stdout.strip() == APPLE_BIN,
            "Native service command does not match Apple executable")
    for source, name in [(WATCH, "retired-watch.plist"), (CUSTOM, "retired-custom.plist")]:
        require(source.is_file() and not source.is_symlink(),
                f"Cannot retire unexpected agent: {source}")
        root("/bin/mv", source, JOURNAL / name)
    new_phase("RESTORED_NATIVE")
    print("NATIVE_RESTORED: Apple's own ExchangeSync process is running.", flush=True)


def upgrade(checker_text: str) -> None:
    confirm = input("Type UPGRADE-25G342-V6 to stop and replace ExchangeSync: ").strip()
    if confirm != "UPGRADE-25G342-V6":
        print("Cancelled; no changes made.")
        return
    root("/usr/bin/true")
    checker_text = preflight()
    with tempfile.TemporaryDirectory(prefix="exs-25g342-") as temporary:
        stage = Path(temporary)
        os.chmod(stage, 0o700)
        new_checker = stage / "check-update-health.sh"
        new_manifest = stage / "v6-installed.sha256"
        new_checker.write_text(checker_text)
        new_manifest.write_text(NEW_SHA + "\n")
        os.chmod(new_checker, 0o600)
        os.chmod(new_manifest, 0o600)
        require(call("/bin/bash", "-n", new_checker, check=False).returncode == 0,
                "Updated health checker has invalid shell syntax")
        write_backup()
        cutover = False
        try:
            new_phase("CUTOVER")
            cutover = True
            root("/bin/launchctl", "bootout", f"{GUI}/{WATCH_ID}")
            root("/bin/launchctl", "bootout", f"{GUI}/{CUSTOM_ID}")
            require(job_output(CUSTOM_ID) is None, "Previous Exchange process is still registered")
            root("/usr/bin/install", "-o", "root", "-g", "wheel", "-m", "0755", CANDIDATE, ACTIVE)
            root("/usr/bin/install", "-o", "root", "-g", "wheel", "-m", "0600", new_manifest, MANIFEST)
            root("/usr/bin/install", "-o", "root", "-g", "wheel", "-m", "0755", new_checker, CHECKER)
            require(sha(ACTIVE) == NEW_SHA, "Active candidate checksum mismatch")
            require(call("/usr/bin/codesign", "--verify", "-v", ACTIVE, check=False).returncode == 0,
                    "Installed candidate signature invalid")
            root("/bin/launchctl", "bootstrap", GUI, CUSTOM)
            root("/bin/launchctl", "kickstart", "-kp", f"{GUI}/{CUSTOM_ID}")
            pid = verify_process()
            wait_for_hooks(pid)
            root("/bin/launchctl", "bootstrap", GUI, WATCH)
            require(job_output(WATCH_ID) is not None, "Watcher not registered after upgrade")
            audit = call(CHECKER, "--runtime", check=False)
            require(audit.returncode in (0, 10) and "STATIC_OK" in audit.stdout,
                    f"Upgraded watcher checker reports an error: {audit.stdout}\n{audit.stderr}")
            new_phase("WATCH_ENABLED")
            print("UPGRADE_OK: 25G342 patch installed with verified hooks and watcher.", flush=True)
            print(audit.stdout, flush=True)
        except BaseException:
            if cutover:
                try:
                    restore_native()
                except BaseException as recovery_error:
                    try:
                        new_phase("RECOVERY_REQUIRED")
                    except BaseException:
                        pass
                    print(f"CRITICAL: native recovery incomplete: {recovery_error}", file=sys.stderr)
            raise


def main() -> None:
    require(len(sys.argv) == 2 and sys.argv[1] in ("preflight", "apply"),
            "Usage: python3 tools/upgrade_25g342.py preflight | apply")
    checker_text = preflight()
    print("PREFLIGHT_OK: old 25G332 installation is intact; experimental 25G342 candidate is verified.")
    print("Previous SHA-256:", OLD_SHA)
    print("Candidate SHA-256:", NEW_SHA)
    print("No service or calendar has been modified.")
    if sys.argv[1] == "apply":
        upgrade(checker_text)


if __name__ == "__main__":
    try:
        main()
    except (Stop, OSError, ValueError, KeyboardInterrupt) as error:
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(1)
