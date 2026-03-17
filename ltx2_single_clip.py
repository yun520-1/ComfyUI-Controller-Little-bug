#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 使用单 CLIP 加载
修复 DualCLIPLoaderGGUF 问题
"""

import json, uuid, time, requests, websocket, copy
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT.mkdir(parents=True, exist_ok=True)
WORKFLOW_FILE = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json")

TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨", "negative": "blurry, low quality, still frame, modern clothes"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯", "negative": "blurry, low quality, still frame, modern clothes"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海", "negative": "blurry, low quality, still frame, modern ship"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速", "negative": "blurry, low quality, still frame, modern clothes"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技", "negative": "blurry, low quality, still frame, computer"}
]


def convert_with_single_clip(workflow_json, prompt_text, negative_text):
    """
    转换工作流，使用单 CLIP 代替 DualCLIPLoaderGGUF
    """
    nodes = workflow_json.get("nodes", [])
    links = workflow_json.get("links", [])

    link_map = {link[0]: {"src": str(link[1]), "src_slot": link[2], "dst": str(link[3]), "dst_slot": link[4]} for link in links}
    node_map = {str(node["id"]): node for node in nodes}

    api_prompt = {}

    for node in nodes:
        node_id = str(node["id"])
        node_type = node.get("type", "")

        if node_type in ["Note"]:
            continue

        inputs = {}
        widgets = node.get("widgets_values", [])

        # 关键修复：使用 CLIPLoader 代替 DualCLIPLoaderGGUF
        if node_type == "DualCLIPLoaderGGUF":
            # 替换为单 CLIP 加载
            node_type = "CLIPLoader"
            inputs = {
                "clip_name": "gemma-3-12b-it-qat-Q3_K_S.gguf",
                "type": "sd3"  # 使用 sd3 类型
            }
        elif node_type == "CLIPTextEncode":
            if widgets and isinstance(widgets[0], str):
                current = widgets[0]
                inputs["text"] = negative_text if "blurry" in current.lower() else prompt_text
        elif node_type == "EmptyLTXVLatentVideo" and len(widgets) >= 4:
            inputs.update({"width": widgets[0], "height": widgets[1], "length": widgets[2], "batch_size": widgets[3]})
        elif node_type == "UnetLoaderGGUF" and widgets:
            inputs["unet_name"] = widgets[0]
        elif node_type == "VAELoaderKJ" and len(widgets) >= 3:
            inputs.update({"vae_name": widgets[0], "device": widgets[1], "weight_dtype": widgets[2]})
        elif node_type == "KSamplerSelect" and widgets:
            inputs["sampler_name"] = widgets[0]
        elif node_type == "LTXVScheduler" and len(widgets) >= 5:
            inputs.update({"steps": widgets[0], "max_shift": widgets[1], "base_shift": widgets[2], "stretch": widgets[3], "terminal": widgets[4]})
        elif node_type == "CFGGuider" and widgets:
            inputs["cfg"] = widgets[0]
        elif node_type == "RandomNoise" and widgets:
            inputs["noise_seed"] = widgets[0]
        elif node_type == "LoraLoaderModelOnly" and len(widgets) >= 2:
            inputs.update({"lora_name": widgets[0], "strength_model": widgets[1]})
        elif node_type == "SaveVideo" and len(widgets) >= 3:
            inputs.update({"filename_prefix": widgets[0], "format": widgets[1], "codec": widgets[2]})
        elif node_type == "CreateVideo" and widgets:
            inputs["fps"] = widgets[0]
        elif node_type == "LTXVConditioning" and widgets:
            inputs["frame_rate"] = widgets[0]
        elif node_type == "VAEDecodeTiled" and len(widgets) >= 4:
            inputs.update({"tile_size": widgets[0], "overlap": widgets[1], "temporal_size": widgets[2], "temporal_overlap": widgets[3]})
        elif node_type == "ImageScaleBy" and len(widgets) >= 2:
            inputs.update({"upscale_method": widgets[0], "scale_by": widgets[1]})
        elif node_type == "EmptyImage" and len(widgets) >= 4:
            inputs.update({"width": widgets[0], "height": widgets[1], "batch_size": widgets[2], "color": widgets[3]})
        elif node_type == "LatentUpscaleModelLoader" and widgets:
            inputs["model_name"] = widgets[0]
        elif node_type == "ManualSigmas" and widgets:
            inputs["sigmas"] = widgets[0]
        elif node_type == "LTXVConcatAVLatent":
            pass
        elif node_type == "LTXVSeparateAVLatent":
            pass
        elif node_type == "LTXVCropGuides":
            pass
        elif node_type == "LTXVLatentUpsampler":
            pass
        elif node_type == "SamplerCustomAdvanced":
            pass
        elif node_type == "LTXVEmptyLatentAudio" and len(widgets) >= 3:
            inputs.update({"frames_number": widgets[0], "frame_rate": widgets[1], "batch_size": widgets[2]})
        elif node_type == "LTXVAudioVAEDecode":
            pass
        elif node_type == "PrimitiveInt" and widgets:
            inputs["value"] = widgets[0]
        elif node_type == "PrimitiveFloat" and widgets:
            inputs["value"] = widgets[0]
        elif node_type == "GetImageSize":
            pass
        elif node_type == "Reroute":
            continue

        # 处理输入连接
        for inp in node.get("inputs", []):
            input_name = inp.get("name")
            link_id = inp.get("link")

            if link_id and link_id in link_map and input_name:
                link_info = link_map[link_id]
                src_node_id = link_info["src"]
                src_slot = link_info["src_slot"]

                # 跳过 Reroute
                src_node = node_map.get(src_node_id, {})
                if src_node.get("type") == "Reroute":
                    for r_inp in src_node.get("inputs", []):
                        r_link_id = r_inp.get("link")
                        if r_link_id and r_link_id in link_map:
                            r_link = link_map[r_link_id]
                            src_node_id = r_link["src"]
                            src_slot = r_link["src_slot"]
                            break

                # 如果是 CLIPTextEncode 的 clip 输入，指向新的 CLIPLoader
                if node_type == "CLIPTextEncode" and input_name == "clip":
                    # 找到新的 CLIPLoader 节点 ID
                    for nid, ndata in api_prompt.items():
                        if ndata.get("class_type") == "CLIPLoader":
                            inputs[input_name] = [nid, 0]
                            break
                else:
                    inputs[input_name] = [src_node_id, int(src_slot)]

        if inputs or node_type in ["CLIPTextEncode", "CLIPLoader", "EmptyLTXVLatentVideo", "UnetLoaderGGUF", "VAELoaderKJ", "SaveVideo", "CreateVideo"]:
            api_prompt[node_id] = {
                "class_type": node_type,
                "inputs": inputs
            }

    return api_prompt


def queue(api, cid):
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": cid}, timeout=30)
        print(f"状态：{r.status_code}")
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ PID: {pid}")
            return pid
        else:
            print(f"❌ {r.text[:500]}")
    except Exception as e:
        print(f"❌ {e}")
    return None


def monitor(pid, cid, timeout=600):
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{SERVER}/ws?clientId={cid}", timeout=10)
        print("⏳ ", end="", flush=True)
        start = time.time()
        last_pct = -1

        while time.time() - start < timeout:
            try:
                msg = json.loads(ws.recv())
                if msg.get('type') == 'progress':
                    d = msg['data']
                    pct = int(d.get('value', 0) / d.get('max', 100) * 100)
                    if pct != last_pct:
                        print(f"{pct}% ", end="", flush=True)
                        last_pct = pct
                elif msg.get('type') == 'executing' and msg['data'].get('node') is None:
                    print("✅")
                    ws.close()
                    return True
            except: continue
        ws.close()
        return False
    except Exception as e:
        print(f"❌ {e}")
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
                            meta = {"title": title, "timestamp": datetime.now().isoformat(), "model": "LTX-2-19B", "style": "xianxia"}
                            with open(fp.with_suffix('.json'), 'w', encoding='utf-8') as f:
                                json.dump(meta, f, indent=2, ensure_ascii=False)
        return dl
    except Exception as e:
        print(f"❌ {e}")
        return []


def generate(topic, idx, total):
    print(f"\n{'='*60}\n[{idx}/{total}] 📰 {topic['title']}\n📝 {topic['prompt'][:50]}...\n{'='*60}")

    print(f"\n📋 加载工作流...")
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    print(f"   节点：{workflow.get('last_node_id', 0)}")

    print(f"\n🔄 转换 API (使用单 CLIP)...")
    api = convert_with_single_clip(workflow, topic['prompt'], topic['negative'])
    print(f"   API 节点：{len(api)}")

    cid = str(uuid.uuid4())
    pid = queue(api, cid)
    if not pid:
        return {"success": False, "error": "提交失败", "title": topic['title']}

    if not monitor(pid, cid):
        return {"success": False, "error": "超时", "title": topic['title']}

    files = download(pid, topic['title'])
    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*60)
    print("🎬 LTX2 仙人古装 - 单 CLIP 修复版")
    print("="*60)

    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"\n✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接：{SERVER}")
        return 1

    if not WORKFLOW_FILE.exists():
        print(f"❌ 工作流不存在")
        return 1

    print(f"\n📋 主题 ({len(TOPICS)}个):")
    for i, t in enumerate(TOPICS, 1): print(f"  {i}. {t['title']}")

    print(f"\n请选择：1.所有  2.单个  3.测试")
    c = input("输入 (1/2/3): ").strip()

    topics = TOPICS if c == '1' else ([TOPICS[int(input("序号: ").strip())-1]] if c == '2' and 1 <= int(input("序号: ").strip()) <= 5 else [TOPICS[0]]) if c == '3' else []
    if not topics: return 1

    results = []
    for i, topic in enumerate(topics, 1):
        results.append(generate(topic, i, len(topics)))
        if i < len(topics): time.sleep(5)

    print(f"\n{'='*60}\n📊 结果\n{'='*60}")
    ok = sum(1 for r in results if r.get('success'))
    print(f"✅ {ok}/{len(results)}")
    print(f"💾 {OUTPUT}")

    report = {"timestamp": datetime.now().isoformat(), "success": ok, "results": results}
    report_file = OUTPUT / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 {report_file}")

    return 0


if __name__ == "__main__":
    import sys
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n⚠️  中断"); sys.exit(1)
    except Exception as e: print(f"\n❌ {e}"); import traceback; traceback.print_exc(); sys.exit(1)
