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

The module checks macOS build `25G241`, Intel architecture, the exact Objective-C method encodings, and implementation origins before installing both method replacements. It is intentionally fail-closed when those assumptions do not hold.

`src/Autoload.m` attempts installation in the constructor, after relevant `dlopen` returns, and via a fallback worker. This improves late class-registration handling but does not guarantee no callback runs before the hooks are installed.
