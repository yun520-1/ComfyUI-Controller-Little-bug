#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 精简工作流版
过滤掉 Note 等非执行节点
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

# 忽略的节点类型
SKIP_TYPES = ['Note']

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


def load_and_convert_workflow():
    """加载并转换工作流"""
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        wf = json.load(f)

    nodes = wf.get('nodes', [])
    api_workflow = {}

    for node in nodes:
        node_id = str(node.get('id'))
        node_type = node.get('type')

        # 跳过 Note 等非执行节点
        if node_type in SKIP_TYPES:
            continue

        inputs_raw = node.get('inputs', [])

        # 转换 inputs
        inputs_dict = {}
        for inp in inputs_raw:
            name = inp.get('name')
            value = inp.get('value')
            if value is not None:
                inputs_dict[name] = value

        api_node = {'class_type': node_type, 'inputs': inputs_dict}
        api_workflow[node_id] = api_node

    return api_workflow


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """创建工作流"""
    base = load_and_convert_workflow()
    workflow = json.loads(json.dumps(base))

    if seed is None:
        seed = int(time.time() * 1000) % 1000000

    for node_id, node in workflow.items():
        if node['class_type'] == 'CLIPTextEncode':
            inputs = node['inputs']
            if 'text' in inputs:
                text = inputs['text']
                if '<Prompt Start>' in str(text):
                    inputs['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt}"
                else:
                    inputs['text'] = negative

        if node['class_type'] in ['EmptySD3LatentImage', 'EmptyLatentImage']:
            inputs = node['inputs']
            inputs['width'] = width
            inputs['height'] = height
            inputs['batch_size'] = 1

        if node['class_type'] == 'KSampler':
            inputs = node['inputs']
            inputs['seed'] = seed

    return workflow


def queue_prompt(api, client_id):
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
            print(f"❌ {response.status_code}")
            try:
                error = response.json()
                print(f"   错误：{json.dumps(error, indent=2, ensure_ascii=False)[:500]}")
            except:
                print(f"   {response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ {e}")
        return None


def wait_for_completion(prompt_id, timeout=300):
    print(f"⏳ 等待...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://{SERVER}/history/{prompt_id}", timeout=5)
            if r.status_code == 200:
                hist = r.json()
                if prompt_id in hist:
                    status = hist[prompt_id].get('status', {})
                    if status.get('completed'):
                        print("✅ 完成!")
                        return True
                    if status.get('status_str') == 'error':
                        msgs = status.get('messages', [])
                        for m in msgs:
                            if len(m) > 1 and m[0] == 'execution_error':
                                err = m[1]
                                print(f"❌ 节点{err.get('node_id')}: {err.get('exception_message', '')[:150]}")
                        return False
        except:
            pass
        time.sleep(2)

    return False


def download_image(prompt_id):
    try:
        r = requests.get(f"http://{SERVER}/history/{prompt_id}", timeout=10)
        if r.status_code == 200:
            hist = r.json()
            if prompt_id in hist:
                outputs = hist[prompt_id].get('outputs', {})
                for out in outputs.values():
                    if 'images' in out:
                        for img in out['images']:
                            fn = img.get('filename')
                            if fn:
                                img_r = requests.get(f"http://{SERVER}/view?filename={fn}", timeout=30)
                                if img_r.status_code == 200:
                                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    fp = OUTPUT / f"{ts}_{fn}"
                                    with open(fp, 'wb') as f:
                                        f.write(img_r.content)
                                    print(f"  ✅ {fp}")
                                    return str(fp)
        return None
    except Exception as e:
        print(f"❌ {e}")
        return None


def generate(scenario, idx):
    client_id = str(uuid.uuid4())

    print(f"\n{'='*60}")
    print(f"[{idx}/2] {scenario['title']}")
    print(f"{'='*60}")

    workflow = create_workflow(scenario['prompt'], scenario['negative'], 1024, 512)

    pid = queue_prompt(workflow, client_id)
    if not pid:
        return False

    if wait_for_completion(pid):
        fp = download_image(pid)
        if fp:
            print(f"✅ 成功!")
            return True

    return False


def main():
    print("=" * 60)
    print("😂 搞笑美女图片生成器 (精简工作流版)")
    print("=" * 60)
    print()

    print("🔍 检查 ComfyUI...")
    try:
        r = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if r.status_code == 200:
            print(f"✅ ComfyUI: 127.0.0.1:8188")
    except:
        print("❌ 未运行")
        return

    print(f"\n📄 工作流：{WORKFLOW_FILE.name} (过滤 Note 节点)")
    print(f"📐 尺寸：1024x512")
    print(f"📁 输出：{OUTPUT}/")
    print()

    ok = 0
    for i, s in enumerate(SCENARIOS, 1):
        if generate(s, i):
            ok += 1
        time.sleep(3)

    print()
    print("=" * 60)
    print(f"成功：{ok}/{len(SCENARIOS)}")
    print(f"图片：{OUTPUT}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
