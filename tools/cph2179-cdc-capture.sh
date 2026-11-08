#!/usr/bin/env bash
set -euo pipefail

out="${1:-cph2179-cdc-heartbeat.txt}"
seconds="${2:-30}"
[[ "$seconds" =~ ^[1-9][0-9]*$ ]] || {
    echo "usage: $0 [output-file] [capture-seconds]" >&2
    exit 2
}

deadline=$((SECONDS + seconds))
port=""
while (( SECONDS < deadline )); do
    for candidate in /dev/ttyACM* /dev/ttyUSB*; do
        if [[ -c "$candidate" ]]; then
            port="$candidate"
            break 2
        fi
    done
    sleep 0.1
done

if [[ -z "$port" ]]; then
    echo "No CDC serial device appeared within ${seconds}s" >&2
    exit 1
fi

stty -F "$port" 115200 raw -echo -ixon -ixoff
remaining=$((deadline - SECONDS))
(( remaining > 0 )) || remaining=1
echo "Capturing $port to $out for at most ${remaining}s" >&2

set +e
timeout "${remaining}s" cat "$port" | tee "$out"
capture_status=${PIPESTATUS[0]}
set -e
if (( capture_status != 0 && capture_status != 124 )); then
    echo "CDC read failed with status $capture_status" >&2
    exit "$capture_status"
fi
