#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 使用 Z-Image-Turbo 模型
1024*512 分辨率
"""

import json
import uuid
import time
import requests
import websocket
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "funny_beauty_images"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 搞笑美女场景
SCENARIOS = [
    {
        "title": "化妆前后",
        "prompt": "funny cartoon style, beautiful girl comparing makeup before and after, left side messy hair no makeup, right side glamorous with perfect makeup, exaggerated contrast, humor, bright colors, comic style, 4k",
        "negative": "blurry, low quality, dark, serious, realistic, nsfw, ugly, deformed"
    },
    {
        "title": "自拍 vs 他拍",
        "prompt": "funny cartoon style, beautiful girl taking selfie vs someone else taking photo, selfie shows perfect angle, other photo shows funny awkward angle, exaggerated expressions, humor, bright, comic",
        "negative": "blurry, low quality, dark, serious, nsfw, ugly, deformed"
    }
]


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """使用 Z-Image-Turbo GGUF 模型创建工作流"""
    if seed is None:
        seed = int(time.time() * 1000) % 1000000
    
    workflow = {
        # 1. UNet 加载
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
        
        # 2. CLIP 加载
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip_l.safetensors", "type": "sd1x"}},
        
        # 3. VAE 加载
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        
        # 4. 正向提示词
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        
        # 5. 负面提示词
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        
        # 6. 空潜图
        "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": height, "width": width}},
        
        # 7. KSampler
        "7": {"class_type": "KSampler", "inputs": {
            "cfg": 7, 
            "denoise": 1, 
            "latent_image": ["6", 0], 
            "model": ["1", 0],
            "negative": ["5", 0], 
            "positive": ["4", 0],
            "sampler_name": "euler_ancestral", 
            "scheduler": "normal", 
            "seed": seed, 
            "steps": 20
        }},
        
        # 8. VAE 解码
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        
        # 9. 保存图片
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "FunnyBeauty", "images": ["8", 0]}}
    }
    
    return workflow


def queue_prompt(api, client_id):
    """发送生成请求"""
    try:
        response = requests.post(
            f"http://{SERVER}/prompt",
            json={"prompt": api, "client_id": client_id},
            timeout=30
        )
        print(f"状态码：{response.status_code}")
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get('prompt_id')
            print(f"✅ Prompt ID: {prompt_id}")
            return prompt_id
        else:
            print(f"❌ 错误：{response.text[:400]}")
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, client_id, timeout=120):
    """等待生成完成"""
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{SERVER}/ws?clientId={client_id}", timeout=10)
        
        print(f"⏳ 等待生成完成...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = ws.recv(timeout=5)
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get('type') == 'executing':
                        if data.get('data', {}).get('node') is None:
                            print(f"✅ 生成完成!")
                            ws.close()
                            return True
            except:
                pass
            time.sleep(1)
        
        ws.close()
        print(f"⏰ 超时 ({timeout}秒)")
        return False
    except Exception as e:
        print(f"❌ WebSocket 错误：{e}")
        return False


def generate_image(scenario, index):
    """生成单张图片"""
    client_id = str(uuid.uuid4())
    
    print(f"\n[{index}/2] 生成：{scenario['title']}")
    print(f"提示词：{scenario['prompt'][:80]}...")
    
    # 创建工作流
    workflow = create_workflow(
        scenario['prompt'],
        scenario['negative'],
        width=1024,
        height=512
    )
    
    # 发送请求
    prompt_id = queue_prompt(workflow, client_id)
    if not prompt_id:
        return False
    
    # 等待完成
    if wait_for_completion(prompt_id, client_id):
        print(f"✅ '{scenario['title']}' 生成成功!")
        return True
    else:
        print(f"⚠️ '{scenario['title']}' 生成超时")
        return False


def main():
    print("=" * 60)
    print("😂 搞笑美女图片生成器")
    print("=" * 60)
    print()
    
    # 检查连接
    print("🔍 检查 ComfyUI 连接...")
    try:
        response = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        if response.status_code == 200:
            print(f"✅ ComfyUI: {SERVER}")
        else:
            print(f"⚠️ 响应异常：{response.status_code}")
    except:
        print("❌ ComfyUI 未运行")
        print("请启动：cd ~/ComfyUI && python main.py")
        return
    
    print()
    print("📐 尺寸：1024x512")
    print("🎯 模型：Z-Image-Turbo GGUF")
    print("📁 输出：~/Downloads/funny_beauty_images/")
    print()
    
    # 生成图片
    success_count = 0
    for i, scenario in enumerate(SCENARIOS, 1):
        if generate_image(scenario, i):
            success_count += 1
        time.sleep(2)
    
    print()
    print("=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print(f"成功：{success_count}/{len(SCENARIOS)}")
    print()
    print(f"图片位置：{OUTPUT}/")
    print(f"或：~/ComfyUI/output/FunnyBeauty_*.png")
    print()


if __name__ == "__main__":
    main()
