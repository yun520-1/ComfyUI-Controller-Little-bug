#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能网页控制器 - 完全优化版
- 自动检测 ComfyUI 可用模型
- 支持图片/视频模式
- 自定义提示词
- 多种尺寸选择
- 模型选择
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

class ComfyUIManager:
    def __init__(self):
        self.base_url = f"http://{COMFYUI_SERVER}"
        self.client_id = str(uuid.uuid4())
        self.available_models = {"unet": [], "clip": [], "vae": [], "checkpoints": []}
        self.scan_models()

    def scan_models(self):
        try:
            resp = requests.get(f"{self.base_url}/object_info", timeout=10)
            if resp.status_code == 200:
                info = resp.json()
                if "UnetLoaderGGUF" in info:
                    self.available_models["unet"] = info["UnetLoaderGGUF"]["input"]["required"]["unet_name"][0]
                if "CLIPLoader" in info:
                    self.available_models["clip"] = info["CLIPLoader"]["input"]["required"]["clip_name"][0]
                if "VAELoader" in info:
                    self.available_models["vae"] = info["VAELoader"]["input"]["required"]["vae_name"][0]
                if "CheckpointLoaderSimple" in info:
                    ckpts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
                    if ckpts:
                        self.available_models["checkpoints"] = ckpts
                print(f"✅ 扫描到 {len(self.available_models['unet'])} UNet, {len(self.available_models['clip'])} CLIP, {len(self.available_models['vae'])} VAE")
        except Exception as e:
            print(f"❌ 扫描失败：{e}")

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

manager = ComfyUIManager()

PRESET_PROMPTS = {
    "funny": "funny cartoon style, humor, exaggerated expressions, bright colors",
    "portrait": "portrait photography, professional lighting, bokeh, high quality",
    "landscape": "beautiful landscape, nature, mountains, golden hour",
    "anime": "anime style, Japanese animation, colorful, detailed",
    "cyberpunk": "cyberpunk city, neon lights, futuristic, night scene",
    "fantasy": "fantasy world, magic, dragon, castle, epic",
    "scifi": "science fiction, spaceship, alien planet",
    "news": "news illustration, professional, high quality"
}

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>ComfyUI 智能控制器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}
.container{max-width:1100px;margin:0 auto}
h1{color:white;text-align:center;margin-bottom:30px}
.card{background:white;border-radius:15px;padding:25px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
h2{color:#667eea;margin-bottom:15px;font-size:1.3em}
.status-bar{display:flex;justify-content:space-around;background:#f0f4f8;padding:15px;border-radius:10px;margin-bottom:20px;flex-wrap:wrap}
.status-item{text-align:center;padding:10px}
.status-label{color:#666;font-size:0.9em}
.status-value{font-size:1.5em;font-weight:bold;color:#333}
.status-value.idle{color:#27ae60}.status-value.busy{color:#e74c3c}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin-bottom:20px}
.form-group{margin-bottom:15px}
label{display:block;margin-bottom:5px;color:#333;font-weight:500}
input,select,textarea{width:100%;padding:10px;border:2px solid #e0e0e0;border-radius:8px;font-size:1em}
input:focus,select:focus,textarea:focus{outline:none;border-color:#667eea}
textarea{min-height:80px;resize:vertical}
.row{display:flex;gap:10px}.row>.form-group{flex:1}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:15px 30px;border-radius:8px;font-size:1.1em;cursor:pointer;width:100%}
.btn:hover{opacity:0.9}.btn:disabled{opacity:0.5;cursor:not-allowed}
.queue-list{list-style:none}
.queue-item{background:#f8f9fa;padding:15px;margin-bottom:10px;border-radius:8px;border-left:4px solid #667eea;display:flex;justify-content:space-between;align-items:center}
.queue-item.completed{border-left-color:#27ae60}.queue-item.failed{border-left-color:#e74c3c}
.log-area{background:#1e1e1e;color:#d4d4d4;padding:15px;border-radius:8px;font-family:monospace;font-size:0.85em;max-height:200px;overflow-y:auto}
.log-line{margin-bottom:3px}.log-info{color:#6a9955}.log-success{color:#569cd6}.log-error{color:#f44747}
</style></head><body>
<div class="container">
<h1>🎨 ComfyUI 智能控制器</h1>
<div class="card"><div class="status-bar">
<div class="status-item"><div class="status-label">ComfyUI</div><div class="status-value idle" id="comfyui">检查中</div></div>
<div class="status-item"><div class="status-label">运行中</div><div class="status-value idle" id="running">0</div></div>
<div class="status-item"><div class="status-label">排队</div><div class="status-value" id="pending">0</div></div>
<div class="status-item"><div class="status-label">已完成</div><div class="status-value" id="completed">0</div></div>
</div></div>
<div class="grid">
<div class="card"><h2>📝 基础配置</h2>
<div class="form-group"><label>生成模式</label><select id="mode"><option value="image">🖼️ 图片生成</option><option value="video">🎬 视频生成</option></select></div>
<div class="form-group"><label>选择模型</label><select id="model"></select></div>
<div class="row"><div class="form-group"><label>尺寸</label><select id="size"><option value="1024x512">1024x512</option><option value="512x512">512x512</option><option value="768x768">768x768</option><option value="1024x1024">1024x1024</option><option value="1280x720">1280x720</option></select></div>
<div class="form-group"><label>数量</label><input type="number" id="count" min="1" max="10" value="3"></div></div>
<div class="form-group"><label>任务间隔 (秒)</label><input type="number" id="interval" min="0" max="300" value="60"></div>
</div>
<div class="card"><h2>🎨 提示词配置</h2>
<div class="form-group"><label>快速选择</label><select id="preset" onchange="updatePrompt()"><option value="">-- 选择预设 --</option><option value="funny">搞笑幽默</option><option value="portrait">人像写真</option><option value="landscape">风景自然</option><option value="anime">动漫二次元</option><option value="cyberpunk">赛博朋克</option><option value="fantasy">奇幻魔法</option><option value="scifi">科幻太空</option><option value="news">新闻配图</option></select></div>
<div class="form-group"><label>自定义提示词</label><textarea id="prompt" placeholder="输入自定义提示词，或从上方选择预设..."></textarea></div>
<div class="form-group"><label>负面提示词</label><textarea id="negative" placeholder="不想要的内容...">blurry, low quality, ugly, duplicate</textarea></div>
<div class="form-group"><label>附加要求 (可选)</label><textarea id="extra" placeholder="例如：阳光、海滩、女孩、微笑..."></textarea></div>
</div>
</div>
<div class="card"><button type="button" class="btn" id="btn" onclick="start()">🚀 开始生成</button></div>
<div class="card"><h2>📋 任务队列</h2><ul class="queue-list" id="queue"><li class="queue-item"><span>暂无任务</span></li></ul></div>
<div class="card"><h2>📊 运行日志</h2><div class="log-area" id="log"><div class="log-line log-info">等待启动...</div></div></div>
</div>
<script>
let running=false,tasks=[],models=[];
const PRESETS={funny:"funny cartoon style, humor, exaggerated",portrait:"portrait photography, professional lighting",landscape:"beautiful landscape, nature, mountains",anime:"anime style, Japanese animation, colorful",cyberpunk:"cyberpunk city, neon lights, futuristic",fantasy:"fantasy world, magic, dragon",scifi:"science fiction, spaceship, alien",news:"news illustration, professional"};
function updatePrompt(){const p=document.getElementById('preset').value;if(p&&PRESETS[p])document.getElementById('prompt').value=PRESETS[p];}
async function update(){try{const r=await fetch('/api/status'),d=await r.json();
document.getElementById('comfyui').textContent=d.comfyui_ok?'在线':'离线';document.getElementById('comfyui').className='status-value '+(d.comfyui_ok?'idle':'busy');
document.getElementById('running').textContent=d.running||0;document.getElementById('running').className='status-value '+(d.running>0?'busy':'idle');
document.getElementById('pending').textContent=d.pending||0;document.getElementById('completed').textContent=d.completed||0;
if(d.models&&!models.length){models=d.models;document.getElementById('model').innerHTML=models.map(x=>'<option value="'+x+'">'+x+'</option>').join('');}
if(d.tasks){tasks=d.tasks;updateQueue();}}catch(e){console.error(e)}}
function updateQueue(){const q=document.getElementById('queue');if(tasks.length===0){q.innerHTML='<li class="queue-item"><span>暂无任务</span></li>';return;}
q.innerHTML=tasks.map((t,i)=>'<li class="queue-item '+t.status+'"><span>'+(i+1)+'. '+t.title+'</span><span>'+(t.status==='pending'?'⏳等待':t.status==='running'?'▶️运行':t.status==='completed'?'✅完成':'❌失败')+'</span></li>').join('');}
function log(m,t){const l=document.getElementById('log'),d=document.createElement('div');d.className='log-line log-'+t;d.textContent='['+new Date().toLocaleTimeString()+'] '+m;l.appendChild(d);l.scrollTop=l.scrollHeight;}
async function start(){if(running)return;
const data={mode:document.getElementById('mode').value,model:document.getElementById('model').value,size:document.getElementById('size').value,count:+document.getElementById('count').value,interval:+document.getElementById('interval').value,prompt:document.getElementById('prompt').value,negative:document.getElementById('negative').value,extra:document.getElementById('extra').value};
if(!data.prompt){log('请输入提示词','error');return;}
running=true;document.getElementById('btn').disabled=true;document.getElementById('btn').textContent='⏳ 生成中...';
log('开始：'+data.count+' 张 '+data.mode,'info');
try{const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),res=await r.json();
if(res.success){tasks=res.tasks;updateQueue();log('已创建 '+tasks.length+' 个任务','success');
const poll=setInterval(async()=>{await update();if(!controller_running){clearInterval(poll);running=false;document.getElementById('btn').disabled=false;document.getElementById('btn').textContent='🚀 开始生成';log('所有任务完成','success');}},2000);}
else{log('失败：'+res.error,'error');running=false;document.getElementById('btn').disabled=false;}}
catch(e){log('错误：'+e.message,'error');running=false;document.getElementById('btn').disabled=false;}}
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
            q = manager.get_queue()
            self.send_json({'comfyui_ok': True, 'running': len(q.get('queue_running', [])), 'pending': len(q.get('queue_pending', [])), 'completed': sum(1 for t in controller.tasks if t.get('status') == 'completed'), 'controller_running': controller.is_running, 'models': manager.available_models.get('unet', []), 'tasks': controller.tasks})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/start':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length).decode())
            w, h = map(int, data.get('size', '1024x512').split('x'))
            prompt = f"{data.get('prompt', '')}, {data.get('extra', '')}".strip()
            negative = data.get('negative', 'blurry, low quality')
            model = data.get('model', manager.available_models['unet'][0] if manager.available_models['unet'] else 'z_image_turbo-Q8_0.gguf')
            clip = manager.available_models['clip'][0] if manager.available_models['clip'] else 'ltx-2-19b-dev_embeddings_connectors.safetensors'
            vae = manager.available_models['vae'][0] if manager.available_models['vae'] else 'ae.safetensors'

            controller.tasks = []
            for i in range(data['count']):
                wf = {
                    "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": model}},
                    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "sd1x"}},
                    "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
                    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
                    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
                    "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": h, "width": w}},
                    "7": {"class_type": "KSampler", "inputs": {"cfg": 7, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0], "negative": ["5", 0], "positive": ["4", 0], "sampler_name": "euler_ancestral", "scheduler": "normal", "seed": int(time.time()*1000)%1000000+i, "steps": 25}},
                    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
                    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}}
                }
                controller.tasks.append({"id": str(uuid.uuid4()), "title": f"{data['mode']}_{i+1}", "prompt": prompt, "workflow": wf, "status": "pending", "mode": data.get('mode', 'image')})

            self.send_json({'success': True, 'tasks': controller.tasks})
            threading.Thread(target=run_tasks, args=(data.get('interval', 60),), daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, d):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())

    def log_message(self, fmt, *args): pass

class Controller:
    def __init__(self):
        self.tasks = []
        self.is_running = False

controller = Controller()

def run_tasks(interval):
    controller.is_running = True
    for i, task in enumerate(controller.tasks):
        task['status'] = 'running'
        print(f"[{i+1}/{len(controller.tasks)}] {task['title']}")
        while manager.is_busy():
            time.sleep(2)
        try:
            resp = requests.post(f"http://{COMFYUI_SERVER}/prompt", json={"prompt": task['workflow'], "client_id": manager.client_id}, timeout=30)
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
        if i < len(controller.tasks) - 1:
            print(f"  ⏳ 等待 {interval}秒...")
            time.sleep(interval)
    controller.is_running = False
    print("\n✅ 所有任务完成")

def main():
    print("="*60)
    print("🎨 ComfyUI 智能网页控制器 - 完全优化版")
    print("="*60)
    print(f"\n✅ ComfyUI: {COMFYUI_SERVER}")
    print(f"📦 可用模型：{len(manager.available_models['unet'])} UNet, {len(manager.available_models['clip'])} CLIP")
    print(f"🌐 访问：http://127.0.0.1:{CONTROLLER_PORT}")
    print(f"\n按 Ctrl+C 停止\n")
    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://127.0.0.1:{CONTROLLER_PORT}")), daemon=True).start()
    server = HTTPServer(('127.0.0.1', CONTROLLER_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⚠️  停止")

if __name__ == "__main__":
    main()
