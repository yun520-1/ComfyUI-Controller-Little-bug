#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑段子图片生成器 - 1024*512
使用 ComfyUI 生成搞笑段子配图
"""

import json, uuid, time, requests, websocket
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "funny_duanzi_images"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 最新搞笑段子（2026 年 3 月）
DUANZI_TOPICS = [
    {
        "title": "上班迟到",
        "duanzi": "老板问我为什么迟到，我说路上看到一辆法拉利，想看看里面有没有人。老板说那你现在看到了吗？我说看到了，车主正推着车走呢，没油了。",
        "prompt": "搞笑漫画风格，上班族指着路边法拉利豪车，车主推车，夸张表情，幽默场景，明亮色彩，1024x512",
        "negative": "blurry, low quality, dark, serious, realistic"
    },
    {
        "title": "减肥失败",
        "duanzi": "我：教练，我想减肥。教练：那你每天跑步、游泳、骑自行车。我：这么多？教练：不，我是说你想吃哪个。",
        "prompt": "搞笑漫画风格，健身房场景，胖学员问教练，教练指着美食，夸张对比，幽默，明亮，1024x512",
        "negative": "blurry, low quality, dark, serious"
    }
]


def create_txt2img_workflow(prompt, negative, width=1024, height=512, steps=20, cfg=7, seed=None):
    """创建文生图工作流"""
    if seed is None:
        seed = int(time.time() * 1000) % 1000000
    
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "seed": seed,
                "steps": steps
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "v1-5-pruned-emaonly.ckpt"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": height,
                "width": width
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": prompt
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": negative
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": f"FunnyDuanzi_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "images": ["8", 0]
            }
        }
    }


def queue(api, cid):
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


def monitor(pid, cid, timeout=300):
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


def download(pid, title, duanzi):
    try:
        r = requests.get(f"http://{SERVER}/history/{pid}", timeout=10)
        h = r.json()
        if pid not in h: return []
        
        outs = h[pid].get('outputs', {})
        dl = []
        
        for nid, out in outs.items():
            if 'images' in out:
                for img in out['images']:
                    fn = img.get('filename')
                    if fn:
                        p = f"?filename={fn}&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}"
                        u = f"http://{SERVER}/view{p}"
                        r2 = requests.get(u, timeout=30)
                        if r2.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fp = OUTPUT / f"{ts}_{title.replace(' ', '_')}.png"
                            with open(fp, 'wb') as f: f.write(r2.content)
                            print(f"  ✅ {fp.name}")
                            dl.append(str(fp))
                            
                            meta = {
                                "title": title,
                                "duanzi": duanzi,
                                "timestamp": datetime.now().isoformat(),
                                "size": "1024x512",
                                "style": "funny_cartoon"
                            }
                            with open(fp.with_suffix('.json'), 'w', encoding='utf-8') as f:
                                json.dump(meta, f, indent=2, ensure_ascii=False)
        return dl
    except Exception as e:
        print(f"❌ {e}")
        return []


def generate(topic, idx, total):
    print(f"\n{'='*70}")
    print(f"[{idx}/{total}] 📖 {topic['title']}")
    print(f"💬 {topic['duanzi'][:80]}...")
    print(f"🎨 {topic['prompt'][:50]}...")
    print(f"{'='*70}")
    
    # 创建工作流
    print(f"\n📝 创建工作流 (1024x512)...")
    api = create_txt2img_workflow(topic['prompt'], topic['negative'], width=1024, height=512, steps=25, cfg=7)
    
    # 提交
    cid = str(uuid.uuid4())
    pid = queue(api, cid)
    if not pid:
        return {"success": False, "error": "提交失败", "title": topic['title']}
    
    # 监控
    if not monitor(pid, cid):
        return {"success": False, "error": "超时", "title": topic['title']}
    
    # 下载
    files = download(pid, topic['title'], topic['duanzi'])
    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*70)
    print("😂 搞笑段子图片生成器")
    print("📏 1024x512")
    print("="*70)
    
    # 检查连接
    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"\n✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接：{SERVER}")
        return 1
    
    # 显示段子
    print(f"\n📖 搞笑段子 ({len(DUANZI_TOPICS)}个):")
    for i, t in enumerate(DUANZI_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择
    print(f"\n请选择:")
    print(f"  1. 生成所有 ({len(DUANZI_TOPICS)}个)")
    print(f"  2. 生成单个")
    
    c = input("\n输入 (1/2): ").strip()
    
    topics = DUANZI_TOPICS if c == '1' else ([DUANZI_TOPICS[int(input("序号: ").strip())-1]] if c == '2' else [])
    if not topics: return 1
    
    # 生成
    print(f"\n🚀 开始生成...")
    results = []
    for i, topic in enumerate(topics, 1):
        results.append(generate(topic, i, len(topics)))
        if i < len(topics): time.sleep(3)
    
    # 汇总
    print(f"\n{'='*70}")
    print("📊 结果")
    print(f"{'='*70}")
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
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n⚠️  中断"); sys.exit(1)
    except Exception as e: print(f"\n❌ {e}"); import traceback; traceback.print_exc(); sys.exit(1)
