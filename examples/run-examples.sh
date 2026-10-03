#!/usr/bin/env sh
# Run every example pair and compare the exit code with expected-exit.
set -u
here=$(cd "$(dirname "$0")" && pwd)
script="$here/../scripts/fidelity.py"
fail=0
for dir in "$here"/*/; do
  name=$(basename "$dir")
  expected=$(cat "$dir/expected-exit")
  python3 "$script" "$dir/original.txt" "$dir/rewrite.txt" >/dev/null
  got=$?
  if [ "$got" -eq "$expected" ]; then
    echo "ok    $name (exit $got)"
  else
    echo "FAIL  $name: expected exit $expected, got $got"
    fail=1
  fi
done
exit $fail
