import threading, queue, time, json, webbrowser, yaml
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from listener import start_listening
from classifier import TARSClassifier

PORT = 7474
TRIGGERS_PATH = Path(__file__).parent / "triggers.yaml"

def load_triggers():
    with open(TRIGGERS_PATH) as f:
        return yaml.safe_load(f)["triggers"]

tq = queue.Queue()
pq = queue.Queue(maxsize=20)
stop_event  = threading.Event()
_clients    = []
_lock       = threading.Lock()

def _broadcast(data):
    msg = f"data: {json.dumps(data)}\n\n".encode()
    with _lock:
        dead = []
        for q in _clients:
            try: q.put_nowait(msg)
            except queue.Full: dead.append(q)
        for q in dead: _clients.remove(q)

def _bridge():
    c = TARSClassifier()
    t = load_triggers()
    last = time.time()
    while not stop_event.is_set():
        if time.time()-last > 30:
            try: t=load_triggers(); last=time.time()
            except: pass
        try:
            kind, text = pq.get_nowait()
            if kind=="partial": _broadcast({"type":"partial","text":text})
            else: _broadcast({"type":"clear"})
        except queue.Empty: pass
        try:
            s = tq.get_nowait()
            _broadcast({"type":"sentence","text":s})
            name = c.classify(s, t)
            if name:
                tr = next(x for x in t if x["name"]==name)
                _broadcast({"type":"trigger","label":tr.get("reaction",tr.get("visual",name.upper()))})
        except queue.Empty: pass
        time.sleep(0.015)

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>TARS</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d0d;color:#f0f0f0;font-family:'Menlo','Monaco','Courier New',monospace;
     height:100vh;overflow:hidden;display:flex;flex-direction:column;padding:22px 36px}
#hdr{color:#1a5555;font-size:13px;font-weight:bold;letter-spacing:5px;margin-bottom:18px}
#partial{font-size:78px;font-weight:bold;color:#282828;min-height:96px;line-height:1.1;
         margin-bottom:18px;word-break:break-word;transition:color .1s}
#partial.active{color:#353535}
#cursor{display:inline-block;width:3px;height:.85em;background:#00ff88;margin-left:5px;
        vertical-align:middle;animation:blink 1s step-end infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
#divider{height:1px;background:#181818;margin-bottom:18px}
#history{flex:1;overflow:hidden;display:flex;flex-direction:column;gap:3px}
.entry{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
       opacity:0;transform:translateY(-10px);transition:all .3s ease}
.entry.in{opacity:1;transform:translateY(0)}
#overlay{display:none;position:fixed;inset:0;background:#0d0d0d;z-index:99;
         flex-direction:column;align-items:center;justify-content:center;cursor:pointer}
#overlay.show{display:flex}
#ot{font-size:88px;font-weight:bold;color:#ffd700;text-align:center;padding:40px;
    line-height:1.1;animation:pulse 1.5s ease-in-out infinite alternate}
#oh{position:absolute;bottom:28px;color:#2a2a2a;font-size:12px;letter-spacing:3px}
@keyframes pulse{from{opacity:.8}to{opacity:1}}
</style></head><body>
<div id="hdr">▶&nbsp;&nbsp;T A R S</div>
<div id="partial"><span id="pt"></span><span id="cursor"></span></div>
<div id="divider"></div>
<div id="history"></div>
<div id="overlay" onclick="dismiss()"><div id="ot"></div><div id="oh">CLICK TO DISMISS</div></div>
<script>
const pt=document.getElementById('pt'),
      par=document.getElementById('partial'),
      hist=document.getElementById('history'),
      ov=document.getElementById('overlay'),
      ot=document.getElementById('ot');
let history=[],otimer=null;
const SIZES=['46px','34px','26px','20px','16px','13px'],
      COLORS=['#f0f0f0','#aaaaaa','#717171','#505050','#3a3a3a','#2a2a2a'],
      WEIGHTS=['bold','normal','normal','normal','normal','normal'];
function render(){
  hist.innerHTML='';
  history.slice(0,6).forEach((t,i)=>{
    const d=document.createElement('div');
    d.className='entry'; d.textContent=t;
    d.style.fontSize=SIZES[i]; d.style.color=COLORS[i]; d.style.fontWeight=WEIGHTS[i];
    hist.appendChild(d);
    requestAnimationFrame(()=>requestAnimationFrame(()=>d.classList.add('in')));
  });
}
function dismiss(){
  ov.classList.remove('show');
  if(otimer){clearTimeout(otimer);otimer=null;}
}
const es=new EventSource('/events');
es.onmessage=e=>{
  const d=JSON.parse(e.data);
  if(d.type==='partial'){pt.textContent=d.text;par.classList.add('active');}
  else if(d.type==='clear'){pt.textContent='';par.classList.remove('active');}
  else if(d.type==='sentence'){
    pt.textContent='';par.classList.remove('active');
    history.unshift(d.text);history=history.slice(0,10);render();
  }
  else if(d.type==='trigger'){
    if(otimer)clearTimeout(otimer);
    ot.textContent=d.label;ov.classList.add('show');
    otimer=setTimeout(dismiss,3500);
  }
};
es.onerror=()=>setTimeout(()=>location.reload(),2000);
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'||e.key===' ')dismiss();
  if(e.key==='f'||e.key==='F'){
    if(!document.fullscreenElement)document.documentElement.requestFullscreen();
    else document.exitFullscreen();
  }
});
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        if self.path=="/":
            b=HTML.encode(); self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.send_header("Content-Length",len(b)); self.end_headers(); self.wfile.write(b)
        elif self.path=="/events":
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream")
            self.send_header("Cache-Control","no-cache")
            self.send_header("X-Accel-Buffering","no"); self.end_headers()
            cq=queue.Queue(maxsize=50)
            with _lock: _clients.append(cq)
            try:
                while not stop_event.is_set():
                    try: self.wfile.write(cq.get(timeout=25)); self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b'data: {"type":"ping"}\n\n'); self.wfile.flush()
            except: pass
            finally:
                with _lock:
                    try: _clients.remove(cq)
                    except: pass
        else: self.send_response(404); self.end_headers()

def main():
    threading.Thread(target=start_listening,args=(tq,pq,stop_event),daemon=True).start()
    threading.Thread(target=_bridge,daemon=True).start()
    srv=ThreadingHTTPServer(("127.0.0.1",PORT),H)
    print(f"Opening TARS → http://localhost:{PORT}")
    print("Press F in browser for fullscreen, Esc/Space to dismiss triggers\n")
    import subprocess; threading.Timer(1.5,lambda:subprocess.Popen(['open',f'http://localhost:{PORT}'])).start()
    import atexit
    atexit.register(srv.shutdown)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        stop_event.set()
        srv.shutdown()

if __name__=="__main__": main()
