#!/usr/bin/env python3
"""
新闻图片生成器 - API 版本
使用 ComfyUI API 生成 1024x512 新闻图片
"""

import requests
import json
import time
import os

def get_queue_remaining():
    """获取队列状态"""
    try:
        response = requests.get('http://127.0.0.1:8188/queue', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return len(data.get('queue_running', [])) + len(data.get('queue_pending', []))
    except:
        pass
    return 0

def wait_for_completion(prompt_id, timeout=120):
    """等待生成完成"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f'http://127.0.0.1:8188/history/{prompt_id}', timeout=5)
            if response.status_code == 200:
                history = response.json()
                if prompt_id in history:
                    return True
        except:
            pass
        time.sleep(2)
    return False

def generate_news_image(prompt, width=1024, height=512):
    """生成单张新闻图片"""
    server_address = "127.0.0.1:8188"
    seed = int(time.time() * 1000) % (2**32)

    # 简化工作流（需要实际模型名称）
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
                "text": prompt,
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "blurry, low quality, distorted, ugly, deformed, watermark, text",
                "clip": ["4", 1]
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

    # 尝试获取模型列表
    try:
        response = requests.get(f'http://{server_address}/object_info', timeout=5)
        if response.status_code == 200:
            object_info = response.json()
            if 'CheckpointLoaderSimple' in object_info:
                ckpt_info = object_info['CheckpointLoaderSimple']
                if 'input' in ckpt_info and 'required' in ckpt_info['input']:
                    ckpt_names = ckpt_info['input']['required'].get('ckpt_name', [['']])[0]
                    if isinstance(ckpt_names, list):
                        # 使用第一个可用模型
                        model_name = ckpt_names[0] if ckpt_names else "model.safetensors"
                    else:
                        model_name = ckpt_names
                    workflow["4"] = {
                        "class_type": "CheckpointLoaderSimple",
                        "inputs": {"ckpt_name": model_name}
                    }
    except Exception as e:
        print(f"⚠️ 无法获取模型列表：{e}")
        workflow["4"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"}
        }

    # 发送请求
    try:
        response = requests.post(f'http://{server_address}/prompt', json={"prompt": workflow})
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get('prompt_id')
            print(f"✅ 请求成功 - Prompt ID: {prompt_id}")

            # 等待完成
            print(f"⏳ 等待生成完成...")
            if wait_for_completion(prompt_id):
                print(f"✅ 生成完成")
                return True
            else:
                print(f"⏰ 等待超时")
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"响应：{response.text[:200]}")
    except Exception as e:
        print(f"❌ 错误：{e}")

    return False

def main():
    print("=" * 60)
    print("📰 新闻图片生成器 (1024x512)")
    print("=" * 60)
    print()

    # 检查 ComfyUI
    print("🔍 检查 ComfyUI 服务...")
    try:
        response = requests.get('http://127.0.0.1:8188/system_stats', timeout=5)
        if response.status_code == 200:
            print("✅ ComfyUI 服务正常")
        else:
            print(f"⚠️ ComfyUI 响应异常：{response.status_code}")
    except:
        print("❌ ComfyUI 服务未运行")
        print()
        print("请启动 ComfyUI:")
        print("  cd ~/ComfyUI && python main.py")
        return

    print()

    # 检查队列
    queue_size = get_queue_remaining()
    if queue_size > 0:
        print(f"⚠️ 当前队列中有 {queue_size} 个任务")
        print()

    # 提示词
    prompts = [
        "professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic",
        "digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K"
    ]

    print("🎨 开始生成 2 张新闻图片...")
    print(f"📐 尺寸：1024x512")
    print()

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/2] 生成第 {i} 张图片...")
        print(f"提示词：{prompt[:60]}...")
        success = generate_news_image(prompt, width=1024, height=512)
        if success:
            print(f"✅ 第 {i} 张图片已加入队列")
        print()

    print("=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print()
    print("图片位置：~/ComfyUI/output/news_*.png")
    print()
    print("提示：如果生成失败，请使用 ComfyUI Web 界面手动生成")
    print("  http://127.0.0.1:8188")
    print()

if __name__ == "__main__":
    main()
