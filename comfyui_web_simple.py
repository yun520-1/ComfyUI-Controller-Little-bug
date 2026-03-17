#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 网页控制器 - 简化稳定版
"""

import json, uuid, time, requests, sys, webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

COMFYUI_SERVER = "127.0.0.1:8188"
CONTROLLER_PORT = 8189
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class Controller:
    def __init__(self):
        self.base_url = f"http://{COMFYUI_SERVER}"
        self.client_id = str(uuid.uuid4())
        self.tasks = []
        self.is_running = False
        
    def get_queue(self):
        try:
            resp = requests.get(f"{self.base_url}/queue", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except: pass
        return {"queue_running": [], "queue_pending": []}
    
    def is_busy(self):
        q = self.get_queue()
        return len(q.get("queue_running", [])) > 0 or len(q.get("queue_pending", [])) > 0

controller = Controller()

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>ComfyUI 控制器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}
.container{max-width:900px;margin:0 auto}
h1{color:white;text-align:center;margin-bottom:30px}
.card{background:white;border-radius:15px;padding:25px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
.status-bar{display:flex;justify-content:space-around;background:#f0f4f8;padding:15px;border-radius:10px;margin-bottom:20px}
.status-item{text-align:center}
.status-label{color:#666;font-size:0.9em}
.status-value{font-size:1.5em;font-weight:bold;color:#333}
.status-value.idle{color:#27ae60}.status-value.busy{color:#e74c3c}
.form-group{margin-bottom:20px}
label{display:block;margin-bottom:8px;color:#333;font-weight:500}
input,select{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px;font-size:1em}
input:focus,select:focus{outline:none;border-color:#667eea}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:15px 30px;border-radius:8px;font-size:1.1em;cursor:pointer;width:100%}
.btn:hover{opacity:0.9}.btn:disabled{opacity:0.5;cursor:not-allowed}
.queue-list{list-style:none}
.queue-item{background:#f8f9fa;padding:15px;margin-bottom:10px;border-radius:8px;border-left:4px solid #667eea;display:flex;justify-content:space-between;align-items:center}
.queue-item.completed{border-left-color:#27ae60}.queue-item.failed{border-left-color:#e74c3c}
.log-area{background:#1e1e1e;color:#d4d4d4;padding:15px;border-radius:8px;font-family:monospace;font-size:0.9em;max-height:200px;overflow-y:auto}
.log-line{margin-bottom:5px}.log-info{color:#6a9955}.log-success{color:#569cd6}.log-error{color:#f44747}
</style></head><body>
<div class="container">
<h1>🎨 ComfyUI 智能控制器</h1>
<div class="card">
<div class="status-bar">
<div class="status-item"><div class="status-label">ComfyUI</div><div class="status-value idle" id="comfyui-status">检查中</div></div>
<div class="status-item"><div class="status-label">运行中</div><div class="status-value idle" id="running">0</div></div>
<div class="status-item"><div class="status-label">排队</div><div class="status-value" id="pending">0</div></div>
<div class="status-item"><div class="status-label">已完成</div><div class="status-value" id="completed">0</div></div>
</div>
</div>
<div class="card">
<h2 style="color:#667eea;margin-bottom:15px">📝 任务配置</h2>
<form id="form">
<div class="form-group"><label>生成类型</label>
<select id="type"><option value="funny">搞笑幽默</option><option value="portrait">人像写真</option><option value="landscape">风景自然</option><option value="anime">动漫二次元</option><option value="cyberpunk">赛博朋克</option><option value="fantasy">奇幻魔法</option><option value="scifi">科幻太空</option><option value="news">新闻配图</option></select></div>
<div class="form-group"><label>生成数量</label><input type="number" id="count" min="1" max="10" value="3"></div>
<div class="form-group"><label>任务间隔 (秒)</label><input type="number" id="interval" min="0" max="300" value="60"></div>
<button type="submit" class="btn" id="btn">🚀 开始生成</button>
</form>
</div>
<div class="card">
<h2 style="color:#667eea;margin-bottom:15px">📋 任务队列</h2>
<ul class="queue-list" id="queue"><li class="queue-item"><span>暂无任务</span></li></ul>
</div>
<div class="card">
<h2 style="color:#667eea;margin-bottom:15px">📊 日志</h2>
<div class="log-area" id="log"><div class="log-line log-info">等待启动...</div></div>
</div>
</div>
<script>
let running=false,tasks=[];
async function update(){try{
const r=await fetch('/api/status'),d=await r.json();
document.getElementById('comfyui-status').textContent=d.comfyui_ok?'在线':'离线';
document.getElementById('comfyui-status').className='status-value '+(d.comfyui_ok?'idle':'busy');
document.getElementById('running').textContent=d.running;
document.getElementById('running').className='status-value '+(d.running>0?'busy':'idle');
document.getElementById('pending').textContent=d.pending;
document.getElementById('completed').textContent=d.completed;
if(d.tasks){tasks=d.tasks;updateQueue();}
}catch(e){console.error(e)}}
function updateQueue(){const q=document.getElementById('queue');
if(tasks.length===0){q.innerHTML='<li class="queue-item"><span>暂无任务</span></li>';return;}
q.innerHTML=tasks.map((t,i)=>`<li class="queue-item ${t.status}"><span>${i+1}. ${t.title}</span><span>${t.status==='pending'?'等待':t.status==='running'?'运行':t.status==='completed'?'✅完成':'❌失败'}</span></li>`).join('');}
function log(m,t='info'){const l=document.getElementById('log'),d=document.createElement('div');
d.className='log-line log-'+t;d.textContent='['+new Date().toLocaleTimeString()+'] '+m;l.appendChild(d);l.scrollTop=l.scrollHeight;}
document.getElementById('form').onsubmit=async(e)=>{e.preventDefault();if(running)return;
const data={type:document.getElementById('type').value,count:+document.getElementById('count').value,interval:+document.getElementById('interval').value};
running=true;document.getElementById('btn').disabled=true;document.getElementById('btn').textContent='⏳ 生成中...';
log(`开始生成：${data.count} 张 ${data.type}`,'info');
try{const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),res=await r.json();
if(res.success){tasks=res.tasks;updateQueue();log(`已创建 ${tasks.length} 个任务`,'success');
const poll=setInterval(async()=>{await update();if(!controller_running){clearInterval(poll);running=false;document.getElementById('btn').disabled=false;document.getElementById('btn').textContent='🚀 开始生成';log('所有任务完成','success');}},2000);}
else{log('启动失败：'+res.error,'error');running=false;document.getElementById('btn').disabled=false;}}
catch(e){log('错误：'+e.message,'error');running=false;document.getElementById('btn').disabled=false;}};
update();setInterval(update,3000);
</script></body></html>"""

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/api/status':
            q = controller.get_queue()
            self.send_json({
                'comfyui_ok': True,
                'running': len(q.get('queue_running', [])),
                'pending': len(q.get('queue_pending', [])),
                'completed': sum(1 for t in controller.tasks if t.get('status') == 'completed'),
                'controller_running': controller.is_running,
                'tasks': controller.tasks
            })
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/start':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length).decode())
            
            prompts = {"funny":"funny cartoon","portrait":"portrait photography","landscape":"beautiful landscape","anime":"anime style","cyberpunk":"cyberpunk city","fantasy":"fantasy world","scifi":"science fiction","news":"news illustration"}
            base = prompts.get(data['type'], prompts['funny'])
            
            controller.tasks = []
            for i in range(data['count']):
                wf = {"1":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":"z_image_turbo-Q8_0.gguf"}},"2":{"class_type":"CLIPLoader","inputs":{"clip_name":"ltx-2-19b-dev_embeddings_connectors.safetensors","type":"sd1x"}},"3":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},"4":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":f"{base} #{i+1}"}},"5":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":"blurry"}},"6":{"class_type":"EmptyLatentImage","inputs":{"batch_size":1,"height":512,"width":1024}},"7":{"class_type":"KSampler","inputs":{"cfg":7,"denoise":1,"latent_image":["6",0],"model":["1",0],"negative":["5",0],"positive":["4",0],"sampler_name":"euler_ancestral","scheduler":"normal","seed":int(time.time()*1000)%1000000+i,"steps":25}},"8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},"9":{"class_type":"SaveImage","inputs":{"filename_prefix":"ComfyUI","images":["8",0]}}}
                controller.tasks.append({"id":str(uuid.uuid4()),"title":f"{data['type']}_{i+1}","prompt":base,"workflow":wf,"status":"pending"})
            
            self.send_json({'success':True,'tasks':controller.tasks})
            threading.Thread(target=run_tasks,args=(data.get('interval',60),),daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()
    
    def send_json(self,d):
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    
    def log_message(self,fmt,*args):pass

def run_tasks(interval):
    controller.is_running = True
    for i,task in enumerate(controller.tasks):
        task['status'] = 'running'
        print(f"[{i+1}/{len(controller.tasks)}] {task['title']}")
        
        # 等待空闲
        while controller.is_busy():
            time.sleep(2)
        
        # 提交
        try:
            resp = requests.post(f"http://{COMFYUI_SERVER}/prompt",json={"prompt":task['workflow'],"client_id":controller.client_id},timeout=30)
            if resp.status_code == 200:
                pid = resp.json().get('prompt_id')
                print(f"  ✅ 已提交：{pid}")
                task['status'] = 'completed'
            else:
                print(f"  ❌ 失败：{resp.status_code}")
                task['status'] = 'failed'
        except Exception as e:
            print(f"  ❌ 错误：{e}")
            task['status'] = 'failed'
        
        # 间隔
        if i < len(controller.tasks) - 1:
            print(f"  ⏳ 等待 {interval}秒...")
            time.sleep(interval)
    
    controller.is_running = False
    print("\n✅ 所有任务完成")

def main():
    print("="*60)
    print("🎨 ComfyUI 网页控制器")
    print("="*60)
    print(f"\n✅ ComfyUI: {COMFYUI_SERVER}")
    print(f"🌐 访问：http://127.0.0.1:{CONTROLLER_PORT}")
    print(f"\n按 Ctrl+C 停止\n")
    
    # 打开浏览器
    threading.Thread(target=lambda:(time.sleep(1),webbrowser.open(f"http://127.0.0.1:{CONTROLLER_PORT}")),daemon=True).start()
    
    # 运行服务器
    server = HTTPServer(('127.0.0.1', CONTROLLER_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⚠️  停止")

if __name__ == "__main__":
    main()
