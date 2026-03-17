#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 自动运行版
直接提交到 ComfyUI 并执行
"""

import json, uuid, time, requests, websocket
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 5 个仙人古装新闻主题
TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，动态表演", "negative": "blurry, low quality, still frame, modern clothes, microphone"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感", "negative": "blurry, low quality, still frame, modern ship, boat"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行", "negative": "blurry, low quality, still frame, modern clothes, running"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文，动态光效", "negative": "blurry, low quality, still frame, computer, modern tech"}
]

def create_minimal_api(prompt, negative):
    """创建最小化的 LTX2 API 工作流"""
    seed = int(time.time() * 1000) % 1000000

    return {
        # 1. UNet 加载
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-2-19b-dev-Q3_K_S.gguf"}},

        # 2. CLIP 加载 (DualCLIPLoaderGGUF for LTXV)
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {"clip_name1": "gemma-3-12b-it-qat-Q3_K_S.gguf", "clip_name2": "Qwen3-4B-Q8_0.gguf", "type": "ltxv"}},

        # 3. VAE 加载
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2-19b-dev_video_vae.safetensors"}},

        # 4. 正向提示词
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},

        # 5. 负面提示词
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},

        # 6. 空潜视频
        "6": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 768, "height": 512, "length": 97, "batch_size": 1}},

        # 7. LTXV 条件
        "7": {"class_type": "LTXVConditioning", "inputs": {"positive": ["4", 0], "negative": ["5", 0], "frame_rate": 25.0}},

        # 8. 噪声
        "8": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},

        # 9. 采样器
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},

        # 10. 调度器
        "10": {"class_type": "LTXVScheduler", "inputs": {"steps": 31, "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["6", 0]}},

        # 11. CFG Guider
        "11": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "cfg": 4.0}},

        # 12. 采样
        "12": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["8", 0], "guider": ["11", 0], "sampler": ["9", 0], "sigmas": ["10", 0], "latent_image": ["6", 0]}},

        # 13. VAE 解码
        "13": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["12", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64, "temporal_size": 4096, "temporal_overlap": 8}},

        # 14. 创建视频
        "14": {"class_type": "CreateVideo", "inputs": {"images": ["13", 0], "fps": 25.0}},

        # 15. 保存视频
        "15": {"class_type": "SaveVideo", "inputs": {"video": ["14", 0], "filename_prefix": f"Xianxia_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "format": "mp4", "codec": "h264"}}
    }

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
            print(f"❌ {r.text[:300]}")
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

                            # 元数据
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

    # 创建 API 工作流
    api = create_minimal_api(topic['prompt'], topic['negative'])
    print(f"📋 API 节点：{len(api)}")

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
    print("🎬 LTX2 仙人古装新闻视频 - 自动运行")
    print("📅 2026 年 3 月最新新闻")
    print("="*60)

    # 检查连接
    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"\n✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接：{SERVER}")
        return 1

    # 检查模型
    print("\n🔍 模型检查:")
    models = [
        ("unet", "ltx-2-19b-dev-Q3_K_S.gguf"),
        ("clip", "gemma-3-12b-it-qat-Q3_K_S.gguf"),
        ("vae", "ltx-2-19b-dev_video_vae.safetensors")
    ]
    for name, path in models:
        p = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI/models") / ("unet" if name == "unet" else "text_encoders" if name == "clip" else "vae") / path
        print(f"  {'✅' if p.exists() else '❌'} {name}")

    # 显示主题
    print(f"\n📋 主题 ({len(TOPICS)}个):")
    for i, t in enumerate(TOPICS, 1):
        print(f"  {i}. {t['title']}")

    # 询问模式
    print(f"\n请选择:")
    print(f"  1. 生成所有 ({len(TOPICS)}个，约 10-25 分钟)")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")

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
    print("📊 结果汇总")
    print(f"{'='*60}")
    ok = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{ok}/{len(results)}")
    print(f"💾 {OUTPUT}")

    # 报告
    report = {"timestamp": datetime.now().isoformat(), "total": len(results), "success": ok, "results": results}
    report_file = OUTPUT / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 {report_file}")

    if ok > 0:
        print(f"\n🎉 生成完成！")

    return 0

if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
