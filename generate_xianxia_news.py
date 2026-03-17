#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仙人古装新闻图片生成器 - 快速测试版
生成 5 个最新新闻的仙人古装风格图片
"""

import json
import uuid
import time
import requests
import websocket
from pathlib import Path
from datetime import datetime

# 配置
COMFYUI_SERVER = "127.0.0.1:8189"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_news"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，音乐仙境"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态感"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文"}
]

def create_workflow(prompt, width=1024, height=512):
    """创建工作流"""
    style_prompt = prompt + "，仙侠风格，古装，精致，高清，电影感，中国风，传统美学，8K"
    negative = "现代服装，西装，现代建筑，低质量，模糊，变形，丑陋，照片"
    
    return {
        "3": {"class_type": "KSampler", "inputs": {"cfg": 7, "denoise": 1, "latent_image": ["5", 0], "model": ["4", 0], "negative": ["7", 0], "positive": ["6", 0], "sampler_name": "euler_ancestral", "scheduler": "normal", "seed": int(time.time() * 1000) % 1000000, "steps": 25}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": height, "width": width}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": style_prompt}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": negative}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"Xianxia_News", "images": ["8", 0]}}
    }

def queue_prompt(workflow):
    """提交任务"""
    client_id = str(uuid.uuid4())
    try:
        resp = requests.post(f"http://{COMFYUI_SERVER}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('prompt_id')
    except Exception as e:
        print(f"❌ 提交失败：{e}")
    return None

def monitor_progress(prompt_id):
    """监控进度"""
    client_id = str(uuid.uuid4())
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}", timeout=10)
        
        print(f"⏳ 生成中...", end=" ", flush=True)
        start_time = time.time()
        
        while time.time() - start_time < 300:
            try:
                msg = json.loads(ws.recv())
                if msg.get('type') == 'progress':
                    step = msg['data'].get('value', 0)
                    total = msg['data'].get('max', 100)
                    percent = int(step / total * 100)
                    print(f"{percent}%", end=" ", flush=True)
                elif msg.get('type') == 'executing' and msg['data'].get('node') is None:
                    print("✅")
                    ws.close()
                    return True
            except:
                continue
        
        ws.close()
        return False
    except Exception as e:
        print(f"❌ 监控失败：{e}")
        return False

def download_result(prompt_id, news_title):
    """下载结果"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=5)
        history = resp.json()
        
        if prompt_id not in history:
            return []
        
        outputs = history[prompt_id].get('outputs', {})
        downloaded = []
        
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                for img in node_output['images']:
                    if 'filename' in img:
                        params = {'filename': img['filename'], 'subfolder': img.get('subfolder', ''), 'type': img.get('type', 'output')}
                        url = f"http://{COMFYUI_SERVER}/view?{json.dumps(params)}"
                        
                        resp = requests.get(url, timeout=30)
                        if resp.status_code == 200:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_title = news_title.replace(" ", "_")
                            filename = f"{timestamp}_{safe_title}_{img['filename']}"
                            save_path = OUTPUT_DIR / filename
                            
                            with open(save_path, 'wb') as f:
                                f.write(resp.content)
                            
                            print(f"  ✅ {filename}")
                            downloaded.append(str(save_path))
        
        return downloaded
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return []

def main():
    print("="*60)
    print("🎬 仙人古装风格新闻图片生成器")
    print("📅 2026 年 3 月最新新闻")
    print("="*60)
    
    # 检查连接
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        if resp.status_code != 200:
            print("❌ 无法连接 ComfyUI")
            return 1
        print(f"✅ 已连接到 ComfyUI ({COMFYUI_SERVER})")
    except:
        print("❌ 无法连接 ComfyUI")
        return 1
    
    print(f"\n📋 新闻主题：{len(NEWS_TOPICS)}个")
    print(f"💾 输出目录：{OUTPUT_DIR}")
    print(f"\n开始生成...\n")
    
    results = []
    for i, topic in enumerate(NEWS_TOPICS, 1):
        print(f"[{i}/{len(NEWS_TOPICS)}] {topic['title']}")
        
        # 创建工作流
        workflow = create_workflow(topic['prompt'])
        
        # 提交
        prompt_id = queue_prompt(workflow)
        if not prompt_id:
            print(f"  ❌ 提交失败\n")
            results.append({"title": topic['title'], "success": False})
            continue
        
        # 监控
        if not monitor_progress(prompt_id):
            print(f"  ❌ 生成失败\n")
            results.append({"title": topic['title'], "success": False})
            continue
        
        # 下载
        files = download_result(prompt_id, topic['title'])
        if files:
            print(f"  📁 保存：{len(files)}个文件\n")
            results.append({"title": topic['title'], "success": True, "files": files})
        else:
            print(f"  ❌ 下载失败\n")
            results.append({"title": topic['title'], "success": False})
        
        # 等待
        if i < len(NEWS_TOPICS):
            time.sleep(1)
    
    # 汇总
    print("\n" + "="*60)
    print("📊 生成结果汇总")
    print("="*60)
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 目录：{OUTPUT_DIR}")
    
    # 保存报告
    report = {"timestamp": datetime.now().isoformat(), "total": len(results), "success": success, "results": results}
    report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📄 报告：{report_file}")
    
    return 0

if __name__ == "__main__":
    exit(main())
