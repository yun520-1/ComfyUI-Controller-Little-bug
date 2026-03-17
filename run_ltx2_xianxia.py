#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频生成器 - 直接运行版
自动转换工作流并提交到 ComfyUI API
"""

import json
import uuid
import time
import requests
import copy
from pathlib import Path
from datetime import datetime
import websocket

# 配置
COMFYUI_SERVER = "127.0.0.1:8189"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_ltx2_news"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOW_FILE = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感，史诗感", "negative": "blurry, low quality, still frame, modern clothes, suit, watermark, titles"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，动态表演，电影感", "negative": "blurry, low quality, still frame, modern clothes, microphone, watermark"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感，动态", "negative": "blurry, low quality, still frame, modern ship, boat, watermark"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行，湖光山色", "negative": "blurry, low quality, still frame, modern clothes, running, watermark"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文，动态光效", "negative": "blurry, low quality, still frame, computer, modern tech, watermark"}
]


def convert_workflow_to_api(workflow_json, prompt_text, negative_text):
    """将 ComfyUI 工作流转换为 API 格式"""
    api_prompt = {}
    
    # 创建节点查找表
    nodes_by_id = {node["id"]: node for node in workflow_json.get("nodes", [])}
    
    # 处理每个节点
    for node in workflow_json.get("nodes", []):
        node_id = str(node["id"])
        node_type = node.get("type", "")
        
        # 跳过某些特殊节点
        if node_type in ["Reroute", "Note", "PrimitiveNode"]:
            continue
        
        inputs = {}
        widgets = node.get("widgets_values", [])
        
        # 处理 widget 值
        if node_type == "CLIPTextEncode":
            if widgets:
                current = widgets[0] if isinstance(widgets[0], str) else ""
                if "blurry" in current.lower() or "low quality" in current.lower():
                    inputs["text"] = negative_text
                else:
                    inputs["text"] = prompt_text
        elif node_type == "EmptyLTXVLatentVideo":
            inputs["width"] = widgets[0] if len(widgets) > 0 else 768
            inputs["height"] = widgets[1] if len(widgets) > 1 else 512
            inputs["length"] = widgets[2] if len(widgets) > 2 else 97
            inputs["batch_size"] = widgets[3] if len(widgets) > 3 else 1
        elif node_type == "UnetLoaderGGUF":
            inputs["unet_name"] = widgets[0] if len(widgets) > 0 else "ltx-2-19b-dev-Q3_K_S.gguf"
        elif node_type == "DualCLIPLoaderGGUF":
            inputs["clip_name1"] = widgets[0] if len(widgets) > 0 else "gemma-3-12b-it-qat-Q3_K_S.gguf"
            inputs["clip_name2"] = widgets[1] if len(widgets) > 1 else "ltx-2-19b-dev_embeddings_connectors.safetensors"
            inputs["type"] = widgets[2] if len(widgets) > 2 else "ltxv"
        elif node_type == "VAELoaderKJ":
            inputs["vae_name"] = widgets[0] if len(widgets) > 0 else "ltx-2-19b-dev_video_vae.safetensors"
            inputs["device"] = widgets[1] if len(widgets) > 1 else "main_device"
            inputs["weight_dtype"] = widgets[2] if len(widgets) > 2 else "bf16"
        elif node_type == "KSamplerSelect":
            inputs["sampler_name"] = widgets[0] if len(widgets) > 0 else "euler_ancestral"
        elif node_type == "LTXVScheduler":
            inputs["steps"] = widgets[0] if len(widgets) > 0 else 31
            inputs["max_shift"] = widgets[1] if len(widgets) > 1 else 2.05
            inputs["base_shift"] = widgets[2] if len(widgets) > 2 else 0.95
            inputs["stretch"] = widgets[3] if len(widgets) > 3 else True
            inputs["terminal"] = widgets[4] if len(widgets) > 4 else 0.1
        elif node_type == "CFGGuider":
            inputs["cfg"] = widgets[0] if len(widgets) > 0 else 4.0
        elif node_type == "RandomNoise":
            inputs["noise_seed"] = widgets[0] if len(widgets) > 0 else int(time.time() * 1000) % 1000000
        elif node_type == "LoraLoaderModelOnly":
            inputs["lora_name"] = widgets[0] if len(widgets) > 0 else ""
            inputs["strength_model"] = widgets[1] if len(widgets) > 1 else 1.0
        elif node_type == "SaveVideo":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            inputs["filename_prefix"] = f"Xianxia_News_{ts}"
            inputs["format"] = widgets[1] if len(widgets) > 1 else "mp4"
            inputs["codec"] = widgets[2] if len(widgets) > 2 else "auto"
        elif node_type == "CreateVideo":
            inputs["fps"] = widgets[0] if len(widgets) > 0 else 25
        elif node_type == "ImageScaleBy":
            inputs["upscale_method"] = widgets[0] if len(widgets) > 0 else "lanczos"
            inputs["scale_by"] = widgets[1] if len(widgets) > 1 else 0.5
        elif node_type == "EmptyImage":
            inputs["width"] = widgets[0] if len(widgets) > 0 else 1280
            inputs["height"] = widgets[1] if len(widgets) > 1 else 720
            inputs["batch_size"] = widgets[2] if len(widgets) > 2 else 1
        elif node_type == "VAEDecodeTiled":
            inputs["tile_size"] = widgets[0] if len(widgets) > 0 else 512
            inputs["overlap"] = widgets[1] if len(widgets) > 1 else 64
            inputs["temporal_size"] = widgets[2] if len(widgets) > 2 else 4096
            inputs["temporal_overlap"] = widgets[3] if len(widgets) > 3 else 8
        elif node_type == "LatentUpscaleModelLoader":
            inputs["model_name"] = widgets[0] if len(widgets) > 0 else "ltx-2-spatial-upscaler-x2-1.0.safetensors"
        
        # 处理输入连接
        for inp in node.get("inputs", []):
            input_name = inp.get("name", "input")
            link_id = inp.get("link")
            
            if link_id:
                # 查找对应的 link
                for link in workflow_json.get("links", []):
                    if link[0] == link_id:
                        src_node_id = str(link[1])
                        src_output_idx = link[2]
                        
                        # 跳过 Reroute 节点，直接连接到源
                        if src_node_id in nodes_by_id:
                            src_node = nodes_by_id[src_node_id]
                            if src_node.get("type") == "Reroute":
                                # 找到 Reroute 的输入
                                for r_link in workflow_json.get("links", []):
                                    for r_inp in src_node.get("inputs", []):
                                        if r_inp.get("link") == r_link[0]:
                                            src_node_id = str(r_link[1])
                                            break
                            elif src_node.get("type") == "PrimitiveNode":
                                # 处理 PrimitiveNode 的值
                                for p_node in workflow_json.get("nodes", []):
                                    if str(p_node["id"]) == src_node_id:
                                        p_widgets = p_node.get("widgets_values", [])
                                        if p_widgets:
                                            if input_name in ["width", "height", "length", "batch_size"]:
                                                inputs[input_name] = p_widgets[0] if p_widgets else 0
                                            elif input_name == "frame_rate":
                                                inputs[input_name] = float(p_widgets[0]) if p_widgets else 24.0
                                                break
        
        api_prompt[node_id] = {
            "class_type": node_type,
            "inputs": inputs
        }
    
    return api_prompt


def queue_prompt(api_prompt, client_id):
    """提交到 ComfyUI"""
    try:
        print(f"🚀 提交任务...")
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
                print(f"错误：{err}")
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
        
        print(f"⏳ 生成中...", end=" ", flush=True)
        start_time = time.time()
        last_percent = -1
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                print(f"{int(elapsed/60)}min", end=" ", flush=True)
            
            try:
                msg = json.loads(ws.recv())
                msg_type = msg.get('type')
                
                if msg_type == 'progress':
                    data = msg.get('data', {})
                    step = data.get('value', 0)
                    total = data.get('max', 100)
                    percent = int(step / total * 100)
                    if percent != last_percent:
                        print(f"{percent}%", end=" ", flush=True)
                        last_percent = percent
                elif msg_type == 'executing':
                    data = msg.get('data', {})
                    if data.get('node') is None:
                        print("✅")
                        ws.close()
                        return True
                elif msg_type == 'executed':
                    print("✅ 执行完成")
                    ws.close()
                    return True
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
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
            print("❌ 未找到历史记录")
            return []
        
        outputs = history[prompt_id].get('outputs', {})
        downloaded = []
        
        for node_id, output in outputs.items():
            # 视频
            if 'video' in output:
                for vid in output['video']:
                    filename = vid.get('filename')
                    if filename:
                        subfolder = vid.get('subfolder', '')
                        vtype = vid.get('type', 'output')
                        params = f"?filename={filename}&subfolder={subfolder}&type={vtype}"
                        url = f"http://{COMFYUI_SERVER}/view{params}"
                        
                        print(f"  📥 下载视频...")
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
                            meta = {
                                "title": news_title,
                                "timestamp": datetime.now().isoformat(),
                                "model": "LTX-2-19B-GGUF",
                                "style": "xianxia"
                            }
                            with open(filepath.with_suffix('.json'), 'w') as f:
                                json.dump(meta, f, indent=2, ensure_ascii=False)
            
            # 图片
            if 'images' in output:
                for img in output['images']:
                    filename = img.get('filename')
                    if filename:
                        subfolder = img.get('subfolder', '')
                        itype = img.get('type', 'output')
                        params = f"?filename={filename}&subfolder={subfolder}&type={itype}"
                        url = f"http://{COMFYUI_SERVER}/view{params}"
                        
                        resp = requests.get(url, timeout=30)
                        if resp.status_code == 200:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_title = news_title.replace(" ", "_")
                            filepath = OUTPUT_DIR / f"{ts}_{safe_title}_{filename}"
                            
                            with open(filepath, 'wb') as f:
                                f.write(resp.content)
                            
                            print(f"  ✅ 图片：{filepath.name}")
                            downloaded.append(str(filepath))
        
        return downloaded
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return []


def generate(topic, index, total):
    """生成单个视频"""
    print(f"\n{'='*60}")
    print(f"[{index}/{total}] 📰 {topic['title']}")
    print(f"🎨 {topic['prompt'][:50]}...")
    print(f"{'='*60}")
    
    # 加载工作流
    print(f"📋 加载工作流...")
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    # 转换为 API 格式并更新提示词
    print(f"🔄 转换工作流...")
    api_prompt = convert_workflow_to_api(workflow, topic['prompt'], topic['negative'])
    
    # 提交
    client_id = str(uuid.uuid4())
    prompt_id = queue_prompt(api_prompt, client_id)
    if not prompt_id:
        return {"success": False, "error": "提交失败", "title": topic['title']}
    
    # 监控
    if not monitor_progress(prompt_id, client_id):
        return {"success": False, "error": "生成超时", "title": topic['title']}
    
    # 下载
    files = download_result(prompt_id, topic['title'])
    
    return {
        "success": len(files) > 0,
        "files": files,
        "title": topic['title']
    }


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
        print(f"\n✅ ComfyUI 已连接 ({COMFYUI_SERVER})")
    except Exception as e:
        print(f"❌ 无法连接 ComfyUI: {e}")
        return 1
    
    # 显示主题
    print(f"\n📋 新闻主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择模式
    print(f"\n请选择:")
    print(f"  1. 生成所有 ({len(NEWS_TOPICS)}个，约 10-25 分钟)")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")
    
    choice = input("\n输入选择 (1/2/3): ").strip()
    
    results = []
    
    if choice == '1':
        print(f"\n🚀 开始批量生成...")
        for i, topic in enumerate(NEWS_TOPICS, 1):
            result = generate(topic, i, len(NEWS_TOPICS))
            results.append(result)
            if i < len(NEWS_TOPICS):
                print(f"\n⏸️  等待 5 秒...")
                time.sleep(5)
    elif choice == '2':
        idx = int(input("输入序号 (1-5): ").strip())
        if 1 <= idx <= len(NEWS_TOPICS):
            results.append(generate(NEWS_TOPICS[idx-1], 1, 1))
        else:
            print("无效选择")
            return 1
    elif choice == '3':
        print(f"\n🧪 测试模式：生成第一个新闻")
        results.append(generate(NEWS_TOPICS[0], 1, 1))
    else:
        print("无效选择")
        return 1
    
    # 汇总
    print(f"\n{'='*60}")
    print("📊 生成结果汇总")
    print(f"{'='*60}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 目录：{OUTPUT_DIR}")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "success": success,
        "results": results
    }
    report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 报告：{report_file}")
    
    if success > 0:
        print(f"\n🎉 生成完成！")
    
    return 0


if __name__ == "__main__":
    exit(main())
