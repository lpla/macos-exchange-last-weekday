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

## Follow-up validation on Tahoe 26.7.2 (27 October 2026)

- **Machine and operating system:** the same Intel `x86_64` research Mac, macOS Tahoe 26.7.2, build `25G332`; SIP was explicitly disabled. The separately prepared v6 candidate had SHA-256 `cd7f9b4aa78818cd4a38ffe70d08f02b188ce642ffea7ffd2655830be15c7809`. This digest identifies that local candidate only, **not** a released artifact.
- An isolated compatibility laboratory passed its checks. The local deployment's preflight confirmed the untouched Apple Exchange service before installation; code-signature verification and the installed SHA-256 matched the candidate.
- In the initial live process, diagnostics showed `both hooks installed (actual_source=2, observer=2, result=0)` following an initially deferred constructor attempt. A separate live verification returned `HOOKS_ACTIVE`.
- The previously missing monthly Exchange occurrences became visible in native Calendar **after the account was disabled and re-enabled**, forcing a new synchronization. Simply injecting the corrected conversion does not rewrite recurrence rules that EventKit already imported incorrectly. No changes to the meeting series were required.
- Following a normal **reboot**, a new Exchange process mapped the same v6 dylib, and startup diagnostics reported `both hooks installed (actual_source=3, observer=3, result=0)` after 14 attempts by the fallback worker. The passive health watcher also registered. Static health verification matched build, architecture, dylib hash, code signature, service topology and expected launchd state; runtime verification returned `HOOKS_ACTIVE`.
- The Calendar user-interface recurrence display was verified *before* the reboot. Its post-reboot display was not separately reported as part of this record, although the post-reboot hooks were directly verified.
- Two **local deployment-script** defects were found, separate from the Objective-C recurrence patch: (1) a root-owned journal under a `0700` directory was incorrectly inspected using a non-privileged file test, causing a false missing-file error; the local verification function was corrected to use privileged metadata checks. (2) the watch installer treated the absence of an `os_log_info` message in retained Unified Logging as evidence insufficient for activation. For this one installation, prior hook verification was accepted for the unchanged live PID. **That PID-specific temporary exception must not be reused or published as a general verification mechanism.**
- The passive monitor already distinguishes `STATIC_OK_RUNTIME_UNCONFIRMED` from an actual static failure when historical log records are unavailable; the same distinction should be reflected in any future installer. A portable, persistent, process-bound attestation design has **not** yet been implemented.

**Reproducibility boundary:** The checked-in Objective-C source matches the sources used by the local validated `25G332` candidate (both source SHA-256 values match). This proposed branch updates the local build script to compile the exact running build gate for either `25G241` or `25G332`. The resulting repository-built artifact has not yet been independently installed and verified on a clean machine, and the privileged deployment code is not included. This is reproducible **compilation support**, not a turnkey public installer.

## Not tested or not established

- SIP-enabled operation of the experimental v6 library: **not supported**.
- Tahoe on an OpenCore Legacy Patcher Mac: **not tested**. Earlier Sequoia observations only demonstrated the missing-occurrence symptom, not patch compatibility.
- Apple Silicon: **not tested** and intentionally rejected by the build configuration.
- Builds other than `25G241` and the separately validated `25G332` candidate: **not tested**. The updated build script explicitly gates compiled artifacts to the current allowlisted build; no automatic cross-build compatibility is implied.
- Full absence of races when simultaneously installing two Objective-C method hooks: **not established**. Coordination is internal to this library, not with arbitrary runtime callers.
- Automatic compatibility with later Apple private API changes: **not established**.
- Direct capture of the authoritative EWS/Graph payload for the original meeting: **not performed**.
- Apple's current/future fix status: **unknown**; no claim is made that the upstream bug is resolved.

## Publication boundaries

This repository provides source and research artifacts only. It omits privileged deployment automation, private accounts, tenant information, crash dumps, Apple system executables, and machine-specific recovery backups. There is no supported installer or uninstaller in this public project. The original research-machine uninstall finished successfully, but those scripts were designed for that machine's exact state and should not be reused elsewhere.
