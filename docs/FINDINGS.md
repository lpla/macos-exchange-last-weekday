# Technical findings

## Symptom and reproduction

A monthly Exchange rule intended as the last Tuesday of each month is rendered by macOS Calendar as the fifth Tuesday. In the observed September–December 2026 sample, 29 September and 29 December appeared, while 27 October and 24 November were missing. Outlook Web displayed the expected occurrences.

Affected AppleScript recurrence (sanitized):

```text
FREQ=MONTHLY;INTERVAL=1;BYDAY=5TU
```

Expected native EventKit recurrence:

```text
FREQ=MONTHLY;INTERVAL=1;BYDAY=-1TU
```

The actual captured rule also had an `UNTIL` value; it is omitted here because the ordinal is the relevant defect.

## Internal representation

Static inspection of `EventKitDataConsumer.dataconsumer` and isolated runtime probes on Tahoe `25G241` located `+[EXSEKRecurrenceUtils daysOfTheWeekFromPropertiesWithEK:]`, which supplied the `recurrenceDayOfWeekIndex` value directly as the EventKit `weekNumber`.

An independent probe of the internal EWS↔EXS ordinal utilities found that the sentinel for last occurrence maps **`-1 → 5`** when represented internally and **`5 → -1`** on the reverse mapping. EventKit, however, expects `-1` for “last”. On the observed input, the private consumer produced `(weekday=3, weekNumber=5)` where `(weekday=3, weekNumber=-1)` was intended. EventKit weekday index 3 is Tuesday.

The exact production network payload was not packet-captured. The evidence is strongest for the consumer's faulty boundary conversion; it does not prove every Exchange transport path is identical.

## Experimental correction

`src/ExchangeLastWeekdayFix.m` preserves the original Apple conversions while adapting the boundary values:

1. **Import**: call the original converter and replace any returned `EKRecurrenceDayOfWeek` with `weekNumber=5` by a corresponding object with `weekNumber=-1`.
2. **Export**: call the original converter and, if the input days are exclusively last-weekday (`weekNumber=-1`), normalize `EXSCalendarItemProperties.recurrenceDayOfWeekIndex` to 5.

The module checks the exact build compiled into `EXS_EXPECTED_BUILD` (`25G241`, `25G332`, or `25G342` in the supported build script), Intel architecture, the Objective-C method encodings, and implementation origins before installing both method replacements. It is intentionally fail-closed when those assumptions do not hold.

## Imported recurrence persistence and observability (Tahoe 25G332)

In a separate 27 October 2026 experiment with a validated `25G332` candidate, the two runtime method replacements were confirmed within the Exchange synchronization process. Nevertheless, previously misinterpreted occurrences only became visible after the Exchange account was disabled and re-enabled, causing a fresh import. This is consistent with an **already persisted incorrect EventKit recurrence** that the runtime conversion hook cannot retroactively rewrite. No direct EventKit database modification was attempted.

Following a reboot, a fresh process loaded the candidate and the fallback worker installed both hooks (`actual_source=3`); the passive monitoring job was also registered. The post-reboot hook logs were observed directly and the user subsequently confirmed that the formerly missing Calendar occurrences remained visible after reboot.

A logging pitfall was observed during monitor activation: `os_log_info` records previously visible for a live process were later unavailable even though its PID had not changed and the recurrence had been functionally verified. Therefore, the absence of retained installation logs must be treated as **unconfirmed**, not as a proof that hooks were removed. The local installer had also rejected a protected journal file because its unprivileged check could not traverse a root-owned `0700` directory. Both issues are in deployment verification, not the recurrence conversion itself.

These deployment scripts and binaries are **not published**. The Objective-C source matches the `25G332` validated candidate sources byte-for-byte. On this branch, `tools/build.sh` provides an exact compile-time build gate for `25G241`, `25G332`, and the live-tested `25G342`. No publicly vetted installation mechanism is provided, and untested future builds remain rejected.


`src/Autoload.m` attempts installation in the constructor, after relevant `dlopen` returns, and via a fallback worker. This improves late class-registration handling but does not guarantee no callback runs before the hooks are installed.

## Follow-up on Tahoe 25G342 (10 November 2026)

The unmodified private converter still returned week number `5` for EXS ordinal `5` on the release build `25G342`. The same Objective-C v6 source compiled and passed the normal startup, fault-injected deferred startup and deliberate build-mismatch tests in separate subprocesses. An attended update of the persistent custom ExchangeSync service encountered a transient `xpcproxy` launch state that the initial verifier incorrectly rejected. The native Apple daemon was restored automatically; a separately validated, state-specific continuation subsequently installed both hooks in the live `exchangesyncd` process (PID 63638) and enabled the monitor.

The user then confirmed that existing affected Exchange occurrences were present in Apple Calendar and that a newly created affected recurrence worked correctly. The 25G342 deployment has **not yet been checked after another reboot**. Privileged migration scripts remain excluded from the public repository pending a genuinely reusable and reviewed deployment strategy.
