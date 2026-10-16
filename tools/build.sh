#!/bin/zsh
set -euo pipefail
cd "${0:A:h}/.."
mkdir -p build
args=(-arch x86_64 -dynamiclib -fobjc-arc -O2 -Wall -Wextra -Werror
      -framework Foundation -framework EventKit
      -install_name '@rpath/libExchangeLastWeekdayFix.dylib')
/usr/bin/clang "${args[@]}" -o build/libExchangeLastWeekdayFix.v6.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${args[@]}" '-DEXS_EXPECTED_BUILD="X-TEST-MISMATCH"' \
  -o build/libExchangeLastWeekdayFix.v6-mismatch.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${args[@]}" '-DEXS_LAB_TRANSIENT_FAIL_COUNT=8' \
  -o build/libExchangeLastWeekdayFix.v6-transient-test.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
for f in build/*.dylib; do
  /usr/bin/codesign --force --sign - "$f"
  /usr/bin/codesign --verify -v "$f"
done
echo 'Built three isolated lab binaries. Nothing installed in /Library.'
