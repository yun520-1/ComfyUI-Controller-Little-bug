#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 最简单本地运行
使用 subprocess 直接调用 ComfyUI
"""

import subprocess
import json
import copy
from pathlib import Path
from datetime import datetime

# 配置
COMFYUI_DIR = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
WORKFLOW_FILE = COMFYUI_DIR / "user" / "default" / "workflows" / "ltx2_t2v_gguf.json"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PYTHON = COMFYUI_DIR / "venv" / "bin" / "python3"

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台", "negative": "blurry, low quality, still frame, modern clothes, microphone"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚", "negative": "blurry, low quality, still frame, modern ship, boat"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格", "negative": "blurry, low quality, still frame, modern clothes, running"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合", "negative": "blurry, low quality, still frame, computer, modern tech"}
]


def update_workflow(workflow_path, prompt, negative, output_path):
    """更新工作流提示词并保存"""
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    for node in workflow.get("nodes", []):
        if node.get("type") == "CLIPTextEncode":
            widgets = node.get("widgets_values", [])
            if widgets and isinstance(widgets[0], str):
                if "blurry" in widgets[0].lower():
                    node["widgets_values"][0] = negative
                else:
                    node["widgets_values"][0] = prompt
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)
    
    return output_path


def run_comfyui_workflow(workflow_path):
    """运行 ComfyUI 工作流"""
    print(f"\n🚀 运行 ComfyUI 工作流...")
    print(f"   📁 {workflow_path}")
    
    # 使用 main.py 执行
    cmd = [
        str(PYTHON),
        str(COMFYUI_DIR / "main.py"),
        "--listen", "127.0.0.1",
        "--port", "8189",
        "--workflow", str(workflow_path),
        "--output-directory", str(OUTPUT_DIR)
    ]
    
    print(f"   命令：{' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(COMFYUI_DIR),
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            print(f"   ✅ 完成")
            return True
        else:
            print(f"   ❌ 失败：{result.stderr[:500]}")
            return False
    except Exception as e:
        print(f"   ❌ {e}")
        return False


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频 - 本地运行")
    print("="*70)
    
    if not WORKFLOW_FILE.exists():
        print(f"❌ 工作流不存在：{WORKFLOW_FILE}")
        return 1
    
    print(f"\n✅ 工作流：{WORKFLOW_FILE.name}")
    print(f"💾 输出：{OUTPUT_DIR}")
    
    # 显示主题
    print(f"\n📋 主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择
    choice = input("\n请选择 (1 所有/2 单个/3 测试): ").strip()
    
    topics = []
    if choice == '1':
        topics = NEWS_TOPICS
    elif choice == '2':
        idx = int(input("序号 (1-5): ").strip())
        topics = [NEWS_TOPICS[idx-1]] if 1 <= idx <= 5 else []
    elif choice == '3':
        topics = [NEWS_TOPICS[0]]
    
    if not topics:
        return 1
    
    # 生成
    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(topics)}] 📰 {topic['title']}")
        print(f"{'='*70}")
        
        # 保存更新的工作流
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = topic['title'].replace(" ", "_")
        temp_workflow = OUTPUT_DIR / f"workflow_{safe_title}_{ts}.json"
        
        print(f"\n🔄 更新提示词...")
        update_workflow(WORKFLOW_FILE, topic['prompt'], topic['negative'], temp_workflow)
        print(f"   💾 {temp_workflow.name}")
        
        # 运行
        success = run_comfyui_workflow(temp_workflow)
        results.append({"title": topic['title'], "success": success})
    
    # 汇总
    print(f"\n{'='*70}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    
    return 0


if __name__ == "__main__":
    exit(main())
