#!/usr/bin/env python3
"""
GGUF 模型新闻图片生成器
使用 z_image_turbo-Q8_0.gguf 生成 1024x512 新闻图片
"""

import requests
import json
import uuid
import time

SERVER = "127.0.0.1:8188"

def create_workflow(prompt, width=1024, height=512):
    """创建工作流 - 使用 GGUF 模型"""
    seed = int(time.time() * 1000) % (2**32)

    # 先获取对象信息
    try:
        resp = requests.get(f"http://{SERVER}/object_info", timeout=5)
        if resp.status_code == 200:
            object_info = resp.json()

            # 检查是否有 GGUFCheckpointLoader
            if 'GGUFCheckpointLoader' not in object_info:
                print("⚠️ 未找到 GGUFCheckpointLoader 节点")
                print("请安装: https://github.com/city96/ComfyUI-GGUF")
                return None
    except Exception as e:
        print(f"❌ 无法获取对象信息：{e}")
        return None

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
            "class_type": "GGUFCheckpointLoader",
            "inputs": {
                "ckpt_file": "z_image_turbo-Q8_0.gguf",
                "clip_name": "",  # z_image_turbo 内置 CLIP
                "vae_name": "ae.safetensors",
                "dtype": "fp8_e4m3fn"
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
                "clip": ["4", 0],
                "text": prompt
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 0],
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
                "filename_prefix": "news_gguf",
                "images": ["8", 0]
            }
        }
    }

    return workflow


def generate_image(prompt, width=1024, height=512):
    """生成图片"""
    workflow = create_workflow(prompt, width, height)
    if not workflow:
        return None

    try:
        response = requests.post(
            f"http://{SERVER}/prompt",
            json={"prompt": workflow, "client_id": str(uuid.uuid4())},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get('prompt_id')
            print(f"✅ 请求成功 - Prompt ID: {prompt_id}")
            return prompt_id
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"响应：{response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, timeout=120):
    """等待完成"""
    start = time.time()
    print(f"⏳ 等待生成完成...")

    while time.time() - start < timeout:
        try:
            response = requests.get(
                f"http://{SERVER}/history/{prompt_id}",
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

    print(f"⏰ 超时 ({timeout}秒)")
    return False


def main():
    print("=" * 60)
    print("📰 GGUF 新闻图片生成器 (1024x512)")
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

    # 提示词
    prompts = [
        "professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic",
        "digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K"
    ]

    print("🎨 开始生成 2 张新闻图片...")
    print(f"📐 尺寸：1024x512")
    print(f"🎯 模型：z_image_turbo-Q8_0.gguf")
    print()

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/2] 第 {i} 张图片...")
        print(f"提示词：{prompt[:60]}...")

        prompt_id = generate_image(prompt, 1024, 512)
        if prompt_id:
            if wait_for_completion(prompt_id):
                print(f"✅ 第 {i} 张完成")
            else:
                print(f"⚠️ 第 {i} 张超时")
        print()

    print("=" * 60)
    print("📊 完成")
    print("=" * 60)
    print()
    print("图片位置：~/ComfyUI/output/news_gguf_*.png")
    print()


if __name__ == "__main__":
    main()
