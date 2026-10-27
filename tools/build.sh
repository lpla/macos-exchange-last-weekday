#!/bin/zsh
# Build only on individually validated Intel macOS releases.
# This compiles local research artifacts; it does not change any daemon.
set -euo pipefail
cd "${0:A:h}/.."

running_build="$(/usr/bin/sw_vers -buildVersion)"
running_arch="$(/usr/bin/uname -m)"
[[ "$running_arch" == x86_64 ]] || {
  print -u2 -- "Unsupported CPU architecture: $running_arch (Intel x86_64 only)."
  exit 1
}
case "$running_build" in
  25G241|25G332) ;;
  *)
    print -u2 -- "Unvalidated macOS build: $running_build (supported: 25G241, 25G332)."
    exit 1 ;;
esac

mkdir -p build
common_args=(-arch x86_64 -dynamiclib -fobjc-arc -O2 -Wall -Wextra -Werror
             -framework Foundation -framework EventKit
             -install_name '@rpath/libExchangeLastWeekdayFix.dylib')
# Compile the running OS build into the fail-closed C runtime gate.
build_define="-DEXS_EXPECTED_BUILD=\"$running_build\""

/usr/bin/clang "${common_args[@]}" "$build_define" \
  -o build/libExchangeLastWeekdayFix.v6.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${common_args[@]}" '-DEXS_EXPECTED_BUILD="X-TEST-MISMATCH"' \
  -o build/libExchangeLastWeekdayFix.v6-mismatch.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${common_args[@]}" "$build_define" '-DEXS_LAB_TRANSIENT_FAIL_COUNT=8' \
  -o build/libExchangeLastWeekdayFix.v6-transient-test.dylib \
  src/ExchangeLastWeekdayFix.m src/Autoload.m

for f in build/libExchangeLastWeekdayFix.v6.dylib \
         build/libExchangeLastWeekdayFix.v6-mismatch.dylib \
         build/libExchangeLastWeekdayFix.v6-transient-test.dylib; do
  /usr/bin/codesign --force --sign - "$f"
  /usr/bin/codesign --verify -v "$f"
done
print -- "Built three isolated Intel research artifacts for $running_build; no system modifications."
