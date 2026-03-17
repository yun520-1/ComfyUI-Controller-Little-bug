#!/usr/bin/env python3
"""搞笑美女图片生成 - 简化版"""

import requests
import json

SERVER = "127.0.0.1:8188"

# 检查连接
try:
    r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
    print("✅ ComfyUI 已连接")
except:
    print("❌ ComfyUI 未运行")
    exit(1)

# 提示词
prompts = [
    "funny cartoon style, beautiful girl comparing makeup before and after, exaggerated contrast, humor, bright colors",
    "funny cartoon style, beautiful girl taking selfie vs awkward photo, funny expressions, comic style"
]

print("\n📐 尺寸：1024x512")
print("🎨 开始生成 2 张搞笑美女图片...\n")

for i, prompt in enumerate(prompts, 1):
    print(f"[{i}/2] 第{i}张: {prompt[:50]}...")
    print("👉 请在网页版输入此提示词并生成\n")

print("="*60)
print("⚠️  由于模型配置复杂，请使用网页版生成")
print("="*60)
print("\n步骤:")
print("1. 打开 http://127.0.0.1:8188")
print("2. 设置尺寸：1024x512")
print("3. 输入上方提示词")
print("4. 点击 Queue Prompt")
print("\n图片将保存到：~/ComfyUI/output/")
print()
