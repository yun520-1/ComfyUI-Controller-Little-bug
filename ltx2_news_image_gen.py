#!/usr/bin/env python3
"""
LTX2 新闻图片生成器
使用 LTX2 模型生成 1024x512 新闻图片
"""

import json
import uuid
import requests
import websocket
import time
import sys
from pathlib import Path
from datetime import datetime

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_news_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LTX2 模型配置
LTX2_UNET = "ltx-2-19b-dev-Q3_K_S.gguf"
LTX2_CLIP = "ltx-2-19b-dev_embeddings_connectors.safetensors"
LTX2_VAE = "ltx-2-19b-dev_video_vae.safetensors"


def create_ltx2_workflow(prompt, width=1024, height=512, seed=None):
    """创建 LTX2 工作流"""
    if seed is None:
        seed = int(time.time() * 1000) % (2**32)
    
    workflow = {
        "3": {
            "class_type": "LTXVModelConfig",
            "inputs": {
                "dtype": "fp8_e4m3fn",
                "quantization": "gguf"
            }
        },
        "4": {
            "class_type": "GGUFCheckpointLoader",
            "inputs": {
                "ckpt_file": LTX2_UNET,
                "clip_name": LTX2_CLIP,
                "vae_name": LTX2_VAE,
                "dtype": "fp8_e4m3fn"
            }
        },
        "5": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "batch_size": 1,
                "force_square": False,
                "frame_number": 1,
                "height": height,
                "width": width
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 0],
                "text": prompt
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 0],
                "text": "blurry, low quality, distorted, ugly, deformed, watermark, text, worst quality"
            }
        },
        "8": {
            "class_type": "LTXVSampler",
            "inputs": {
                "cfg": 3.0,
                "steps": 25,
                "latent": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "seed": seed
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["4", 2]
            }
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "news_ltx2",
                "images": ["9", 0]
            }
        }
    }
    
    return workflow


def generate_image(prompt, width=1024, height=512):
    """生成单张图片"""
    server_address = COMFYUI_SERVER
    client_id = str(uuid.uuid4())
    
    # 创建工作流
    workflow = create_ltx2_workflow(prompt, width, height)
    
    try:
        # 发送请求
        url = f"http://{server_address}/prompt"
        data = {"prompt": workflow, "client_id": client_id}
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get('prompt_id')
            print(f"✅ 请求成功 - Prompt ID: {prompt_id}")
            return prompt_id
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"响应：{response.text[:500]}")
            return None
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, timeout=300):
    """等待生成完成"""
    start_time = time.time()
    print(f"⏳ 等待生成完成...")
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"http://{COMFYUI_SERVER}/history/{prompt_id}",
                timeout=5
            )
            if response.status_code == 200:
                history = response.json()
                if prompt_id in history:
                    print(f"✅ 生成完成!")
                    return True
        except:
            pass
        time.sleep(2)
    
    print(f"⏰ 等待超时 ({timeout}秒)")
    return False


def main():
    print("=" * 60)
    print("🎨 LTX2 新闻图片生成器")
    print("=" * 60)
    print()
    
    # 检查连接
    print("🔍 检查 ComfyUI 连接...")
    try:
        response = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        if response.status_code == 200:
            print(f"✅ ComfyUI: {COMFYUI_SERVER}")
        else:
            print(f"⚠️ ComfyUI 响应异常：{response.status_code}")
    except:
        print("❌ ComfyUI 服务未运行")
        print()
        print("请启动 ComfyUI:")
        print("  cd ~/ComfyUI && python main.py")
        return
    
    print()
    
    # 新闻图片提示词
    prompts = [
        "professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic, highly detailed",
        "digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K, highly detailed"
    ]
    
    print("📰 开始生成 2 张新闻图片...")
    print(f"📐 尺寸：1024x512")
    print(f"🎯 模型：LTX2 GGUF")
    print()
    
    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/2] 生成第 {i} 张图片...")
        print(f"提示词：{prompt[:60]}...")
        
        prompt_id = generate_image(prompt, width=1024, height=512)
        if prompt_id:
            if wait_for_completion(prompt_id):
                print(f"✅ 第 {i} 张图片生成成功")
            else:
                print(f"⚠️ 第 {i} 张图片生成超时")
        else:
            print(f"❌ 第 {i} 张图片生成失败")
        
        print()
    
    print("=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print()
    print(f"图片位置：{OUTPUT_DIR}/")
    print(f"或：~/ComfyUI/output/news_ltx2_*.png")
    print()


if __name__ == "__main__":
    main()
