#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 直接使用官方工作流
从 z_image_turbo_gguf.json 工作流模板生成
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
WORKFLOW_FILE = Path.home() / "Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/z_image_turbo_gguf.json"

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


def load_base_workflow():
    """加载基础工作流"""
    if not WORKFLOW_FILE.exists():
        print(f"❌ 工作流文件不存在：{WORKFLOW_FILE}")
        return None

    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        wf = json.load(f)

    # 转换为 API 格式
    nodes = wf.get('nodes', [])
    api_workflow = {}

    for node in nodes:
        node_id = str(node.get('id'))
        node_type = node.get('type')
        inputs = node.get('inputs', {})

        api_node = {'class_type': node_type, 'inputs': {}}

        for k, v in inputs.items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
                # 节点连接
                api_node['inputs'][k] = [str(v[0]), v[1]]
            else:
                # 普通值
                api_node['inputs'][k] = v

        api_workflow[node_id] = api_node

    return api_workflow


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """基于官方工作流创建"""
    base_workflow = load_base_workflow()
    if not base_workflow:
        return None

    if seed is None:
        seed = int(time.time() * 1000) % 1000000

    workflow = json.loads(json.dumps(base_workflow))  # 深拷贝

    # 修改提示词
    for node_id, node in workflow.items():
        if node['class_type'] == 'CLIPTextEncode':
            inputs = node['inputs']
            if 'text' in inputs:
                # 找到正向提示词节点（通常包含<Prompt Start>）
                if '<Prompt Start>' in str(inputs.get('text', '')):
                    inputs['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt}"
                else:
                    inputs['text'] = negative

    # 修改尺寸
    for node_id, node in workflow.items():
        if node['class_type'] == 'EmptyLatentImage':
            inputs = node['inputs']
            inputs['width'] = width
            inputs['height'] = height
            inputs['batch_size'] = 1

    # 修改种子
    for node_id, node in workflow.items():
        if node['class_type'] == 'KSampler':
            inputs = node['inputs']
            inputs['seed'] = seed

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
            try:
                error_data = response.json()
                if 'node_errors' in error_data:
                    for node_id, errors in error_data['node_errors'].items():
                        for err in errors:
                            print(f"   节点{node_id}: {err.get('message', '')}")
            except:
                print(f"   错误：{response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def wait_for_completion(prompt_id, client_id, timeout=300):
    """等待完成"""
    try:
        print(f"⏳ 等待生成完成... (最多{timeout}秒)")
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
                            messages = status.get('messages', [])
                            for msg in messages:
                                if len(msg) > 1 and msg[0] == 'execution_error':
                                    err_data = msg[1]
                                    print(f"❌ 节点{err_data.get('node_id')}: {err_data.get('exception_message', '')[:200]}")
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
    if not workflow:
        return False

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
    print("😂 搞笑美女图片生成器 (官方工作流版)")
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
    print("📄 工作流：z_image_turbo_gguf.json")
    print("📐 尺寸：1024x512")
    print("🎯 模型：Z-Image-Turbo-Q8_0.gguf")
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
