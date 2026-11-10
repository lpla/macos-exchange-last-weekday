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
- The user subsequently confirmed that the previously missing Exchange occurrences **remained visible after reboot** without requiring another account reimport. The post-reboot hooks were also directly verified.
- Two **local deployment-script** defects were found, separate from the Objective-C recurrence patch: (1) a root-owned journal under a `0700` directory was incorrectly inspected using a non-privileged file test, causing a false missing-file error; the local verification function was corrected to use privileged metadata checks. (2) the watch installer treated the absence of an `os_log_info` message in retained Unified Logging as evidence insufficient for activation. For this one installation, prior hook verification was accepted for the unchanged live PID. **That PID-specific temporary exception must not be reused or published as a general verification mechanism.**
- The passive monitor already distinguishes `STATIC_OK_RUNTIME_UNCONFIRMED` from an actual static failure when historical log records are unavailable; the same distinction should be reflected in any future installer. A portable, persistent, process-bound attestation design has **not** yet been implemented.

**Reproducibility boundary:** The checked-in Objective-C source matches the sources used by the local validated `25G332` candidate (both source SHA-256 values match). The build script compiles the exact running build gate for `25G241`, `25G332` or `25G342`. The resulting repository-built artifact has not yet been independently installed and verified on a clean machine, and the privileged deployment code is not included. This is reproducible **compilation support**, not a turnkey public installer.

## Tahoe 26.7.3 investigation (build 25G342)

An Intel `x86_64` Mac running **macOS 26.7.3, exact build `25G342`**, executed `zsh tools/run-25g342-lab.sh` on 10 November 2026. Observed results:

- Eight portable static regression tests passed.
- Apple's **unmodified** private Exchange-to-EventKit converter still maps EXS Tuesday ordinal `5` to EventKit `weekNumber=5`, rather than the intended `-1`. The original bug therefore remains reproducible in this isolated converter.
- The opt-in build produced three experimental x86_64 libraries in `build/experimental-25G342`; macOS code-signature verification succeeded for all three.
- **Normal isolated process:** hook installation succeeded after relevant `dlopen` (`source=2`, `installed=1`, `last_rc=0`); the forward conversion mapped `5 → -1`, the reverse mapped `-1 → 5`, and ordinal `4` remained unchanged.
- **Transient-failure isolated process:** fault-injected initial result `-8`, then successful worker installation (`source=3`, `attempts=9`) with the same correct bidirectional conversions.
- **Intentional build mismatch:** the candidate refused activation (`initial_rc=-5`, `state=-1`, `installed=0`, no worker), preserving the unmodified conversions.

### Live migration and recovery on Tahoe 25G342 (10 November 2026)

- Before the migration, the 25G332 dylib was still mapped in the custom ExchangeSync service after the OS update. The old passive monitor correctly reported `INCOMPATIBLE_PLATFORM`.
- The guarded migration preflight verified both pinned SHA-256 digests, previous journal `WATCH_ENABLED`, expected launchd overrides and custom agent topology. **All 13 portable tests passed**.
- During initial migration the replacement service was temporarily reported by `ps` as `xpcproxy io.lpla.exchange-last-weekday-sync`. The migration's immediate executable assertion falsely rejected that transitional state. Its recovery procedure reported `NATIVE_RESTORED`, confirming the native Apple service had restarted.
- A separately supplied, state-specific continuation (`resume_25g342.py`) confirmed the journal `RESTORED_NATIVE`, the new on-disk dylib digest `75b240444c7f2a64eadaa7bf2a7da79663ef5b0e80049486231ae967694bf321`, the preserved agents and native topology. It allowed the transitional `xpcproxy` state to resolve before verification.
- The resumed live deployment returned **`HOOKS_ACTIVE` in PID 63638** and **`UPGRADE_OK`**; the passive monitor was enabled, reported `Runtime hook evidence: OBSERVED_ACTIVE_RECENTLY` and `STATIC_OK` for 25G342. Both hooks were observed in the live daemon.
- **Functional confirmation:** the user verified that the previously missing Exchange occurrences appear correctly in Apple Calendar **and** that creating a new recurrence of the previously affected type works with the 25G342 patch active. No account reimport was reported necessary for these checks.
- **Still pending:** persistence following a full reboot and a dedicated post-cutover restore-native test on 25G342. The ad hoc local migration and recovery continuation are not published as generally reusable tooling.

The laboratory reported `ISOLATED_LAB_PASSED` without changing any calendar or Exchange account during the isolated tests. Subsequent attended deployment established **live daemon hook activation and functional recurrence correctness** on this particular Intel 25G342 host. This is not a general deployment guarantee; full reboot persistence and a fresh 25G342 rollback test remain pending.

## Not tested or not established

- SIP-enabled operation of the experimental v6 library: **not supported**.
- Tahoe on an OpenCore Legacy Patcher Mac: **not tested**. Earlier Sequoia observations only demonstrated the missing-occurrence symptom, not patch compatibility.
- Apple Silicon: **not tested** and intentionally rejected by the build configuration.
- Live deployment on builds other than `25G241`, `25G332` and `25G342`: **not established**. For `25G342`, the live daemon hooks and end-user recurrence behaviour were confirmed on one Intel Mac, but reboot persistence has not yet been checked. Later builds are untested and rejected.
- Full absence of races when simultaneously installing two Objective-C method hooks: **not established**. Coordination is internal to this library, not with arbitrary runtime callers.
- Automatic compatibility with later Apple private API changes: **not established**.
- Direct capture of the authoritative EWS/Graph payload for the original meeting: **not performed**.
- Apple's current/future fix status: **unknown**; no claim is made that the upstream bug is resolved.

## Publication boundaries

This repository provides source and research artifacts only. It omits privileged deployment automation, private accounts, tenant information, crash dumps, Apple system executables, and machine-specific recovery backups. The one-host migration script and follow-up recovery continuation used for 25G342 are not included; the former prematurely rejected a transitional `xpcproxy` process and required an attended recovery. There is no supported installer or uninstaller in this public project. The original research-machine uninstall finished successfully, but those scripts were designed for that machine's exact state and should not be reused elsewhere.
