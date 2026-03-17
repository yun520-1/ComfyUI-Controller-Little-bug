#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 正确的工作流转换版
直接读取原始工作流文件并正确转换为 API 格式
"""

import json, uuid, time, requests, websocket, copy
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT.mkdir(parents=True, exist_ok=True)
WORKFLOW_FILE = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json")

TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台", "negative": "blurry, low quality, still frame, modern clothes, microphone"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚", "negative": "blurry, low quality, still frame, modern ship, boat"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格", "negative": "blurry, low quality, still frame, modern clothes, running"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合", "negative": "blurry, low quality, still frame, computer, modern tech"}
]


def convert_workflow_to_api(workflow_json, prompt_text, negative_text):
    """
    正确转换 ComfyUI 工作流为 API 格式
    保留所有节点连接
    """
    nodes = workflow_json.get("nodes", [])
    links = workflow_json.get("links", [])

    # 创建 link 查找表：link_id -> (src_node_id, src_slot, dst_node_id, dst_slot)
    link_map = {}
    for link in links:
        link_id, src_node_id, src_slot, dst_node_id, dst_slot = link[0], str(link[1]), link[2], str(link[3]), link[4]
        link_map[link_id] = {
            "src": src_node_id,
            "src_slot": src_slot,
            "dst": dst_node_id,
            "dst_slot": dst_slot
        }

    # 创建节点查找表
    node_map = {str(node["id"]): node for node in nodes}

    # 构建 API prompt
    api_prompt = {}

    for node in nodes:
        node_id = str(node["id"])
        node_type = node.get("type", "")

        # 跳过不需要提交的节点
        if node_type in ["Note"]:
            continue

        # 提取 inputs
        inputs = {}

        # 1. 处理 widget 值
        widgets = node.get("widgets_values", [])

        if node_type == "CLIPTextEncode":
            if widgets and isinstance(widgets[0], str):
                current = widgets[0]
                # 更新提示词
                if "blurry" in current.lower() or "low quality" in current.lower():
                    inputs["text"] = negative_text
                else:
                    inputs["text"] = prompt_text
        elif node_type == "EmptyLTXVLatentVideo" and len(widgets) >= 4:
            inputs.update({"width": widgets[0], "height": widgets[1], "length": widgets[2], "batch_size": widgets[3]})
        elif node_type == "UnetLoaderGGUF" and widgets:
            inputs["unet_name"] = widgets[0]
        elif node_type == "DualCLIPLoaderGGUF" and len(widgets) >= 3:
            inputs.update({"clip_name1": widgets[0], "clip_name2": widgets[1], "type": widgets[2]})
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
            pass  # 无 widget
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
            continue  # 跳过 Reroute，直接连接

        # 2. 处理输入连接
        for inp in node.get("inputs", []):
            input_name = inp.get("name")
            link_id = inp.get("link")

            if link_id and link_id in link_map and input_name:
                link_info = link_map[link_id]
                src_node_id = link_info["src"]
                src_slot = link_info["src_slot"]

                # 跳过 Reroute 节点，找到实际源
                src_node = node_map.get(src_node_id, {})
                if src_node.get("type") == "Reroute":
                    # 找到 Reroute 的输入
                    for r_inp in src_node.get("inputs", []):
                        r_link_id = r_inp.get("link")
                        if r_link_id and r_link_id in link_map:
                            r_link = link_map[r_link_id]
                            src_node_id = r_link["src"]
                            src_slot = r_link["src_slot"]
                            break

                inputs[input_name] = [src_node_id, int(src_slot)]

        # 添加到 API prompt
        if inputs or node_type in ["CLIPTextEncode", "EmptyLTXVLatentVideo", "UnetLoaderGGUF", "VAELoaderKJ", "DualCLIPLoaderGGUF", "SaveVideo", "CreateVideo"]:
            api_prompt[node_id] = {
                "class_type": node_type,
                "inputs": inputs
            }

    return api_prompt


def queue(api, cid):
    """提交任务"""
    try:
        r = requests.post(f"http://{SERVER}/prompt", json={"prompt": api, "client_id": cid}, timeout=30)
        print(f"状态：{r.status_code}")
        if r.status_code == 200:
            pid = r.json().get('prompt_id')
            print(f"✅ PID: {pid}")
            return pid
        else:
            print(f"❌ {r.text[:500]}")
            try:
                err = r.json()
                print(f"错误：{json.dumps(err, indent=2, ensure_ascii=False)[:1000]}")
            except: pass
    except Exception as e:
        print(f"❌ {e}")
    return None


def monitor(pid, cid, timeout=600):
    """监控进度"""
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
    """下载结果"""
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        h = r.json()
        if pid not in h:
            print("❌ 无历史记录")
            return []

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
                            with open(fp, 'wb') as f:
                                f.write(r2.content)
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
    """生成单个视频"""
    print(f"\n{'='*60}")
    print(f"[{idx}/{total}] 📰 {topic['title']}")
    print(f"📝 {topic['prompt'][:50]}...")
    print(f"{'='*60}")

    # 加载工作流
    print(f"\n📋 加载工作流...")
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    print(f"   节点：{workflow.get('last_node_id', 0)}, 连接：{len(workflow.get('links', []))}")

    # 转换为 API 格式
    print(f"\n🔄 转换 API 格式...")
    api = convert_workflow_to_api(workflow, topic['prompt'], topic['negative'])
    print(f"   API 节点：{len(api)}")

    # 提交
    cid = str(uuid.uuid4())
    pid = queue(api, cid)
    if not pid:
        return {"success": False, "error": "提交失败", "title": topic['title']}

    # 监控
    if not monitor(pid, cid):
        return {"success": False, "error": "超时", "title": topic['title']}

    # 下载
    files = download(pid, topic['title'])
    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*60)
    print("🎬 LTX2 仙人古装新闻视频 - 正确转换版")
    print("📅 2026 年 3 月最新新闻")
    print("="*60)

    # 检查连接
    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"\n✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接：{SERVER}")
        return 1

    # 检查工作流
    if not WORKFLOW_FILE.exists():
        print(f"❌ 工作流不存在：{WORKFLOW_FILE}")
        return 1
    print(f"✅ 工作流：{WORKFLOW_FILE.name}")

    # 显示主题
    print(f"\n📋 主题 ({len(TOPICS)}个):")
    for i, t in enumerate(TOPICS, 1):
        print(f"  {i}. {t['title']}")

    # 选择模式
    print(f"\n请选择:")
    print(f"  1. 生成所有  2. 生成单个  3. 测试第一个")
    c = input("\n输入 (1/2/3): ").strip()

    topics = []
    if c == '1':
        topics = TOPICS
    elif c == '2':
        idx = int(input("序号 (1-5): ").strip())
        topics = [TOPICS[idx-1]] if 1 <= idx <= 5 else []
    elif c == '3':
        topics = [TOPICS[0]]

    if not topics:
        print("❌ 无效选择")
        return 1

    # 生成
    print(f"\n🚀 开始生成...")
    results = []
    for i, topic in enumerate(topics, 1):
        results.append(generate(topic, i, len(topics)))
        if i < len(topics):
            print("\n⏸️  等待 5 秒...")
            time.sleep(5)

    # 汇总
    print(f"\n{'='*60}")
    print("📊 结果")
    print(f"{'='*60}")
    ok = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{ok}/{len(results)}")
    print(f"💾 {OUTPUT}")

    # 报告
    report = {"timestamp": datetime.now().isoformat(), "success": ok, "results": results}
    report_file = OUTPUT / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 {report_file}")

    if ok > 0:
        print(f"\n🎉 完成！")

    return 0


if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
