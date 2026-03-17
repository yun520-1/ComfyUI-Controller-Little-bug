#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 网页版智能控制器
- 实时读取 ComfyUI 任务队列
- 自动排队等待
- 任务间隔 1 分钟
- 浏览器打开即可使用
"""

import json, uuid, time, requests, websocket, sys, webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import urllib.parse

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
CONTROLLER_PORT = 8189  # 网页控制器端口
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 任务间隔（秒）
TASK_INTERVAL = 60


class ComfyUIMonitor:
    """ComfyUI 任务监控器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        
    def get_queue(self) -> Dict:
        """获取当前队列"""
        try:
            resp = requests.get(f"{self.base_url}/queue", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except: pass
        return {"queue_running": [], "queue_pending": []}
    
    def get_history(self, prompt_id: str) -> Dict:
        """获取历史记录"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except: pass
        return {}
    
    def is_busy(self) -> bool:
        """检查是否正在运行任务"""
        queue = self.get_queue()
        running = queue.get("queue_running", [])
        pending = queue.get("queue_pending", [])
        return len(running) > 0 or len(pending) > 0
    
    def wait_for_idle(self, timeout: int = 300, callback=None) -> bool:
        """等待空闲"""
        start = time.time()
        last_status = ""
        
        while time.time() - start < timeout:
            queue = self.get_queue()
            running = len(queue.get("queue_running", []))
            pending = len(queue.get("queue_pending", []))
            
            status = f"运行中：{running} | 排队：{pending}"
            if status != last_status:
                if callback:
                    callback(status, running, pending)
                last_status = status
            
            if running == 0 and pending == 0:
                return True
            
            time.sleep(2)
        
        return False


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.monitor = ComfyUIMonitor(server)
        self.task_queue = []
        self.current_task = None
        self.last_task_time = 0
        
    def add_task(self, task: Dict):
        """添加任务到队列"""
        self.task_queue.append({
            **task,
            "id": str(uuid.uuid4()),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        })
        print(f"✅ 任务已添加：{task.get('title', '未知')}")
    
    def wait_interval(self):
        """等待任务间隔"""
        if self.last_task_time > 0:
            elapsed = time.time() - self.last_task_time
            if elapsed < TASK_INTERVAL:
                wait_time = TASK_INTERVAL - elapsed
                print(f"⏳ 等待任务间隔：{wait_time:.0f}秒")
                time.sleep(wait_time)
    
    def execute_task(self, task: Dict) -> bool:
        """执行单个任务"""
        print(f"\n{'='*70}")
        print(f"🚀 执行任务：{task.get('title', '未知')}")
        print(f"   提示词：{task.get('prompt', '')[:60]}...")
        
        # 等待空闲
        print(f"\n⏳ 等待 ComfyUI 空闲...")
        self.monitor.wait_for_idle(timeout=300, callback=lambda s, r, p: print(f"   {s}", end="\r"))
        print(f"   ✅ ComfyUI 空闲")
        
        # 等待任务间隔
        self.wait_interval()
        
        # 提交任务
        workflow = task.get('workflow')
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=30
            )
            
            if resp.status_code != 200:
                print(f"❌ 提交失败：{resp.status_code}")
                return False
            
            pid = resp.json().get('prompt_id')
            print(f"✅ 已提交 (ID: {pid})")
            
            # 监控进度
            return self.monitor_progress(pid)
            
        except Exception as e:
            print(f"❌ 错误：{e}")
            return False
    
    def monitor_progress(self, prompt_id: str, timeout: int = 300) -> bool:
        """监控进度"""
        try:
            ws = websocket.WebSocket()
            ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            
            print(f"⏳ 生成中...", end=" ", flush=True)
            start = time.time()
            last_pct = -1
            
            while time.time() - start < timeout:
                try:
                    msg = json.loads(ws.recv())
                    if msg.get('type') == 'progress':
                        pct = int(msg['data'].get('value', 0) / msg['data'].get('max', 100) * 100)
                        if pct != last_pct:
                            print(f"{pct}% ", end="", flush=True)
                            last_pct = pct
                    elif msg.get('type') == 'executing' and msg['data'].get('node') is None:
                        print("✅")
                        ws.close()
                        self.last_task_time = time.time()
                        return True
                except: continue
            
            ws.close()
            return False
        except Exception as e:
            print(f"❌ 监控失败：{e}")
            return False
    
    def download_result(self, prompt_id: str, title: str = "") -> List[str]:
        """下载结果"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            history = resp.json().get(prompt_id, {})
            
            outputs = history.get('outputs', {})
            downloaded = []
            
            for node_id, output in outputs.items():
                if 'images' in output:
                    for img in output['images']:
                        filename = img.get('filename')
                        if filename:
                            params = f"?filename={filename}&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}"
                            url = f"{self.base_url}/view{params}"
                            
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filepath = OUTPUT_DIR / f"{ts}_{title.replace(' ', '_') if title else 'image'}.png"
                                
                                with open(filepath, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"  ✅ {filepath.name}")
                                downloaded.append(str(filepath))
            
            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def run_queue(self):
        """运行任务队列"""
        print(f"\n{'='*70}")
        print(f"📋 任务队列：{len(self.task_queue)} 个任务")
        print(f"⏱️  任务间隔：{TASK_INTERVAL}秒")
        print(f"{'='*70}")
        
        for i, task in enumerate(self.task_queue, 1):
            print(f"\n📊 进度：[{i}/{len(self.task_queue)}]")
            
            success = self.execute_task(task)
            task['status'] = 'completed' if success else 'failed'
            
            if success:
                # 下载结果
                files = self.download_result("last", task.get('title', 'task'))
                task['files'] = files
            
            # 更新任务状态
            self.current_task = task
        
        # 汇总
        print(f"\n{'='*70}")
        print(f"📊 任务完成")
        completed = sum(1 for t in self.task_queue if t.get('status') == 'completed')
        print(f"✅ 成功：{completed}/{len(self.task_queue)}")
        print(f"💾 {OUTPUT_DIR}")


# ============ 网页界面 ============

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComfyUI 智能控制器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        .status-bar {
            background: #f0f4f8;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
        }
        .status-item {
            text-align: center;
            padding: 10px 20px;
        }
        .status-label {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .status-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }
        .status-value.busy { color: #e74c3c; }
        .status-value.idle { color: #27ae60; }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea {
            min-height: 100px;
            resize: vertical;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:active {
            transform: translateY(0);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .queue-list {
            list-style: none;
        }
        .queue-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .queue-item.completed { border-left-color: #27ae60; }
        .queue-item.failed { border-left-color: #e74c3c; }
        .queue-item-title {
            font-weight: 600;
            color: #333;
        }
        .queue-item-status {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .status-pending { background: #ffeaa7; color: #d35400; }
        .status-running { background: #74b9ff; color: #0984e3; }
        .status-completed { background: #55efc4; color: #00b894; }
        .status-failed { background: #fab1a0; color: #d63031; }
        .log-area {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            max-height: 300px;
            overflow-y: auto;
        }
        .log-line {
            margin-bottom: 5px;
            padding: 3px 0;
        }
        .log-info { color: #6a9955; }
        .log-success { color: #569cd6; }
        .log-error { color: #f44747; }
        .log-warning { color: #dcdcaa; }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 ComfyUI 智能控制器</h1>
        
        <!-- 状态栏 -->
        <div class="card">
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-label">ComfyUI 状态</div>
                    <div class="status-value" id="comfyui-status">检查中...</div>
                </div>
                <div class="status-item">
                    <div class="status-label">运行中任务</div>
                    <div class="status-value" id="running-count">0</div>
                </div>
                <div class="status-item">
                    <div class="status-label">排队任务</div>
                    <div class="status-value" id="pending-count">0</div>
                </div>
                <div class="status-item">
                    <div class="status-label">已完成</div>
                    <div class="status-value" id="completed-count">0</div>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <!-- 任务配置 -->
            <div class="card">
                <h2>📝 任务配置</h2>
                <form id="task-form">
                    <div class="form-group">
                        <label>生成类型</label>
                        <select id="gen-type">
                            <option value="funny">搞笑幽默</option>
                            <option value="portrait">人像写真</option>
                            <option value="landscape">风景自然</option>
                            <option value="anime">动漫二次元</option>
                            <option value="cyberpunk">赛博朋克</option>
                            <option value="fantasy">奇幻魔法</option>
                            <option value="scifi">科幻太空</option>
                            <option value="news">新闻配图</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>生成数量</label>
                        <input type="number" id="count" min="1" max="10" value="3">
                    </div>
                    
                    <div class="form-group">
                        <label>自定义主题（可选）</label>
                        <textarea id="custom-topic" placeholder="输入自定义主题，留空则使用默认提示词"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>任务间隔（秒）</label>
                        <input type="number" id="interval" min="0" max="300" value="60">
                    </div>
                    
                    <button type="submit" class="btn" id="start-btn">
                        🚀 开始生成
                    </button>
                </form>
            </div>
            
            <!-- 任务队列 -->
            <div class="card">
                <h2>📋 任务队列</h2>
                <ul class="queue-list" id="queue-list">
                    <li class="queue-item">
                        <span class="queue-item-title">暂无任务</span>
                    </li>
                </ul>
                <div class="progress-bar" style="display: none;" id="progress-container">
                    <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                </div>
            </div>
        </div>
        
        <!-- 日志区域 -->
        <div class="card">
            <h2>📊 运行日志</h2>
            <div class="log-area" id="log-area">
                <div class="log-line log-info">等待任务启动...</div>
            </div>
        </div>
    </div>
    
    <script>
        let isRunning = false;
        let taskQueue = [];
        
        // 更新状态
        async function updateStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                
                document.getElementById('comfyui-status').textContent = data.comfyui_connected ? '在线' : '离线';
                document.getElementById('comfyui-status').className = 'status-value ' + (data.comfyui_connected ? 'idle' : 'busy');
                document.getElementById('running-count').textContent = data.running;
                document.getElementById('running-count').className = 'status-value ' + (data.running > 0 ? 'busy' : 'idle');
                document.getElementById('pending-count').textContent = data.pending;
                document.getElementById('completed-count').textContent = data.completed;
            } catch (e) {
                console.error('Status update failed:', e);
            }
        }
        
        // 添加日志
        function addLog(message, type = 'info') {
            const logArea = document.getElementById('log-area');
            const line = document.createElement('div');
            line.className = `log-line log-${type}`;
            const time = new Date().toLocaleTimeString();
            line.textContent = `[${time}] ${message}`;
            logArea.appendChild(line);
            logArea.scrollTop = logArea.scrollHeight;
        }
        
        // 更新队列显示
        function updateQueue() {
            const queueList = document.getElementById('queue-list');
            if (taskQueue.length === 0) {
                queueList.innerHTML = '<li class="queue-item"><span class="queue-item-title">暂无任务</span></li>';
                return;
            }
            
            queueList.innerHTML = taskQueue.map((task, i) => `
                <li class="queue-item ${task.status}">
                    <span class="queue-item-title">${i + 1}. ${task.title}</span>
                    <span class="queue-item-status status-${task.status}">${task.status === 'pending' ? '等待中' : task.status === 'running' ? '运行中' : task.status === 'completed' ? '完成' : '失败'}</span>
                </li>
            `).join('');
            
            // 更新进度条
            const completed = taskQueue.filter(t => t.status === 'completed').length;
            const progress = (completed / taskQueue.length) * 100;
            document.getElementById('progress-fill').style.width = progress + '%';
        }
        
        // 提交任务
        document.getElementById('task-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (isRunning) {
                addLog('任务已在运行中', 'warning');
                return;
            }
            
            const formData = {
                gen_type: document.getElementById('gen-type').value,
                count: parseInt(document.getElementById('count').value),
                custom_topic: document.getElementById('custom-topic').value,
                interval: parseInt(document.getElementById('interval').value)
            };
            
            isRunning = true;
            document.getElementById('start-btn').disabled = true;
            document.getElementById('start-btn').textContent = '⏳ 生成中...';
            
            addLog(`开始生成：${formData.count} 张 ${formData.gen_type} 类型图片`, 'info');
            addLog(`任务间隔：${formData.interval} 秒`, 'info');
            
            try {
                const resp = await fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(formData)
                });
                
                const result = await resp.json();
                
                if (result.success) {
                    taskQueue = result.tasks;
                    addLog(`已创建 ${taskQueue.length} 个任务`, 'success');
                    updateQueue();
                    
                    // 轮询状态
                    const pollInterval = setInterval(async () => {
                        await updateStatus();
                        
                        const statusResp = await fetch('/api/status');
                        const status = await statusResp.json();
                        
                        if (status.tasks) {
                            taskQueue = status.tasks;
                            updateQueue();
                        }
                        
                        if (!status.is_running) {
                            clearInterval(pollInterval);
                            isRunning = false;
                            document.getElementById('start-btn').disabled = false;
                            document.getElementById('start-btn').textContent = '🚀 开始生成';
                            addLog('所有任务已完成', 'success');
                        }
                    }, 2000);
                    
                } else {
                    addLog(`启动失败：${result.error}`, 'error');
                    isRunning = false;
                    document.getElementById('start-btn').disabled = false;
                    document.getElementById('start-btn').textContent = '🚀 开始生成';
                }
            } catch (e) {
                addLog(`错误：${e.message}`, 'error');
                isRunning = false;
                document.getElementById('start-btn').disabled = false;
                document.getElementById('start-btn').textContent = '🚀 开始生成';
            }
        });
        
        // 初始化
        updateStatus();
        setInterval(updateStatus, 3000);
    </script>
</body>
</html>
"""


class WebHandler(SimpleHTTPRequestHandler):
    """网页处理器"""
    
    def __init__(self, *args, scheduler=None, **kwargs):
        self.scheduler = scheduler
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif self.path == '/api/status':
            self.send_json({
                'comfyui_connected': True,
                'running': len(self.scheduler.monitor.get_queue().get('queue_running', [])),
                'pending': len(self.scheduler.monitor.get_queue().get('queue_pending', [])),
                'completed': sum(1 for t in self.scheduler.task_queue if t.get('status') == 'completed'),
                'is_running': self.scheduler.current_task is not None,
                'tasks': self.scheduler.task_queue
            })
        else:
            super().do_GET(self)
    
    def do_POST(self):
        if self.path == '/api/start':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            # 创建任务
            self.scheduler.task_queue = []
            gen_type = data.get('gen_type', 'funny')
            count = data.get('count', 3)
            interval = data.get('interval', 60)
            
            TASK_INTERVAL = interval
            
            # 生成提示词
            prompts = {
                "funny": "funny cartoon style, humor, exaggerated, bright colors",
                "portrait": "portrait photography, professional lighting, bokeh, high quality",
                "landscape": "beautiful landscape, nature, mountains, golden hour, high quality",
                "anime": "anime style, Japanese animation, colorful, detailed",
                "cyberpunk": "cyberpunk city, neon lights, futuristic, night scene",
                "fantasy": "fantasy world, magic, dragon, castle, epic",
                "scifi": "science fiction, spaceship, alien planet, futuristic",
                "news": "news illustration, professional, high quality"
            }
            
            base_prompt = prompts.get(gen_type, prompts["funny"])
            
            for i in range(count):
                workflow = {
                    "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
                    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "ltx-2-19b-dev_embeddings_connectors.safetensors", "type": "sd1x"}},
                    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
                    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": f"{base_prompt}, {data.get('custom_topic', '')}"}},
                    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "blurry, low quality"}},
                    "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 512, "width": 1024}},
                    "7": {"class_type": "KSampler", "inputs": {"cfg": 7, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0], "negative": ["5", 0], "positive": ["4", 0], "sampler_name": "euler_ancestral", "scheduler": "normal", "seed": int(time.time() * 1000) % 1000000 + i, "steps": 25}},
                    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
                    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"ComfyUI_{gen_type}", "images": ["8", 0]}}
                }
                
                self.scheduler.add_task({
                    "title": f"{gen_type}_{i+1}",
                    "prompt": base_prompt,
                    "workflow": workflow
                })
            
            self.send_json({'success': True, 'tasks': self.scheduler.task_queue})
        else:
            super().do_POST(self)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def run_web_server(scheduler, port=CONTROLLER_PORT):
    """运行网页服务器"""
    handler = lambda *args, **kwargs: WebHandler(*args, scheduler=scheduler, **kwargs)
    server = HTTPServer(('127.0.0.1', port), handler)
    print(f"\n🌐 网页控制器运行中：http://127.0.0.1:{port}")
    server.serve_forever()


def main():
    print("="*70)
    print("🎨 ComfyUI 网页版智能控制器")
    print("="*70)
    
    # 创建调度器
    scheduler = TaskScheduler()
    
    # 检查 ComfyUI 连接
    if not scheduler.monitor.get_queue():
        print(f"\n❌ 无法连接 ComfyUI ({COMFYUI_SERVER})")
        print(f"💡 确保 ComfyUI 正在运行")
        return 1
    
    print(f"✅ ComfyUI: {COMFYUI_SERVER}")
    
    # 在后台运行网页服务器
    web_thread = threading.Thread(target=run_web_server, args=(scheduler,), daemon=True)
    web_thread.start()
    
    # 自动打开浏览器
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{CONTROLLER_PORT}")
    print(f"🌐 已打开浏览器")
    
    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n⚠️  停止")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
