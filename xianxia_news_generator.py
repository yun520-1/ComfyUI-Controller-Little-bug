#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仙人古装风格新闻视频生成器
使用最新新闻主题，生成仙人/古装风格的图片/视频
"""

import json
import uuid
import time
import requests
import websocket
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# ComfyUI 配置
COMFYUI_SERVER = "127.0.0.1:8189"
OUTPUT_DIR = Path.home() / "Downloads" / "xianxia_news"

# 最新新闻主题（2026 年 3 月）
NEWS_TOPICS = [
    {
        "title": "两会召开",
        "description": "全国人民代表大会和政协会议在北京召开",
        "xianxia_prompt": "仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨"
    },
    {
        "title": "汪峰演唱会",
        "description": "2026 汪峰武汉演唱会将于 3 月 14 日在武汉光谷国际网球中心举行",
        "xianxia_prompt": "仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台"
    },
    {
        "title": "海洋经济高质量发展",
        "description": "习近平总书记文章推动海洋经济高质量发展",
        "xianxia_prompt": "东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚"
    },
    {
        "title": "西湖马拉松",
        "description": "西湖半程马拉松 3 月 22 日开跑",
        "xianxia_prompt": "仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格"
    },
    {
        "title": "人工智能发展",
        "description": "金华抢抓人工智能发展机遇",
        "xianxia_prompt": "仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合"
    }
]

class XianxiaVideoGenerator:
    """仙人古装风格视频生成器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.ws = None
        
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
    
    def create_xianxia_workflow(self, prompt: str, negative: str = "",
                                width: int = 1024, height: int = 512,
                                steps: int = 25, cfg: float = 7,
                                frames: int = 16, is_video: bool = True) -> Dict:
        """创建仙人古装风格工作流"""
        
        # 基础提示词增强
        style_enhance = "，仙侠风格，古装，仙风道骨，精致，高清，电影感，史诗感，中国风，传统美学"
        full_prompt = prompt + style_enhance
        
        if not negative:
            negative = "现代服装，西装，现代建筑，低质量，模糊，变形，丑陋"
        
        if is_video:
            # 视频工作流（使用 AnimateDiff 或类似节点）
            workflow = {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "cfg": cfg,
                        "denoise": 1,
                        "latent_image": ["5", 0],
                        "model": ["4", 0],
                        "negative": ["7", 0],
                        "positive": ["6", 0],
                        "sampler_name": "euler_ancestral",
                        "scheduler": "normal",
                        "seed": int(time.time() * 1000) % 1000000,
                        "steps": steps
                    }
                },
                "4": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": "v1-5-pruned-emaonly.ckpt"
                    }
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {
                        "batch_size": frames,
                        "height": height,
                        "width": width
                    }
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "clip": ["4", 1],
                        "text": full_prompt
                    }
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "clip": ["4", 1],
                        "text": negative
                    }
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {
                        "samples": ["3", 0],
                        "vae": ["4", 2]
                    }
                },
                "9": {
                    "class_type": "SaveImage",
                    "inputs": {
                        "filename_prefix": f"Xianxia_News_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        "images": ["8", 0]
                    }
                }
            }
        else:
            # 图片工作流
            workflow = {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "cfg": cfg,
                        "denoise": 1,
                        "latent_image": ["5", 0],
                        "model": ["4", 0],
                        "negative": ["7", 0],
                        "positive": ["6", 0],
                        "sampler_name": "euler_ancestral",
                        "scheduler": "normal",
                        "seed": int(time.time() * 1000) % 1000000,
                        "steps": steps
                    }
                },
                "4": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": "v1-5-pruned-emaonly.ckpt"
                    }
                },
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {
                        "batch_size": 1,
                        "height": height,
                        "width": width
                    }
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "clip": ["4", 1],
                        "text": full_prompt
                    }
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "clip": ["4", 1],
                        "text": negative
                    }
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {
                        "samples": ["3", 0],
                        "vae": ["4", 2]
                    }
                },
                "9": {
                    "class_type": "SaveImage",
                    "inputs": {
                        "filename_prefix": f"Xianxia_News_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        "images": ["8", 0]
                    }
                }
            }
        
        return workflow
    
    def queue_prompt(self, workflow: Dict) -> str:
        """提交任务"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get('prompt_id')
                print(f"✅ 任务已提交 (ID: {prompt_id})")
                return prompt_id
        except Exception as e:
            print(f"❌ 提交失败：{e}")
        return None
    
    def monitor_progress(self, prompt_id: str, timeout: int = 300) -> bool:
        """监控进度"""
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            
            start_time = time.time()
            
            while True:
                if time.time() - start_time > timeout:
                    print("⏰ 超时!")
                    break
                
                try:
                    msg = json.loads(self.ws.recv())
                    msg_type = msg.get('type')
                    data = msg.get('data', {})
                    
                    if msg_type == 'progress':
                        step = data.get('value', 0)
                        total = data.get('max', 100)
                        percent = int(step / total * 100)
                        print(f"   进度：{percent}% ({step}/{total})")
                    
                    elif msg_type == 'executing':
                        if data.get('node') is None:
                            print(f"✅ 完成!")
                            return True
                except:
                    continue
                    
        except Exception as e:
            print(f"❌ 监控失败：{e}")
        finally:
            if self.ws:
                self.ws.close()
        return False
    
    def download_result(self, prompt_id: str, news_title: str) -> List[str]:
        """下载结果"""
        history_url = f"{self.base_url}/history/{prompt_id}"
        downloaded = []
        
        try:
            resp = requests.get(history_url, timeout=5)
            history = resp.json()
            
            if prompt_id not in history:
                print("❌ 未找到历史记录")
                return []
            
            outputs = history[prompt_id].get('outputs', {})
            
            # 创建输出目录
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            for node_id, node_output in outputs.items():
                if 'images' in node_output:
                    for img in node_output['images']:
                        if 'filename' in img:
                            params = {
                                'filename': img['filename'],
                                'subfolder': img.get('subfolder', ''),
                                'type': img.get('type', 'output')
                            }
                            url = f"{self.base_url}/view?{params}"
                            
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                safe_title = news_title.replace(" ", "_")
                                filename = f"{timestamp}_{safe_title}_{img['filename']}"
                                save_path = OUTPUT_DIR / filename
                                
                                with open(save_path, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"✅ 已保存：{save_path}")
                                downloaded.append(str(save_path))
                                
                                # 保存元数据
                                meta = {
                                    "news_title": news_title,
                                    "prompt": history[prompt_id].get('prompt', ''),
                                    "timestamp": datetime.now().isoformat(),
                                    "style": "xianxia_ancient"
                                }
                                meta_path = save_path.with_suffix('.json')
                                with open(meta_path, 'w', encoding='utf-8') as f:
                                    json.dump(meta, f, ensure_ascii=False, indent=2)
            
            return downloaded
            
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def generate_news_video(self, news_topic: Dict, is_video: bool = False) -> Dict:
        """生成单个新闻视频/图片"""
        print(f"\n{'='*60}")
        print(f"📰 新闻主题：{news_topic['title']}")
        print(f"📝 描述：{news_topic['description']}")
        print(f"🎨 仙人风格：{news_topic['xianxia_prompt']}")
        print(f"{'='*60}")
        
        # 确保输出目录存在
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # 创建工作流
        workflow = self.create_xianxia_workflow(
            prompt=news_topic['xianxia_prompt'],
            width=1024,
            height=512,
            steps=25,
            is_video=is_video
        )
        
        # 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}
        
        # 监控进度
        if not self.monitor_progress(prompt_id):
            return {"success": False, "error": "生成失败"}
        
        # 下载结果
        files = self.download_result(prompt_id, news_topic['title'])
        
        return {
            "success": True,
            "files": files,
            "news_title": news_topic['title']
        }
    
    def batch_generate(self, news_topics: List[Dict], is_video: bool = False) -> List[Dict]:
        """批量生成"""
        results = []
        
        print(f"\n🚀 开始批量生成仙人古装新闻视频，共 {len(news_topics)} 个主题")
        
        for i, topic in enumerate(news_topics, 1):
            print(f"\n[{i}/{len(news_topics)}]")
            result = self.generate_news_video(topic, is_video)
            results.append(result)
            
            # 任务间等待
            if i < len(news_topics):
                time.sleep(2)
        
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
    print("🎬 仙人古装风格新闻视频生成器")
    print("📅 2026 年 3 月最新新闻")
    print("="*60)
    
    generator = XianxiaVideoGenerator(COMFYUI_SERVER)
    
    # 检查连接
    if not generator.check_connection():
        print("\n❌ 无法连接到 ComfyUI，请确保 ComfyUI 正在运行在 8189 端口")
        print("启动命令：cd /path/to/ComfyUI && python main.py --listen 0.0.0.0 --port 8189")
        return 1
    
    # 显示新闻主题
    print(f"\n📋 新闻主题列表 ({len(NEWS_TOPICS)}个):")
    for i, topic in enumerate(NEWS_TOPICS, 1):
        print(f"  {i}. {topic['title']}")
    
    # 询问生成模式
    print(f"\n请选择生成模式:")
    print("  1. 生成所有新闻图片 (推荐)")
    print("  2. 生成所有新闻视频 (需要 AnimateDiff)")
    print("  3. 生成单个新闻图片")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == '1':
        # 批量生成图片
        results = generator.batch_generate(NEWS_TOPICS, is_video=False)
    elif choice == '2':
        # 批量生成视频
        print("\n⚠️  视频生成需要 AnimateDiff 或其他视频节点支持")
        confirm = input("继续？(y/n): ").strip().lower()
        if confirm == 'y':
            results = generator.batch_generate(NEWS_TOPICS, is_video=True)
        else:
            print("已取消")
            return 0
    elif choice == '3':
        # 单个生成
        print("\n选择新闻主题:")
        for i, topic in enumerate(NEWS_TOPICS, 1):
            print(f"  {i}. {topic['title']}")
        
        topic_idx = int(input("请输入序号 (1-5): ").strip())
        if 1 <= topic_idx <= len(NEWS_TOPICS):
            results = [generator.generate_news_video(NEWS_TOPICS[topic_idx-1], is_video=False)]
        else:
            print("无效选择")
            return 1
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
    print(f"💾 保存目录：{OUTPUT_DIR}")
    
    return 0


if __name__ == "__main__":
    exit(main())
