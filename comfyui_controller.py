#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 控制器
支持：
- 连接 ComfyUI 服务器
- 提交文生图/图生图任务
- 监控生成进度
- 下载生成的图片
- 管理工作流

用法：
    python comfyui_controller.py --prompt "一个美丽的女孩" --negative "模糊，低质量"
    python comfyui_controller.py --workflow workflow.json
    python comfyui_controller.py --queue  # 查看队列状态
"""

import json
import uuid
import time
import argparse
import websocket
import requests
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"  # ComfyUI 服务器地址
OUTPUT_DIR = Path("/home/admin/Downloads/comfyui_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============ 默认工作流（文生图） ============
DEFAULT_WORKFLOW = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 8,
            "denoise": 1,
            "latent_image": ["5", 0],
            "model": ["4", 0],
            "negative": ["7", 0],
            "positive": ["6", 0],
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 123456789,
            "steps": 20
        }
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "v1-5-pruned-emaonly.ckpt"
        }
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "batch_size": 1,
            "height": 512,
            "width": 512
        }
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["4", 1],
            "text": "positive prompt here"
        }
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["4", 1],
            "text": "negative prompt here"
        }
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2]
        }
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "ComfyUI",
            "images": ["8", 0]
        }
    }
}

class ComfyUIController:
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.ws = None
        
    def check_connection(self):
        """检查 ComfyUI 是否可连接"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                print(f"✅ 已连接到 ComfyUI ({self.server})")
                return True
        except Exception as e:
            print(f"❌ 无法连接 ComfyUI: {e}")
            print(f"   请确保 ComfyUI 正在运行：python main.py --listen 0.0.0.0")
            return False
        return False
    
    def get_queue(self):
        """获取当前队列状态"""
        try:
            resp = requests.get(f"{self.base_url}/queue", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"\n📊 队列状态:")
                print(f"   运行中：{len(data.get('running', []))} 个任务")
                print(f"   等待中：{len(data.get('queue_pending', []))} 个任务")
                return data
        except Exception as e:
            print(f"❌ 获取队列失败：{e}")
        return None
    
    def get_history(self, prompt_id=None):
        """获取历史记录"""
        try:
            url = f"{self.base_url}/history"
            if prompt_id:
                url += f"/{prompt_id}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"❌ 获取历史失败：{e}")
        return None
    
    def get_models(self):
        """获取可用模型列表"""
        try:
            resp = requests.get(f"{self.base_url}/object_info/CheckpointLoaderSimple", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [[]])
                if models:
                    print(f"\n📦 可用模型:")
                    for m in models[0][:10]:  # 只显示前 10 个
                        print(f"   - {m}")
                    if len(models[0]) > 10:
                        print(f"   ... 共 {len(models[0])} 个模型")
                    return models[0]
        except Exception as e:
            print(f"❌ 获取模型列表失败：{e}")
        return []
    
    def queue_prompt(self, workflow):
        """提交工作流到队列"""
        prompt = {
            "prompt": workflow,
            "client_id": self.client_id
        }
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json=prompt,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get('prompt_id')
                print(f"✅ 任务已提交 (ID: {prompt_id})")
                return prompt_id
        except Exception as e:
            print(f"❌ 提交任务失败：{e}")
        return None
    
    def monitor_progress(self, prompt_id, timeout=300):
        """监控生成进度"""
        self.ws = websocket.WebSocket()
        try:
            self.ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            print(f"\n⏳ 等待生成完成...")
            
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    print("⏰ 超时!")
                    break
                
                try:
                    msg = json.loads(self.ws.recv())
                    msg_type = msg.get('type')
                    data = msg.get('data', {})
                    
                    if msg_type == 'progress':
                        step = data.get('value', 0)
                        total = data.get('max', 100)
                        percent = int(step / total * 100)
                        print(f"   进度：{percent}% ({step}/{total})")
                    
                    elif msg_type == 'executing':
                        node = data.get('node')
                        if node is None:
                            print(f"✅ 生成完成!")
                            break
                        else:
                            print(f"   执行节点：{node}")
                    
                    elif msg_type == 'executed':
                        print(f"   节点 {data.get('node')} 执行完成")
                    
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception as e:
                    print(f"   WebSocket 错误：{e}")
                    break
            
            return True
            
        except Exception as e:
            print(f"❌ 监控失败：{e}")
            return False
        finally:
            if self.ws:
                self.ws.close()
    
    def download_images(self, prompt_id):
        """下载生成的图片"""
        history = self.get_history(prompt_id)
        if not history or prompt_id not in history:
            print("❌ 未找到历史记录")
            return []
        
        outputs = history[prompt_id].get('outputs', {})
        downloaded = []
        
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                for img in node_output['images']:
                    if 'filename' in img and 'subfolder' in img and 'type' in img:
                        params = {
                            'filename': img['filename'],
                            'subfolder': img['subfolder'],
                            'type': img['type']
                        }
                        url = f"{self.base_url}/view?{urllib.parse.urlencode(params)}"
                        
                        try:
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"comfyui_{timestamp}_{img['filename']}"
                                save_path = OUTPUT_DIR / filename
                                
                                with open(save_path, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"✅ 已保存：{save_path}")
                                downloaded.append(str(save_path))
                        except Exception as e:
                            print(f"❌ 下载失败：{e}")
        
        return downloaded
    
    def create_workflow(self, prompt, negative="ugly, blurry, low quality", 
                       model="v1-5-pruned-emaonly.ckpt", 
                       width=512, height=512, 
                       steps=20, cfg=8, seed=None):
        """创建工作流"""
        workflow = json.loads(json.dumps(DEFAULT_WORKFLOW))  # 深拷贝
        
        # 设置提示词
        workflow["6"]["inputs"]["text"] = prompt
        workflow["7"]["inputs"]["text"] = negative
        
        # 设置模型
        workflow["4"]["inputs"]["ckpt_name"] = model
        
        # 设置尺寸
        workflow["5"]["inputs"]["width"] = width
        workflow["5"]["inputs"]["height"] = height
        
        # 设置采样参数
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["cfg"] = cfg
        workflow["3"]["inputs"]["seed"] = seed if seed else int(time.time() * 1000) % 1000000
        
        return workflow
    
    def generate(self, prompt, negative="ugly, blurry, low quality", **kwargs):
        """一键生成：创建工作流 + 提交 + 监控 + 下载"""
        print(f"\n🎨 开始生成:")
        print(f"   提示词：{prompt[:50]}..." if len(prompt) > 50 else f"   提示词：{prompt}")
        print(f"   负面词：{negative}")
        
        # 创建工作流
        workflow = self.create_workflow(prompt, negative, **kwargs)
        
        # 提交
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return None
        
        # 监控进度
        if self.monitor_progress(prompt_id):
            # 下载图片
            images = self.download_images(prompt_id)
            return images
        
        return None


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 控制器")
    parser.add_argument("--prompt", "-p", type=str, help="正向提示词")
    parser.add_argument("--negative", "-n", type=str, default="ugly, blurry, low quality", help="负面提示词")
    parser.add_argument("--workflow", "-w", type=str, help="工作流 JSON 文件路径")
    parser.add_argument("--server", "-s", type=str, default=COMFYUI_SERVER, help="ComfyUI 服务器地址")
    parser.add_argument("--model", "-m", type=str, default="v1-5-pruned-emaonly.ckpt", help="模型名称")
    parser.add_argument("--width", type=int, default=512, help="图片宽度")
    parser.add_argument("--height", type=int, default=512, help="图片高度")
    parser.add_argument("--steps", type=int, default=20, help="采样步数")
    parser.add_argument("--cfg", type=float, default=8, help="CFG 值")
    parser.add_argument("--seed", type=int, help="随机种子（不填则随机）")
    parser.add_argument("--queue", action="store_true", help="查看队列状态")
    parser.add_argument("--models", action="store_true", help="查看可用模型")
    parser.add_argument("--history", type=str, help="查看指定 prompt_id 的历史")
    
    args = parser.parse_args()
    
    controller = ComfyUIController(args.server)
    
    # 检查连接
    if not controller.check_connection():
        return 1
    
    # 查看队列
    if args.queue:
        controller.get_queue()
        return 0
    
    # 查看模型
    if args.models:
        controller.get_models()
        return 0
    
    # 查看历史
    if args.history:
        history = controller.get_history(args.history)
        if history:
            print(json.dumps(history, indent=2, ensure_ascii=False))
        return 0
    
    # 生成图片
    if args.prompt:
        images = controller.generate(
            prompt=args.prompt,
            negative=args.negative,
            model=args.model,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
            seed=args.seed
        )
        if images:
            print(f"\n✅ 生成完成！共 {len(images)} 张图片")
            for img in images:
                print(f"   {img}")
        return 0
    
    # 加载工作流文件
    if args.workflow:
        workflow_path = Path(args.workflow)
        if workflow_path.exists():
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            prompt_id = controller.queue_prompt(workflow)
            if prompt_id:
                controller.monitor_progress(prompt_id)
                controller.download_images(prompt_id)
        else:
            print(f"❌ 工作流文件不存在：{args.workflow}")
        return 0
    
    # 无参数时显示帮助
    parser.print_help()
    print(f"\n💡 示例:")
    print(f"   python {__file__} --prompt \"一个美丽的女孩\" --model \"v1-5-pruned-emaonly.ckpt\"")
    print(f"   python {__file__} --workflow my_workflow.json")
    print(f"   python {__file__} --queue")
    return 0


if __name__ == '__main__':
    exit(main())
