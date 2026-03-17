#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频 - 本地直接运行版
直接使用 ComfyUI 的 Python 接口，不通过 API
"""

import sys
import os
import json
import copy
from pathlib import Path
from datetime import datetime
import time

# ComfyUI 路径
COMFYUI_PATH = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI"
sys.path.insert(0, COMFYUI_PATH)

# 设置环境变量
os.environ["COMFYUI_PATH"] = COMFYUI_PATH

# 工作流和输出
WORKFLOW_FILE = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"
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


def load_workflow():
    """加载工作流"""
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_workflow_prompts(workflow, prompt, negative):
    """更新工作流中的提示词"""
    wf = copy.deepcopy(workflow)

    for node in wf.get("nodes", []):
        if node.get("type") == "CLIPTextEncode":
            widgets = node.get("widgets_values", [])
            if widgets and isinstance(widgets[0], str):
                if "blurry" in widgets[0].lower() or "low quality" in widgets[0].lower():
                    node["widgets_values"][0] = negative
                    print(f"   ✅ 负面提示词已更新")
                else:
                    node["widgets_values"][0] = prompt
                    print(f"   ✅ 正向提示词已更新")

    return wf


def save_workflow_for_execution(workflow, topic_title):
    """保存更新后的工作流用于执行"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = topic_title.replace(" ", "_")
    output_file = OUTPUT_DIR / f"workflow_{safe_title}_{ts}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)

    print(f"   💾 工作流已保存：{output_file.name}")
    return output_file


def execute_workflow_comfyui(workflow_file):
    """使用 ComfyUI 执行工作流"""
    print(f"\n🚀 使用 ComfyUI 执行工作流...")
    print(f"   📁 {workflow_file}")

    # 方法 1：使用 comfy-cli（如果已安装）
    try:
        import subprocess
        result = subprocess.run(
            ["comfy", "run", "--workflow", str(workflow_file)],
            cwd=COMFYUI_PATH,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            print(f"   ✅ 执行完成")
            return True
        else:
            print(f"   ❌ 执行失败：{result.stderr[:500]}")
    except FileNotFoundError:
        print(f"   ⚠️  comfy-cli 未安装")
    except Exception as e:
        print(f"   ❌ 执行失败：{e}")

    # 方法 2：直接调用 ComfyUI Python
    print(f"\n🔄 尝试直接调用 ComfyUI...")

    try:
        # 导入 ComfyUI 模块
        import execution
        import server
        import comfy.model_management as model_management

        print(f"   ✅ ComfyUI 模块已加载")

        # 加载工作流
        with open(workflow_file, 'r') as f:
            workflow = json.load(f)

        # 转换为 API 格式
        from nodes import NODE_CLASS_MAPPINGS

        print(f"   📋 节点数：{len(NODE_CLASS_MAPPINGS)}")

        # 执行
        executor = execution.PromptExecutor(server)

        print(f"   ⏳ 执行中...")
        # 这里需要更复杂的执行逻辑
        # 建议使用 comfy-cli 或 Web 界面

        return False

    except Exception as e:
        print(f"   ❌ {e}")
        return False

    return False


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频 - 本地直接运行")
    print("="*70)

    print(f"\n📂 ComfyUI 路径：{COMFYUI_PATH}")
    print(f"💾 输出目录：{OUTPUT_DIR}")

    # 检查 ComfyUI 是否存在
    if not Path(COMFYUI_PATH).exists():
        print(f"❌ ComfyUI 路径不存在：{COMFYUI_PATH}")
        return 1

    # 检查工作流
    if not Path(WORKFLOW_FILE).exists():
        print(f"❌ 工作流不存在：{WORKFLOW_FILE}")
        return 1

    print(f"✅ 工作流：{WORKFLOW_FILE}")

    # 显示主题
    print(f"\n📋 新闻主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")

    # 选择模式
    print(f"\n请选择:")
    print(f"  1. 生成所有")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")

    choice = input("\n输入 (1/2/3): ").strip()

    topics_to_generate = []

    if choice == '1':
        topics_to_generate = NEWS_TOPICS
    elif choice == '2':
        idx = int(input("序号 (1-5): ").strip())
        if 1 <= idx <= 5:
            topics_to_generate = [NEWS_TOPICS[idx-1]]
    elif choice == '3':
        topics_to_generate = [NEWS_TOPICS[0]]
    else:
        return 1

    # 加载工作流
    print(f"\n📋 加载工作流...")
    workflow = load_workflow()
    print(f"   节点数：{workflow.get('last_node_id', 0)}")

    # 生成每个主题
    results = []
    for i, topic in enumerate(topics_to_generate, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(topics_to_generate)}] 📰 {topic['title']}")
        print(f"{'='*70}")

        # 更新提示词
        print(f"\n🔄 更新提示词...")
        updated_workflow = update_workflow_prompts(workflow, topic['prompt'], topic['negative'])

        # 保存更新后的工作流
        workflow_file = save_workflow_for_execution(updated_workflow, topic['title'])

        # 执行
        success = execute_workflow_comfyui(workflow_file)

        results.append({
            "title": topic['title'],
            "success": success,
            "workflow": str(workflow_file)
        })

    # 汇总
    print(f"\n{'='*70}")
    print("📊 结果汇总")
    print(f"{'='*70}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 {OUTPUT_DIR}")

    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
