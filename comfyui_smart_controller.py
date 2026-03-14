#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能控制器 - 增强版
功能：
- AI 自动生成提示词
- 自动跑图片/视频
- 自动保存 + 智能整理文件
- 批量任务支持
- 工作流管理
"""

import json
import uuid
import time
import argparse
import websocket
import requests
import urllib.request
import urllib.parse
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
OUTPUT_DIR = Path("/home/admin/Downloads/comfyui_output")
ORGANIZED_DIR = Path("/home/admin/Downloads/comfyui_organized")

# 自动整理的分类目录
CATEGORIES = {
    "portrait": ["人物", "肖像", "人像", "girl", "boy", "woman", "man", "portrait"],
    "landscape": ["风景", "自然", "山水", "landscape", "nature", "mountain", "river"],
    "cyberpunk": ["赛博朋克", "霓虹", "未来", "cyberpunk", "neon", "futuristic"],
    "anime": ["动漫", "二次元", "anime", "manga", "cartoon"],
    "realistic": ["写实", "真实", "照片", "realistic", "photo", "real"],
    "fantasy": ["奇幻", "魔法", "幻想", "fantasy", "magic", "dragon"],
    "scifi": ["科幻", "太空", "宇宙", "sci-fi", "space", "alien"],
    "architecture": ["建筑", "房屋", "室内", "architecture", "building", "interior"],
    "animal": ["动物", "宠物", "猫", "狗", "animal", "cat", "dog"],
    "food": ["美食", "食物", "餐饮", "food", "drink", "restaurant"]
}

# AI 提示词生成模板
PROMPT_TEMPLATES = {
    "portrait": "一个{age}{gender}，{style}风格，{lighting}光线，{background}背景，高清，精致，专业摄影",
    "landscape": "{season}{time}的{scene}，{weather}，{style}风格，高分辨率，细节丰富",
    "cyberpunk": "赛博朋克风格{subject}，霓虹灯，高科技，未来城市，{time}，电影感，8K",
    "anime": "动漫风格{subject}，{art_style}画风，精致五官，{color_tone}色调，高质量",
    "fantasy": "奇幻风格{subject}，魔法元素，神秘氛围，{lighting}光线，史诗感"
}

class AIPromptGenerator:
    """AI 提示词生成器"""
    
    def __init__(self):
        self.templates = PROMPT_TEMPLATES
    
    def generate(self, subject: str, style: str = "realistic", 
                 quality: str = "high", extra_details: str = "") -> str:
        """根据主题自动生成提示词"""
        
        # 确定分类
        category = self._classify(subject)
        
        # 选择模板
        template = self.templates.get(category, self.templates["realistic"])
        
        # 填充模板
        prompt = template.format(
            age=self._random_choice(["年轻", "中年", "老年", ""]),
            gender=self._random_choice(["男性", "女性", ""]),
            style=style,
            lighting=self._random_choice(["柔和", "自然", "戏剧性", "电影"]),
            background=self._random_choice(["简洁", "虚化", "自然", "城市"]),
            season=self._random_choice(["春天", "夏天", "秋天", "冬天", ""]),
            time=self._random_choice(["清晨", "黄昏", "夜晚", "正午"]),
            scene=subject,
            weather=self._random_choice(["晴天", "多云", "雨后", "雪景"]),
            subject=subject,
            art_style=self._random_choice(["日式", "美式", "韩系", "中国风"]),
            color_tone=self._random_choice(["温暖", "冷色", "鲜艳", "柔和"]),
            time=self._random_choice(["白天", "夜晚", "黄昏"])
        )
        
        # 添加质量词
        quality_words = {
            "high": "高清，精致，高质量，细节丰富，8K",
            "medium": "高质量，清晰，细节良好",
            "low": "清晰，可用质量"
        }
        prompt += "，" + quality_words.get(quality, quality_words["high"])
        
        if extra_details:
            prompt += "，" + extra_details
        
        return prompt
    
    def generate_negative(self, style: str = "realistic") -> str:
        """自动生成负面提示词"""
        base_negative = "模糊，低质量，变形，丑陋，多余的手指，水印，文字"
        
        style_negatives = {
            "portrait": "畸形五官，不对称，恐怖谷效应",
            "landscape": "过度饱和，不自然，PS 痕迹",
            "cyberpunk": "过时风格，低科技感",
            "anime": "崩坏，比例失调，线条粗糙",
            "realistic": "卡通，绘画感，不真实"
        }
        
        return base_negative + "，" + style_negatives.get(style, "")
    
    def _classify(self, text: str) -> str:
        """简单分类"""
        text_lower = text.lower() + text
        for category, keywords in CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        return "realistic"
    
    def _random_choice(self, options: List[str]) -> str:
        """随机选择（基于时间种子）"""
        import random
        random.seed(int(time.time()) % 1000)
        return random.choice(options)
    
    def batch_generate(self, subjects: List[str], style: str = "realistic") -> List[Dict]:
        """批量生成提示词"""
        results = []
        for subject in subjects:
            prompt = self.generate(subject, style)
            negative = self.generate_negative(style)
            results.append({
                "subject": subject,
                "prompt": prompt,
                "negative": negative,
                "category": self._classify(subject)
            })
        return results


class ComfyUIIntelligentController:
    """ComfyUI 智能控制器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.prompt_generator = AIPromptGenerator()
        self.ws = None
        self.task_history = []
        
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
    
    def auto_generate_prompt(self, subject: str, style: str = "realistic", 
                            quality: str = "high") -> Dict:
        """AI 自动生成提示词"""
        print(f"\n🤖 AI 生成提示词:")
        print(f"   主题：{subject}")
        print(f"   风格：{style}")
        
        prompt = self.prompt_generator.generate(subject, style, quality)
        negative = self.prompt_generator.generate_negative(style)
        category = self.prompt_generator._classify(subject)
        
        print(f"   分类：{category}")
        print(f"   正向：{prompt[:60]}...")
        print(f"   负面：{negative[:40]}...")
        
        return {
            "prompt": prompt,
            "negative": negative,
            "category": category
        }
    
    def create_workflow(self, prompt: str, negative: str, 
                       width: int = 512, height: int = 512,
                       steps: int = 20, cfg: float = 7, 
                       seed: int = None, model: str = None) -> Dict:
        """创建工作流"""
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
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": seed if seed else int(time.time() * 1000) % 1000000,
                    "steps": steps
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model if model else "v1-5-pruned-emaonly.ckpt"
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
                    "text": prompt
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
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                }
            }
        }
        return workflow
    
    def create_video_workflow(self, prompt: str, negative: str,
                             frames: int = 16, fps: int = 8,
                             width: int = 512, height: int = 512) -> Dict:
        """创建视频生成工作流（需要 AnimateDiff 或类似节点）"""
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 8,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": int(time.time() * 1000) % 1000000,
                    "steps": 20
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
                    "text": prompt
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
                "class_type": "VideoCombine",
                "inputs": {
                    "frame_rate": fps,
                    "loop_count": 0,
                    "filename_prefix": "ComfyUI_Video",
                    "format": "video/h264-mp4",
                    "images": ["8", 0]
                }
            }
        }
        return workflow
    
    def queue_prompt(self, workflow: Dict) -> Optional[str]:
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
            
            print(f"\n⏳ 生成中...")
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
    
    def download_and_organize(self, prompt_id: str, category: str = "uncategorized",
                             subject: str = "") -> List[str]:
        """下载并整理文件"""
        history_url = f"{self.base_url}/history/{prompt_id}"
        try:
            resp = requests.get(history_url, timeout=5)
            history = resp.json()
            
            if prompt_id not in history:
                print("❌ 未找到历史记录")
                return []
            
            outputs = history[prompt_id].get('outputs', {})
            downloaded = []
            
            # 创建分类目录
            category_dir = ORGANIZED_DIR / category / datetime.now().strftime("%Y-%m-%d")
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # 同时保存到原始目录
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
                            url = f"{self.base_url}/view?{urllib.parse.urlencode(params)}"
                            
                            try:
                                resp = requests.get(url, timeout=30)
                                if resp.status_code == 200:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    
                                    # 生成有意义的文件名
                                    safe_subject = re.sub(r'[^\w\u4e00-\u9fff]', '_', subject[:20])
                                    filename = f"{timestamp}_{safe_subject}_{img['filename']}"
                                    
                                    # 保存两份：原始目录 + 分类目录
                                    for save_dir in [OUTPUT_DIR, category_dir]:
                                        save_path = save_dir / filename
                                        with open(save_path, 'wb') as f:
                                            f.write(resp.content)
                                    
                                    print(f"✅ 已保存：{category_dir / filename}")
                                    downloaded.append(str(category_dir / filename))
                                    
                                    # 生成元数据文件
                                    meta_path = save_path.with_suffix('.json')
                                    meta = {
                                        "prompt": history[prompt_id].get('prompt', ''),
                                        "negative": "",
                                        "category": category,
                                        "subject": subject,
                                        "timestamp": datetime.now().isoformat(),
                                        "seed": history[prompt_id].get('seed', 0)
                                    }
                                    with open(meta_path, 'w', encoding='utf-8') as f:
                                        json.dump(meta, f, ensure_ascii=False, indent=2)
                                        
                            except Exception as e:
                                print(f"❌ 下载失败：{e}")
            
            return downloaded
            
        except Exception as e:
            print(f"❌ 整理失败：{e}")
            return []
    
    def auto_generate(self, subject: str, style: str = "realistic",
                     width: int = 512, height: int = 512,
                     steps: int = 20, is_video: bool = False) -> Dict:
        """一键全自动：生成提示词 → 跑图 → 保存整理"""
        print(f"\n🎨 开始全自动生成:")
        print(f"   主题：{subject}")
        print(f"   风格：{style}")
        print(f"   类型：{'视频' if is_video else '图片'}")
        
        # 1. AI 生成提示词
        prompt_data = self.auto_generate_prompt(subject, style)
        
        # 2. 创建工作流
        if is_video:
            workflow = self.create_video_workflow(
                prompt_data["prompt"],
                prompt_data["negative"],
                width=width,
                height=height
            )
        else:
            workflow = self.create_workflow(
                prompt_data["prompt"],
                prompt_data["negative"],
                width=width,
                height=height,
                steps=steps
            )
        
        # 3. 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}
        
        # 4. 监控进度
        if not self.monitor_progress(prompt_id):
            return {"success": False, "error": "生成失败"}
        
        # 5. 下载并整理
        files = self.download_and_organize(
            prompt_id,
            category=prompt_data["category"],
            subject=subject
        )
        
        # 6. 记录历史
        task_record = {
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "style": style,
            "category": prompt_data["category"],
            "files": files,
            "prompt_id": prompt_id
        }
        self.task_history.append(task_record)
        
        return {
            "success": True,
            "files": files,
            "prompt": prompt_data["prompt"],
            "category": prompt_data["category"]
        }
    
    def batch_auto_generate(self, subjects: List[str], style: str = "realistic",
                           is_video: bool = False) -> List[Dict]:
        """批量全自动生成"""
        print(f"\n🚀 开始批量生成，共 {len(subjects)} 个主题")
        results = []
        
        for i, subject in enumerate(subjects, 1):
            print(f"\n{'='*50}")
            print(f"任务 {i}/{len(subjects)}: {subject}")
            print(f"{'='*50}")
            
            result = self.auto_generate(subject, style, is_video=is_video)
            results.append(result)
            
            # 任务间等待，避免队列拥堵
            if i < len(subjects):
                time.sleep(2)
        
        return results
    
    def organize_existing_files(self):
        """整理已有文件"""
        print(f"\n📁 开始整理已有文件...")
        
        if not OUTPUT_DIR.exists():
            print("   输出目录不存在")
            return
        
        # 移动所有文件到分类目录
        for file in OUTPUT_DIR.glob("*"):
            if file.is_file() and file.suffix in ['.png', '.jpg', '.jpeg', '.webp', '.mp4']:
                # 尝试从文件名提取信息
                category = "uncategorized"
                
                # 读取元数据文件（如果有）
                meta_file = file.with_suffix('.json')
                if meta_file.exists():
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                            category = meta.get('category', 'uncategorized')
                    except:
                        pass
                
                # 移动到分类目录
                category_dir = ORGANIZED_DIR / category / datetime.now().strftime("%Y-%m-%d")
                category_dir.mkdir(parents=True, exist_ok=True)
                
                dest = category_dir / file.name
                if not dest.exists():
                    shutil.copy2(file, dest)
                    print(f"   整理：{file.name} → {category}/")
        
        print(f"✅ 整理完成！")


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 智能控制器")
    parser.add_argument("--prompt", "-p", type=str, help="手动输入提示词")
    parser.add_argument("--subject", "-s", type=str, help="主题（AI 自动生成提示词）")
    parser.add_argument("--style", type=str, default="realistic", 
                       choices=["realistic", "portrait", "landscape", "cyberpunk", 
                               "anime", "fantasy", "scifi"],
                       help="风格")
    parser.add_argument("--batch", type=str, help="批量主题文件（每行一个主题）")
    parser.add_argument("--video", action="store_true", help="生成视频")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--organize", action="store_true", help="整理已有文件")
    parser.add_argument("--server", type=str, default=COMFYUI_SERVER)
    
    args = parser.parse_args()
    
    controller = ComfyUIIntelligentController(args.server)
    
    if not controller.check_connection():
        return 1
    
    if args.organize:
        controller.organize_existing_files()
        return 0
    
    if args.batch:
        # 批量生成
        with open(args.batch, 'r', encoding='utf-8') as f:
            subjects = [line.strip() for line in f if line.strip()]
        results = controller.batch_auto_generate(subjects, args.style, args.video)
        
        # 生成报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": len(subjects),
            "success": sum(1 for r in results if r.get('success')),
            "results": results
        }
        
        report_file = ORGANIZED_DIR / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 批量完成！报告：{report_file}")
        return 0
    
    if args.subject:
        # 单个主题自动生成
        result = controller.auto_generate(
            args.subject,
            args.style,
            width=args.width,
            height=args.height,
            steps=args.steps,
            is_video=args.video
        )
        
        if result['success']:
            print(f"\n✅ 生成完成!")
            print(f"   分类：{result['category']}")
            print(f"   文件：{result['files']}")
        return 0
    
    if args.prompt:
        # 手动提示词
        workflow = controller.create_workflow(args.prompt, "low quality")
        prompt_id = controller.queue_prompt(workflow)
        if prompt_id:
            controller.monitor_progress(prompt_id)
            controller.download_and_organize(prompt_id, "manual", "manual")
        return 0
    
    parser.print_help()
    print(f"\n💡 示例:")
    print(f"   # AI 自动生成提示词并跑图")
    print(f"   python3 {__file__} --subject '一个美丽的女孩' --style portrait")
    print(f"")
    print(f"   # 批量生成")
    print(f"   python3 {__file__} --batch subjects.txt --style cyberpunk")
    print(f"")
    print(f"   # 生成视频")
    print(f"   python3 {__file__} --subject '赛博朋克城市' --video")
    print(f"")
    print(f"   # 整理已有文件")
    print(f"   python3 {__file__} --organize")
    
    return 0


if __name__ == '__main__':
    exit(main())
