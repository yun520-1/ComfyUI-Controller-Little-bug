#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI LTX2 仙人古装新闻视频生成器
优化版本 - 直接使用本地 LTX2 模型和工作流
"""

import json
import uuid
import time
import argparse
import websocket
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import copy

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_ltx2_news"
LTX2_WORKFLOW = COMFYUI_PATH / "user" / "default" / "workflows" / "ltx2_t2v_gguf.json"

# LTX2 模型
LTX2_MODEL = "ltx-2-19b-dev-Q3_K_S.gguf"
LTX2_CLIP = "gemma-3-12b-it-qat-Q3_K_S.gguf"
LTX2_VAE = "ltx-2-19b-dev_video_vae.safetensors"

# 仙人古装新闻主题（2026 年 3 月最新）
XIANXIA_NEWS_TOPICS = [
    {"title": "两会召开", "news": "全国人民代表大会和政协会议在北京召开", "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感", "negative": "blurry, low quality, still frame, modern clothes, suit"},
    {"title": "汪峰演唱会", "news": "2026 汪峰武汉演唱会将于 3 月 14 日举行", "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台", "negative": "blurry, low quality, still frame, modern clothes, microphone"},
    {"title": "海洋经济", "news": "推动海洋经济高质量发展", "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚", "negative": "blurry, low quality, still frame, modern ship, boat"},
    {"title": "西湖马拉松", "news": "西湖半程马拉松 3 月 22 日开跑", "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格", "negative": "blurry, low quality, still frame, modern clothes, running"},
    {"title": "人工智能", "news": "金华抢抓人工智能发展机遇", "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合", "negative": "blurry, low quality, still frame, computer, modern tech"}
]


class LTX2Generator:
    """LTX2 视频生成器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        
    def check_connection(self) -> bool:
        """检查连接"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                print(f"✅ ComfyUI: {self.server}")
                return True
        except Exception as e:
            print(f"❌ 无法连接：{e}")
        return False
    
    def check_models(self) -> bool:
        """检查本地模型"""
        print(f"\n🔍 检查 LTX2 模型...")
        models = {
            "unet": COMFYUI_PATH / "models" / "unet" / LTX2_MODEL,
            "clip": COMFYUI_PATH / "models" / "text_encoders" / LTX2_CLIP,
            "vae": COMFYUI_PATH / "models" / "vae" / LTX2_VAE,
            "workflow": LTX2_WORKFLOW
        }
        
        all_ok = True
        for name, path in models.items():
            if path.exists():
                size = path.stat().st_size / (1024**3)
                print(f"   ✅ {name}: {path.name} ({size:.1f}GB)")
            else:
                print(f"   ❌ {name}: 缺失")
                all_ok = False
        return all_ok
    
    def load_workflow(self) -> Dict:
        """加载工作流"""
        with open(LTX2_WORKFLOW, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def update_prompts(self, workflow: Dict, prompt: str, negative: str) -> Dict:
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
    
    def convert_to_api(self, workflow: Dict) -> Dict:
        """转换为 API 格式"""
        api_prompt = {}
        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])
        link_map = {link[0]: link for link in links}
        
        for node in nodes:
            node_id = str(node["id"])
            node_type = node.get("type", "")
            
            if node_type in ["Reroute", "Note", "PrimitiveNode", "GetImageSize"]:
                continue
            
            inputs = {}
            widgets = node.get("widgets_values", [])
            
            # Widget 处理
            if node_type == "CLIPTextEncode" and widgets: inputs["text"] = widgets[0]
            elif node_type == "EmptyLTXVLatentVideo" and len(widgets) >= 4:
                inputs.update({"width": widgets[0], "height": widgets[1], "length": widgets[2], "batch_size": widgets[3]})
            elif node_type == "UnetLoaderGGUF" and widgets: inputs["unet_name"] = widgets[0]
            elif node_type == "DualCLIPLoaderGGUF" and len(widgets) >= 2:
                inputs.update({"clip_name1": widgets[0], "clip_name2": widgets[1], "type": widgets[2] if len(widgets) > 2 else "ltxv"})
            elif node_type == "VAELoaderKJ" and widgets:
                inputs.update({"vae_name": widgets[0], "device": widgets[1] if len(widgets) > 1 else "main_device"})
            elif node_type == "KSamplerSelect" and widgets: inputs["sampler_name"] = widgets[0]
            elif node_type == "LTXVScheduler" and len(widgets) >= 5:
                inputs.update({"steps": widgets[0], "max_shift": widgets[1], "base_shift": widgets[2], "stretch": widgets[3], "terminal": widgets[4]})
            elif node_type == "CFGGuider" and widgets: inputs["cfg"] = widgets[0]
            elif node_type == "RandomNoise" and widgets: inputs["noise_seed"] = widgets[0]
            elif node_type == "LoraLoaderModelOnly" and len(widgets) >= 2:
                inputs.update({"lora_name": widgets[0], "strength_model": widgets[1]})
            elif node_type == "SaveVideo" and widgets:
                inputs.update({"filename_prefix": widgets[0], "format": widgets[1] if len(widgets) > 1 else "mp4"})
            elif node_type == "CreateVideo" and widgets: inputs["fps"] = widgets[0]
            
            # 连接处理
            for inp in node.get("inputs", []):
                input_name, link_id = inp.get("name"), inp.get("link")
                if link_id and link_id in link_map and input_name:
                    link = link_map[link_id]
                    src_node_id, src_output = str(link[1]), link[2]
                    
                    # 跳过 Reroute
                    src_node = next((n for n in nodes if str(n["id"]) == src_node_id), None)
                    if src_node and src_node.get("type") == "Reroute":
                        for r_inp in src_node.get("inputs", []):
                            r_link_id = r_inp.get("link")
                            if r_link_id and r_link_id in link_map:
                                r_link = link_map[r_link_id]
                                src_node_id, src_output = str(r_link[1]), r_link[2]
                                break
                    
                    inputs[input_name] = [src_node_id, src_output]
            
            if inputs or node_type in ["CLIPTextEncode", "EmptyLTXVLatentVideo", "UnetLoaderGGUF", "VAELoaderKJ", "DualCLIPLoaderGGUF"]:
                api_prompt[node_id] = {"class_type": node_type, "inputs": inputs}
        
        return api_prompt
    
    def queue_prompt(self, api_prompt: Dict) -> str:
        """提交任务"""
        try:
            resp = requests.post(f"{self.base_url}/prompt", json={"prompt": api_prompt, "client_id": self.client_id}, timeout=30)
            if resp.status_code == 200:
                prompt_id = resp.json().get('prompt_id')
                print(f"✅ 已提交 (ID: {prompt_id})")
                return prompt_id
        except Exception as e:
            print(f"❌ 提交失败：{e}")
        return None
    
    def monitor(self, prompt_id: str, timeout: int = 600) -> bool:
        """监控进度"""
        try:
            ws = websocket.WebSocket()
            ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            print(f"⏳ 生成中...", end=" ", flush=True)
            start = time.time()
            last_pct = -1
            
            while time.time() - start < timeout:
                if int(time.time() - start) % 30 == 0 and int(time.time() - start) > 0:
                    print(f"{int((time.time() - start)/60)}min", end=" ", flush=True)
                
                try:
                    msg = json.loads(ws.recv())
                    if msg.get('type') == 'progress':
                        pct = int(msg['data'].get('value', 0) / msg['data'].get('max', 100) * 100)
                        if pct != last_pct:
                            print(f"{pct}%", end=" ", flush=True)
                            last_pct = pct
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
    
    def download(self, prompt_id: str, title: str) -> List[str]:
        """下载结果"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            history = resp.json()
            if prompt_id not in history:
                return []
            
            outputs = history[prompt_id].get('outputs', {})
            downloaded = []
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            for node_id, output in outputs.items():
                for key, items in [('video', output.get('video', [])), ('images', output.get('images', []))]:
                    for item in items:
                        filename = item.get('filename')
                        if filename:
                            params = f"?filename={filename}&subfolder={item.get('subfolder', '')}&type={item.get('type', 'output')}"
                            url = f"{self.base_url}/view{params}"
                            resp = requests.get(url, timeout=120 if key == 'video' else 30)
                            if resp.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filepath = OUTPUT_DIR / f"{ts}_{title.replace(' ', '_')}.{('mp4' if key == 'video' else 'png')}"
                                with open(filepath, 'wb') as f:
                                    f.write(resp.content)
                                print(f"  ✅ {filepath.name}")
                                downloaded.append(str(filepath))
            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def generate(self, topic: Dict, idx: int, total: int) -> Dict:
        """生成单个视频"""
        print(f"\n{'='*70}\n[{idx}/{total}] 📰 {topic['title']}\n📝 {topic['news']}\n🎨 {topic['prompt'][:50]}...\n{'='*70}")
        
        # 加载并更新
        print(f"\n📋 加载工作流...")
        workflow = self.load_workflow()
        print(f"\n🔄 更新提示词...")
        workflow = self.update_prompts(workflow, topic['prompt'], topic['negative'])
        
        # 转换并提交
        print(f"\n🔄 转换 API 格式...")
        api_prompt = self.convert_to_api(workflow)
        print(f"   API 节点：{len(api_prompt)}")
        
        prompt_id = self.queue_prompt(api_prompt)
        if not prompt_id:
            return {"success": False, "error": "提交失败", "title": topic['title']}
        
        if not self.monitor(prompt_id):
            return {"success": False, "error": "生成失败", "title": topic['title']}
        
        files = self.download(prompt_id, topic['title'])
        return {"success": len(files) > 0, "files": files, "title": topic['title']}
    
    def batch_generate(self, topics: List[Dict]) -> List[Dict]:
        """批量生成"""
        results = []
        print(f"\n🚀 批量生成 {len(topics)} 个视频...")
        print(f"💾 {OUTPUT_DIR}\n")
        
        for i, topic in enumerate(topics, 1):
            results.append(self.generate(topic, i, len(topics)))
            if i < len(topics):
                time.sleep(5)
        
        return results


def main():
    print("="*70)
    print("🎬 LTX2 仙人古装新闻视频生成器")
    print("📅 2026 年 3 月最新新闻")
    print("="*70)
    
    gen = LTX2Generator()
    
    if not gen.check_connection():
        return 1
    
    if not gen.check_models():
        print("\n⚠️  部分模型缺失")
    
    # 显示主题
    print(f"\n📋 主题 ({len(XIANXIA_NEWS_TOPICS)}个):")
    for i, t in enumerate(XIANXIA_NEWS_TOPICS, 1):
        print(f"  {i}. {t['title']}")
    
    # 选择
    print(f"\n请选择:")
    print(f"  1. 生成所有  2. 生成单个  3. 测试第一个")
    choice = input("\n输入 (1/2/3): ").strip()
    
    topics = []
    if choice == '1':
        topics = XIANXIA_NEWS_TOPICS
    elif choice == '2':
        idx = int(input("序号 (1-5): ").strip())
        topics = [XIANXIA_NEWS_TOPICS[idx-1]] if 1 <= idx <= 5 else []
    elif choice == '3':
        topics = [XIANXIA_NEWS_TOPICS[0]]
    
    if not topics:
        print("无效选择")
        return 1
    
    # 生成
    results = gen.batch_generate(topics)
    
    # 汇总
    print(f"\n{'='*70}\n📊 结果\n{'='*70}")
    success = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success}/{len(results)}")
    print(f"💾 {OUTPUT_DIR}")
    
    # 报告
    report = {"timestamp": datetime.now().isoformat(), "success": success, "results": results}
    report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 {report_file}")
    
    return 0


if __name__ == "__main__":
    exit(main())
