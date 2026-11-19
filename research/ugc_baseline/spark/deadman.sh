#!/bin/bash
# Host cron (*/5): independent of the container. Restarts a stopped container; alerts on stale heartbeat
# or on no progress for 60 min. Alerts rate-limited to once per hour per kind. Signal-only pushes.
T=$HOME/tribe; W=$T/work; HB=$W/heartbeat.json; DM=$T/deadman; mkdir -p $DM; ST=$DM/state; LOG=$DM/deadman.log
note(){ echo "$(date -Is) deadman: $*" >> $LOG; }
push(){ local k=$1 m=$2 f=$DM/.alert_$1; [ -f $f ] && [ $(( $(date +%s) - $(stat -c %Y $f) )) -lt 3600 ] && return
  ( . $T/ntfy.env && curl -sf -m 15 -H "Title: Spark job" -d "$m" "$NTFY_SERVER/$NTFY_BRIEF_TOPIC" >/dev/null ) && touch $f || note "PUSH_FAILED $m"; note "PUSH: $m"; }
[ "${1:-}" = "--test-push" ] && { rm -f $DM/.alert_test; push test "test alert: monitoring path works"; exit; }
if ! docker ps --format '{{.Names}}' | grep -qx tribe; then
  docker start tribe >/dev/null 2>&1 && { note "container was down, started it"; push down "container was down, restarted it"; } \
    || { note "container down and start FAILED"; push downfail "container down and could not restart, needs a look"; }
  exit
fi
now=$(date +%s)
[ -f $HB ] || { push nohb "no heartbeat file, needs a look"; exit; }
hb_age=$((now - $(stat -c %Y $HB)))
state=$(python3 -c "import json;print(json.load(open('$HB'))['state'])" 2>/dev/null || echo unknown)
done_n=$(python3 -c "import json;print(json.load(open('$HB'))['done'])" 2>/dev/null || echo -1)
[ "$hb_age" -gt 900 ] && push stale "supervisor silent for $((hb_age/60)) min, needs a look"
[ "$state" = failed ] && push failed "job in FAILED state, needs a look"
if [ "$state" = running ]; then
  read -r last_n last_t < <(cat $ST 2>/dev/null || echo "-1 $now")
  if [ "$done_n" != "$last_n" ]; then echo "$done_n $now" > $ST
  elif [ $((now - last_t)) -gt 3600 ]; then push noprog "no progress for $(( (now - last_t)/60 )) min, needs a look"; fi
fi
