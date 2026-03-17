#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 直接使用本地工作流
复制 z_image_turbo_gguf.json 并修改提示词
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

SCENARIOS = [
    {
        "title": "化妆前后",
        "prompt": "funny cartoon style, beautiful girl comparing makeup before and after, exaggerated contrast, humor, bright colors, comic style, 4k",
    },
    {
        "title": "自拍 vs 他拍",
        "prompt": "funny cartoon style, beautiful girl taking selfie vs someone else taking photo, funny awkward angle, exaggerated expressions, humor, bright, comic",
    }
]


def load_workflow_json():
    """直接加载 JSON 工作流文件"""
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_to_api(wf_json, prompt_text, width=1024, height=512, seed=None):
    """将 ComfyUI 工作流 JSON 转换为 API 格式"""
    nodes = wf_json.get('nodes', [])
    links = wf_json.get('links', [])
    
    # 构建链接映射
    link_map = {}
    for link in links:
        link_id, src_node, src_slot, tgt_node, tgt_slot, _ = link
        if tgt_node not in link_map:
            link_map[tgt_node] = {}
        link_map[tgt_node][tgt_slot] = [str(src_node), src_slot]
    
    api_workflow = {}
    
    for node in nodes:
        node_id = str(node.get('id'))
        node_type = node.get('type')
        
        # 跳过 Note 节点
        if node_type == 'Note':
            continue
        
        inputs_raw = node.get('inputs', [])
        widgets_values = node.get('widgets_values', [])
        
        inputs_dict = {}
        
        # 处理有链接的 inputs
        for inp in inputs_raw:
            name = inp.get('name')
            link_id = inp.get('link')
            
            if link_id is not None:
                for link in links:
                    if link[0] == link_id:
                        src_node, src_slot = link[1], link[2]
                        inputs_dict[name] = [str(src_node), src_slot]
                        break
        
        # 处理 widgets_values（按顺序对应无链接的 inputs）
        widget_idx = 0
        for inp in inputs_raw:
            name = inp.get('name')
            link_id = inp.get('link')
            
            if link_id is None and widget_idx < len(widgets_values):
                inputs_dict[name] = widgets_values[widget_idx]
                widget_idx += 1
        
        api_workflow[node_id] = {
            'class_type': node_type,
            'inputs': inputs_dict
        }
    
    # 修改提示词（节点 6 是正向，节点 7 是负向）
    if '6' in api_workflow:
        api_workflow['6']['inputs']['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt_text}"
    if '7' in api_workflow:
        api_workflow['7']['inputs']['text'] = "blurry ugly bad"
    
    # 修改尺寸（节点 13）
    if '13' in api_workflow:
        api_workflow['13']['inputs']['width'] = width
        api_workflow['13']['inputs']['height'] = height
    
    # 修改种子（节点 3）
    if seed and '3' in api_workflow:
        inputs = api_workflow['3']['inputs']
        inputs['seed'] = seed
        # 修复 sampler 和 scheduler - 确保类型正确
        inputs['sampler_name'] = 'euler'
        inputs['scheduler'] = 'simple'
        inputs['steps'] = 20
        inputs['cfg'] = 7.0
        inputs['denoise'] = 1.0
    
    return api_workflow


def queue_prompt(api, client_id):
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": client_id}, timeout=30)
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ Prompt ID: {pid}")
            return pid
        else:
            print(f"❌ {r.status_code}")
            try:
                err = r.json()
                print(f"   错误：{json.dumps(err, indent=2, ensure_ascii=False)[:600]}")
            except:
                print(f"   {r.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ {e}")
        return None


def wait_completion(pid, timeout=300):
    print("⏳ 等待...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://{SERVER}/history/{pid}", timeout=5)
            if r.status_code == 200:
                hist = r.json()
                if pid in hist:
                    status = hist[pid].get('status', {})
                    if status.get('completed'):
                        print("✅ 完成!")
                        return True
                    if status.get('status_str') == 'error':
                        for m in status.get('messages', []):
                            if len(m) > 1 and m[0] == 'execution_error':
                                err = m[1]
                                print(f"❌ 节点{err.get('node_id')}: {err.get('exception_message', '')[:150]}")
                        return False
        except:
            pass
        time.sleep(2)
    return False


def download_image(pid):
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        if r.status_code == 200:
            hist = r.json()
            if pid in hist:
                for out in hist[pid].get('outputs', {}).values():
                    for img in out.get('images', []):
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
    
    wf_json = load_workflow_json()
    seed = int(time.time() * 1000) % 1000000
    api_wf = convert_to_api(wf_json, scenario['prompt'], 1024, 512, seed)
    
    pid = queue_prompt(api_wf, client_id)
    if not pid:
        return False
    
    if wait_completion(pid):
        fp = download_image(pid)
        if fp:
            print("✅ 成功!")
            return True
    return False


def main():
    print("=" * 60)
    print("😂 搞笑美女图片生成器 (本地工作流版)")
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
    
    print(f"\n📄 工作流：{WORKFLOW_FILE.name}")
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
