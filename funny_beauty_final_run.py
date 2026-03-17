#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑美女图片生成器 - 最终运行版
基于官方 z_image_turbo_gguf.json 工作流
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
    {"title": "化妆前后", "prompt": "funny cartoon style, beautiful girl comparing makeup before and after, exaggerated contrast, humor, bright colors, comic style, 4k"},
    {"title": "自拍 vs 他拍", "prompt": "funny cartoon style, beautiful girl taking selfie vs someone else taking photo, funny awkward angle, exaggerated expressions, humor, bright, comic"}
]

def load_and_convert(prompt_text, width=1024, height=512, seed=None):
    """加载并转换工作流"""
    with open(WORKFLOW_FILE, 'r') as f:
        wf = json.load(f)
    
    nodes = wf.get('nodes', [])
    links = wf.get('links', [])
    
    # 构建链接映射
    link_map = {}
    for link in links:
        link_id, src, src_slot, tgt, tgt_slot, _ = link
        link_map.setdefault(tgt, {})[tgt_slot] = [str(src), src_slot]
    
    api_wf = {}
    for node in nodes:
        nid = str(node['id'])
        ntype = node['type']
        if ntype == 'Note':
            continue
        
        inputs_raw = node.get('inputs', [])
        widgets = node.get('widgets_values', [])
        
        inputs_dict = {}
        # 处理链接
        for inp in inputs_raw:
            name = inp['name']
            lid = inp.get('link')
            if lid is not None:
                for link in links:
                    if link[0] == lid:
                        inputs_dict[name] = [str(link[1]), link[2]]
                        break
        
        # 处理 widgets
        wi = 0
        for inp in inputs_raw:
            name = inp['name']
            if inp.get('link') is None and wi < len(widgets):
                inputs_dict[name] = widgets[wi]
                wi += 1
        
        api_wf[nid] = {'class_type': ntype, 'inputs': inputs_dict}
    
    # 修改提示词 (节点 6)
    if '6' in api_wf:
        api_wf['6']['inputs']['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt_text}"
    # 负面提示词 (节点 7)
    if '7' in api_wf:
        api_wf['7']['inputs']['text'] = "blurry ugly bad"
    # 尺寸 (节点 13)
    if '13' in api_wf:
        api_wf['13']['inputs']['width'] = width
        api_wf['13']['inputs']['height'] = height
    # 种子和参数 (节点 3)
    if seed and '3' in api_wf:
        api_wf['3']['inputs']['seed'] = seed
        api_wf['3']['inputs']['sampler_name'] = 'euler'
        api_wf['3']['inputs']['scheduler'] = 'simple'
        api_wf['3']['inputs']['steps'] = 20
        api_wf['3']['inputs']['cfg'] = 7.0
        api_wf['3']['inputs']['denoise'] = 1.0
    
    return api_wf

def queue(api, cid):
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": cid}, timeout=30)
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ {pid}")
            return pid
        print(f"❌ {r.status_code}")
        try:
            e = r.json()
            if 'node_errors' in e:
                for n, errs in e['node_errors'].items():
                    for err in errs:
                        print(f"   节点{n}: {err.get('message', '')[:100]}")
        except: pass
        return None
    except Exception as ex:
        print(f"❌ {ex}")
        return None

def wait(pid, timeout=300):
    print("⏳ 等待...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"http://{SERVER}/history/{pid}", timeout=5)
            if r.status_code == 200:
                h = r.json()
                if pid in h:
                    st = h[pid].get('status', {})
                    if st.get('completed'):
                        print("✅ 完成!")
                        return True
                    if st.get('status_str') == 'error':
                        for m in st.get('messages', []):
                            if len(m) > 1 and m[0] == 'execution_error':
                                e = m[1]
                                print(f"❌ 节点{e.get('node_id')}: {e.get('exception_message', '')[:150]}")
                        return False
        except: pass
        time.sleep(2)
    return False

def download(pid):
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        if r.status_code == 200:
            h = r.json()
            if pid in h:
                for out in h[pid].get('outputs', {}).values():
                    for img in out.get('images', []):
                        fn = img.get('filename')
                        if fn:
                            ir = requests.get(f"http://{SERVER}/view?filename={fn}", timeout=30)
                            if ir.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fp = OUTPUT / f"{ts}_{fn}"
                                with open(fp, 'wb') as f:
                                    f.write(ir.content)
                                print(f"  ✅ {fp}")
                                return str(fp)
        return None
    except Exception as e:
        print(f"❌ {e}")
        return None

def gen(scenario, idx):
    cid = str(uuid.uuid4())
    print(f"\n{'='*50}")
    print(f"[{idx}/2] {scenario['title']}")
    print(f"{'='*50}")
    
    seed = int(time.time() * 1000) % 1000000
    wf = load_and_convert(scenario['prompt'], 1024, 512, seed)
    
    pid = queue(wf, cid)
    if not pid:
        return False
    
    if wait(pid):
        fp = download(pid)
        if fp:
            print("✅ 成功!")
            return True
    return False

def main():
    print("=" * 50)
    print("😂 搞笑美女图片生成")
    print("=" * 50)
    
    try:
        r = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if r.status_code != 200:
            print("❌ ComfyUI 未运行")
            return
    except:
        print("❌ ComfyUI 未运行")
        return
    
    print(f"📁 输出：{OUTPUT}/")
    print()
    
    ok = 0
    for i, s in enumerate(SCENARIOS, 1):
        if gen(s, i):
            ok += 1
        time.sleep(2)
    
    print()
    print("=" * 50)
    print(f"成功：{ok}/{len(SCENARIOS)}")
    if ok > 0:
        print(f"图片位置：{OUTPUT}/")
    print("=" * 50)

if __name__ == "__main__":
    main()
