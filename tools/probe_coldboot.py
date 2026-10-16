#!/usr/bin/env python3
"""Isolated v6 startup and bidirectional tests: no calendar, Exchange or daemon access.

Three fresh Python subprocesses preload different dylibs using DYLD_INSERT_LIBRARIES.
The intentionally mismatched dylib MUST refuse to patch. The matching one
should hook synchronously when dlopen returns, if that loader path is used.
"""
from __future__ import annotations
import ctypes as C
import os
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ('/System/Library/PrivateFrameworks/ExchangeSync.framework/Versions/A/'
          'DataConsumers/EventKitDataConsumer.dataconsumer/Contents/MacOS/EventKitDataConsumer')
BUILT = ROOT / 'build'


def objc_api(objc, name, restype, *args):
    fn = getattr(objc, name)
    fn.restype = restype
    fn.argtypes = list(args)
    return fn


def conversion_tests(expect_patched):
    objc = C.CDLL('/usr/lib/libobjc.A.dylib')
    klass = objc_api(objc, 'objc_getClass', C.c_void_p, C.c_char_p)
    sel = objc_api(objc, 'sel_registerName', C.c_void_p, C.c_char_p)
    send0 = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
    send1 = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
    sendInt = C.CFUNCTYPE(C.c_int64, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
    sendIdx = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64)(('objc_msgSend', objc))
    sendSetInt = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_int64)(('objc_msgSend', objc))
    sendSetUInt = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint64)(('objc_msgSend', objc))
    send2Int = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64)(('objc_msgSend', objc))
    sendVoid2 = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
    util = klass(b'EXSEKRecurrenceUtils')
    props_cls = klass(b'EXSCalendarItemProperties')
    day_cls = klass(b'EKRecurrenceDayOfWeek')
    array_cls = klass(b'NSArray')
    if not all((util, props_cls, day_cls, array_cls)):
        raise RuntimeError('Required Apple classes unavailable')
    props = send0(send0(props_cls, sel(b'alloc')), sel(b'init'))
    if not props:
        raise RuntimeError('EXSCalendarItemProperties init failed')
    sendSetUInt(props, sel(b'setRecurrenceDaysOfWeek:'), 4)  # Tuesday mask

    for ordinal in (4, 5):
        sendSetInt(props, sel(b'setRecurrenceDayOfWeekIndex:'), ordinal)
        days = send1(util, sel(b'daysOfTheWeekFromPropertiesWithEK:'), props)
        if not days or sendInt(days, sel(b'count')) != 1:
            raise AssertionError('Unexpected forward conversion array')
        day = sendIdx(days, sel(b'objectAtIndex:'), 0)
        value = (sendInt(day, sel(b'dayOfTheWeek')), sendInt(day, sel(b'weekNumber')))
        expected = (3, (-1 if ordinal == 5 else ordinal) if expect_patched else ordinal)
        print(f'  EXS {ordinal} -> EventKit {value}; expected {expected}', flush=True)
        assert value == expected

    for ordinal in (4, -1):
        day = send2Int(day_cls, sel(b'dayOfWeek:weekNumber:'), 3, ordinal)
        days = send1(array_cls, sel(b'arrayWithObject:'), day)
        sendVoid2(util, sel(b'EKdaysOfTheWeek:toProperties:'), days, props)
        value = sendInt(props, sel(b'recurrenceDayOfWeekIndex'))
        expected = 5 if ordinal == -1 and expect_patched else ordinal
        print(f'  EventKit {ordinal} -> EXS {value}; expected {expected}', flush=True)
        assert value == expected


def child(mode):
    fpath = BUILT / {'normal': 'libExchangeLastWeekdayFix.v6.dylib',
                      'mismatch': 'libExchangeLastWeekdayFix.v6-mismatch.dylib',
                      'transient': 'libExchangeLastWeekdayFix.v6-transient-test.dylib'}[mode]
    assert os.environ.get('DYLD_INSERT_LIBRARIES') == str(fpath), 'Injected dylib does not match target'
    lib = C.CDLL(str(fpath))
    names = ('exchange_last_weekday_patch_version', 'exchange_last_weekday_build_compatible',
             'exchange_last_weekday_autoload_state', 'exchange_last_weekday_installed',
             'exchange_last_weekday_startup_source', 'exchange_last_weekday_seen_plugin_dlopen',
             'exchange_last_weekday_installed_after_dlopen',
             'exchange_last_weekday_actual_installer_source',
             'exchange_last_weekday_attempt_count', 'exchange_last_weekday_last_result',
             'exchange_last_weekday_constructor_entered', 'exchange_last_weekday_initial_result',
             'exchange_last_weekday_worker_started', 'exchange_last_weekday_worker_running',
             'exchange_last_weekday_worker_finished')
    funcs = {}
    for name in names:
        fn = getattr(lib, name)
        fn.restype = C.c_int
        funcs[name] = fn
    def val(name):
        return funcs['exchange_last_weekday_' + name]()
    print('Platform:', platform.mac_ver(), platform.machine(), 'mode:', mode, flush=True)
    print('Build match:', val('build_compatible'), 'installed before loading plugin:', val('installed'), flush=True)
    assert val('patch_version') == 6
    assert val('constructor_entered') == 1, 'Constructor never ran'
    initial = val('initial_result')
    expected_initial = {'normal': (-1, -2, -8), 'mismatch': (-5,), 'transient': (-8,)}[mode]
    print('Constructor result:', initial, 'expected:', expected_initial,
          'worker_started:', val('worker_started'), flush=True)
    assert initial in expected_initial, 'Unexpected constructor result'
    if mode != 'mismatch':
        assert val('worker_started') == 1, 'Fallback thread not started after transient result'
    else:
        assert val('worker_started') == 0, 'Worker wrongly started on incompatible OS'
    assert val('installed') == 0, 'Plugin was already loaded; test process not isolated'
    C.CDLL(PLUGIN, mode=C.RTLD_GLOBAL)
    if mode == 'transient':
        import time
        deadline = time.monotonic() + 8
        while not val('installed') and time.monotonic() < deadline:
            time.sleep(0.1)
    print('After plugin dlopen / permitted worker retries:', {
        'installed': val('installed'), 'state': val('autoload_state'),
        'source': val('startup_source'), 'target_dlopen': val('seen_plugin_dlopen'),
        'post_dlopen_installed': val('installed_after_dlopen'),
        'actual_installer_source': val('actual_installer_source'),
        'attempts': val('attempt_count'), 'last_rc': val('last_result'),
        'worker_started': val('worker_started'),
        'worker_finished': val('worker_finished')}, flush=True)
    if mode in ('normal', 'transient'):
        assert val('build_compatible') == 1, 'OS build gate did not match 25G241'
        assert val('installed') == 1, 'Hooks did not install after plugin became ready'
        assert val('seen_plugin_dlopen') >= 1, 'The dlopen interposer did not see the plugin'
        if mode == 'normal':
            assert val('installed_after_dlopen') >= 1, 'Post-dlopen did not observe hooks'
        if val('startup_source') != 2:
            print('NOTE: worker installed hooks and interposer also observed plugin loading.')
        assert val('actual_installer_source') in (2, 3), 'Unknown actual installation origin'
        initial_actual = val('actual_installer_source')
        # A later invocation pretending to be the polling worker cannot
        # change provenance after both hooks have already been installed.
        later = getattr(lib, 'exchange_last_weekday_install_from')
        later.argtypes = [C.c_int]
        later.restype = C.c_int
        assert later(3) == 1, 'Expected already-installed from a later observer'
        assert val('actual_installer_source') == initial_actual, 'Provenance changed after installation'
        conversion_tests(True)
        print(f'PASS: {mode} installs hooks and preserves attribution.', flush=True)
    else:
        assert val('build_compatible') == 0, 'Intentional mismatch was incorrectly accepted'
        assert val('installed') == 0, 'A mismatched build installed hooks!'
        assert val('autoload_state') == -1, 'Mismatch did not produce explicit refusal'
        assert val('actual_installer_source') == 0, 'Unexpected attribution for rejected build'
        conversion_tests(False)
        print('PASS: forced unsupported build did not patch either direction.', flush=True)


def main():
    if sys.platform != 'darwin' or platform.machine() != 'x86_64':
        raise SystemExit('This probe requires macOS Intel x86_64')
    if os.environ.get('EXS_V6_TEST_CHILD'):
        child(os.environ['EXS_V6_TEST_CHILD'])
        return
    for name in ('libExchangeLastWeekdayFix.v6.dylib', 'libExchangeLastWeekdayFix.v6-mismatch.dylib',
                 'libExchangeLastWeekdayFix.v6-transient-test.dylib'):
        if not (BUILT / name).is_file():
            raise SystemExit(f'Missing {name}; run ./tools/build.sh first')
    for mode in ('normal', 'transient', 'mismatch'):
        print('\n=== FRESH ISOLATED PROCESS:', mode, '===', flush=True)
        env = os.environ.copy()
        env.pop('DYLD_INSERT_LIBRARIES', None)
        env['EXS_V6_TEST_CHILD'] = mode
        lib = BUILT / {'normal': 'libExchangeLastWeekdayFix.v6.dylib',
                       'mismatch': 'libExchangeLastWeekdayFix.v6-mismatch.dylib',
                       'transient': 'libExchangeLastWeekdayFix.v6-transient-test.dylib'}[mode]
        env['DYLD_INSERT_LIBRARIES'] = str(lib)
        res = subprocess.run([sys.executable, str(Path(__file__).resolve())], env=env, check=False)
        if res.returncode:
            raise SystemExit(f'FAIL/INCONCLUSIVE: {mode} process exited with {res.returncode}')
    print('\nPASS: three isolated startup, transient recovery and mismatch tests completed.')
    print('No process, account or calendar on the Mac was modified.')


if __name__ == '__main__':
    main()
