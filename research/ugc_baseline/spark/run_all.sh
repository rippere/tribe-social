#!/bin/bash
# Container entrypoint (under tini). Supervises the batch: relaunch on exit, kill+relaunch on stall,
# quarantine clips that stall twice, then analyze. Never exits silently: every state change -> events.log,
# important ones -> signal-only push. Writes heartbeat.json every loop for the host dead-man check.
set -u
W=/tribe/work; LOG=$W/events.log; HB=$W/heartbeat.json; BLOG=$W/batch.log
exec 9>$W/run_all.lock; flock -n 9 || { echo "supervisor already running"; exec sleep infinity; }
note(){ echo "$(date -Is) $*" >> $LOG; }
push(){ ( . /tribe/ntfy.env && curl -sf -m 15 -H "Title: Spark job" -d "$1" "$NTFY_SERVER/$NTFY_BRIEF_TOPIC" >/dev/null ) || note "PUSH_FAILED: $1"; note "PUSH: $1"; }
cfg(){ STALL=600; CLIP_BASE=900; CLIP_PER_S=30; MAXR=10; [ -f $W/supervisor.env ] && . $W/supervisor.env; }
total=$(ls /tribe/ugc/*.mp4 | wc -l)
ndone(){ ls /tribe/ugc_preds/*_preds.npy 2>/dev/null | wc -l; }
nquar(){ [ -f $W/quarantine.txt ] && sort -u $W/quarantine.txt | grep -c . || echo 0; }
wpid(){ pgrep -f "python batch.py" | head -1; }
beat(){ printf '{"ts":%s,"state":"%s","done":%s,"total":%s,"quarantined":%s,"restarts":%s,"detail":"%s"}\n' \
  "$(date +%s)" "$1" "$(ndone)" "$total" "$(nquar)" "${restarts:-0}" "${2:-}" > $HB.tmp && mv $HB.tmp $HB; }
idle(){ while :; do beat "$1" "${2:-}"; sleep 300; done; }
clear_inflight(){ python - <<'PY'
import glob, sqlite3
for db in glob.glob("/tribe/cache/*/inflight.db"):
    try:
        c = sqlite3.connect(db, timeout=20); n = c.execute("DELETE FROM inflight").rowcount; c.commit(); c.close()
        if n: print(f"cleared {n} stale claim(s) in {db.split('/')[3][:60]}")
    except Exception as e: print(f"inflight clear failed {db}: {e}")
PY
}
kill_worker(){ local p; p=$(wpid); [ -z "$p" ] && return; kill -TERM $p; for _ in $(seq 20); do kill -0 $p 2>/dev/null || break; sleep 1; done; kill -KILL $p 2>/dev/null; sleep 3; }
[ -f /tribe/ugc_results/DONE ] && { note "supervisor start: already DONE"; idle done; }
note "supervisor start (pid $$), $(ndone)/$total done"; restarts=0; last_q=$(nquar)
while :; do
  cfg; d=$(ndone); q=$(nquar)
  [ "$q" -gt "$last_q" ] && { push "1 item skipped after repeated failures ($q total skipped)"; last_q=$q; }
  [ $((d + q)) -ge "$total" ] && break
  if [ -z "$(wpid)" ]; then
    if [ "$restarts" -ge "$MAXR" ]; then note "GIVING UP after $MAXR launches"; push "GAVE UP after $MAXR restarts, needs a look"; idle failed "max restarts"; fi
    note "$(clear_inflight)"; restarts=$((restarts + 1)); note "LAUNCH worker #$restarts ($d/$total done, $q quarantined)"
    [ "$restarts" -gt 1 ] && [ "${just_stalled:-0}" != 1 ] && push "worker exited and was restarted (#$restarts), $d/$total done"; just_stalled=0
    python batch.py /tribe/ugc /tribe/ugc_preds >> $BLOG 2>&1 &
    sleep 30; continue
  fi
  now=$(date +%s); log_age=$((now - $(stat -c %Y $BLOG))); clip=""; clip_age=0; limit=0
  if [ -f $W/current.json ]; then
    read -r clip started < <(python -c 'import json;d=json.load(open("/tribe/work/current.json"));print(d["clip"],int(d["started"]))')
    clip_age=$((now - started))
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 /tribe/ugc/$clip.mp4 2>/dev/null | cut -d. -f1); dur=${dur:-60}
    limit=$((CLIP_BASE + CLIP_PER_S * dur))
  fi
  if [ "$log_age" -gt "$STALL" ] || { [ "$limit" -gt 0 ] && [ "$clip_age" -gt "$limit" ]; }; then
    note "STALL clip=$clip log_age=${log_age}s clip_age=${clip_age}s limit=${limit}s -> kill + relaunch"
    if [ -n "$clip" ]; then echo "$clip" >> $W/attempts.txt
      [ "$(grep -cx "$clip" $W/attempts.txt)" -ge 2 ] && { echo "$clip" >> $W/quarantine.txt; note "QUARANTINE $clip (2 stalls/failures)"; }
    fi
    kill_worker; push "stall detected, worker killed and relaunched"; just_stalled=1; continue
  fi
  beat running "clip=$clip clip_age=${clip_age}s/${limit}s log_age=${log_age}s"; sleep 60
done
note "ANALYSIS start: $(ndone)/$total scored, $(nquar) quarantined"; beat analyzing
if python analyze_baseline.py /tribe/ugc_preds vetting.json /tribe/ugc_results > $W/analysis.log 2>&1; then
  echo "$(date -Is) DONE scored=$(ndone)/$total quarantined=$(nquar)" > /tribe/ugc_results/DONE
  note "DONE"; push "finished: $(ndone)/$total scored, $(nquar) skipped, results ready"; idle done
else note "ANALYSIS FAILED (see analysis.log)"; push "analysis FAILED, needs a look"; idle failed analysis; fi
