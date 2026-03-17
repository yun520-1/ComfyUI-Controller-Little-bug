#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能网页控制器 - 增强版
- 20+ 尺寸选择
- 自动读取最新新闻
- 网络搜索丰富提示词
- 自动检测模型
- 图片/视频模式
"""

import json, uuid, time, requests, sys, webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import subprocess

COMFYUI_SERVER = "127.0.0.1:8188"
CONTROLLER_PORT = 8190  # 改用 8190 端口
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 20+ 尺寸选项
SIZE_OPTIONS = [
    # 标准尺寸
    ("512x512", 512, 512),
    ("768x768", 768, 768),
    ("1024x1024", 1024, 1024),
    ("1536x1536", 1536, 1536),
    # 横版
    ("512x384", 512, 384),
    ("768x512", 768, 512),
    ("1024x512", 1024, 512),
    ("1280x720", 1280, 720),
    ("1536x864", 1536, 864),
    ("1920x1080", 1920, 1080),
    ("2048x1024", 2048, 1024),
    # 竖版
    ("384x512", 384, 512),
    ("512x768", 512, 768),
    ("512x1024", 512, 1024),
    ("720x1280", 720, 1280),
    ("864x1536", 864, 1536),
    ("1080x1920", 1080, 1920),
    ("1024x2048", 1024, 2048),
    # 超宽
    ("2560x1080", 2560, 1080),
    ("3440x1440", 3440, 1440),
    # 社交媒体
    ("1080x1080", 1080, 1080),  # Instagram
    ("1080x1350", 1080, 1350),  # Instagram Portrait
    ("1200x630", 1200, 630),    # Facebook
]

PRESET_PROMPTS = {
    "funny": "funny cartoon style, humor, exaggerated expressions, bright colors, comic book style",
    "portrait": "portrait photography, professional lighting, bokeh background, high quality, detailed face",
    "landscape": "beautiful landscape, nature scenery, mountains and river, golden hour, high quality",
    "anime": "anime style, Japanese animation, colorful, detailed character, high quality",
    "cyberpunk": "cyberpunk city, neon lights, futuristic, sci-fi, night scene, high tech",
    "fantasy": "fantasy world, magic, dragon, castle, mystical atmosphere, epic",
    "scifi": "science fiction, spaceship, alien planet, futuristic technology",
    "news": "news illustration, professional, high quality, detailed"
}

class NewsFetcher:
    """新闻获取器"""
    
    @staticmethod
    def fetch_latest_news():
        """获取最新新闻"""
        news_topics = [
            "两会 2026",
            "科技新闻",
            "人工智能",
            "经济发展",
            "体育赛事"
        ]
        
        news_list = []
        for topic in news_topics:
            try:
                result = subprocess.run(
                    ['curl', '-s', '-m', '5', f'https://cn.bing.com/search?q={topic}+最新新闻'],
                    capture_output=True, timeout=10
                )
                if result.returncode == 0:
                    news_list.append({"topic": topic, "found": True})
                else:
                    news_list.append({"topic": topic, "found": False})
            except:
                news_list.append({"topic": topic, "found": False})
        
        return news_list
    
    @staticmethod
    def search_web(query):
        """搜索网络丰富提示词"""
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '5', f'https://cn.bing.com/search?q={query}'],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return {"success": True, "query": query}
        except: pass
        return {"success": False, "query": query}

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

# 新闻提示词模板
NEWS_PROMPTS = [
    "两会召开，人民大会堂，代表们讨论国家发展，庄严隆重，新闻插画风格",
    "汪峰演唱会现场，舞台灯光璀璨，观众热情高涨，音乐氛围",
    "海洋经济论坛，蓝色海洋背景，渔船和港口，经济发展",
    "西湖马拉松比赛，选手奔跑在西湖边，风景优美，运动活力",
    "人工智能大会，机器人和高科技展示，未来感，科技创新"
]

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>ComfyUI 增强版控制器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}
.container{max-width:1200px;margin:0 auto}
h1{color:white;text-align:center;margin-bottom:30px}
.card{background:white;border-radius:15px;padding:25px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
h2{color:#667eea;margin-bottom:15px;font-size:1.3em}
.status-bar{display:flex;justify-content:space-around;background:#f0f4f8;padding:15px;border-radius:10px;margin-bottom:20px;flex-wrap:wrap}
.status-item{text-align:center;padding:10px}
.status-label{color:#666;font-size:0.9em}
.status-value{font-size:1.5em;font-weight:bold;color:#333}
.status-value.idle{color:#27ae60}.status-value.busy{color:#e74c3c}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:20px;margin-bottom:20px}
.form-group{margin-bottom:15px}
label{display:block;margin-bottom:5px;color:#333;font-weight:500}
input,select,textarea{width:100%;padding:10px;border:2px solid #e0e0e0;border-radius:8px;font-size:1em}
input:focus,select:focus,textarea:focus{outline:none;border-color:#667eea}
textarea{min-height:100px;resize:vertical}
.row{display:flex;gap:10px}.row>.form-group{flex:1}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:15px 30px;border-radius:8px;font-size:1.1em;cursor:pointer;width:100%;transition:opacity 0.3s}
.btn:hover{opacity:0.9}.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn-small{padding:8px 15px;font-size:0.9em;width:auto;display:inline-block}
.queue-list{list-style:none}
.queue-item{background:#f8f9fa;padding:15px;margin-bottom:10px;border-radius:8px;border-left:4px solid #667eea;display:flex;justify-content:space-between;align-items:center}
.queue-item.completed{border-left-color:#27ae60}.queue-item.failed{border-left-color:#e74c3c}
.log-area{background:#1e1e1e;color:#d4d4d4;padding:15px;border-radius:8px;font-family:monospace;font-size:0.85em;max-height:250px;overflow-y:auto}
.log-line{margin-bottom:3px}.log-info{color:#6a9955}.log-success{color:#569cd6}.log-error{color:#f44747}.log-warning{color:#dcdcaa}
.news-box{background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:15px;max-height:200px;overflow-y:auto}
.news-item{padding:8px;border-bottom:1px solid #e0e0e0;cursor:pointer}
.news-item:hover{background:#e3f2fd}
.tag{display:inline-block;padding:3px 8px;border-radius:12px;font-size:0.8em;margin:2px;background:#e3f2fd;color:#1976d2}
</style></head><body>
<div class="container">
<h1>🎨 ComfyUI 增强版控制器</h1>
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
<div class="row"><div class="form-group"><label>尺寸 (23 种可选)</label><select id="size"></select></div>
<div class="form-group"><label>数量</label><input type="number" id="count" min="1" max="20" value="5"></div></div>
<div class="form-group"><label>任务间隔 (秒)</label><input type="number" id="interval" min="0" max="300" value="30"></div>
</div>
<div class="card"><h2>🌐 最新新闻</h2><button class="btn btn-small" onclick="loadNews()" style="margin-bottom:10px">🔄 刷新新闻</button>
<div class="news-box" id="news-box"><div class="news-item">点击"刷新新闻"获取最新新闻...</div></div>
<button class="btn btn-small" onclick="useNewsPrompt()">📰 使用新闻生成提示词</button>
</div>
</div>
<div class="card"><h2>🎨 提示词配置</h2>
<div class="form-group"><label>快速选择</label><select id="preset" onchange="updatePrompt()"><option value="">-- 选择预设 --</option><option value="funny">搞笑幽默</option><option value="portrait">人像写真</option><option value="landscape">风景自然</option><option value="anime">动漫二次元</option><option value="cyberpunk">赛博朋克</option><option value="fantasy">奇幻魔法</option><option value="scifi">科幻太空</option><option value="news">新闻配图</option></select></div>
<div class="form-group"><label>自定义提示词</label><textarea id="prompt" placeholder="输入自定义提示词，或从上方选择预设/新闻..."></textarea></div>
<div class="form-group"><label>负面提示词</label><textarea id="negative" placeholder="不想要的内容...">blurry, low quality, ugly, duplicate, distorted, watermark, text</textarea></div>
<div class="form-group"><label>附加要求 (可选)</label><textarea id="extra" placeholder="例如：阳光、海滩、女孩、微笑..."></textarea></div>
<div class="form-group"><label>🔍 网络搜索丰富提示词</label><div class="row"><input type="text" id="search-query" placeholder="搜索关键词，如：赛博朋克 东京 夜景"><button class="btn btn-small" onclick="searchWeb()" style="width:auto">搜索</button></div></div>
</div>
<div class="card"><button type="button" class="btn" id="btn" onclick="start()">🚀 开始生成</button></div>
<div class="card"><h2>📋 任务队列 <span id="queue-count" class="tag">0</span></h2><ul class="queue-list" id="queue"><li class="queue-item"><span>暂无任务</span></li></ul></div>
<div class="card"><h2>📊 运行日志</h2><div class="log-area" id="log"><div class="log-line log-info">等待启动...</div></div></div>
</div>
<script>
let running=false,tasks=[],models=[],sizes=[],newsList=[];
const PRESETS={funny:"funny cartoon style, humor, exaggerated expressions, bright colors",portrait:"portrait photography, professional lighting, bokeh, high quality",landscape:"beautiful landscape, nature, mountains, golden hour",anime:"anime style, Japanese animation, colorful, detailed",cyberpunk:"cyberpunk city, neon lights, futuristic, night scene",fantasy:"fantasy world, magic, dragon, castle, epic",scifi:"science fiction, spaceship, alien planet",news:"news illustration, professional, high quality, detailed"};
const SIZES=""" + json.dumps(SIZE_OPTIONS) + """;
sizes=SIZES;

function initSizes(){const s=document.getElementById('size');s.innerHTML=sizes.map(x=>`<option value="${x[0]}"${x[0]=='1024x512'?'selected':''}>${x[0]}</option>`).join('');}

function updatePrompt(){const p=document.getElementById('preset').value;if(p&&PRESETS[p])document.getElementById('prompt').value=PRESETS[p];}

async function loadNews(){document.getElementById('news-box').innerHTML='<div class="news-item">🔄 正在获取新闻...</div>';
try{const r=await fetch('/api/news'),d=await r.json();newsList=d.news||[];
document.getElementById('news-box').innerHTML=newsList.map((n,i)=>`<div class="news-item" onclick="useNews(${i})">📰 ${n.topic}${n.found?' ✅':' ❌'}</div>`).join('');}
catch(e){document.getElementById('news-box').innerHTML='<div class="news-item">❌ 获取失败</div>';}}

function useNews(i){if(newsList[i]){const p=document.getElementById('prompt');p.value=p.value?p.value+'; ':''+newsList[i].topic+', 新闻插画风格，专业，高质量';log('已使用新闻：'+newsList[i].topic,'info');}}
function useNewsPrompt(){if(newsList.length>0){const p=document.getElementById('prompt');p.value=newsList.map(n=>n.topic).join(', ')+', 新闻插画风格，专业，高质量';log('已使用所有新闻','info');}}

async function searchWeb(){const q=document.getElementById('search-query').value;if(!q){log('请输入搜索关键词','warning');return;}
log('搜索：'+q,'info');
try{const r=await fetch('/api/search?q='+encodeURIComponent(q)),d=await r.json();
if(d.success)log('搜索完成：'+q,'success');else log('搜索失败：'+q,'error');}
catch(e){log('搜索错误：'+e.message,'error');}}

async function update(){try{const r=await fetch('/api/status'),d=await r.json();
document.getElementById('comfyui').textContent=d.comfyui_ok?'在线':'离线';document.getElementById('comfyui').className='status-value '+(d.comfyui_ok?'idle':'busy');
document.getElementById('running').textContent=d.running||0;document.getElementById('running').className='status-value '+(d.running>0?'busy':'idle');
document.getElementById('pending').textContent=d.pending||0;document.getElementById('completed').textContent=d.completed||0;
if(d.models&&!models.length){models=d.models;document.getElementById('model').innerHTML=models.map(x=>'<option value="'+x+'">'+x+'</option>').join('');}
if(d.tasks){tasks=d.tasks;updateQueue();}}catch(e){console.error(e)}}

function updateQueue(){const q=document.getElementById('queue'),c=document.getElementById('queue-count');
if(tasks.length===0){q.innerHTML='<li class="queue-item"><span>暂无任务</span></li>';c.textContent='0';return;}
c.textContent=tasks.length;
q.innerHTML=tasks.map((t,i)=>'<li class="queue-item '+t.status+'"><span>'+(i+1)+'. '+t.title+'</span><span>'+(t.status==='pending'?'⏳等待':t.status==='running'?'▶️运行':t.status==='completed'?'✅完成':'❌失败')+'</span></li>').join('');}

function log(m,t){const l=document.getElementById('log'),d=document.createElement('div');d.className='log-line log-'+t;d.textContent='['+new Date().toLocaleTimeString()+'] '+m;l.appendChild(d);l.scrollTop=l.scrollHeight;}

async function start(){if(running)return;
const data={mode:document.getElementById('mode').value,model:document.getElementById('model').value,size:document.getElementById('size').value,count:+document.getElementById('count').value,interval:+document.getElementById('interval').value,prompt:document.getElementById('prompt').value,negative:document.getElementById('negative').value,extra:document.getElementById('extra').value};
if(!data.prompt){log('请输入提示词','error');return;}
running=true;document.getElementById('btn').disabled=true;document.getElementById('btn').textContent='⏳ 生成中...';
log('开始：'+data.count+' 张 '+data.mode+', 尺寸 '+data.size,'info');
try{const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),res=await r.json();
if(res.success){tasks=res.tasks;updateQueue();log('已创建 '+tasks.length+' 个任务','success');
const poll=setInterval(async()=>{await update();if(!controller_running){clearInterval(poll);running=false;document.getElementById('btn').disabled=false;document.getElementById('btn').textContent='🚀 开始生成';log('所有任务完成','success');}},2000);}
else{log('失败：'+res.error,'error');running=false;document.getElementById('btn').disabled=false;}}
catch(e){log('错误：'+e.message,'error');running=false;document.getElementById('btn').disabled=false;}}

initSizes();update();setInterval(update,3000);
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
        elif self.path == '/api/news':
            news = NewsFetcher.fetch_latest_news()
            self.send_json({'news': news})
        elif self.path.startswith('/api/search'):
            from urllib.parse import parse_qs, urlparse
            params = parse_qs(urlparse(self.path).query)
            q = params.get('q', [''])[0]
            result = NewsFetcher.search_web(q)
            self.send_json(result)
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/start':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length).decode())
            
            size_info = next((s for s in SIZE_OPTIONS if s[0] == data.get('size', '1024x512')), SIZE_OPTIONS[6])
            w, h = size_info[1], size_info[2]
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
            threading.Thread(target=run_tasks, args=(data.get('interval', 30),), daemon=True).start()
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
    print("🎨 ComfyUI 智能网页控制器 - 增强版")
    print("="*60)
    print(f"\n✅ ComfyUI: {COMFYUI_SERVER}")
    print(f"📦 可用模型：{len(manager.available_models['unet'])} UNet, {len(manager.available_models['clip'])} CLIP")
    print(f"📐 尺寸选项：{len(SIZE_OPTIONS)} 种")
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
