#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频生成器 v2
使用已有的 LTX-2-19B GGUF 模型和工作流
"""

import json
import uuid
import time
import requests
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# 配置
COMFYUI_SERVER = "127.0.0.1:8189"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LTX2 工作流路径
LTX2_WORKFLOW_PATH = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit, watermark"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，动态表演，电影感", "negative": "blurry, low quality, still frame, modern clothes, microphone, watermark"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感，电影感", "negative": "blurry, low quality, still frame, modern ship, boat, watermark"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行，电影感", "negative": "blurry, low quality, still frame, modern clothes, running, watermark"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文，电影感", "negative": "blurry, low quality, still frame, computer, modern tech, watermark"}
]


def load_workflow():
    """加载 LTX2 工作流"""
    with open(LTX2_WORKFLOW_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_prompt(workflow, prompt, negative):
    """更新工作流提示词"""
    wf = copy.deepcopy(workflow)
    for node in wf.get("nodes", []):
        if node.get("type") == "CLIPTextEncode":
            vals = node.get("widgets_values", [])
            if vals and isinstance(vals[0], str):
                if "blurry" in vals[0].lower():
                    node["widgets_values"][0] = negative
                    print(f"   ✅ 负面提示词已更新")
                else:
                    node["widgets_values"][0] = prompt
                    print(f"   ✅ 正向提示词已更新")
    return wf


def queue_prompt(workflow, client_id):
    """提交任务到 ComfyUI"""
    try:
        # ComfyUI 接受完整工作流格式
        resp = requests.post(
            f"http://{COMFYUI_SERVER}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            prompt_id = data.get('prompt_id')
            print(f"✅ 任务已提交 (ID: {prompt_id})")
            return prompt_id
        else:
            print(f"❌ 提交失败：{resp.status_code}")
            print(f"响应：{resp.text[:300]}")
    except Exception as e:
        print(f"❌ 提交失败：{e}")
    return None


def monitor_progress(prompt_id, client_id, timeout=600):
    """监控进度"""
    import websocket
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}", timeout=10)

        print(f"⏳ 视频生成中...", end=" ", flush=True)
        start_time = time.time()
        last_update = time.time()

        while time.time() - start_time < timeout:
            if time.time() - last_update > 30:
                print(f"{int((time.time() - start_time)/60)}min", end=" ", flush=True)
                last_update = time.time()

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


def download_video(prompt_id, news_title):
    """下载视频"""
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=5)
        history = resp.json()

        if prompt_id not in history:
            return []

        outputs = history[prompt_id].get('outputs', {})
        downloaded = []

        for node_id, output in outputs.items():
            # 视频
            if 'video' in output:
                for vid in output['video']:
                    if 'filename' in vid:
                        params = {'filename': vid['filename'], 'subfolder': vid.get('subfolder', ''), 'type': vid.get('type', 'output')}
                        url = f"http://{COMFYUI_SERVER}/view?{json.dumps(params)}"

                        resp = requests.get(url, timeout=120)
                        if resp.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_title = news_title.replace(" ", "_")
                            filename = f"{ts}_{safe_title}.mp4"
                            save_path = OUTPUT_DIR / filename

                            with open(save_path, 'wb') as f:
                                f.write(resp.content)

                            print(f"  ✅ 视频：{filename}")
                            downloaded.append(str(save_path))

            # 图片
            if 'images' in output:
                for img in output['images']:
                    if 'filename' in img:
                        params = {'filename': img['filename'], 'subfolder': img.get('subfolder', ''), 'type': img.get('type', 'output')}
                        url = f"http://{COMFYUI_SERVER}/view?{json.dumps(params)}"

                        resp = requests.get(url, timeout=30)
                        if resp.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_title = news_title.replace(" ", "_")
                            filename = f"{ts}_{safe_title}_{img['filename']}"
                            save_path = OUTPUT_DIR / filename

                            with open(save_path, 'wb') as f:
                                f.write(resp.content)

                            print(f"  ✅ 图片：{filename}")
                            downloaded.append(str(save_path))

        return downloaded
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return []


def generate_video(topic, client_id):
    """生成单个视频"""
    print(f"\n{'='*60}")
    print(f"📰 {topic['title']}")
    print(f"🎨 {topic['prompt'][:50]}...")
    print(f"{'='*60}")

    # 加载并更新工作流
    workflow = load_workflow()
    workflow = update_prompt(workflow, topic['prompt'], topic['negative'])

    # 提交
    prompt_id = queue_prompt(workflow, client_id)
    if not prompt_id:
        return {"success": False, "error": "提交失败"}

    # 监控
    if not monitor_progress(prompt_id, client_id):
        return {"success": False, "error": "生成失败"}

    # 下载
    files = download_video(prompt_id, topic['title'])

    return {"success": len(files) > 0, "files": files, "title": topic['title']}


def main():
    print("="*60)
    print("🎬 LTX2 仙人古装新闻视频生成器")
    print("📅 2026 年 3 月最新新闻")
    print("🤖 LTX-2-19B-GGUF (Q3_K_S)")
    print("="*60)

    # 检查连接
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        if resp.status_code != 200:
            print("❌ 无法连接 ComfyUI")
            return 1
        print(f"\n✅ 已连接到 ComfyUI ({COMFYUI_SERVER})")
    except:
        print("❌ 无法连接 ComfyUI")
        return 1

    # 显示主题
    print(f"\n📋 新闻主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")

    # 选择模式
    print(f"\n请选择:")
    print("  1. 生成所有 (约 10-25 分钟)")
    print("  2. 生成单个")
    print("  3. 测试第一个")

    choice = input("\n输入选择 (1/2/3): ").strip()

    client_id = str(uuid.uuid4())
    results = []

    if choice == '1':
        print(f"\n🚀 批量生成开始...")
        for i, topic in enumerate(NEWS_TOPICS, 1):
            print(f"\n[{i}/{len(NEWS_TOPICS)}]")
            results.append(generate_video(topic, client_id))
            if i < len(NEWS_TOPICS):
                time.sleep(5)
    elif choice == '2':
        idx = int(input("输入序号 (1-5): ").strip())
        if 1 <= idx <= 5:
            results.append(generate_video(NEWS_TOPICS[idx-1], client_id))
    elif choice == '3':
        print("\n🧪 测试模式")
        results.append(generate_video(NEWS_TOPICS[0], client_id))
    else:
        print("无效选择")
        return 1

    # 汇总
    print(f"\n{'='*60}")
    print("📊 结果汇总")
    print(f"{'='*60}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 {OUTPUT_DIR}")

    # 保存报告
    report = {"timestamp": datetime.now().isoformat(), "total": len(results), "success": success, "results": results}
    report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📄 报告：{report_file}")

    return 0


if __name__ == "__main__":
    exit(main())
