#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 美女跳舞视频生成器 - 修复版
直接复制官方 ltx2_t2v_gguf.json 工作流，正确处理 Reroute 节点
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

SCENARIOS = [
    {
        "title": "优雅芭蕾",
        "prompt": "A beautiful young girl performing elegant ballet dance, graceful movements, pink tutu, ballet shoes, spotlight on stage, cinematic lighting, high quality, detailed",
    },
    {
        "title": "街头街舞",
        "prompt": "A beautiful young girl doing hip hop street dance, dynamic movements, urban background, trendy outfit, energetic, cool attitude, cinematic, high quality",
    }
]


def load_and_convert(prompt_text, width=768, height=512, frames=97, seed=None):
    """加载并转换工作流 - 保留 Reroute 节点"""
    with open(WORKFLOW_FILE, 'r') as f:
        wf = json.load(f)
    
    nodes = wf.get('nodes', [])
    links = wf.get('links', [])  # [link_id, src_node, src_slot, tgt_node, tgt_slot, type]
    
    # 构建链接映射：target -> {slot: (src, slot)}
    link_map = {}
    for link in links:
        lid, src, src_slot, tgt, tgt_slot, _ = link
        link_map.setdefault(tgt, {})[tgt_slot] = (src, src_slot)
    
    # 构建节点 ID -> 类型映射
    node_types = {node['id']: node['type'] for node in nodes}
    
    api_wf = {}
    
    for node in nodes:
        nid = node['id']
        ntype = node['type']
        
        # 跳过 Note 节点
        if ntype == 'Note':
            continue
        
        # Reroute 节点特殊处理 - 保留但简化
        if ntype == 'Reroute':
            # 找到 Reroute 的输入源
            inputs_raw = node.get('inputs', [])
            for inp in inputs_raw:
                if inp.get('name') == 'input':
                    lid = inp.get('link')
                    if lid:
                        # 找到输入链接的源
                        for link in links:
                            if link[0] == lid:
                                src_node, src_slot = link[1], link[2]
                                # 找到所有使用此 Reroute 输出的节点，重定向
                                for tgt_link in links:
                                    if tgt_link[1] == nid:  # Reroute 是源
                                        tgt_node, tgt_slot = tgt_link[3], tgt_link[4]
                                        # 这个会在处理目标节点时处理
                                break
            continue  # 跳过 Reroute 节点本身
        
        inputs_raw = node.get('inputs', [])
        widgets = node.get('widgets_values', [])
        
        inputs_dict = {}
        
        # 处理有链接的 inputs
        for inp in inputs_raw:
            name = inp['name']
            lid = inp.get('link')
            
            if lid is not None:
                # 查找链接源
                for link in links:
                    if link[0] == lid:
                        src_node, src_slot = link[1], link[2]
                        
                        # 如果源是 Reroute，找 Reroute 的输入
                        if node_types.get(src_node) == 'Reroute':
                            for in_link in links:
                                if in_link[3] == src_node:  # Reroute 是目标
                                    src_node, src_slot = in_link[1], in_link[2]
                                    # 递归处理多层 Reroute
                                    while node_types.get(src_node) == 'Reroute':
                                        for deeper_link in links:
                                            if deeper_link[3] == src_node:
                                                src_node, src_slot = deeper_link[1], deeper_link[2]
                                                break
                                        else:
                                            break
                        
                        inputs_dict[name] = [str(src_node), src_slot]
                        break
        
        # 处理 widgets_values
        wi = 0
        for inp in inputs_raw:
            name = inp['name']
            if inp.get('link') is None and wi < len(widgets):
                inputs_dict[name] = widgets[wi]
                wi += 1
        
        api_wf[str(nid)] = {'class_type': ntype, 'inputs': inputs_dict}
    
    # 修改提示词 (节点 5 是正向)
    if '5' in api_wf:
        api_wf['5']['inputs']['text'] = prompt_text
    
    # 修改尺寸和帧数 (节点 14: EmptyLTXVLatentVideo)
    if '14' in api_wf:
        inputs = api_wf['14']['inputs']
        inputs['width'] = width
        inputs['height'] = height
        inputs['length'] = frames
        inputs['batch_size'] = 1
    
    # 修改 LTXVEmptyLatentAudio (节点 13) - 音频帧数必须与视频一致
    if '13' in api_wf:
        inputs = api_wf['13']['inputs']
        inputs['length'] = frames  # 音频长度 (帧数)
        inputs['frame_rate'] = 25
        inputs['batch_size'] = 1
    
    # 修改 LTXVConditioning (节点 23) - 帧率
    if '23' in api_wf:
        api_wf['23']['inputs']['frame_rate'] = 25
    
    # 修改 PrimitiveInt (节点 10) - 总帧数
    if '10' in api_wf:
        api_wf['10']['inputs']['value'] = frames
    
    # 修改 PrimitiveInt (节点 11) - 可能也是帧数相关
    if '11' in api_wf:
        api_wf['11']['inputs']['value'] = frames
    
    # 修改种子 (节点 16 和 32)
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
            if 'node_errors' in e:
                for n, errs in e['node_errors'].items():
                    for err in errs:
                        print(f"   节点{n}: {err.get('message', '')[:200]}")
            elif 'error' in e:
                print(f"   {e['error'].get('message', '')[:200]}")
        except:
            pass
        return None
    except Exception as ex:
        print(f"❌ {ex}")
        return None


def wait(pid, timeout=900):
    """等待视频生成 (最长 15 分钟)"""
    print("⏳ 等待视频生成...")
    t0 = time.time()
    last_report = 0
    
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
                                print(f"❌ 节点{e.get('node_id')}: {e.get('exception_message', '')[:200]}")
                        return False
            
            # 每 30 秒报告进度
            elapsed = int(time.time() - t0)
            if elapsed - last_report >= 30:
                print(f"   已等待 {elapsed}秒...")
                last_report = elapsed
        except:
            pass
        time.sleep(2)
    
    print("⏰ 超时")
    return False


def download_video(pid, title):
    """下载视频"""
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        if r.status_code == 200:
            h = r.json()
            if pid in h:
                outputs = h[pid].get('outputs', {})
                for nid, out in outputs.items():
                    # 视频
                    for vid in out.get('videos', []):
                        fn = vid.get('filename')
                        if fn:
                            vr = requests.get(f"http://{SERVER}/view?filename={fn}", timeout=120)
                            if vr.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                ext = Path(fn).suffix or '.mp4'
                                fp = OUTPUT / f"{ts}_{title}{ext}"
                                with open(fp, 'wb') as f:
                                    f.write(vr.content)
                                print(f"  ✅ 视频：{fp}")
                                return str(fp)
                    
                    # 图片帧
                    for img in out.get('images', []):
                        fn = img.get('filename')
                        if fn:
                            ir = requests.get(f"http://{SERVER}/view?filename={fn}", timeout=60)
                            if ir.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fp = OUTPUT / f"{ts}_{title}_{fn}"
                                with open(fp, 'wb') as f:
                                    f.write(ir.content)
                                print(f"  ✅ 帧：{fp}")
        return None
    except Exception as e:
        print(f"❌ {e}")
        return None


def generate(scenario, idx):
    cid = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"[{idx}/{len(SCENARIOS)}] {scenario['title']}")
    print(f"{'='*60}")
    print(f"提示词：{scenario['prompt'][:70]}...")
    
    seed = int(time.time() * 1000) % 1000000
    wf = load_and_convert(scenario['prompt'], 768, 512, 97, seed)
    
    pid = queue(wf, cid)
    if not pid:
        return False
    
    if wait(pid):
        fp = download_video(pid, scenario['title'])
        if fp:
            print(f"✅ 成功!")
            return True
    
    print(f"⚠️ 失败")
    return False


def main():
    print("=" * 60)
    print("💃 LTX2 美女跳舞视频生成器 (修复版)")
    print("=" * 60)
    print()
    
    print("🔍 检查 ComfyUI...")
    try:
        r = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if r.status_code == 200:
            print(f"✅ ComfyUI: 127.0.0.1:8188")
    except:
        print("❌ ComfyUI 未运行")
        return
    
    print(f"\n📄 工作流：ltx2_t2v_gguf.json")
    print("🎯 模型：LTX-2-19B-Q3_K_S.gguf")
    print("📐 尺寸：768x512")
    print("🎬 帧数：97 帧 (~4 秒@25fps)")
    print(f"📁 输出：{OUTPUT}/")
    print()
    
    ok = 0
    for i, s in enumerate(SCENARIOS, 1):
        if generate(s, i):
            ok += 1
        time.sleep(5)
    
    print()
    print("=" * 60)
    print(f"成功：{ok}/{len(SCENARIOS)}")
    if ok > 0:
        print(f"视频：{OUTPUT}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
