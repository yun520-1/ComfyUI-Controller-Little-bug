#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 美女跳舞视频生成器
基于官方 ltx2_t2v_gguf.json 工作流
使用 LTX-2-19B GGUF 模型
"""

import json
import uuid
import time
import requests
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "ltx2_dance_videos"
OUTPUT.mkdir(parents=True, exist_ok=True)
WORKFLOW_FILE = Path.home() / "Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"

# 跳舞视频场景
SCENARIOS = [
    {
        "title": "优雅芭蕾",
        "prompt": "A beautiful young girl performing elegant ballet dance, graceful movements, pink tutu, ballet shoes, spotlight on stage, cinematic lighting, high quality, detailed",
        "negative": "blurry, low quality, still frame, frames, watermark, overlay, titles, has blurbox, has subtitles"
    },
    {
        "title": "街头街舞",
        "prompt": "A beautiful young girl doing hip hop street dance, dynamic movements, urban background, trendy outfit, energetic, cool attitude, cinematic, high quality",
        "negative": "blurry, low quality, still frame, frames, watermark, overlay, titles, has blurbox, has subtitles"
    }
]


def load_and_convert(prompt_text, negative, width=768, height=512, frames=97, seed=None):
    """加载并转换 LTX2 工作流"""
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
        
        # 跳过 Reroute 节点 - 需要重新映射链接
        if ntype == 'Reroute':
            # 找到连接到 Reroute 的节点，直接连到 Reroute 的输出
            for link in links:
                if link[1] == int(nid):  # Reroute 是源
                    reroute_out_link = link
                    # 找到 Reroute 的输入链接
                    for in_link in links:
                        if in_link[3] == int(nid):  # Reroute 是目标
                            # 重新映射：源 -> 原 Reroute 输出目标
                            for tgt_link in links:
                                if tgt_link[1] == int(nid):
                                    pass  # 需要复杂的重映射，简化处理：跳过
            continue
        
        inputs_dict = {}
        # 处理链接
        for inp in inputs_raw:
            name = inp['name']
            lid = inp.get('link')
            if lid is not None:
                # 查找链接源，如果是 Reroute，找 Reroute 的源
                src_node, src_slot = None, None
                for link in links:
                    if link[0] == lid:
                        src_node, src_slot = str(link[1]), link[2]
                        # 检查是否是 Reroute
                        for n in nodes:
                            if str(n['id']) == src_node and n['type'] == 'Reroute':
                                # 找 Reroute 的输入源
                                for in_link in links:
                                    if in_link[3] == int(src_node):
                                        src_node, src_slot = str(in_link[1]), in_link[2]
                        break
                if src_node:
                    inputs_dict[name] = [src_node, src_slot]
        
        # 处理 widgets
        wi = 0
        for inp in inputs_raw:
            name = inp['name']
            if inp.get('link') is None and wi < len(widgets):
                inputs_dict[name] = widgets[wi]
                wi += 1
        
        api_wf[nid] = {'class_type': ntype, 'inputs': inputs_dict}
    
    # 修改提示词 (节点 5 是正向，节点 6 是负向)
    if '5' in api_wf:
        api_wf['5']['inputs']['text'] = prompt_text
    if '6' in api_wf:
        api_wf['6']['inputs']['text'] = negative
    
    # 修改尺寸 (节点 14)
    if '14' in api_wf:
        api_wf['14']['inputs']['width'] = width
        api_wf['14']['inputs']['height'] = height
        api_wf['14']['inputs']['length'] = frames
        api_wf['14']['inputs']['batch_size'] = 1
    
    # 修改种子 (节点 16)
    if seed:
        if '16' in api_wf:
            api_wf['16']['inputs']['seed'] = seed
        if '32' in api_wf:
            api_wf['32']['inputs']['seed'] = seed
    
    return api_wf


def queue(api, cid):
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": cid}, timeout=30)
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ Prompt ID: {pid}")
            return pid
        print(f"❌ {r.status_code}")
        try:
            e = r.json()
            print(f"   错误详情：{json.dumps(e, indent=2, ensure_ascii=False)[:800]}")
        except:
            pass
        return None
    except Exception as ex:
        print(f"❌ {ex}")
        return None


def wait(pid, timeout=600):
    """等待视频生成完成 (视频需要更长时间)"""
    print("⏳ 等待视频生成... (最多 10 分钟)")
    t0 = time.time()
    elapsed = 0
    
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"http://{SERVER}/history/{pid}", timeout=5)
            if r.status_code == 200:
                h = r.json()
                if pid in h:
                    st = h[pid].get('status', {})
                    if st.get('completed'):
                        print("✅ 视频生成完成!")
                        return True
                    if st.get('status_str') == 'error':
                        for m in st.get('messages', []):
                            if len(m) > 1 and m[0] == 'execution_error':
                                e = m[1]
                                print(f"❌ 节点{e.get('node_id')}: {e.get('exception_message', '')[:200]}")
                        return False
                    
                    # 显示进度
                    curr = elapsed
                    elapsed = int(time.time() - t0)
                    if elapsed - curr >= 30:
                        print(f"   已等待 {elapsed}秒...")
        except:
            pass
        time.sleep(2)
    
    print("⏰ 超时")
    return False


def download_video(pid, title):
    """下载生成的视频"""
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        if r.status_code == 200:
            h = r.json()
            if pid in h:
                outputs = h[pid].get('outputs', {})
                for out in outputs.values():
                    if 'videos' in out:
                        for vid in out['videos']:
                            fn = vid.get('filename')
                            if fn:
                                vr = requests.get(f"http://{SERVER}/view?filename={fn}", timeout=60)
                                if vr.status_code == 200:
                                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    fp = OUTPUT / f"{ts}_{title}_{fn}"
                                    with open(fp, 'wb') as f:
                                        f.write(vr.content)
                                    print(f"  ✅ 视频已保存：{fp}")
                                    return str(fp)
                    # 有些工作流使用 images 输出视频帧
                    if 'images' in out:
                        print(f"   找到图片帧，可能需要合成视频")
        return None
    except Exception as e:
        print(f"❌ 下载错误：{e}")
        return None


def generate(scenario, idx):
    """生成单个视频"""
    cid = str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"[{idx}/{len(SCENARIOS)}] 生成：{scenario['title']}")
    print(f"{'='*60}")
    print(f"提示词：{scenario['prompt'][:80]}...")
    
    seed = int(time.time() * 1000) % 1000000
    wf = load_and_convert(scenario['prompt'], scenario['negative'], 768, 512, 97, seed)
    
    pid = queue(wf, cid)
    if not pid:
        return False
    
    if wait(pid):
        fp = download_video(pid, scenario['title'])
        if fp:
            print(f"✅ '{scenario['title']}' 成功!")
            return True
    
    print(f"⚠️ '{scenario['title']}' 失败")
    return False


def main():
    print("=" * 60)
    print("💃 LTX2 美女跳舞视频生成器")
    print("=" * 60)
    print()
    
    print("🔍 检查 ComfyUI...")
    try:
        r = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if r.status_code == 200:
            print(f"✅ ComfyUI: 127.0.0.1:8188")
        else:
            print(f"⚠️ 响应异常：{r.status_code}")
    except:
        print("❌ ComfyUI 未运行")
        return
    
    print()
    print("📄 工作流：ltx2_t2v_gguf.json")
    print("🎯 模型：LTX-2-19B-Q3_K_S.gguf")
    print("📐 尺寸：768x512")
    print("🎬 帧数：97 帧 (约 4 秒@25fps)")
    print(f"📁 输出：{OUTPUT}/")
    print()
    
    ok = 0
    for i, s in enumerate(SCENARIOS, 1):
        if generate(s, i):
            ok += 1
        time.sleep(5)  # 视频生成间隔长一些
    
    print()
    print("=" * 60)
    print("📊 完成")
    print("=" * 60)
    print(f"成功：{ok}/{len(SCENARIOS)}")
    if ok > 0:
        print(f"视频位置：{OUTPUT}/")
    print()


if __name__ == "__main__":
    main()
