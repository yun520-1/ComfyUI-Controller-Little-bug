#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 超级智能控制器 - 增强版
功能：
- 读取本地 ComfyUI 模型和工作流
- 自动匹配运行（优先本地）
- 系统配置检测与智能下载
- AI 自动生成提示词
- 自动保存 + 智能整理文件
- 批量任务支持
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
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

# 导入本地资源管理器
from local_resource_manager import LocalComfyUIManager

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_output"
ORGANIZED_DIR = Path.home() / "Downloads" / "comfyui_organized"
MODEL_DOWNLOAD_DIR = Path.home() / "Downloads" / "comfyui_models"

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

# 模型下载源（优先国内镜像）
MODEL_SOURCES = [
    {
        "name": "ModelScope (阿里)",
        "base_url": "https://modelscope.cn/models",
        "priority": 1
    },
    {
        "name": "Wisemodel (始智)",
        "base_url": "https://wisemodel.cn/models",
        "priority": 2
    },
    {
        "name": "HuggingFace (镜像)",
        "base_url": "https://hf-mirror.com",
        "priority": 3
    },
    {
        "name": "HuggingFace",
        "base_url": "https://huggingface.co",
        "priority": 4
    }
]

# 推荐模型配置
RECOMMENDED_MODELS = {
    "SD 1.5": {
        "file": "v1-5-pruned-emaonly.ckpt",
        "size": "4.27 GB",
        "vram": 4,
        "url": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt",
        "description": "经典模型，兼容性好"
    },
    "SD 2.1": {
        "file": "v2-1_512-ema-pruned.ckpt",
        "size": "5.22 GB",
        "vram": 6,
        "url": "https://huggingface.co/stabilityai/stable-diffusion-2-1/resolve/main/v2-1_512-ema-pruned.ckpt",
        "description": "质量更好，需要更多显存"
    },
    "SDXL 1.0": {
        "file": "sd_xl_base_1.0.safetensors",
        "size": "6.94 GB",
        "vram": 8,
        "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        "description": "高质量，推荐 8GB+ 显存"
    },
    "SDXL Turbo": {
        "file": "sd_xl_turbo_1.0.safetensors",
        "size": "6.94 GB",
        "vram": 8,
        "url": "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0.safetensors",
        "description": "快速生成，1-4 步即可"
    }
}


class AIPromptGenerator:
    """AI 提示词生成器"""

    def __init__(self):
        self.templates = {
            "portrait": "一个{age}{gender}，{style}风格，{lighting}光线，{background}背景，高清，精致，专业摄影",
            "landscape": "{season}{time}的{scene}，{weather}，{style}风格，高分辨率，细节丰富",
            "cyberpunk": "赛博朋克风格{subject}，霓虹灯，高科技，未来城市，{time}，电影感，8K",
            "anime": "动漫风格{subject}，{art_style}画风，精致五官，{color_tone}色调，高质量",
            "fantasy": "奇幻风格{subject}，魔法元素，神秘氛围，{lighting}光线，史诗感",
            "realistic": "写实风格{subject}，照片级真实，{lighting}光线，高细节，专业摄影"
        }

    def generate(self, subject: str, style: str = "realistic",
                 quality: str = "high", extra_details: str = "") -> str:
        """根据主题自动生成提示词"""
        category = self._classify(subject)
        template = self.templates.get(category, self.templates["realistic"])

        import random
        random.seed(int(time.time()) % 1000)

        prompt = template.format(
            age=random.choice(["年轻", "中年", "老年", ""]),
            gender=random.choice(["男性", "女性", ""]),
            style=style,
            lighting=random.choice(["柔和", "自然", "戏剧性", "电影"]),
            background=random.choice(["简洁", "虚化", "自然", "城市"]),
            season=random.choice(["春天", "夏天", "秋天", "冬天", ""]),
            time=random.choice(["清晨", "黄昏", "夜晚", "正午"]),
            scene=subject,
            weather=random.choice(["晴天", "多云", "雨后", "雪景"]),
            subject=subject,
            art_style=random.choice(["日式", "美式", "韩系", "中国风"]),
            color_tone=random.choice(["温暖", "冷色", "鲜艳", "柔和"])
        )

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


class ModelDownloader:
    """智能模型下载器"""

    def __init__(self, comfyui_path: Path = None):
        self.comfyui_path = comfyui_path
        self.download_dir = MODEL_DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def check_model_exists(self, model_name: str) -> Optional[Path]:
        """检查模型是否已存在"""
        if not self.comfyui_path:
            return None

        checkpoints_dir = self.comfyui_path / "models" / "checkpoints"
        if not checkpoints_dir.exists():
            return None

        # 检查各种可能的扩展名
        for ext in ["*.ckpt", "*.safetensors", "*.pt", "*.pth"]:
            for model_file in checkpoints_dir.glob(ext):
                if model_name.lower() in model_file.name.lower():
                    return model_file

        return None

    def download_model(self, model_name: str, system_config: Dict = None) -> Dict:
        """下载模型（带进度显示）"""
        print(f"\n📥 下载模型：{model_name}")

        # 检查是否已存在
        existing = self.check_model_exists(model_name)
        if existing:
            print(f"✅ 模型已存在：{existing}")
            return {
                "success": True,
                "path": str(existing),
                "message": "模型已存在，无需下载"
            }

        # 获取模型信息
        model_info = RECOMMENDED_MODELS.get(model_name)
        if not model_info:
            # 尝试模糊匹配
            for key, info in RECOMMENDED_MODELS.items():
                if key.lower() in model_name.lower():
                    model_info = info
                    break

        if not model_info:
            return {
                "success": False,
                "error": f"未知模型：{model_name}"
            }

        # 检查系统配置
        if system_config:
            gpu_mem = 0
            if system_config.get("gpu_memory"):
                try:
                    gpu_mem = float(system_config["gpu_memory"].replace(" GB", ""))
                except:
                    pass

            if gpu_mem < model_info["vram"]:
                print(f"⚠️  警告：模型需要 {model_info['vram']}GB 显存，当前只有 {gpu_mem}GB")
                response = input("继续下载？(y/n): ")
                if response.lower() != 'y':
                    return {
                        "success": False,
                        "error": "用户取消下载"
                    }

        # 下载模型
        url = model_info["url"]
        dest_path = self.comfyui_path / "models" / "checkpoints" / model_info["file"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"   来源：{url}")
        print(f"   大小：{model_info['size']}")
        print(f"   目标：{dest_path}")

        try:
            # 使用 urllib 下载（带进度）
            def reporthook(blocknum, blocksize, totalsize):
                readsofar = blocknum * blocksize
                if totalsize > 0:
                    percent = readsofar * 100 / totalsize
                    print(f"\r   进度：{percent:.1f}% ({readsofar/1024/1024:.1f}MB / {totalsize/1024/1024:.1f}MB)", end="")

            urllib.request.urlretrieve(url, dest_path, reporthook)
            print()  # 换行
            print(f"✅ 下载完成：{dest_path}")

            return {
                "success": True,
                "path": str(dest_path),
                "message": "下载成功"
            }

        except Exception as e:
            print(f"\n❌ 下载失败：{e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_recommended_model(self, system_config: Dict) -> str:
        """根据系统配置推荐模型"""
        gpu_mem = 0
        if system_config.get("gpu_memory"):
            try:
                gpu_mem = float(system_config["gpu_memory"].replace(" GB", ""))
            except:
                pass

        if gpu_mem >= 16:
            return "SDXL 1.0"
        elif gpu_mem >= 8:
            return "SDXL Turbo"
        elif gpu_mem >= 6:
            return "SD 2.1"
        else:
            return "SD 1.5"


class ComfyUISuperController:
    """ComfyUI 超级智能控制器"""

    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.prompt_generator = AIPromptGenerator()
        self.local_manager = LocalComfyUIManager()
        self.model_downloader = None
        self.system_config = None
        self.ws = None

    def initialize(self, auto_detect: bool = True) -> Dict:
        """初始化控制器（检测系统、查找 ComfyUI）"""
        print("\n🚀 初始化 ComfyUI 超级控制器...")

        # 检测系统配置
        self.system_config = self.local_manager.detect_system_config()

        # 查找 ComfyUI
        if auto_detect:
            self.local_manager.find_comfyui()
            if self.local_manager.comfyui_path:
                self.model_downloader = ModelDownloader(self.local_manager.comfyui_path)
                # 扫描本地资源
                self.local_manager.scan_models()
                self.local_manager.scan_workflows()

        # 检查连接
        connected = self.check_connection()

        return {
            "system_config": self.system_config,
            "comfyui_path": str(self.local_manager.comfyui_path) if self.local_manager.comfyui_path else None,
            "connected": connected
        }

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

    def find_best_model(self, required_model: str = None) -> Dict:
        """查找最佳可用模型（优先本地）"""
        print(f"\n🔍 查找模型...")

        # 1. 扫描本地模型
        local_models = self.local_manager.available_models.get("checkpoints", {})
        local_files = local_models.get("files", []) if local_models else []

        if required_model:
            # 检查指定模型
            for model_file in local_files:
                if required_model.lower() in model_file.lower():
                    print(f"✅ 找到本地模型：{model_file}")
                    return {
                        "source": "local",
                        "model": model_file,
                        "path": str(self.local_manager.comfyui_path / "models" / "checkpoints" / model_file)
                    }

        # 2. 如果没有指定模型或本地没有，推荐合适的
        if local_files:
            # 使用第一个本地模型
            recommended = local_files[0]
            print(f"✅ 使用本地模型：{recommended}")
            return {
                "source": "local",
                "model": recommended,
                "path": str(self.local_manager.comfyui_path / "models" / "checkpoints" / recommended)
            }

        # 3. 本地没有，推荐并下载
        print("⚠️  本地没有找到模型")
        recommended_model = self.model_downloader.get_recommended_model(self.system_config) if self.model_downloader else "SD 1.5"
        print(f"💡 推荐下载：{recommended_model}")

        return {
            "source": "download",
            "model": recommended_model,
            "needs_download": True
        }

    def auto_generate_prompt(self, subject: str, style: str = "realistic",
                            quality: str = "high") -> Dict:
        """AI 自动生成提示词"""
        prompt = self.prompt_generator.generate(subject, style, quality)
        negative = self.prompt_generator.generate_negative(style)
        category = self.prompt_generator._classify(subject)

        return {
            "prompt": prompt,
            "negative": negative,
            "category": category
        }

    def create_workflow(self, prompt: str, negative: str,
                       width: int = 512, height: int = 512,
                       steps: int = 20, cfg: float = 7,
                       seed: int = None, model: str = None) -> Dict:
        """创建工作流（自动使用本地模型）"""
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

    def load_local_workflow(self, workflow_id: str) -> Optional[Dict]:
        """加载本地工作流"""
        workflows = self.local_manager.available_workflows.get("custom", [])
        for wf in workflows:
            if wf["name"] == workflow_id or wf["path"].endswith(f"{workflow_id}.json"):
                with open(wf["path"], 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None

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

            category_dir = ORGANIZED_DIR / category / datetime.now().strftime("%Y-%m-%d")
            category_dir.mkdir(parents=True, exist_ok=True)
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
                                    safe_subject = re.sub(r'[^\w\u4e00-\u9fff]', '_', subject[:20])
                                    filename = f"{timestamp}_{safe_subject}_{img['filename']}"

                                    for save_dir in [OUTPUT_DIR, category_dir]:
                                        save_path = save_dir / filename
                                        with open(save_path, 'wb') as f:
                                            f.write(resp.content)

                                    print(f"✅ 已保存：{category_dir / filename}")
                                    downloaded.append(str(category_dir / filename))

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

    def smart_generate(self, subject: str, style: str = "realistic",
                      width: int = None, height: int = None,
                      steps: int = 20, model: str = None) -> Dict:
        """智能生成：自动选择最佳模型和工作流"""
        print(f"\n🎨 开始智能生成:")
        print(f"   主题：{subject}")
        print(f"   风格：{style}")

        # 1. 查找最佳模型
        model_info = self.find_best_model(model)

        # 2. 如果需要下载，先下载
        if model_info.get("needs_download"):
            print(f"\n📥 需要下载模型：{model_info['model']}")
            download_result = self.model_downloader.download_model(
                model_info['model'],
                self.system_config
            )
            if not download_result['success']:
                return {"success": False, "error": download_result.get('error')}
            model_info['model'] = download_result['path']

        # 3. AI 生成提示词
        prompt_data = self.auto_generate_prompt(subject, style)

        # 4. 根据系统配置调整参数
        if not width or not height:
            gpu_mem = 0
            if self.system_config.get("gpu_memory"):
                try:
                    gpu_mem = float(self.system_config["gpu_memory"].replace(" GB", ""))
                except:
                    pass

            if gpu_mem >= 8:
                width, height = 1024, 1024
            else:
                width, height = 512, 512

        # 5. 创建工作流
        model_name = os.path.basename(model_info.get('path', model_info.get('model', '')))
        workflow = self.create_workflow(
            prompt_data["prompt"],
            prompt_data["negative"],
            width=width,
            height=height,
            steps=steps,
            model=model_name
        )

        # 6. 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}

        # 7. 监控进度
        if not self.monitor_progress(prompt_id):
            return {"success": False, "error": "生成失败"}

        # 8. 下载并整理
        files = self.download_and_organize(
            prompt_id,
            category=prompt_data["category"],
            subject=subject
        )

        return {
            "success": True,
            "files": files,
            "prompt": prompt_data["prompt"],
            "category": prompt_data["category"],
            "model_used": model_name,
            "resolution": f"{width}x{height}"
        }

    def run_local_workflow(self, workflow_path: str, prompt: str = None,
                          negative: str = None, **kwargs) -> Dict:
        """运行本地工作流文件"""
        print(f"\n🚀 运行本地工作流：{workflow_path}")

        workflow_path = Path(workflow_path)
        if not workflow_path.exists():
            return {"success": False, "error": f"文件不存在：{workflow_path}"}

        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"读取失败：{e}"}

        # 替换提示词
        if prompt:
            for node_id, node_data in workflow.items():
                if node_data.get("class_type") == "CLIPTextEncode":
                    inputs = node_data.get("inputs", {})
                    if "text" in inputs:
                        current = inputs.get("text", "")
                        if "negative" in current.lower():
                            if negative:
                                node_data["inputs"]["text"] = negative
                        else:
                            node_data["inputs"]["text"] = prompt

        # 更新参数
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            if "KSampler" in class_type:
                if "steps" in kwargs:
                    node_data["inputs"]["steps"] = kwargs["steps"]
                if "cfg" in kwargs:
                    node_data["inputs"]["cfg"] = kwargs["cfg"]

            if "EmptyLatentImage" in class_type:
                if "width" in kwargs:
                    node_data["inputs"]["width"] = kwargs["width"]
                if "height" in kwargs:
                    node_data["inputs"]["height"] = kwargs["height"]

        # 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}

        # 监控进度
        if not self.monitor_progress(prompt_id):
            return {"success": False, "error": "生成失败"}

        # 下载结果
        files = self.download_and_organize(prompt_id, "workflow", Path(workflow_path).stem)

        return {
            "success": True,
            "files": files,
            "workflow": workflow_path.name
        }

    def generate_report(self) -> str:
        """生成系统报告"""
        return self.local_manager.generate_report()


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 超级智能控制器")
    parser.add_argument("--subject", "-s", type=str, help="主题（AI 自动生成提示词）")
    parser.add_argument("--style", type=str, default="realistic",
                       choices=["realistic", "portrait", "landscape", "cyberpunk",
                               "anime", "fantasy", "scifi"],
                       help="风格")
    parser.add_argument("--width", type=int, help="宽度（自动检测如果未指定）")
    parser.add_argument("--height", type=int, help="高度（自动检测如果未指定）")
    parser.add_argument("--steps", type=int, default=20, help="采样步数")
    parser.add_argument("--model", type=str, help="指定模型（优先本地）")
    parser.add_argument("--workflow", type=str, help="本地工作流文件路径")
    parser.add_argument("--scan", action="store_true", help="扫描本地资源")
    parser.add_argument("--report", action="store_true", help="生成系统报告")
    parser.add_argument("--server", type=str, default=COMFYUI_SERVER)

    args = parser.parse_args()

    controller = ComfyUISuperController(args.server)

    # 初始化
    init_result = controller.initialize()

    if args.scan:
        # 扫描模式
        print(f"\n📊 扫描结果:")
        print(f"ComfyUI 路径：{init_result['comfyui_path']}")
        print(f"连接状态：{'✅ 已连接' if init_result['connected'] else '❌ 未连接'}")
        return 0

    if args.report:
        # 生成报告
        report_path = controller.generate_report()
        print(f"\n📄 报告已保存：{report_path}")
        return 0

    if not init_result['connected']:
        print("❌ 无法连接到 ComfyUI，请确保 ComfyUI 正在运行")
        return 1

    if args.workflow:
        # 运行本地工作流
        result = controller.run_local_workflow(
            args.workflow,
            prompt=args.subject,
            steps=args.steps,
            width=args.width,
            height=args.height
        )
        if result['success']:
            print(f"\n✅ 工作流执行完成!")
            print(f"   文件：{result['files']}")
        return 0

    if args.subject:
        # 智能生成
        result = controller.smart_generate(
            args.subject,
            args.style,
            width=args.width,
            height=args.height,
            steps=args.steps,
            model=args.model
        )

        if result['success']:
            print(f"\n✅ 生成完成!")
            print(f"   分类：{result['category']}")
            print(f"   模型：{result['model_used']}")
            print(f"   分辨率：{result['resolution']}")
            print(f"   文件：{result['files']}")
        else:
            print(f"\n❌ 生成失败：{result.get('error')}")
        return 0

    parser.print_help()
    print(f"\n💡 示例:")
    print(f"   # 智能生成（自动选择模型）")
    print(f"   python3 {__file__} --subject '一个美丽的女孩' --style portrait")
    print(f"")
    print(f"   # 指定模型")
    print(f"   python3 {__file__} --subject '赛博朋克城市' --model 'SDXL 1.0'")
    print(f"")
    print(f"   # 使用本地工作流")
    print(f"   python3 {__file__} --workflow my_workflow.json --subject '测试'")
    print(f"")
    print(f"   # 扫描本地资源")
    print(f"   python3 {__file__} --scan")
    print(f"")
    print(f"   # 生成系统报告")
    print(f"   python3 {__file__} --report")

    return 0


if __name__ == '__main__':
    exit(main())
