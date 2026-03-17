#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接在 ComfyUI 本地执行工作流
不使用 API，直接调用 ComfyUI 的执行器
"""

import sys
import os
import json
import copy
import uuid
import time
from pathlib import Path
from datetime import datetime

# ComfyUI 路径
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
sys.path.insert(0, str(COMFYUI_PATH))

# 工作流和输出
WORKFLOW_FILE = COMFYUI_PATH / "user" / "default" / "workflows" / "ltx2_t2v_gguf.json"
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
    """加载工作流 JSON"""
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_prompts(workflow, prompt, negative):
    """更新提示词"""
    wf = copy.deepcopy(workflow)
    for node in wf.get("nodes", []):
        if node.get("type") == "CLIPTextEncode":
            widgets = node.get("widgets_values", [])
            if widgets and isinstance(widgets[0], str):
                if "blurry" in widgets[0].lower():
                    node["widgets_values"][0] = negative
                else:
                    node["widgets_values"][0] = prompt
    return wf


def convert_to_api_format(workflow):
    """将 ComfyUI 工作流转换为 API 格式"""
    api_prompt = {}

    for node in workflow.get("nodes", []):
        node_id = str(node["id"])
        node_type = node.get("type", "")

        # 跳过特殊节点
        if node_type in ["Reroute", "Note", "PrimitiveNode"]:
            continue

        inputs = {}
        widgets = node.get("widgets_values", [])

        # 处理 widget
        if node_type == "CLIPTextEncode" and widgets:
            inputs["text"] = widgets[0]
        elif node_type == "EmptyLTXVLatentVideo" and len(widgets) >= 4:
            inputs["width"] = widgets[0]
            inputs["height"] = widgets[1]
            inputs["length"] = widgets[2]
            inputs["batch_size"] = widgets[3]
        elif node_type == "UnetLoaderGGUF" and widgets:
            inputs["unet_name"] = widgets[0]
        elif node_type == "CLIPLoaderGGUF" and widgets:
            inputs["clip_name"] = widgets[0]
            inputs["type"] = widgets[1] if len(widgets) > 1 else "ltxv"
        elif node_type == "VAELoaderKJ" and widgets:
            inputs["vae_name"] = widgets[0]
            inputs["device"] = widgets[1] if len(widgets) > 1 else "main_device"
            inputs["weight_dtype"] = widgets[2] if len(widgets) > 2 else "bf16"
        elif node_type == "KSamplerSelect" and widgets:
            inputs["sampler_name"] = widgets[0]
        elif node_type == "LTXVScheduler" and len(widgets) >= 5:
            inputs["steps"] = widgets[0]
            inputs["max_shift"] = widgets[1]
            inputs["base_shift"] = widgets[2]
            inputs["stretch"] = widgets[3]
            inputs["terminal"] = widgets[4]
        elif node_type == "CFGGuider" and widgets:
            inputs["cfg"] = widgets[0]
        elif node_type == "RandomNoise" and widgets:
            inputs["noise_seed"] = widgets[0]
        elif node_type == "LoraLoaderModelOnly" and len(widgets) >= 2:
            inputs["lora_name"] = widgets[0]
            inputs["strength_model"] = widgets[1]
        elif node_type == "SaveVideo" and widgets:
            inputs["filename_prefix"] = widgets[0]
            inputs["format"] = widgets[1] if len(widgets) > 1 else "mp4"
            inputs["codec"] = widgets[2] if len(widgets) > 2 else "auto"
        elif node_type == "CreateVideo" and widgets:
            inputs["fps"] = widgets[0]
        elif node_type == "LTXVConditioning" and len(widgets) >= 1:
            inputs["frame_rate"] = widgets[0]

        # 处理输入连接
        for inp in node.get("inputs", []):
            input_name = inp.get("name")
            link_id = inp.get("link")

            if link_id and input_name:
                # 查找 link
                for link in workflow.get("links", []):
                    if link[0] == link_id:
                        src_node_id = str(link[1])
                        src_output = link[2]
                        inputs[input_name] = [src_node_id, src_output]
                        break

        api_prompt[node_id] = {
            "class_type": node_type,
            "inputs": inputs
        }

    return api_prompt


def execute_with_comfyui(api_prompt):
    """使用 ComfyUI 执行器执行"""
    print(f"\n🚀 使用 ComfyUI 执行器执行...")

    try:
        # 导入 ComfyUI 模块
        from execution import PromptExecutor, validate_prompt
        from server import PromptServer
        import comfy.model_management as model_management

        print(f"   ✅ ComfyUI 模块已加载")

        # 创建 PromptServer 实例
        server = PromptServer.instance if hasattr(PromptServer, 'instance') else None

        if not server:
            print(f"   ⚠️  创建新的 PromptServer...")
            # 需要初始化
            import folder_paths
            folder_paths.set_output_directory(str(OUTPUT_DIR))

        # 验证 prompt
        print(f"   📋 验证工作流...")
        validation_result = validate_prompt(api_prompt)

        if validation_result[0]:  # 有错误
            print(f"   ❌ 验证失败:")
            for node_id, errors in validation_result[0].items():
                print(f"      节点 {node_id}: {errors}")
            return False

        print(f"   ✅ 验证通过")

        # 执行
        print(f"   ⏳ 执行中...")
        prompt_id = str(uuid.uuid4())

        # 创建执行器
        executor = PromptExecutor(server)

        # 执行 prompt
        import asyncio

        async def run():
            await executor.execute(prompt_id, api_prompt, {}, {}, True)

        # 运行
        asyncio.run(run())

        print(f"   ✅ 执行完成")
        return True

    except ImportError as e:
        print(f"   ❌ 导入失败：{e}")
        print(f"   💡 建议：在 ComfyUI 虚拟环境中运行")
        return False
    except Exception as e:
        print(f"   ❌ 执行失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频 - 本地直接执行")
    print("="*70)

    print(f"\n📂 ComfyUI: {COMFYUI_PATH}")
    print(f"💾 输出：{OUTPUT_DIR}")

    # 检查
    if not COMFYUI_PATH.exists():
        print(f"❌ ComfyUI 不存在：{COMFYUI_PATH}")
        return 1

    if not WORKFLOW_FILE.exists():
        print(f"❌ 工作流不存在：{WORKFLOW_FILE}")
        return 1

    print(f"✅ 工作流：{WORKFLOW_FILE.name}")

    # 显示主题
    print(f"\n📋 主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")

    # 选择
    print(f"\n请选择:")
    print(f"  1. 生成所有")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")

    choice = input("\n输入 (1/2/3): ").strip()

    topics = []
    if choice == '1':
        topics = NEWS_TOPICS
    elif choice == '2':
        idx = int(input("序号 (1-5): ").strip())
        topics = [NEWS_TOPICS[idx-1]] if 1 <= idx <= 5 else []
    elif choice == '3':
        topics = [NEWS_TOPICS[0]]

    if not topics:
        print("无效选择")
        return 1

    # 加载工作流
    print(f"\n📋 加载工作流...")
    workflow = load_workflow()
    print(f"   节点：{workflow.get('last_node_id', 0)}")

    # 生成
    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(topics)}] 📰 {topic['title']}")
        print(f"{'='*70}")

        # 更新提示词
        print(f"\n🔄 更新提示词...")
        updated = update_prompts(workflow, topic['prompt'], topic['negative'])

        # 转换为 API 格式
        print(f"🔄 转换格式...")
        api_prompt = convert_to_api_format(updated)
        print(f"   API 节点：{len(api_prompt)}")

        # 执行
        success = execute_with_comfyui(api_prompt)
        results.append({"title": topic['title'], "success": success})

        if i < len(topics):
            time.sleep(5)

    # 汇总
    print(f"\n{'='*70}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 {OUTPUT_DIR}")

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
