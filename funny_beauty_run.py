#!/usr/bin/env python3
"""搞笑美女图片生成 - 快速版"""

import requests
import json
import uuid
import time
from pathlib import Path

SERVER = "127.0.0.1:8188"

print("="*60)
print("😂 搞笑美女图片生成")
print("="*60)
print()

# 检查
try:
    r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
    print("✅ ComfyUI 已连接")
except:
    print("❌ ComfyUI 未运行")
    exit(1)

# 工作流
workflow = {
    "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "ltx-2-19b-dev_embeddings_connectors.safetensors", "type": "stable_diffusion"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "funny cartoon style, beautiful girl comparing makeup before and after, exaggerated contrast, humor, bright colors, comic style, 4k"}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "blurry, low quality, ugly, deformed, nsfw"}},
    "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 512, "width": 1024}},
    "7": {"class_type": "KSampler", "inputs": {"cfg": 7, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0], "negative": ["5", 0], "positive": ["4", 0], "sampler_name": "euler_ancestral", "scheduler": "normal", "seed": int(time.time()*1000)%(2**32), "steps": 20}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "FunnyBeauty", "images": ["8", 0]}}
}

print("\n📐 尺寸：1024x512")
print("🎯 模型：Z-Image-Turbo GGUF")
print()

# 发送
client_id = str(uuid.uuid4())
print("📤 发送第 1 张请求...")
r = requests.post(f"http://{SERVER}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=30)

if r.status_code == 200:
    result = r.json()
    prompt_id = result.get('prompt_id')
    print(f"✅ 请求成功 - Prompt ID: {prompt_id}")
    print(f"\n⏳ 等待生成完成...")
    print("   预计时间：15-30 秒")
    print(f"\n图片将保存到：~/ComfyUI/output/FunnyBeauty_*.png")
else:
    print(f"❌ 请求失败：{r.status_code}")
    print(f"错误：{r.text[:300]}")

print()
