#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 最小化 API 版本
直接构建最小可用的工作流，跳过复杂节点
"""

import json
import uuid
import time
import requests
from pathlib import Path
from datetime import datetime
import websocket
import sys

# 配置
COMFYUI_SERVER = "127.0.0.1:8189"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台", "negative": "blurry, low quality, still frame, modern clothes, microphone"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚", "negative": "blurry, low quality, still frame, modern ship, boat"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格", "negative": "blurry, low quality, still frame, modern clothes, running"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合", "negative": "blurry, low quality, still frame, computer, modern tech"}
]


def create_minimal_workflow(prompt_text, negative_text):
    """
    创建最小化的 LTX2 视频生成工作流
    只包含必要的节点
    """
    seed = int(time.time() * 1000) % 1000000
    
    workflow = {
        # 1. 加载 UNet 模型 (LTX2)
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "ltx-2-19b-dev-Q3_K_S.gguf"
            }
        },
        # 2. 加载 CLIP (只用 Gemma)
        "2": {
            "class_type": "CLIPLoaderGGUF",
            "inputs": {
                "clip_name": "gemma-3-12b-it-qat-Q3_K_S.gguf",
                "type": "ltxv"
            }
        },
        # 3. 加载 VAE
        "3": {
            "class_type": "VAELoaderKJ",
            "inputs": {
                "vae_name": "ltx-2-19b-dev_video_vae.safetensors",
                "device": "main_device",
                "weight_dtype": "bf16"
            }
        },
        # 4. 正向提示词
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": prompt_text
            }
        },
        # 5. 负面提示词
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": negative_text
            }
        },
        # 6. 创建空潜视频
        "6": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "width": 768,
                "height": 512,
                "length": 97,
                "batch_size": 1
            }
        },
        # 7. LTXV 条件处理
        "7": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "frame_rate": 25.0
            }
        },
        # 8. 随机噪声
        "8": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed
            }
        },
        # 9. 采样器选择
        "9": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler_ancestral"
            }
        },
        # 10. LTXV 调度器
        "10": {
            "class_type": "LTXVScheduler",
            "inputs": {
                "steps": 31,
                "max_shift": 2.05,
                "base_shift": 0.95,
                "stretch": True,
                "terminal": 0.1,
                "latent": ["6", 0]
            }
        },
        # 11. CFG Guider
        "11": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["1", 0],
                "positive": ["7", 0],
                "negative": ["7", 1],
                "cfg": 4.0
            }
        },
        # 12. 采样器 (Custom Advanced)
        "12": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["8", 0],
                "guider": ["11", 0],
                "sampler": ["9", 0],
                "sigmas": ["10", 0],
                "latent_image": ["6", 0]
            }
        },
        # 13. VAE 解码 (分块解码)
        "13": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["12", 0],
                "vae": ["3", 0],
                "tile_size": 512,
                "overlap": 64,
                "temporal_size": 4096,
                "temporal_overlap": 8
            }
        },
        # 14. 创建视频 (IMAGE → VIDEO)
        "14": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["13", 0],
                "fps": 25.0
            }
        },
        # 15. 保存视频
        "15": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["14", 0],
                "filename_prefix": f"Xianxia_News_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "format": "mp4",
                "codec": "auto"
            }
        }
    }
    
    return workflow


def queue_prompt(api_prompt, client_id):
    """提交任务"""
    try:
        print(f"🚀 提交任务到 ComfyUI...")
        resp = requests.post(
            f"http://{COMFYUI_SERVER}/prompt",
            json={"prompt": api_prompt, "client_id": client_id},
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            prompt_id = data.get('prompt_id')
            print(f"✅ 任务已提交 (ID: {prompt_id})")
            return prompt_id
        else:
            print(f"❌ 提交失败：{resp.status_code}")
            try:
                err = resp.json()
                print(f"错误：{json.dumps(err, indent=2, ensure_ascii=False)[:1000]}")
            except:
                print(f"响应：{resp.text[:500]}")
    except Exception as e:
        print(f"❌ 提交失败：{e}")
    return None


def monitor_progress(prompt_id, client_id, timeout=600):
    """监控进度"""
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}", timeout=10)
        
        print(f"⏳ 视频生成中...", end=" ", flush=True)
        start_time = time.time()
        last_percent = -1
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                print(f"{int(elapsed/60)}min", end=" ", flush=True)
            
            try:
                msg = json.loads(ws.recv())
                msg_type = msg.get('type')
                data = msg.get('data', {})
                
                if msg_type == 'progress':
                    step = data.get('value', 0)
                    total = data.get('max', 100)
                    percent = int(step / total * 100)
                    if percent != last_percent:
                        print(f"{percent}%", end=" ", flush=True)
                        last_percent = percent
                elif msg_type == 'executing':
                    if data.get('node') is None:
                        print("✅")
                        ws.close()
                        return True
                elif msg_type == 'executed':
                    print("✅")
                    ws.close()
                    return True
            except:
                continue
        
        ws.close()
        print("⏰ 超时")
        return False
    except Exception as e:
        print(f"❌ 监控失败：{e}")
        return False


def download_result(prompt_id, news_title):
    """下载结果"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=10)
        history = resp.json()
        
        if prompt_id not in history:
            return []
        
        outputs = history[prompt_id].get('outputs', {})
        downloaded = []
        
        for node_id, output in outputs.items():
            if 'video' in output:
                for vid in output['video']:
                    filename = vid.get('filename')
                    if filename:
                        params = f"?filename={filename}&subfolder={vid.get('subfolder', '')}&type={vid.get('type', 'output')}"
                        url = f"http://{COMFYUI_SERVER}/view{params}"
                        
                        print(f"  📥 下载...")
                        resp = requests.get(url, timeout=120)
                        if resp.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_title = news_title.replace(" ", "_")
                            filepath = OUTPUT_DIR / f"{ts}_{safe_title}.mp4"
                            
                            with open(filepath, 'wb') as f:
                                f.write(resp.content)
                            
                            print(f"  ✅ {filepath.name}")
                            downloaded.append(str(filepath))
                            
                            # 元数据
                            meta = {"title": news_title, "timestamp": datetime.now().isoformat(), "model": "LTX-2-19B"}
                            with open(filepath.with_suffix('.json'), 'w') as f:
                                json.dump(meta, f, indent=2)
        
        return downloaded
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return []


def generate(topic, index, total):
    """生成单个视频"""
    print(f"\n{'='*70}")
    print(f"[{index}/{total}] 📰 {topic['title']}")
    print(f"🎨 {topic['prompt'][:50]}...")
    print(f"{'='*70}")
    
    # 创建工作流
    print(f"\n📝 创建工作流...")
    workflow = create_minimal_workflow(topic['prompt'], topic['negative'])
    print(f"   节点数：{len(workflow)}")
    
    # 提交
    client_id = str(uuid.uuid4())
    prompt_id = queue_prompt(workflow, client_id)
    if not prompt_id:
        return {"success": False, "error": "提交失败", "title": topic['title']}
    
    # 监控
    if not monitor_progress(prompt_id, client_id):
        return {"success": False, "error": "生成失败", "title": topic['title']}
    
    # 下载
    files = download_result(prompt_id, topic['title'])
    
    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频 - 最小化 API 版")
    print("📅 2026 年 3 月最新新闻")
    print("="*70)
    
    # 检查连接
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        if resp.status_code != 200:
            print("❌ 无法连接 ComfyUI")
            return 1
        print(f"\n✅ ComfyUI: {COMFYUI_SERVER}")
        print(f"💾 {OUTPUT_DIR}")
    except:
        print("❌ 无法连接 ComfyUI")
        return 1
    
    print(f"\n📋 主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择模式
    print(f"\n请选择:")
    print(f"  1. 生成所有")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")
    
    choice = input("\n输入 (1/2/3): ").strip()
    results = []
    
    if choice == '1':
        for i, topic in enumerate(NEWS_TOPICS, 1):
            results.append(generate(topic, i, len(NEWS_TOPICS)))
            if i < len(NEWS_TOPICS):
                time.sleep(5)
    elif choice == '2':
        idx = int(input("序号 (1-5): ").strip())
        if 1 <= idx <= 5:
            results.append(generate(NEWS_TOPICS[idx-1], 1, 1))
    elif choice == '3':
        print(f"\n🧪 测试：{NEWS_TOPICS[0]['title']}")
        results.append(generate(NEWS_TOPICS[0], 1, 1))
    else:
        return 1
    
    # 汇总
    print(f"\n{'='*70}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 {OUTPUT_DIR}")
    
    # 保存报告
    report = {"timestamp": datetime.now().isoformat(), "success": success, "results": results}
    report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"📄 {report_file}")
    
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print(f"\n⚠️  中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        sys.exit(1)
