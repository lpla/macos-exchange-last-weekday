#!/usr/bin/env python3
"""Generate local, static placeholders for monthly last-weekday Exchange omissions.

Does not access Exchange, EventKit, calendars, or any private APIs.
All data stays in the generated local ICS file until the user chooses to import it.
"""
import argparse
import calendar
import datetime as dt
import hashlib
from pathlib import Path
import re
from zoneinfo import ZoneInfo

WEEKDAYS = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}


def last_weekday(year, month, weekday):
    last = calendar.monthrange(year, month)[1]
    return dt.date(year, month, last - ((dt.date(year, month, last).weekday() - weekday) % 7))


def occurrences(first, until, weekday):
    """Yield last weekday of each month in inclusive [first, until]."""
    y, m = first.year, first.month
    while (y, m) <= (until.year, until.month):
        date = last_weekday(y, m, weekday)
        if first <= date <= until:
            yield date
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def ics_text(value):
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    """Fold iCalendar content lines by UTF-8 octets (RFC 5545, 75 bytes)."""
    parts, current, n = [], '', 0
    for ch in line:
        size = len(ch.encode('utf-8'))
        if n + size > 75:
            parts.append(current)
            current, n = ' ', 1
        current += ch
        n += size
    parts.append(current)
    return '\r\n'.join(parts)


def generate(first, until, weekday, when, duration, timezone, title, exclude=()):
    tz = ZoneInfo(timezone)
    skipped = set(exclude)
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Calendar Recurrence Diagnostic//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']
    restored = []
    for date in occurrences(first, until, weekday):
        # Fifth-occurrence months already show up in the affected Calendar client.
        if ((date.day - 1) // 7 + 1) == 5 or date in skipped:
            continue
        start = dt.datetime.combine(date, when, tzinfo=tz).astimezone(dt.timezone.utc)
        end = start + dt.timedelta(minutes=duration)
        stamp = lambda d: d.strftime('%Y%m%dT%H%M%SZ')
        uid_data = f'{title}|{stamp(start)}|{duration}|{timezone}'.encode()
        uid = hashlib.sha256(uid_data).hexdigest()[:32] + '@local.invalid'
        lines.extend(['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{now}',
                      f'DTSTART:{stamp(start)}', f'DTEND:{stamp(end)}',
                      f'SUMMARY:{ics_text(title)}',
                      'DESCRIPTION:Local placeholder only. Verify the original Outlook meeting. This is not an Exchange invitation.',
                      'TRANSP:TRANSPARENT', 'END:VEVENT'])
        restored.append((date, stamp(start)))
    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold(line) for line in lines) + '\r\n', restored


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--first', required=True, type=dt.date.fromisoformat)
    p.add_argument('--until', required=True, type=dt.date.fromisoformat)
    p.add_argument('--weekday', choices=list(WEEKDAYS), required=True)
    p.add_argument('--at', required=True, help='Local clock time HH:MM')
    p.add_argument('--minutes', type=int, default=60)
    p.add_argument('--timezone', default='Europe/Madrid')
    p.add_argument('--title', default='Check Outlook recurring meeting')
    p.add_argument('--exclude', action='append', default=[], type=dt.date.fromisoformat,
                   help='Known cancelled or modified occurrence; repeat as needed')
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    if a.first > a.until or a.minutes < 1 or a.minutes > 1440:
        p.error('Invalid date interval or duration')
    try:
        hh, mm = map(int, a.at.split(':'))
        when = dt.time(hh, mm)
        content, restored = generate(a.first, a.until, WEEKDAYS[a.weekday],
                                      when, a.minutes, a.timezone, a.title, a.exclude)
    except (ValueError, KeyError) as exc:
        p.error(str(exc))
    a.out.write_bytes(content.encode('utf-8'))
    print(f'Created {a.out} with {len(restored)} local placeholders:')
    for date, utc_start in restored:
        print(f'  {date.isoformat()} -> {utc_start}')
    print('Nothing was added to Calendar automatically. Import the ICS manually only after reviewing it.')


if __name__ == '__main__':
    main()
