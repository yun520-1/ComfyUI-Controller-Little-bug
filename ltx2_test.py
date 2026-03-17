#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 快速测试版
"""

import json, uuid, time, requests, websocket, copy
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT.mkdir(parents=True, exist_ok=True)
WORKFLOW = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json")

TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨", "negative": "blurry, low quality, modern clothes"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会", "negative": "blurry, low quality, modern clothes"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法", "negative": "blurry, low quality, modern ship"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开", "negative": "blurry, low quality, modern clothes"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技", "negative": "blurry, low quality, computer"}
]

def load_wf():
    with open(WORKFLOW) as f: return json.load(f)

def update_prompts(wf, p, n):
    for node in wf.get("nodes", []):
        if node.get("type") == "CLIPTextEncode":
            w = node.get("widgets_values", [])
            if w and isinstance(w[0], str):
                node["widgets_values"][0] = n if "blurry" in w[0].lower() else p
    return wf

def to_api(wf):
    api = {}
    nodes, links = wf.get("nodes", []), {l[0]: l for l in wf.get("links", [])}
    for node in nodes:
        nid, ntype = str(node["id"]), node.get("type", "")
        if ntype in ["Reroute", "Note", "PrimitiveNode", "GetImageSize"]: continue
        inputs = {}
        w = node.get("widgets_values", [])
        if ntype == "CLIPTextEncode" and w: inputs["text"] = w[0]
        elif ntype == "EmptyLTXVLatentVideo" and len(w) >= 4: inputs.update({"width": w[0], "height": w[1], "length": w[2], "batch_size": w[3]})
        elif ntype == "UnetLoaderGGUF" and w: inputs["unet_name"] = w[0]
        elif ntype == "DualCLIPLoaderGGUF" and len(w) >= 2: inputs.update({"clip_name1": w[0], "clip_name2": w[1], "type": w[2] if len(w) > 2 else "ltxv"})
        elif ntype == "VAELoaderKJ" and w: inputs.update({"vae_name": w[0], "device": w[1] if len(w) > 1 else "main_device"})
        elif ntype == "KSamplerSelect" and w: inputs["sampler_name"] = w[0]
        elif ntype == "LTXVScheduler" and len(w) >= 5: inputs.update({"steps": w[0], "max_shift": w[1], "base_shift": w[2], "stretch": w[3], "terminal": w[4]})
        elif ntype == "CFGGuider" and w: inputs["cfg"] = w[0]
        elif ntype == "RandomNoise" and w: inputs["noise_seed"] = w[0]
        elif ntype == "LoraLoaderModelOnly" and len(w) >= 2: inputs.update({"lora_name": w[0], "strength_model": w[1]})
        elif ntype == "SaveVideo" and w: inputs.update({"filename_prefix": w[0], "format": w[1] if len(w) > 1 else "mp4"})
        elif ntype == "CreateVideo" and w: inputs["fps"] = w[0]
        elif ntype == "LTXVConditioning" and w: inputs["frame_rate"] = w[0]
        
        for inp in node.get("inputs", []):
            iname, lid = inp.get("name"), inp.get("link")
            if lid and lid in links and iname:
                l = links[lid]
                sid, so = str(l[1]), l[2]
                sn = next((n for n in nodes if str(n["id"]) == sid), None)
                if sn and sn.get("type") == "Reroute":
                    for ri in sn.get("inputs", []):
                        rlid = ri.get("link")
                        if rlid and rlid in links:
                            rl = links[rlid]
                            sid, so = str(rl[1]), rl[2]
                            break
                inputs[iname] = [sid, so]
        
        if inputs or ntype in ["CLIPTextEncode", "EmptyLTXVLatentVideo", "UnetLoaderGGUF", "VAELoaderKJ", "DualCLIPLoaderGGUF"]:
            api[nid] = {"class_type": ntype, "inputs": inputs}
    return api

def queue(api, cid):
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": cid}, timeout=30)
        print(f"提交状态：{r.status_code}")
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ PID: {pid}")
            return pid
        else:
            print(f"错误：{r.text[:500]}")
            try: print(f"JSON: {r.json()}")
            except: pass
    except Exception as e:
        print(f"异常：{e}")
    return None

def monitor(pid, cid, timeout=600):
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{SERVER}/ws?clientId={cid}", timeout=10)
        print("⏳ 监控中...", end=" ", flush=True)
        start = time.time()
        while time.time() - start < timeout:
            try:
                msg = json.loads(ws.recv())
                t = msg.get('type')
                if t == 'progress':
                    d = msg.get('data', {})
                    pct = int(d.get('value', 0) / d.get('max', 100) * 100)
                    print(f"{pct}%", end=" ", flush=True)
                elif t == 'executing' and msg['data'].get('node') is None:
                    print("✅")
                    ws.close()
                    return True
            except: continue
        ws.close()
        return False
    except Exception as e:
        print(f"监控异常：{e}")
        return False

def download(pid, title):
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        h = r.json()
        if pid not in h: return []
        outs = h[pid].get('outputs', {})
        dl = []
        for nid, out in outs.items():
            for k, items in [('video', out.get('video', [])), ('images', out.get('images', []))]:
                for it in items:
                    fn = it.get('filename')
                    if fn:
                        p = f"?filename={fn}&subfolder={it.get('subfolder', '')}&type={it.get('type', 'output')}"
                        u = f"http://{SERVER}/view{p}"
                        r2 = requests.get(u, timeout=120 if k == 'video' else 30)
                        if r2.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fp = OUTPUT / f"{ts}_{title.replace(' ', '_')}.{'mp4' if k == 'video' else 'png'}"
                            with open(fp, 'wb') as f: f.write(r2.content)
                            print(f"  ✅ {fp.name}")
                            dl.append(str(fp))
        return dl
    except Exception as e:
        print(f"下载异常：{e}")
        return []

def main():
    print("="*60)
    print("🎬 LTX2 仙人古装新闻视频")
    print("="*60)
    
    # 检查连接
    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接：{SERVER}")
        return 1
    
    # 检查模型
    print("\n🔍 模型:")
    for name, path in [("unet", "ltx-2-19b-dev-Q3_K_S.gguf"), ("clip", "gemma-3-12b-it-qat-Q3_K_S.gguf"), ("vae", "ltx-2-19b-dev_video_vae.safetensors")]:
        p = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI/models") / ("unet" if name == "unet" else "text_encoders" if name == "clip" else "vae") / path
        print(f"  {'✅' if p.exists() else '❌'} {name}: {path}")
    
    # 显示主题
    print(f"\n📋 主题 ({len(TOPICS)}个):")
    for i, t in enumerate(TOPICS, 1): print(f"  {i}. {t['title']}")
    
    # 选择
    c = input("\n选择 (1 所有/2 单个/3 测试): ").strip()
    topics = TOPICS if c == '1' else ([TOPICS[int(input("序号: ").strip())-1]] if c == '2' else [TOPICS[0]]) if c == '3' else []
    if not topics: return 1
    
    # 生成
    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n{'='*60}\n[{i}/{len(topics)}] {topic['title']}\n{'='*60}")
        
        wf = update_prompts(load_wf(), topic['prompt'], topic['negative'])
        api = to_api(wf)
        print(f"API 节点：{len(api)}")
        
        cid = str(uuid.uuid4())
        pid = queue(api, cid)
        
        if pid:
            if monitor(pid, cid):
                files = download(pid, topic['title'])
                results.append({"title": topic['title'], "success": len(files) > 0, "files": files})
            else:
                results.append({"title": topic['title'], "success": False, "error": "超时"})
        else:
            results.append({"title": topic['title'], "success": False, "error": "提交失败"})
        
        if i < len(topics): time.sleep(5)
    
    # 汇总
    print(f"\n{'='*60}\n结果\n{'='*60}")
    ok = sum(1 for r in results if r.get('success'))
    print(f"✅ {ok}/{len(results)}")
    print(f"💾 {OUTPUT}")
    
    return 0

if __name__ == "__main__": exit(main())
