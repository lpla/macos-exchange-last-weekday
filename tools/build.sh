#!/bin/zsh
# Build only for individually validated Intel macOS builds.
# The 25G342 lab keeps optional test artifacts separate from normal builds.
# No installation, SIP modification, daemon operations or calendar access.
set -euo pipefail
cd "${0:A:h}/.."

running_build="$(/usr/bin/sw_vers -buildVersion)"
running_arch="$(/usr/bin/uname -m)"
[[ "$running_arch" == x86_64 ]] || {
  print -u2 -- "Unsupported CPU architecture: $running_arch (Intel x86_64 only)."
  exit 1
}

out_dir="build"
case "$running_build" in
  25G241|25G332|25G342)
    if [[ $# == 1 && "$1" == "--experimental-25G342" && "$running_build" == 25G342 ]]; then
      out_dir="build/experimental-25G342"
    elif (( $# != 0 )); then
      print -u2 -- "Unsupported build option. Use --experimental-25G342 only on build 25G342."
      exit 1
    fi
    ;;
  *)
    print -u2 -- "Unvalidated macOS build: $running_build (supported: 25G241, 25G332, 25G342)."
    exit 1
    ;;
esac

mkdir -p "$out_dir"
common_args=(-arch x86_64 -dynamiclib -fobjc-arc -O2 -Wall -Wextra -Werror
             -framework Foundation -framework EventKit
             -install_name '@rpath/libExchangeLastWeekdayFix.dylib')
# Compile the exact running build into the fail-closed Objective-C runtime gate.
build_define="-DEXS_EXPECTED_BUILD=\"$running_build\""

/usr/bin/clang "${common_args[@]}" "$build_define" \
  -o "$out_dir/libExchangeLastWeekdayFix.v6.dylib" \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${common_args[@]}" '-DEXS_EXPECTED_BUILD="X-TEST-MISMATCH"' \
  -o "$out_dir/libExchangeLastWeekdayFix.v6-mismatch.dylib" \
  src/ExchangeLastWeekdayFix.m src/Autoload.m
/usr/bin/clang "${common_args[@]}" "$build_define" '-DEXS_LAB_TRANSIENT_FAIL_COUNT=8' \
  -o "$out_dir/libExchangeLastWeekdayFix.v6-transient-test.dylib" \
  src/ExchangeLastWeekdayFix.m src/Autoload.m

for f in "$out_dir/libExchangeLastWeekdayFix.v6.dylib" \
         "$out_dir/libExchangeLastWeekdayFix.v6-mismatch.dylib" \
         "$out_dir/libExchangeLastWeekdayFix.v6-transient-test.dylib"; do
  /usr/bin/codesign --force --sign - "$f"
  /usr/bin/codesign --verify -v "$f"
done
print -- "Built three local Intel research artifacts for $running_build in $out_dir; no system modifications."
if [[ "$out_dir" == build/experimental-25G342 ]]; then
  print -- "ISOLATED LAB ARTIFACTS: do not install or inject the test variants."
fi
