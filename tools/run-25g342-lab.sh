#!/bin/zsh
# Isolated predeployment compatibility lab for Intel Tahoe 26.7.3 (25G342).
# Does not use sudo, disable SIP, register launchd jobs or access calendars.
set -euo pipefail
cd "${0:A:h}/.."

[[ "$(/usr/bin/uname -m)" == "x86_64" ]] || {
  print -u2 -- "Requires an Intel Mac."
  exit 1
}
[[ "$(/usr/bin/sw_vers -productVersion)" == "26.7.3" &&
   "$(/usr/bin/sw_vers -buildVersion)" == "25G342" ]] || {
  print -u2 -- "Requires macOS Tahoe 26.7.3, exact build 25G342."
  exit 1
}
[[ "$(/usr/bin/id -u)" != "0" ]] || {
  print -u2 -- "Run as the standard GUI user, not as root."
  exit 1
}

print -- "PHASE 1: portable static regression tests"
/usr/bin/env python3 -m unittest discover -s tests -v

print -- "PHASE 2: Apple's unmodified Exchange-to-EventKit conversion in a synthetic isolated process"
print -- "If the 5-to-5 bug is no longer present, STOP and review; no patch is needed."
/usr/bin/env python3 tools/isolated_eventkit_probe.py

print -- "PHASE 3: build experimental artifacts restricted to the running build"
/bin/zsh tools/build.sh --experimental-25G342

print -- "PHASE 4: three fresh isolated subprocesses (normal, transient, mismatch)"
EXS_V6_EXPERIMENTAL_25G342=1 /usr/bin/env python3 tools/probe_coldboot.py

print -- "ISOLATED_LAB_PASSED for 25G342. No live daemon or calendar was modified."
print -- "This is NOT approval for privileged installation: live deployment and rollback remain untested."
