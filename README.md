# macOS Exchange last-weekday recurrence bug

**Research and experimental patch; not a recommended system modification.**

On affected macOS installations, a monthly Microsoft Exchange meeting repeating on the **last Tuesday** can be imported into Apple Calendar as the **fifth Tuesday**, so occurrences in months with only four Tuesdays disappear. The same issue may affect other “last weekday” rules, but the confirmed example was Tuesday.

The core mismatch is `BYDAY=5TU` versus the expected `BYDAY=-1TU`. Apple EventKit expresses the last occurrence using `weekNumber = -1`, while an internal ExchangeSync representation uses ordinal `5` for “last”. The private `EXSEKRecurrenceUtils` consumer passes the ordinal through without normalization.

## Observed results

- Reproduced on an Intel Mac running **macOS Tahoe 26.7.1, build 25G241**. The missing-month symptom was also observed on a separate Mac running Sequoia, but that installation's precise build and private ABI were **not** validated.
- Static disassembly and an isolated invocation of Apple's private `EventKitDataConsumer` using synthetic properties confirmed that ordinal `5` reaches EventKit as `5` rather than `-1`.
- An experimental Objective-C **v6** library normalized the conversion in both directions (`5 → -1` on import, `-1 → 5` on export). On the tested Intel build, it was verified in the live Exchange daemon, after cold boots and during multiple recurring-series editing scenarios.
- The v6 library was later **fully uninstalled**. Apple's original Exchange service was restored; it synchronized non-recurring events after reboot with **System Integrity Protection (SIP) enabled**. This is a rollback verification, **not** evidence that Apple has fixed the last-weekday bug.
- On **27 October 2026**, an independently prepared v6 candidate was validated on the same Intel research Mac after upgrading to **macOS Tahoe 26.7.2, build `25G332`**. Both hooks were verified in the live Exchange daemon and again following a reboot. Previously missing Exchange recurrences reappeared after disabling and re-enabling the Exchange account to force reimport. The root-owned passive health monitor also registered after reboot. This is one-system experimental validation, not a general compatibility guarantee.
- **The checked-in source still explicitly permits only build `25G241`.** The `25G332` candidate and machine-specific privileged deployment scripts are not distributed in this public repository; checking out `main` does not reproduce that live deployment. See the validation notes.
- No SIP-compatible automatic patch was developed. **Tahoe with OpenCore Legacy Patcher and Apple Silicon remain untested**.

See [technical findings](docs/FINDINGS.md) and [validation and limitations](docs/VALIDATION.md).

## Repository contents

- `src/`: Objective-C v6 experimental conversion patch and initialization hooks.
- `tools/build.sh`: compiles and ad-hoc-signs three **local test artifacts** on the exact supported architecture; **does not install them**.
- `tools/isolated_eventkit_probe.py`: probes the unmodified private Apple converter in a separate local process with synthetic data; does not access a calendar account.
- `tools/probe_coldboot.py`: v6 isolated startup and bidirectional conversion tests with Apple private classes. It requires the experimental build artifacts and may crash an isolated process if Apple changes the private ABI.
- `tools/missing_occurrences.py`: optional local `.ics` placeholder generator. **Not a sync repair**. Do not import blindly; manual placeholders can become inaccurate or duplicate genuine appointments.
- `tests/`: portable unit tests for the ICS generator.

**This repository intentionally does not include privileged installation scripts, a ready-to-run daemon deployment, Apple binaries, customer calendar data, or a packaged dylib.**

## Safe reproduction

Compare a non-sensitive Exchange test series repeating on the last Tuesday of each month in Outlook on the web and native Apple Calendar. Inspect the imported recurrence rule in Calendar: the affected representation is `5TU` instead of `-1TU`. Never edit real shared meeting series merely to test a workaround.

You can run the portable placeholder-generator tests without changing a calendar:

```sh
python3 -m unittest discover -s tests -v
```

The isolated probes require the appropriate **macOS Intel build** and may crash their own process; they are not run by CI and are not needed for normal use.

### Experimental build (not installation)

On the validated Intel macOS build with Xcode Command Line Tools:

```zsh
./tools/build.sh
```

It creates three ad-hoc-signed test dylibs under the ignored `build/` directory, including a deliberately mismatched-build variant and a deliberately fault-injected variant. **Never inject or deploy the test variants.** No system state is changed by the build command itself.

## Workaround and warnings

Until Apple corrects the behavior, check the authoritative Exchange recurrence in Outlook on the web. Avoid editing affected series from macOS Calendar. The optional ICS generator produces separate static placeholders for missing dates; these require manual updates after any rescheduling, cancellation, or exception. Importing placeholders into iCloud may sync them to other devices and cause duplicates.

The v6 approach uses **private Apple APIs** and injection into a system synchronization service. Its validation required SIP to be disabled on a dedicated research Mac. **Do not disable SIP just to use this repository**, particularly on a managed or work computer. It is research code, not a supported fix, and a macOS update can change or invalidate the private ABI.

The issue was reported to Apple. No Feedback Assistant identifier or corporate event data is included here.

## License

Code in this repository is available under the [MIT License](LICENSE). Apple frameworks and system binaries are **not** included or licensed by this project.
