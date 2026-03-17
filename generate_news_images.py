#!/usr/bin/env python3
"""
最新新闻图片生成器 - 简化版
生成 1024*512 的新闻风格图片
"""

import requests
import json
import time
import os

def check_comfyui():
    """检查 ComfyUI 服务"""
    try:
        response = requests.get('http://127.0.0.1:8188/system_stats', timeout=5)
        return response.status_code == 200
    except:
        return False

def generate_news_image(prompt, width=1024, height=512, seed=None):
    """生成新闻图片"""
    server_address = "127.0.0.1:8188"
    
    if seed is None:
        seed = int(time.time() * 1000) % (2**32)
    
    # 简化的工作流
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 7,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": seed,
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "sd_xl_base_1.0.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": height,
                "width": width
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": prompt
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": "blurry, low quality, distorted, ugly, deformed, watermark, text"
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
                "filename_prefix": "news",
                "images": ["8", 0]
            }
        }
    }
    
    try:
        response = requests.post(
            f"http://{server_address}/prompt",
            json={"prompt": workflow}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功 - Prompt ID: {result.get('prompt_id')}")
            return True
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"响应：{response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        return False

def main():
    print("=" * 60)
    print("📰 最新新闻图片生成器 (1024x512)")
    print("=" * 60)
    print()
    
    print("🔍 检查 ComfyUI 服务...")
    if not check_comfyui():
        print("❌ ComfyUI 服务未运行")
        print()
        print("请启动 ComfyUI:")
        print("  cd ~/ComfyUI && python main.py")
        return
    
    print("✅ ComfyUI 服务正常")
    print()
    
    # 两个新闻主题
    prompts = [
        "professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting",
        "digital news headline background, futuristic screen display, latest news ticker, blue red theme, professional broadcast studio"
    ]
    
    print("🎨 开始生成 2 张新闻图片...")
    print(f"📐 尺寸：1024x512")
    print()
    
    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/2] 生成第 {i} 张图片...")
        print(f"提示词：{prompt[:60]}...")
        success = generate_news_image(prompt, width=1024, height=512)
        if success:
            print(f"✅ 第 {i} 张图片生成成功")
        print()
    
    print("=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print()
    print("图片位置：~/ComfyUI/output/news_*.png")
    print()

if __name__ == "__main__":
    main()
