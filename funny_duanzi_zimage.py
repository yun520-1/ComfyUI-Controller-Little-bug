#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搞笑段子图片生成器 - 使用 Z-Image-Turbo 模型
1024*512 分辨率
"""

import json, uuid, time, requests, websocket
from pathlib import Path
from datetime import datetime

SERVER = "127.0.0.1:8188"
OUTPUT = Path.home() / "Downloads" / "funny_duanzi_images"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 搞笑段子
DUANZI = [
    {"title": "上班迟到", "duanzi": "老板问我为什么迟到，我说路上看到一辆法拉利。老板说那你现在看到了吗？我说看到了，车主正推着车走呢，没油了。", "prompt": "funny cartoon style, office worker pointing at Ferrari sports car, car owner pushing car, exaggerated expressions, humor, bright colors, comic", "negative": "blurry, low quality, dark, serious, realistic, nsfw"},
    {"title": "减肥失败", "duanzi": "教练，我想减肥。教练：那你每天跑步、游泳、骑自行车。我：这么多？教练：不，我是说你想吃哪个。", "prompt": "funny cartoon style, gym scene, fat student asking coach, coach pointing at food, exaggerated contrast, humor, bright, comic style", "negative": "blurry, low quality, dark, serious, nsfw"}
]


def create_workflow(prompt, negative, width=1024, height=512, seed=None):
    """使用 Z-Image-Turbo GGUF 模型创建工作流"""
    if seed is None:
        seed = int(time.time() * 1000) % 1000000
    
    return {
        # 1. UNet 加载
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
        
        # 2. CLIP 加载
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip_l.safetensors", "type": "sd1x"}},
        
        # 3. VAE 加载
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        
        # 4. 正向提示词
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        
        # 5. 负面提示词
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        
        # 6. 空潜图
        "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": height, "width": width}},
        
        # 7. KSampler
        "7": {"class_type": "KSampler", "inputs": {
            "cfg": 7, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0],
            "negative": ["5", 0], "positive": ["4", 0],
            "sampler_name": "euler_ancestral", "scheduler": "normal", "seed": seed, "steps": 20
        }},
        
        # 8. VAE 解码
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        
        # 9. 保存图片
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"FunnyDuanzi_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "images": ["8", 0]}}
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
            print(f"❌ {r.text[:400]}")
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
                            
                            meta = {"title": title, "duanzi": duanzi, "timestamp": datetime.now().isoformat(), "size": "1024x512"}
                            with open(fp.with_suffix('.json'), 'w', encoding='utf-8') as f:
                                json.dump(meta, f, indent=2, ensure_ascii=False)
        return dl
    except Exception as e:
        print(f"❌ {e}")
        return []


def generate(topic, idx, total):
    print(f"\n{'='*70}\n[{idx}/{total}] 📖 {topic['title']}\n💬 {topic['duanzi'][:60]}...\n🎨 {topic['prompt'][:50]}...\n{'='*70}")
    
    print(f"\n📝 创建工作流 (1024x512)...")
    api = create_workflow(topic['prompt'], topic['negative'], width=1024, height=512)
    
    cid = str(uuid.uuid4())
    pid = queue(api, cid)
    if not pid: return {"success": False, "title": topic['title']}
    
    if not monitor(pid, cid): return {"success": False, "title": topic['title']}
    
    files = download(pid, topic['title'], topic['duanzi'])
    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*70)
    print("😂 搞笑段子图片生成 - Z-Image-Turbo")
    print("📏 1024x512")
    print("="*70)
    
    try:
        r = requests.get(f"http://{SERVER}/system_stats", timeout=5)
        print(f"\n✅ ComfyUI: {SERVER}")
    except:
        print(f"❌ 无法连接")
        return 1
    
    print(f"\n📖 段子 ({len(DUANZI)}个):")
    for i, t in enumerate(DUANZI, 1): print(f"  {i}. {t['title']}")
    
    c = input("\n选择 (1 所有/2 单个): ").strip()
    topics = DUANZI if c == '1' else ([DUANZI[int(input("序号: ").strip())-1]] if c == '2' else [])
    if not topics: return 1
    
    results = []
    for i, topic in enumerate(topics, 1):
        results.append(generate(topic, i, len(topics)))
        if i < len(topics): time.sleep(3)
    
    print(f"\n{'='*70}\n📊 结果\n{'='*70}")
    ok = sum(1 for r in results if r.get('success'))
    print(f"✅ {ok}/{len(results)}")
    print(f"💾 {OUTPUT}")
    
    report = {"timestamp": datetime.now().isoformat(), "success": ok, "results": results}
    report_file = OUTPUT / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 {report_file}")
    
    if ok > 0: print(f"\n🎉 完成！")
    return 0


if __name__ == "__main__":
    import sys
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n⚠️  中断"); sys.exit(1)
    except Exception as e: print(f"\n❌ {e}"); import traceback; traceback.print_exc(); sys.exit(1)
