#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - LoaderGGUF 版
使用官方 LoaderGGUF 节点
1024*512 分辨率
"""

import json
import uuid
import time
import requests
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "funny_beauty_images"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 搞笑美女场景
SCENARIOS = [
    {
        "title": "化妆前后",
        "prompt": "funny cartoon style, beautiful girl comparing makeup before and after, exaggerated contrast, humor, bright colors, comic style, 4k",
        "negative": "blurry, low quality, ugly, deformed, nsfw"
    },
    {
        "title": "自拍 vs 他拍",
        "prompt": "funny cartoon style, beautiful girl taking selfie vs someone else taking photo, funny awkward angle, exaggerated expressions, humor, bright, comic",
        "negative": "blurry, low quality, ugly, deformed, nsfw"
    }
]


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """创建工作流 - 使用 LoaderGGUF"""
    if seed is None:
        seed = int(time.time() * 1000) % 1000000
    
    # 使用 LoaderGGUF (官方配置)
    workflow = {
        # 1. LoaderGGUF (同时加载 UNet 和 CLIP)
        "1": {
            "class_type": "LoaderGGUF",
            "inputs": {
                "ckpt_name": "z_image_turbo-Q8_0.gguf"
            }
        },
        
        # 2. VAE 加载
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors"
            }
        },
        
        # 3. 正向提示词
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 0],  # LoaderGGUF 输出 CLIP
                "text": f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt}"
            }
        },
        
        # 4. 负面提示词
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 0],
                "text": negative
            }
        },
        
        # 5. 空潜图
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": height,
                "width": width
            }
        },
        
        # 6. KSampler
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 7.0,
                "denoise": 1.0,
                "latent_image": ["5", 0],
                "model": ["1", 0],  # LoaderGGUF 输出 Model
                "negative": ["4", 0],
                "positive": ["3", 0],
                "sampler_name": "euler",
                "scheduler": "simple",
                "seed": seed,
                "steps": 20
            }
        },
        
        # 7. VAE 解码
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["6", 0],
                "vae": ["2", 0]
            }
        },
        
        # 8. 保存图片
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "FunnyBeauty",
                "images": ["7", 0]
            }
        }
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
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, client_id, timeout=300):
    """等待完成"""
    try:
        print(f"⏳ 等待生成完成...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://{SERVER}/history/{prompt_id}", timeout=5)
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        item = history[prompt_id]
                        status = item.get('status', {})
                        
                        if status.get('completed', False):
                            print(f"✅ 生成完成!")
                            return True
                        
                        if status.get('status_str') == 'error':
                            print(f"❌ 执行错误")
                            return False
            except:
                pass
            time.sleep(2)
        
        print(f"⏰ 超时")
        return False
    except Exception as e:
        print(f"❌ 错误：{e}")
        return False


def download_image(prompt_id):
    """下载图片"""
    try:
        response = requests.get(f"http://{SERVER}/history/{prompt_id}", timeout=10)
        if response.status_code == 200:
            history = response.json()
            if prompt_id in history:
                outputs = history[prompt_id].get('outputs', {})
                for node_id, output in outputs.items():
                    if 'images' in output:
                        for img in output['images']:
                            filename = img.get('filename')
                            if filename:
                                url = f"http://{SERVER}/view?filename={filename}"
                                img_response = requests.get(url, timeout=30)
                                if img_response.status_code == 200:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filepath = OUTPUT / f"{timestamp}_{filename}"
                                    with open(filepath, 'wb') as f:
                                        f.write(img_response.content)
                                    print(f"  ✅ 已保存：{filepath}")
                                    return str(filepath)
        return None
    except Exception as e:
        print(f"❌ 下载错误：{e}")
        return None


def generate_image(scenario, index):
    """生成图片"""
    client_id = str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"[{index}/2] 生成：{scenario['title']}")
    print(f"{'='*60}")
    print(f"提示词：{scenario['prompt'][:80]}...")
    
    workflow = create_workflow(scenario['prompt'], scenario['negative'], 1024, 512)
    
    prompt_id = queue_prompt(workflow, client_id)
    if not prompt_id:
        return False
    
    if wait_for_completion(prompt_id, client_id):
        filepath = download_image(prompt_id)
        if filepath:
            print(f"✅ '{scenario['title']}' 成功!")
            return True
    
    print(f"⚠️ '{scenario['title']}' 失败")
    return False


def main():
    print("=" * 60)
    print("😂 搞笑美女图片生成器 (LoaderGGUF 版)")
    print("=" * 60)
    print()
    
    print("🔍 检查 ComfyUI...")
    try:
        response = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if response.status_code == 200:
            print(f"✅ ComfyUI: 127.0.0.1:8188")
        else:
            print(f"⚠️ 响应异常：{response.status_code}")
    except:
        print("❌ ComfyUI 未运行")
        return
    
    print()
    print("📐 尺寸：1024x512")
    print("🎯 模型：Z-Image-Turbo-Q8_0.gguf (LoaderGGUF)")
    print(f"📁 输出：{OUTPUT}/")
    print()
    
    success_count = 0
    for i, scenario in enumerate(SCENARIOS, 1):
        if generate_image(scenario, i):
            success_count += 1
        time.sleep(3)
    
    print()
    print("=" * 60)
    print("📊 完成")
    print("=" * 60)
    print(f"成功：{success_count}/{len(SCENARIOS)}")
    print()
    print(f"图片位置：{OUTPUT}/")
    print()


if __name__ == "__main__":
    main()
