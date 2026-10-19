from __future__ import annotations

import json
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from save_data import SaveDataError
from save_runtime import prepare_runtime, select_dataset


SETUP_HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>EFT 存档迁移确认</title>
<style>body{font:15px/1.6 system-ui,sans-serif;background:#f5f5f7;color:#1d1d1f;margin:0;padding:5vw}
main{max-width:700px;margin:auto;background:white;border-radius:20px;padding:28px;box-shadow:0 8px 30px #0001}
button,select{font:inherit;border:1px solid #ddd;border-radius:9px;padding:9px 14px;margin:6px 8px 6px 0}
button{background:#007aff;color:white;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}p{color:#515154}</style>
<main><h1>先确认旧存档</h1><p>发现旧版存档或未选择的存档集。尚未迁移，也没有创建空白档案替代它。</p>
<p>请先关闭使用同一旧目录的程序。确认后只会备份、复制到新的独立目录；所有原始数据库和失败副本都会保留，不合并两个非空存档。</p>
<pre id="inventory">正在只读检查…</pre><button id="migrate" disabled>备份并迁移旧存档</button>
<label id="legacySourceField" hidden>选择旧存档来源<select id="legacySource" aria-label="选择旧存档来源"></select></label>
<button id="createEmpty" hidden>创建空白档案，保留所有旧存档</button>
<select id="datasets" aria-label="已有存档集"></select><button id="select" disabled>选择此存档集</button>
<p id="status" role="status">关闭本页即可暂不迁移。</p></main><script>
let setup; const status=document.getElementById('status');
async function load(){setup=await(await fetch('/api/save-setup')).json();
document.getElementById('inventory').textContent=setup.root+'\\n'+(setup.databases||[]).map(entry=>JSON.stringify(entry)).join('\\n');
const sources=setup.legacy_roots||[];const choice=document.getElementById('legacySource');
document.getElementById('legacySourceField').hidden=!sources.length;document.getElementById('createEmpty').hidden=!sources.length;
choice.replaceChildren(new Option('请选择；不会自动合并',''),...sources.map(source=>{const option=new Option(source.path+' · 任务 '+(source.counts.tasks||0)+' / 档案 '+(source.counts.profiles||0)+(source.available?'':' · 不可迁移：'+source.notice),source.path);option.disabled=!source.available;return option}));
document.getElementById('migrate').disabled=sources.length? !choice.value:!(setup.databases||[]).length;
document.getElementById('datasets').replaceChildren(...(setup.datasets||[]).map(id=>new Option(id,id)));
document.getElementById('select').disabled=!(setup.datasets||[]).length;}
async function action(kind){document.querySelectorAll('button').forEach(button=>button.disabled=true);status.textContent='正在备份和校验，请勿关闭程序…';
try{const response=await fetch('/api/save-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,token:setup.token,action:kind,dataset_id:document.getElementById('datasets').value,source_root:document.getElementById('legacySource').value})});
const result=await response.json();if(!response.ok)throw Error(result.error);status.textContent='存档已就绪，正在启动…';
for(let attempt=0;attempt<60;attempt++){await new Promise(resolve=>setTimeout(resolve,1000));try{if((await fetch('/api/state')).ok){location.reload();return}}catch{}}
status.textContent='请刷新页面查看程序，或检查控制台。';}catch(error){status.textContent=error.message;await load();}}
document.getElementById('migrate').onclick=()=>action('migrate');document.getElementById('select').onclick=()=>action('select');load().catch(error=>status.textContent=error.message);
document.getElementById('legacySource').onchange=()=>document.getElementById('migrate').disabled=!document.getElementById('legacySource').value;
document.getElementById('createEmpty').onclick=()=>{if(confirm('创建新的空白存档？已发现的所有旧存档会保留，可稍后分别导入。'))action('create-empty')};
</script></html>"""


def run_save_setup(root, lock, initial_status, *, bind, port=None, no_browser=False, source_root=None):
    token = str(uuid.uuid4())
    operation_lock = threading.Lock()
    prepared = []

    class SetupHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                self.send_body(200, SETUP_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/save-setup":
                self.send_body(200, json.dumps({**initial_status.public_data(), "token": token}).encode(), "application/json")
            else:
                self.send_body(404, b"{}", "application/json")

        def do_POST(self):
            try:
                if urlparse(self.path).path != "/api/save-setup":
                    raise ValueError("未知请求。")
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).netloc.casefold() != self.headers.get("Host", "").casefold():
                    raise ValueError("跨站请求已拒绝。")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("确认请求无效。")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or payload.get("confirmed") is not True or payload.get("token") != token:
                    raise ValueError("需要明确确认。")
                with operation_lock:
                    if prepared:
                        raise ValueError("存档正在启动，请稍后刷新。")
                    if payload.get("action") == "migrate":
                        selected_source = source_root
                        if initial_status.legacy_roots:
                            available = {entry["path"] for entry in initial_status.legacy_roots if entry["available"]}
                            if payload.get("source_root") not in available:
                                raise ValueError("请明确选择一份可迁移的旧存档；不会自动合并。")
                            selected_source = payload["source_root"]
                        result = prepare_runtime(root, migrate=True, source_root=selected_source, lock=lock)
                    elif payload.get("action") == "create-empty" and initial_status.legacy_roots:
                        result = prepare_runtime(root, lock=lock)
                    elif payload.get("action") == "select":
                        select_dataset(root, payload.get("dataset_id"), lock=lock)
                        result = prepare_runtime(root, lock=lock)
                    else:
                        raise ValueError("未知迁移操作。")
                    if result.status != "ready":
                        raise ValueError("存档未就绪；原数据保留。")
                    prepared.append(result)
                self.send_body(200, b'{"status":"ready"}', "application/json")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            except (ValueError, SaveDataError, OSError) as error:
                self.send_body(409, json.dumps({"error": str(error)}, ensure_ascii=False).encode(), "application/json")

    server = bind(None, SetupHandler, port=port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"旧存档需要明确确认：{url}", flush=True)
    if not no_browser:
        webbrowser.open(url, new=2)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return None, server.server_port
    finally:
        server.server_close()
    return (prepared[0] if prepared else None), server.server_port
