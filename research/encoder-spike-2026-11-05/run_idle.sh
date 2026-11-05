#!/bin/zsh
# Spike 2 driver: each mode starts only when a 10 s `top` sample shows the CPU >= 70% idle.
# Checks every 15 minutes; no mode starts 12 hours or more after launch (each skipped mode gets
# a gave_up row). While a mode runs, `top` samples CPU idle back to back (10 s each); the row
# keeps their mean and minimum. The job itself takes about 40% of 10 cores, so a mean below
# 40% idle means other work competed: flagged in RESULTS. Exit code = number of failed modes.
set -u
cd "${0:A:h}/../.."
ORT=~/.lcc/bench/encoder-spike-2026-11-05/venv/bin/python
PT=~/lcc/.venv/bin/python
S=research/encoder-spike-2026-11-05/spike.py
LOG=research/encoder-spike-2026-11-05/out/idle-log.tsv
ERR=research/encoder-spike-2026-11-05/out/idle-stderr.log
DEADLINE=$(( $(date +%s) + 12 * 3600 ))
FAILED=0
[[ -f $LOG ]] || print -r -- $'mode\ttime\tidle_before\tidle_during_mean\tidle_during_min\tload_before\tload_after\texit' > $LOG

cpu_idle() {  # integer % idle over a 10 s sample ("CPU usage: a% user, b% sys, c% idle")
  top -l 2 -s 10 -n 0 | awk '/CPU usage/ {v = $7} END {sub("%", "", v); print int(v)}'
}

row() { print -r -- "${(pj:\t:)@}" >> $LOG }

run() {
  local py=$1 mode=$2; shift 2
  local before
  while true; do
    if (( $(date +%s) >= DEADLINE )); then
      row "${mode}${*:+ $*}" "$(date -u +%FT%TZ)" '' '' '' '' '' gave_up
      (( FAILED++ ))
      return
    fi
    before=$(cpu_idle)
    (( before >= 70 )) && break
    sleep 900
  done
  local start=$(date -u +%FT%TZ) load=$(sysctl -n vm.loadavg)
  "$py" -I $S $mode "$@" > /dev/null 2>> $ERR &
  local pid=$! s
  local -a samples
  while kill -0 $pid 2> /dev/null; do
    s=$(cpu_idle)
    kill -0 $pid 2> /dev/null && samples+=($s)  # only samples that ended with the job running
  done
  wait $pid
  local code=$?
  (( code )) && (( FAILED++ ))
  local stats=$(print -l -- $samples | awk 'NF {t += $1; if (n == 0 || $1 < m) m = $1; n++}
    END {if (n) printf "%d\t%d", t / n, m; else printf "\t"}')
  row "${mode}${*:+ $*}" "$start" "$before" "${stats%%$'\t'*}" "${stats##*$'\t'}" "$load" "$(sysctl -n vm.loadavg)" "$code"
}

run $ORT ort-fp32
run $ORT ort-int8
run $ORT ort-int8-pruned
run $ORT ort-int8-pruned-lowmem
run $PT fp32 --tag idle
run $PT int8 --tag idle
print "done, $FAILED failed"
exit $FAILED
