#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频生成器 - 后台运行版
直接使用 ComfyUI API，无需浏览器
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
WORKFLOW_FILE = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"

# 新闻主题
NEWS_TOPICS = [
    {"title": "两会召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感，史诗感", "negative": "blurry, low quality, still frame, modern clothes, suit, watermark, titles, subtitles"},
    {"title": "汪峰演唱会", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，动态表演，电影感", "negative": "blurry, low quality, still frame, modern clothes, microphone, watermark"},
    {"title": "海洋经济", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感，动态", "negative": "blurry, low quality, still frame, modern ship, boat, watermark"},
    {"title": "西湖马拉松", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行，湖光山色", "negative": "blurry, low quality, still frame, modern clothes, running, watermark"},
    {"title": "人工智能", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文，动态光效", "negative": "blurry, low quality, still frame, computer, modern tech, watermark"}
]


def load_workflow_json():
    """加载工作流 JSON"""
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_api_prompt(workflow, prompt_text, negative_text):
    """
    构建 API 格式的 prompt
    关键：正确处理节点连接，跳过 Reroute 等特殊节点
    """
    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])
    
    # 创建 link 查找表：link_id -> (src_node_id, src_output_slot, dst_node_id, dst_input_name)
    link_map = {}
    for link in links:
        link_id, src_node_id, src_output, dst_node_id, dst_input = link[0], str(link[1]), link[2], str(link[3]), link[4]
        link_map[link_id] = {
            "src_node": src_node_id,
            "src_output": src_output,
            "dst_node": dst_node_id,
            "dst_input": dst_input
        }
    
    # 创建节点查找表
    node_map = {str(node["id"]): node for node in nodes}
    
    # 构建 API prompt
    api_prompt = {}
    
    for node in nodes:
        node_id = str(node["id"])
        node_type = node.get("type", "")
        
        # 跳过不需要提交的节点
        if node_type in ["Reroute", "Note", "PrimitiveNode", "GetImageSize", "LTXVCropGuides", "LTXVConcatAVLatent", "LTXVSeparateAVLatent", "LTXVLatentUpsampler", "SamplerCustomAdvanced", "LTXVConditioning", "LTXVEmptyLatentAudio", "LTXVAudioVAEDecode", "LTXVConcatAVLatent"]:
            continue
        
        # 获取 widget 值
        widgets = node.get("widgets_values", [])
        
        # 构建 inputs
        inputs = {}
        
        # 1. 处理 widget 值作为 inputs
        if node_type == "CLIPTextEncode":
            if widgets and isinstance(widgets[0], str):
                current = widgets[0]
                if "blurry" in current.lower() or "low quality" in current.lower():
                    inputs["text"] = negative_text
                    print(f"   [节点{node_id}] 负面提示词已更新")
                else:
                    inputs["text"] = prompt_text
                    print(f"   [节点{node_id}] 正向提示词已更新")
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
            inputs["noise_seed"] = int(time.time() * 1000) % 1000000
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
        
        # 2. 处理节点输入连接
        for inp in node.get("inputs", []):
            input_name = inp.get("name", "input")
            link_id = inp.get("link")
            
            if link_id and link_id in link_map:
                link_info = link_map[link_id]
                src_node_id = link_info["src_node"]
                src_output = link_info["src_output"]
                
                # 跳过 Reroute，找到实际源节点
                src_node = node_map.get(src_node_id, {})
                if src_node.get("type") == "Reroute":
                    # 找到 Reroute 的输入 link
                    for r_inp in src_node.get("inputs", []):
                        r_link_id = r_inp.get("link")
                        if r_link_id and r_link_id in link_map:
                            r_link = link_map[r_link_id]
                            src_node_id = r_link["src_node"]
                            src_output = r_link["src_output"]
                            break
                
                # 添加连接
                inputs[input_name] = [src_node_id, src_output]
        
        # 添加到 api_prompt
        api_prompt[node_id] = {
            "class_type": node_type,
            "inputs": inputs
        }
    
    return api_prompt


def queue_prompt(api_prompt, client_id):
    """提交任务"""
    try:
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
                print(f"错误详情：{json.dumps(err, indent=2, ensure_ascii=False)}")
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
        last_msg_time = time.time()
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            
            # 每 30 秒显示一次时间
            if time.time() - last_msg_time > 30:
                print(f"{int(elapsed/60)}分钟", end=" ", flush=True)
                last_msg_time = time.time()
            
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
                            
                            print(f"  ✅ 视频已保存：{filepath.name}")
                            downloaded.append(str(filepath))
                            
                            # 元数据
                            meta = {
                                "title": news_title,
                                "timestamp": datetime.now().isoformat(),
                                "model": "LTX-2-19B-GGUF",
                                "style": "xianxia_ancient",
                                "prompt": news_title
                            }
                            with open(filepath.with_suffix('.json'), 'w', encoding='utf-8') as f:
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
    print(f"\n{'='*70}")
    print(f"[{index}/{total}] 📰 新闻：{topic['title']}")
    print(f"🎨 提示词：{topic['prompt'][:50]}...")
    print(f"{'='*70}")
    
    # 加载工作流
    print(f"\n📋 加载工作流...")
    workflow = load_workflow_json()
    print(f"   工作流 ID: {workflow.get('id', 'N/A')[:20]}...")
    print(f"   节点数：{workflow.get('last_node_id', 0)}")
    
    # 构建 API prompt
    print(f"\n🔄 转换工作流格式...")
    api_prompt = build_api_prompt(workflow, topic['prompt'], topic['negative'])
    print(f"   API 节点数：{len(api_prompt)}")
    
    # 提交
    client_id = str(uuid.uuid4())
    print(f"\n🚀 提交任务...")
    prompt_id = queue_prompt(api_prompt, client_id)
    if not prompt_id:
        return {"success": False, "error": "提交失败", "title": topic['title']}
    
    # 监控
    if not monitor_progress(prompt_id, client_id):
        return {"success": False, "error": "生成失败", "title": topic['title']}
    
    # 下载
    files = download_result(prompt_id, topic['title'])
    
    return {
        "success": len(files) > 0,
        "files": files,
        "title": topic['title']
    }


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频生成器 - 后台运行版")
    print("📅 2026 年 3 月最新新闻")
    print("🤖 模型：LTX-2-19B-GGUF (Q3_K_S)")
    print("="*70)
    
    # 检查连接
    try:
        resp = requests.get(f"http://{COMFYUI_SERVER}/system_stats", timeout=5)
        if resp.status_code != 200:
            print("❌ 无法连接 ComfyUI")
            return 1
        print(f"\n✅ ComfyUI 已连接：{COMFYUI_SERVER}")
        print(f"💾 输出目录：{OUTPUT_DIR}")
    except Exception as e:
        print(f"❌ 无法连接 ComfyUI: {e}")
        return 1
    
    # 显示主题
    print(f"\n📋 新闻主题 ({len(NEWS_TOPICS)}个):")
    for i, t in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择模式
    print(f"\n请选择生成模式:")
    print(f"  1. 生成所有 ({len(NEWS_TOPICS)}个，约 10-25 分钟)")
    print(f"  2. 生成单个")
    print(f"  3. 测试第一个")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    results = []
    
    if choice == '1':
        print(f"\n🚀 开始批量生成所有新闻视频...")
        for i, topic in enumerate(NEWS_TOPICS, 1):
            result = generate(topic, i, len(NEWS_TOPICS))
            results.append(result)
            if i < len(NEWS_TOPICS):
                print(f"\n⏸️  等待 5 秒，准备下一个...")
                time.sleep(5)
    elif choice == '2':
        idx = int(input("请输入序号 (1-5): ").strip())
        if 1 <= idx <= len(NEWS_TOPICS):
            results.append(generate(NEWS_TOPICS[idx-1], 1, 1))
        else:
            print("无效选择")
            return 1
    elif choice == '3':
        print(f"\n🧪 测试模式：生成第一个新闻视频")
        results.append(generate(NEWS_TOPICS[0], 1, 1))
    else:
        print("无效选择")
        return 1
    
    # 汇总
    print(f"\n{'='*70}")
    print("📊 生成结果汇总")
    print(f"{'='*70}")
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
        print(f"\n🎉 生成完成！ComfyUI 保持运行状态")
    else:
        print(f"\n⚠️  生成失败，请检查 ComfyUI 日志")
    
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print(f"\n\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
