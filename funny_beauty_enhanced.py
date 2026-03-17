#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 增强版
使用可用的模型配置
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


def get_available_models():
    """获取可用模型"""
    try:
        response = requests.get(f"http://{SERVER}/object_info", timeout=5)
        if response.status_code == 200:
            object_info = response.json()
            
            # 获取可用 CLIP
            clip_list = []
            if 'CLIPLoader' in object_info:
                clip_list = object_info['CLIPLoader']['input']['required']['clip_name'][0]
            
            # 获取可用 VAE
            vae_list = []
            if 'VAELoader' in object_info:
                vae_list = object_info['VAELoader']['input']['required']['vae_name'][0]
            
            return clip_list, vae_list
    except:
        pass
    
    return [], []


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """创建工作流 - 使用可用模型"""
    if seed is None:
        seed = int(time.time() * 1000) % 1000000
    
    # 获取可用模型
    clip_list, vae_list = get_available_models()
    
    # 选择 CLIP 模型
    clip_name = "ltx-2-19b-dev_embeddings_connectors.safetensors"
    if clip_list:
        # 优先选择 clip_l 或 sd1x 相关
        for c in clip_list:
            if 'clip_l' in c.lower() or 'sd1' in c.lower():
                clip_name = c
                break
        else:
            clip_name = clip_list[0]
    
    # 选择 VAE 模型
    vae_name = "ae.safetensors"
    if vae_list:
        for v in vae_list:
            if 'ae.safetensors' in v or 'vae' in v.lower():
                vae_name = v
                break
        else:
            vae_name = vae_list[0]
    
    print(f"   使用 CLIP: {clip_name}")
    print(f"   使用 VAE: {vae_name}")
    
    workflow = {
        # 1. UNet 加载
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
        
        # 2. CLIP 加载
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip_name, "type": "stable_diffusion"}},
        
        # 3. VAE 加载
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        
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
    """发送请求"""
    try:
        response = requests.post(
            f"http://{SERVER}/prompt",
            json={"prompt": api, "client_id": client_id},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get('prompt_id')
            print(f"✅ Prompt ID: {prompt_id}")
            return prompt_id
        else:
            print(f"❌ 状态码：{response.status_code}")
            print(f"响应：{response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, client_id, timeout=120):
    """等待完成"""
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{SERVER}/ws?clientId={client_id}", timeout=10)
        
        print(f"⏳ 等待生成完成...")
        start_time = time.time()
        last_pct = -1
        
        while time.time() - start_time < timeout:
            try:
                message = ws.recv(timeout=5)
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get('type') == 'progress':
                        pct = int(data.get('data', {}).get('value', 0) / data.get('data', {}).get('max', 100) * 100)
                        if pct != last_pct:
                            print(f"   {pct}%...")
                            last_pct = pct
                    elif data.get('type') == 'executing':
                        if data.get('data', {}).get('node') is None:
                            print(f"✅ 生成完成!")
                            ws.close()
                            return True
            except:
                pass
            time.sleep(1)
        
        ws.close()
        print(f"⏰ 超时")
        return False
    except Exception as e:
        print(f"❌ WebSocket 错误：{e}")
        return False


def generate_image(scenario, index):
    """生成图片"""
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
        print(f"✅ '{scenario['title']}' 成功!")
        return True
    else:
        print(f"⚠️ '{scenario['title']}' 超时")
        return False


def main():
    print("=" * 60)
    print("😂 搞笑美女图片生成器 (增强版)")
    print("=" * 60)
    print()
    
    # 检查连接
    print("🔍 检查 ComfyUI...")
    try:
        response = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        if response.status_code == 200:
            print(f"✅ ComfyUI: {SERVER}")
        else:
            print(f"⚠️ 响应异常：{response.status_code}")
    except:
        print("❌ ComfyUI 未运行")
        return
    
    print()
    
    # 获取可用模型
    print("📦 检测可用模型...")
    clip_list, vae_list = get_available_models()
    print(f"   可用 CLIP: {len(clip_list)} 个")
    print(f"   可用 VAE: {len(vae_list)} 个")
    print()
    
    print("📐 尺寸：1024x512")
    print("🎯 模型：Z-Image-Turbo GGUF")
    print(f"📁 输出：{OUTPUT}/")
    print()
    
    # 生成
    success_count = 0
    for i, scenario in enumerate(SCENARIOS, 1):
        if generate_image(scenario, i):
            success_count += 1
        time.sleep(2)
    
    print()
    print("=" * 60)
    print("📊 完成")
    print("=" * 60)
    print(f"成功：{success_count}/{len(SCENARIOS)}")
    print()
    print(f"图片位置：{OUTPUT}/")
    print(f"或：~/ComfyUI/output/FunnyBeauty_*.png")
    print()


if __name__ == "__main__":
    main()
