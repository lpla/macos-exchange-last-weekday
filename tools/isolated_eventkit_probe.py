#!/usr/bin/env python3
"""EXPERIMENTAL: call Apple's private Exchange -> EventKit conversion on synthetic data.

Run only on macOS (x86_64 and arm64e builds may differ), in an isolated Python
process. It never attaches to exchangesyncd or reads any calendar, mailbox or
account. It does load a private system plug-in, which may be disallowed by macOS.
"""
import ctypes as C
import platform
import sys


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This probe requires macOS.')
    location = ('/System/Library/PrivateFrameworks/ExchangeSync.framework/'
                'Versions/A/DataConsumers/EventKitDataConsumer.dataconsumer/'
                'Contents/MacOS/EventKitDataConsumer')
    print('macOS architecture:', platform.machine(), flush=True)
    print('Private bundle:', location, flush=True)
    try:
        C.CDLL(location, mode=C.RTLD_GLOBAL)
    except OSError as exc:
        raise SystemExit('Cannot load the system bundle in this process: '
                         f'{exc}\nDo not disable SIP or library validation to run this probe.')
    objc = C.CDLL('/usr/lib/libobjc.A.dylib')

    def bind(name, result, *argtypes):
        f = getattr(objc, name)
        f.restype, f.argtypes = result, list(argtypes)
        return f

    cls_for = bind('objc_getClass', C.c_void_p, C.c_char_p)
    selector = bind('sel_registerName', C.c_void_p, C.c_char_p)
    make_class = bind('objc_allocateClassPair', C.c_void_p, C.c_void_p,
                      C.c_char_p, C.c_size_t)
    add_method = bind('class_addMethod', C.c_bool, C.c_void_p, C.c_void_p,
                      C.c_void_p, C.c_char_p)
    register = bind('objc_registerClassPair', None, C.c_void_p)

    cls = cls_for(b'NSObject')
    fake_cls = make_class(cls, b'SyntheticEXSRecurrencePropertiesProbe', 0)
    if not fake_cls:
        raise SystemExit('Could not allocate synthetic Objective-C class')

    ordinal = [5]
    # EXS day bitmask: 0x04 is Tuesday (EKTuesday = 3, because Sunday = 1).
    CALLBACK = C.CFUNCTYPE(C.c_int64, C.c_void_p, C.c_void_p)

    @CALLBACK
    def days_of_week(_obj, _cmd):
        return 0x04

    @CALLBACK
    def week_index(_obj, _cmd):
        return ordinal[0]

    callbacks = (days_of_week, week_index)  # keep references alive
    for name, cb in [(b'recurrenceDaysOfWeek', callbacks[0]),
                     (b'recurrenceDayOfWeekIndex', callbacks[1])]:
        if not add_method(fake_cls, selector(name), C.cast(cb, C.c_void_p),
                          b'q16@0:8'):
            raise SystemExit(f'Could not add selector: {name.decode()}')
    register(fake_cls)

    # objc_msgSend: first two implicit arguments are 'self' and '_cmd'.
    msg_ptr = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p)(
        ('objc_msgSend', objc))
    msg_obj = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p)(
        ('objc_msgSend', objc))
    msg_index = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64)(
        ('objc_msgSend', objc))
    msg_int = C.CFUNCTYPE(C.c_int64, C.c_void_p, C.c_void_p)(
        ('objc_msgSend', objc))

    instance = msg_ptr(msg_ptr(fake_cls, selector(b'alloc')), selector(b'init'))
    utils = cls_for(b'EXSEKRecurrenceUtils')
    if not utils:
        raise SystemExit('EXSEKRecurrenceUtils was not registered by the bundle')

    print('\nSynthetic Tuesday monthly recurrence:')
    print('EXS index  ->  EventKit weekday  EventKit week number', flush=True)
    for value in (1, 2, 3, 4, 5, -1):
        ordinal[0] = value
        arr = msg_obj(utils, selector(b'daysOfTheWeekFromPropertiesWithEK:'),
                      instance)
        if not arr:
            raise RuntimeError(f'Converter returned nil for index {value}')
        count = msg_int(arr, selector(b'count'))
        if count != 1:
            raise RuntimeError(f'Unexpected number of days: {count}')
        weekday = msg_index(arr, selector(b'objectAtIndex:'), 0)
        day = msg_int(weekday, selector(b'dayOfTheWeek'))
        number = msg_int(weekday, selector(b'weekNumber'))
        print(f'{value:>9}  -> {day:>16}  {number:>20}', flush=True)
        if day != 3 or number != value:
            raise AssertionError('Unexpected conversion: investigate before patching')
    print('\nProbe passed: input ordinal 5 is passed through unchanged.')
    print('This does not patch macOS or prove which network backend populated EXS.')


if __name__ == '__main__':
    main()
