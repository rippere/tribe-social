"""Blind human review of the UGC baseline's human/AI labels.

Shows each included clip (video + 8-frame contact sheet) under an anonymous ID, in a fixed random order,
without its file name, search-source label or the subagent's call. Labels save on every click to
human_labels.json beside this file (carries clip IDs: keep it out of the public repo).

    python research/ugc_baseline/label_review.py [--port 8790]
"""
import argparse, json, os, random, re, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "human_labels.json"
LOCK = threading.Lock()

clips = sorted(v["name"] for v in json.loads((HERE / "vetting.json").read_text()) if v["include"])
random.Random(20261119).shuffle(clips)
ANON = {f"c{i+1:02d}": name for i, name in enumerate(clips)}


def load():
    return json.loads(OUT.read_text()) if OUT.exists() else {}


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UGC label review</title><style>
:root{--bg:#0d0f12;--fg:#e8e8e8;--mut:#8a9099;--card:#171a1f;--acc:#e8a830;--ai:#7aa2f7;--hu:#9ece6a;--un:#a0a0a0}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.bar{height:6px;background:var(--card);border-radius:3px;margin:8px 0 16px}.bar>i{display:block;height:100%;background:var(--acc);border-radius:3px}
.grid{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:16px}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
video{width:100%;max-height:70vh;background:#000;border-radius:8px}
img{width:100%;border-radius:8px}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
button{font:inherit;padding:10px 18px;border-radius:8px;border:1px solid #333;background:var(--card);color:var(--fg);cursor:pointer}
button.sel{outline:2px solid var(--acc)}
.ai{border-color:var(--ai)}.hu{border-color:var(--hu)}.un{border-color:var(--un)}
input{font:inherit;width:100%;box-sizing:border-box;padding:8px;border-radius:8px;border:1px solid #333;background:var(--card);color:var(--fg)}
.mut{color:var(--mut);font-size:13px}
</style></head><body><main>
<div class="top"><b id="title"></b><span class="mut" id="prog"></span></div>
<div class="bar"><i id="fill"></i></div>
<div class="grid"><video id="v" controls muted playsinline></video><img id="s" alt="contact sheet"></div>
<div class="btns">
 <button class="ai" data-l="ai">AI-made (a)</button><button class="hu" data-l="human">Human-made (h)</button>
 <button class="un" data-l="unclear">Unclear (u)</button>
 <span style="flex:1"></span><button id="prev">&larr; Prev</button><button id="next">Next &rarr;</button><button id="skip">Next unlabelled (n)</button>
</div>
<input id="note" placeholder="Optional note (what gave it away?)">
<p class="mut">Label from what you see and hear, as a viewer would. Each click saves. Keys: a / h / u label and advance, &larr; &rarr; move.</p>
</main><script>
let ids=[],labels={},i=0;const $=s=>document.querySelector(s);
async function init(){const r=await (await fetch('state')).json();ids=r.ids;labels=r.labels;
 i=Math.max(0,ids.findIndex(x=>!labels[x]));if(i<0)i=0;show()}
function show(){const id=ids[i];$('#title').textContent=`Clip ${id}  (${i+1} of ${ids.length})`;
 const n=ids.filter(x=>labels[x]).length;$('#prog').textContent=`${n} labelled`;$('#fill').style.width=(100*n/ids.length)+'%';
 $('#v').src='clip/'+id;$('#v').play().catch(()=>{});$('#s').src='sheet/'+id;$('#note').value=(labels[id]||{}).note||'';
 document.querySelectorAll('[data-l]').forEach(b=>b.classList.toggle('sel',(labels[id]||{}).label===b.dataset.l))}
async function save(l){const id=ids[i];labels[id]={label:l,note:$('#note').value};
 await fetch('label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,label:l,note:$('#note').value})});
 if(i<ids.length-1)i++;show()}
document.querySelectorAll('[data-l]').forEach(b=>b.onclick=()=>save(b.dataset.l));
$('#prev').onclick=()=>{if(i>0){i--;show()}};$('#next').onclick=()=>{if(i<ids.length-1){i++;show()}};
$('#skip').onclick=()=>{const j=ids.findIndex((x,k)=>k>i&&!labels[x]);const k=j>=0?j:ids.findIndex(x=>!labels[x]);if(k>=0){i=k;show()}};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;
 if(e.key==='a')save('ai');else if(e.key==='h')save('human');else if(e.key==='u')save('unclear');
 else if(e.key==='n')$('#skip').click();else if(e.key==='ArrowLeft')$('#prev').click();else if(e.key==='ArrowRight')$('#next').click()});
init();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def file(self, path, ctype):
        size = path.stat().st_size
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        with open(path, "rb") as f:
            if not m:
                return self.send(200, f.read(), ctype, {"Accept-Ranges": "bytes"})
            start = int(m.group(1) or 0)
            end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            f.seek(start)
            body = f.read(end - start + 1)
        self.send(206, body, ctype, {"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{size}"})

    def do_GET(self):
        p = self.path.split("?")[0].strip("/")
        if p == "":
            return self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        if p == "state":
            names = {n: k for k, n in ANON.items()}
            labels = {names[n]: v for n, v in load().items() if n in names}
            return self.send(200, json.dumps({"ids": list(ANON), "labels": labels}).encode(), "application/json")
        kind, _, aid = p.partition("/")
        name = ANON.get(aid)
        if name and kind == "clip":
            # review_cache/ holds H.264 + faststart copies (source clips are partly AV1/VP9, which
            # Safari and some browsers won't play); fall back to the original if missing.
            cached = HERE / "review_cache" / f"{name}.mp4"
            return self.file(cached if cached.exists() else HERE / "clips" / f"{name}.mp4", "video/mp4")
        if name and kind == "sheet":
            return self.file(HERE / "sheets" / f"{name}.jpg", "image/jpeg")
        self.send(404, b"not found", "text/plain")

    do_HEAD = do_GET

    def do_POST(self):
        if self.path.strip("/") != "label":
            return self.send(404, b"not found", "text/plain")
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        name = ANON.get(d.get("id"))
        if not name or d.get("label") not in ("ai", "human", "unclear"):
            return self.send(400, b"bad label", "text/plain")
        with LOCK:
            data = load()
            data[name] = {"label": d["label"], "note": str(d.get("note", ""))[:500]}
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
            os.replace(tmp, OUT)
        self.send(200, b"{}", "application/json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    a = ap.parse_args()
    print(f"{len(ANON)} clips, labels -> {OUT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()
