# Validation, limitations, and current project status

## User-observed tests on an Intel Tahoe Mac

- System: macOS Tahoe 26.7.1, build `25G241`, Intel `x86_64`.
- An initial isolated Apple consumer probe confirmed an unmodified internal ordinal of 5 is passed to EventKit as week number 5.
- Experimental bidirectional code was tested on synthetic and real EXS property objects in isolated subprocesses.
- v6 ran inside `exchangesyncd`; verification logs for the live process reported `both hooks installed` with `actual_source=2` (post-`dlopen`) on a service restart. On a prior cold boot, the fallback installation route (`actual_source=3`) was also observed.
- Recurrence tests included editing complete series, editing individual occurrences, series splitting, and cross-client synchronization, without observed duplication in those test cases. These tests do not constitute a general guarantee.
- Later versions investigated an additional Objective-C initializer hook; these did not demonstrate a benefit sufficient to replace v6.
- The experimental service was handed back to Apple's unmodified daemon and tested with **new non-recurring events in both directions** (Calendar and Outlook Web).
- After a separate controlled uninstall and reboot, Apple's daemon ran without injection. A further boot with **SIP re-enabled** confirmed the original service running and ordinary non-recurring events synchronizing.

## Not tested or not established

- SIP-enabled operation of the experimental v6 library: **not supported**.
- Tahoe on an OpenCore Legacy Patcher Mac: **not tested**. Earlier Sequoia observations only demonstrated the missing-occurrence symptom, not patch compatibility.
- Apple Silicon: **not tested** and intentionally rejected by the build configuration.
- Build versions other than `25G241`: **not tested** and rejected by the v6 build gate.
- Full absence of races when simultaneously installing two Objective-C method hooks: **not established**. Coordination is internal to this library, not with arbitrary runtime callers.
- Automatic compatibility with later Apple private API changes: **not established**.
- Direct capture of the authoritative EWS/Graph payload for the original meeting: **not performed**.
- Apple's current/future fix status: **unknown**; no claim is made that the upstream bug is resolved.

## Publication boundaries

This repository provides source and research artifacts only. It omits privileged deployment automation, private accounts, tenant information, crash dumps, Apple system executables, and machine-specific recovery backups. There is no supported installer or uninstaller in this public project. The original research-machine uninstall finished successfully, but those scripts were designed for that machine's exact state and should not be reused elsewhere.
