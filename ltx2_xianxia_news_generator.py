#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2 仙人古装新闻视频生成器
使用已有的 LTX-2-19B GGUF 模型生成仙人古装风格新闻视频
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

# 新闻主题（2026 年 3 月最新）
NEWS_TOPICS = [
    {
        "title": "两会召开",
        "prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感",
        "negative": "blurry, low quality, still frame, modern clothes, suit, modern building, watermark, titles, subtitles"
    },
    {
        "title": "汪峰演唱会",
        "prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，音乐仙境，动态表演，电影感",
        "negative": "blurry, low quality, still frame, modern clothes, microphone, stage, watermark, titles"
    },
    {
        "title": "海洋经济",
        "prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感，动态海浪，电影感",
        "negative": "blurry, low quality, still frame, modern ship, boat, watermark, titles, subtitles"
    },
    {
        "title": "西湖马拉松",
        "prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行，湖光山色，电影感",
        "negative": "blurry, low quality, still frame, modern clothes, running, marathon, watermark, titles"
    },
    {
        "title": "人工智能",
        "prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文，动态光效，电影感",
        "negative": "blurry, low quality, still frame, computer, modern tech, watermark, titles, subtitles"
    }
]


class LTX2XianxiaGenerator:
    """LTX2 仙人古装视频生成器"""
    
    def __init__(self, server=COMFYUI_SERVER, workflow_path=LTX2_WORKFLOW_PATH):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.workflow_path = Path(workflow_path)
        self.client_id = str(uuid.uuid4())
        
    def check_connection(self) -> bool:
        """检查连接"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                print(f"✅ 已连接到 ComfyUI ({self.server})")
                return True
        except Exception as e:
            print(f"❌ 无法连接 ComfyUI: {e}")
        return False
    
    def load_workflow(self) -> Dict:
        """加载 LTX2 工作流"""
        if not self.workflow_path.exists():
            raise FileNotFoundError(f"工作流文件不存在：{self.workflow_path}")
        
        with open(self.workflow_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        print(f"✅ 已加载 LTX2 工作流")
        return workflow
    
    def update_workflow_prompt(self, workflow: Dict, prompt: str, negative: str) -> Dict:
        """更新工作流提示词"""
        workflow_copy = copy.deepcopy(workflow)
        
        # LTX2 工作流格式：nodes 是列表
        nodes = workflow_copy.get("nodes", [])
        
        for node in nodes:
            if not isinstance(node, dict):
                continue
            
            if node.get("type") == "CLIPTextEncode":
                widgets_value = node.get("widgets_values", [])
                if isinstance(widgets_value, list) and len(widgets_value) > 0:
                    current_text = widgets_value[0] if isinstance(widgets_value[0], str) else ""
                    # 判断是正向还是负面提示词
                    if "blurry" in current_text.lower() or "low quality" in current_text.lower():
                        # 负面提示词
                        node["widgets_values"][0] = negative
                        print(f"   ✅ 负面提示词已更新")
                    else:
                        # 正向提示词
                        node["widgets_values"][0] = prompt
                        print(f"   ✅ 正向提示词已更新")
        
        return workflow_copy
    
    def queue_prompt(self, workflow: Dict) -> str:
        """提交任务"""
        try:
            # LTX2 工作流格式转换：从 ComfyUI 格式转换为 API 格式
            prompt_dict = {}
            
            # 如果是 ComfyUI 导出格式（包含 nodes 列表）
            if "nodes" in workflow:
                # 转换为节点字典格式
                for node in workflow["nodes"]:
                    if not isinstance(node, dict):
                        continue
                    node_id = str(node.get("id", ""))
                    if node_id:
                        prompt_dict[node_id] = {
                            "class_type": node.get("type", ""),
                            "inputs": {}
                        }
                        # 提取 widgets_values 作为 inputs
                        widgets = node.get("widgets_values", [])
                        if widgets:
                            # 根据节点类型处理
                            node_type = node.get("type", "")
                            if node_type == "CLIPTextEncode":
                                prompt_dict[node_id]["inputs"]["text"] = widgets[0] if len(widgets) > 0 else ""
                            elif node_type == "EmptyLTXVLatentVideo":
                                prompt_dict[node_id]["inputs"]["width"] = widgets[0] if len(widgets) > 0 else 768
                                prompt_dict[node_id]["inputs"]["height"] = widgets[1] if len(widgets) > 1 else 512
                                prompt_dict[node_id]["inputs"]["length"] = widgets[2] if len(widgets) > 2 else 97
                                prompt_dict[node_id]["inputs"]["batch_size"] = widgets[3] if len(widgets) > 3 else 1
            else:
                # 已经是 API 格式
                prompt_dict = workflow
            
            # 提交
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": prompt_dict, "client_id": self.client_id},
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get('prompt_id')
                print(f"✅ 任务已提交 (ID: {prompt_id})")
                return prompt_id
            else:
                print(f"❌ 提交失败：{resp.status_code}")
                print(f"响应：{resp.text[:500]}")
        except Exception as e:
            print(f"❌ 提交失败：{e}")
            import traceback
            traceback.print_exc()
        return None
    
    def monitor_progress(self, prompt_id: str, timeout: int = 600) -> bool:
        """监控进度（LTX2 视频生成较慢）"""
        import websocket
        
        try:
            ws = websocket.WebSocket()
            ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            
            print(f"⏳ 视频生成中...", end=" ", flush=True)
            start_time = time.time()
            last_update = time.time()
            
            while time.time() - start_time < timeout:
                if time.time() - last_update > 30:
                    print(f"{int((time.time() - start_time)/60)}分钟", end=" ", flush=True)
                    last_update = time.time()
                
                try:
                    msg = json.loads(ws.recv())
                    msg_type = msg.get('type')
                    data = msg.get('data', {})
                    
                    if msg_type == 'progress':
                        step = data.get('value', 0)
                        total = data.get('max', 100)
                        percent = int(step / total * 100)
                        print(f"{percent}%", end=" ", flush=True)
                    elif msg_type == 'executing':
                        if data.get('node') is None:
                            print("✅")
                            ws.close()
                            return True
                except:
                    continue
            
            ws.close()
            print("⏰ 超时!")
            return False
        except Exception as e:
            print(f"❌ 监控失败：{e}")
            return False
    
    def download_video(self, prompt_id: str, news_title: str) -> List[str]:
        """下载生成的视频"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=5)
            history = resp.json()
            
            if prompt_id not in history:
                print("❌ 未找到历史记录")
                return []
            
            outputs = history[prompt_id].get('outputs', {})
            downloaded = []
            
            for node_id, node_output in outputs.items():
                # 检查视频输出
                if 'video' in node_output:
                    for video in node_output['video']:
                        if 'filename' in video:
                            params = {
                                'filename': video['filename'],
                                'subfolder': video.get('subfolder', ''),
                                'type': video.get('type', 'output')
                            }
                            url = f"{self.base_url}/view?{json.dumps(params)}"
                            
                            resp = requests.get(url, timeout=120)
                            if resp.status_code == 200:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                safe_title = news_title.replace(" ", "_")
                                filename = f"{timestamp}_{safe_title}.mp4"
                                save_path = OUTPUT_DIR / filename
                                
                                with open(save_path, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"  ✅ 视频已保存：{filename}")
                                downloaded.append(str(save_path))
                                
                                # 保存元数据
                                meta = {
                                    "news_title": news_title,
                                    "prompt": history[prompt_id].get('prompt', ''),
                                    "timestamp": datetime.now().isoformat(),
                                    "model": "LTX-2-19B-GGUF",
                                    "style": "xianxia_ancient"
                                }
                                meta_path = save_path.with_suffix('.json')
                                with open(meta_path, 'w', encoding='utf-8') as f:
                                    json.dump(meta, f, ensure_ascii=False, indent=2)
                
                # 检查图片输出（如果有）
                if 'images' in node_output:
                    for img in node_output['images']:
                        if 'filename' in img:
                            params = {
                                'filename': img['filename'],
                                'subfolder': img.get('subfolder', ''),
                                'type': img.get('type', 'output')
                            }
                            url = f"{self.base_url}/view?{json.dumps(params)}"
                            
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                safe_title = news_title.replace(" ", "_")
                                filename = f"{timestamp}_{safe_title}_{img['filename']}"
                                save_path = OUTPUT_DIR / filename
                                
                                with open(save_path, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"  ✅ 图片已保存：{filename}")
                                downloaded.append(str(save_path))
            
            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def generate_video(self, news_topic: Dict) -> Dict:
        """生成单个新闻视频"""
        print(f"\n{'='*60}")
        print(f"📰 新闻：{news_topic['title']}")
        print(f"🎨 仙人风格：{news_topic['prompt'][:50]}...")
        print(f"{'='*60}")
        
        # 加载工作流
        workflow = self.load_workflow()
        
        # 更新提示词
        workflow = self.update_workflow_prompt(
            workflow,
            news_topic['prompt'],
            news_topic['negative']
        )
        
        # 提交任务（需要提取 prompt 字段）
        prompt_dict = workflow  # LTX2 工作流直接就是 prompt 字典
        prompt_id = self.queue_prompt(prompt_dict)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}
        
        # 监控进度
        if not self.monitor_progress(prompt_id):
            return {"success": False, "error": "生成失败"}
        
        # 下载视频
        files = self.download_video(prompt_id, news_topic['title'])
        
        return {
            "success": len(files) > 0,
            "files": files,
            "news_title": news_topic['title']
        }
    
    def batch_generate(self, news_topics: List[Dict]) -> List[Dict]:
        """批量生成"""
        results = []
        
        print(f"\n🚀 开始批量生成仙人古装新闻视频，共 {len(news_topics)} 个主题")
        print(f"💾 输出目录：{OUTPUT_DIR}")
        print(f"⏱️  预计每个视频 2-5 分钟\n")
        
        for i, topic in enumerate(news_topics, 1):
            print(f"\n[{i}/{len(news_topics)}]")
            result = self.generate_video(topic)
            results.append(result)
            
            # 任务间等待
            if i < len(news_topics):
                print(f"\n⏸️  等待 5 秒...")
                time.sleep(5)
        
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """生成报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "success": sum(1 for r in results if r.get('success')),
            "details": results
        }
        
        report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存：{report_file}")
        return str(report_file)


def main():
    print("="*60)
    print("🎬 LTX2 仙人古装新闻视频生成器")
    print("📅 2026 年 3 月最新新闻")
    print("🤖 模型：LTX-2-19B-GGUF (Q3_K_S)")
    print("="*60)
    
    generator = LTX2XianxiaGenerator(COMFYUI_SERVER)
    
    # 检查连接
    if not generator.check_connection():
        print("\n❌ 无法连接到 ComfyUI，请确保 ComfyUI 正在运行在 8189 端口")
        return 1
    
    # 显示新闻主题
    print(f"\n📋 新闻主题列表 ({len(NEWS_TOPICS)}个):")
    for i, topic in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {topic['title']}")
    
    # 询问生成模式
    print(f"\n请选择生成模式:")
    print("  1. 生成所有新闻视频 (推荐，约 10-25 分钟)")
    print("  2. 生成单个新闻视频")
    print("  3. 仅测试第一个新闻")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == '1':
        # 批量生成
        results = generator.batch_generate(NEWS_TOPICS)
    elif choice == '2':
        # 单个生成
        print("\n选择新闻主题:")
        for i, topic in enumerate(NEWS_TOPICS, 1):
            print(f"  {i}. {topic['title']}")
        
        topic_idx = int(input("请输入序号 (1-5): ").strip())
        if 1 <= topic_idx <= len(NEWS_TOPICS):
            results = [generator.generate_video(NEWS_TOPICS[topic_idx-1])]
        else:
            print("无效选择")
            return 1
    elif choice == '3':
        # 测试第一个
        print("\n🧪 测试模式：仅生成第一个新闻")
        results = [generator.generate_video(NEWS_TOPICS[0])]
    else:
        print("无效选择")
        return 1
    
    # 生成报告
    generator.generate_report(results)
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("📊 生成结果汇总")
    print(f"{'='*60}")
    success_count = sum(1 for r in results if r.get('success'))
    print(f"✅ 成功：{success_count}/{len(results)}")
    print(f"💾 目录：{OUTPUT_DIR}")
    
    if success_count > 0:
        print(f"\n🎉 生成完成！请查看输出目录")
    
    return 0


if __name__ == "__main__":
    exit(main())
