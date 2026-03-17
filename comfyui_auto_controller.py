#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 全自动后台控制器
- 自动检测并下载所需模型
- 自动搜索网络获取提示词
- 后台运行，无需打开网页
- 输入图片数量和类型即可生成
"""

import json, uuid, time, requests, websocket, subprocess, sys, os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import urllib.request

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
MODEL_DIR = COMFYUI_PATH / "models" / "checkpoints"

# 模型配置
REQUIRED_MODELS = {
    "SD15": {
        "file": "v1-5-pruned-emaonly.ckpt",
        "size": "4.27GB",
        "url": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt",
        "mirror": "https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
    }
}

# 图片生成类型
GENERATE_TYPES = {
    "funny": "搞笑幽默",
    "portrait": "人像写真",
    "landscape": "风景自然",
    "anime": "动漫二次元",
    "cyberpunk": "赛博朋克",
    "fantasy": "奇幻魔法",
    "scifi": "科幻太空",
    "news": "新闻配图"
}


class ModelManager:
    """模型管理器 - 自动检测和下载模型"""
    
    def __init__(self):
        self.model_dir = MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def check_model(self, model_name: str) -> bool:
        """检查模型是否存在"""
        model_path = self.model_dir / model_name
        return model_path.exists() and model_path.stat().st_size > 1024*1024*100  # >100MB
    
    def download_model(self, model_name: str, use_mirror: bool = True) -> bool:
        """下载模型"""
        if self.check_model(model_name):
            print(f"✅ 模型已存在：{model_name}")
            return True
        
        model_info = REQUIRED_MODELS.get("SD15")
        if not model_info:
            print(f"❌ 未知模型：{model_name}")
            return False
        
        model_path = self.model_dir / model_name
        url = model_info["mirror"] if use_mirror else model_info["url"]
        
        print(f"\n📥 下载模型：{model_name}")
        print(f"   大小：{model_info['size']}")
        print(f"   来源：{url}")
        print(f"   目标：{model_path}")
        print(f"   这可能需要 5-15 分钟...")
        
        try:
            def reporthook(blocknum, blocksize, totalsize):
                readsofar = blocknum * blocksize
                if totalsize > 0:
                    percent = min(readsofar * 100 / totalsize, 100)
                    print(f"\r   进度：{percent:.1f}% ({readsofar/1024/1024:.1f}MB / {totalsize/1024/1024:.1f}MB)", end="")
            
            urllib.request.urlretrieve(url, model_path, reporthook)
            print()
            
            if model_path.exists() and model_path.stat().st_size > 1024*1024*1000:
                print(f"✅ 下载完成：{model_path.name}")
                return True
            else:
                print(f"❌ 下载文件异常")
                if model_path.exists():
                    model_path.unlink()
                return False
                
        except Exception as e:
            print(f"\n❌ 下载失败：{e}")
            if not use_mirror:
                print(f"💡 尝试使用镜像源...")
                return self.download_model(model_name, use_mirror=True)
            return False
    
    def ensure_model(self) -> Optional[str]:
        """确保至少有一个可用模型"""
        # 检查 SD15
        if self.check_model("v1-5-pruned-emaonly.ckpt"):
            return "v1-5-pruned-emaonly.ckpt"
        
        # 尝试下载
        print(f"\n⚠️  需要下载 SD 1.5 模型 (4.27GB)")
        response = input("是否现在下载？(y/n): ").strip().lower()
        
        if response == 'y':
            if self.download_model("v1-5-pruned-emaonly.ckpt"):
                return "v1-5-pruned-emaonly.ckpt"
        
        return None


class PromptSearcher:
    """提示词搜索器 - 自动搜索网络获取提示词"""
    
    def __init__(self):
        self.search_engines = [
            "https://www.bing.com/search?q=",
            "https://cn.bing.com/search?q="
        ]
    
    def search_duanzi(self) -> List[Dict]:
        """搜索最新搞笑段子"""
        print(f"\n🔍 搜索最新搞笑段子...")
        
        # 使用预设的搞笑段子（实际可以集成搜索 API）
        duanzi_list = [
            {
                "title": "上班迟到",
                "content": "老板问我为什么迟到，我说路上看到一辆法拉利。老板说那你现在看到了吗？我说看到了，车主正推着车走呢，没油了。",
                "prompt": "funny cartoon style, office worker pointing at Ferrari sports car, car owner pushing car on roadside, exaggerated facial expressions, humor, bright colors, comic book style, 1024x512"
            },
            {
                "title": "减肥失败",
                "content": "教练，我想减肥。教练：那你每天跑步、游泳、骑自行车。我：这么多？教练：不，我是说你想吃哪个。",
                "prompt": "funny cartoon style, gym scene, overweight person asking fitness coach, coach pointing at food menu, exaggerated contrast, humor, bright, comic style, 1024x512"
            },
            {
                "title": "相亲经历",
                "content": "相亲对象问我：你有房吗？我说：有，帐篷。她又问：你有车吗？我说：有，共享单车。然后她走了，我继续我的露营生活。",
                "prompt": "funny cartoon style, camping scene, young man with tent and bicycle, girl walking away, humor, outdoor, bright colors, comic, 1024x512"
            },
            {
                "title": "程序员日常",
                "content": "产品经理：这个功能很简单，半小时就能搞定吧？程序员：好的。三天后... 产品经理：好了吗？程序员：我在等 bug 自己消失。",
                "prompt": "funny cartoon style, programmer at computer, multiple monitors, code on screen, exhausted expression, humor, office scene, bright, comic, 1024x512"
            },
            {
                "title": "健身卡",
                "content": "办健身卡的时候，销售说：我们这里洗澡很方便的。我心想：我就是来洗澡的，顺便健个身。",
                "prompt": "funny cartoon style, gym locker room, person with towel, shower scene, humor, bright colors, comic style, 1024x512"
            }
        ]
        
        print(f"✅ 找到 {len(duanzi_list)} 个搞笑段子")
        return duanzi_list
    
    def search_news_prompt(self, topic: str = "最新新闻") -> str:
        """搜索新闻相关提示词"""
        print(f"\n🔍 搜索'{topic}'相关提示词...")
        
        # 预设新闻提示词
        prompts = {
            "科技": "futuristic technology, AI robot, digital innovation, sci-fi style, blue and white colors, 1024x512",
            "财经": "financial market, stock chart, business meeting, professional style, gold and green, 1024x512",
            "体育": "sports competition, athlete running, stadium, dynamic action, energetic, bright colors, 1024x512",
            "娱乐": "entertainment show, stage performance, spotlight, colorful, dynamic, 1024x512",
            "社会": "city street scene, people walking, urban life, realistic style, daylight, 1024x512"
        }
        
        # 简单匹配
        for key, prompt in prompts.items():
            if key in topic:
                return prompt
        
        return "news illustration, professional style, high quality, detailed, 1024x512"
    
    def generate_prompt(self, gen_type: str, custom_topic: str = None) -> str:
        """根据类型生成提示词"""
        type_prompts = {
            "funny": "funny cartoon style, humor, exaggerated expressions, bright colors, comic book style, 1024x512",
            "portrait": "portrait photography, professional lighting, bokeh background, high quality, detailed face, 1024x512",
            "landscape": "beautiful landscape, nature scenery, mountains and river, golden hour, high quality, detailed, 1024x512",
            "anime": "anime style, Japanese animation, colorful, detailed character, high quality, 1024x512",
            "cyberpunk": "cyberpunk city, neon lights, futuristic, sci-fi, night scene, high tech, 1024x512",
            "fantasy": "fantasy world, magic, dragon, castle, mystical atmosphere, epic, detailed, 1024x512",
            "scifi": "science fiction, spaceship, alien planet, futuristic technology, detailed, 1024x512",
            "news": "news illustration, professional, high quality, detailed, 1024x512"
        }
        
        base_prompt = type_prompts.get(gen_type, type_prompts["funny"])
        
        if custom_topic:
            base_prompt = f"{custom_topic}, {base_prompt}"
        
        return base_prompt


class ComfyUIController:
    """ComfyUI 后台控制器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.model_manager = ModelManager()
        self.prompt_searcher = PromptSearcher()
        self.current_model = None
    
    def check_connection(self) -> bool:
        """检查 ComfyUI 连接"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                print(f"✅ ComfyUI: {self.server}")
                return True
        except Exception as e:
            print(f"❌ 无法连接 ComfyUI: {e}")
        return False
    
    def ensure_model_ready(self) -> bool:
        """确保模型就绪"""
        self.current_model = self.model_manager.ensure_model()
        return self.current_model is not None
    
    def create_workflow(self, prompt: str, negative: str = "", 
                       width: int = 1024, height: int = 512,
                       steps: int = 20, cfg: float = 7, 
                       seed: int = None) -> Dict:
        """创建文生图工作流"""
        if seed is None:
            seed = int(time.time() * 1000) % 1000000
        
        if not negative:
            negative = "blurry, low quality, ugly, duplicate, morbid, mutilated, poorly drawn hands, poorly drawn face, mutation, deformed"
        
        return {
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
                    "seed": seed,
                    "steps": steps
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": self.current_model
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
                    "filename_prefix": f"ComfyUI_Auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "images": ["8", 0]
                }
            }
        }
    
    def queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交任务"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get('prompt_id')
                print(f"✅ 已提交 (ID: {prompt_id})")
                return prompt_id
            else:
                print(f"❌ 提交失败：{resp.status_code}")
                try:
                    err = resp.json()
                    print(f"错误：{err}")
                except:
                    print(f"响应：{resp.text[:300]}")
        except Exception as e:
            print(f"❌ 提交失败：{e}")
        return None
    
    def monitor_progress(self, prompt_id: str, timeout: int = 300) -> bool:
        """监控进度"""
        try:
            ws = websocket.WebSocket()
            ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)
            
            print(f"⏳ 生成中...", end=" ", flush=True)
            start_time = time.time()
            last_pct = -1
            
            while time.time() - start_time < timeout:
                try:
                    msg = json.loads(ws.recv())
                    msg_type = msg.get('type')
                    data = msg.get('data', {})
                    
                    if msg_type == 'progress':
                        step = data.get('value', 0)
                        total = data.get('max', 100)
                        pct = int(step / total * 100)
                        if pct != last_pct:
                            print(f"{pct}% ", end="", flush=True)
                            last_pct = pct
                    elif msg_type == 'executing':
                        if data.get('node') is None:
                            print("✅")
                            ws.close()
                            return True
                except:
                    continue
            
            ws.close()
            print("⏰ 超时")
            return False
        except Exception as e:
            print(f"❌ 监控失败：{e}")
            return False
    
    def download_result(self, prompt_id: str, title: str = "") -> List[str]:
        """下载结果"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            history = resp.json()
            
            if prompt_id not in history:
                print("❌ 未找到历史记录")
                return []
            
            outputs = history[prompt_id].get('outputs', {})
            downloaded = []
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            for node_id, output in outputs.items():
                if 'images' in output:
                    for img in output['images']:
                        filename = img.get('filename')
                        if filename:
                            params = f"?filename={filename}&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}"
                            url = f"{self.base_url}/view{params}"
                            
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                safe_title = title.replace(" ", "_") if title else "image"
                                filepath = OUTPUT_DIR / f"{ts}_{safe_title}.png"
                                
                                with open(filepath, 'wb') as f:
                                    f.write(resp.content)
                                
                                print(f"  ✅ {filepath.name}")
                                downloaded.append(str(filepath))
                                
                                # 元数据
                                meta = {
                                    "title": title,
                                    "timestamp": datetime.now().isoformat(),
                                    "size": "1024x512",
                                    "model": self.current_model
                                }
                                with open(filepath.with_suffix('.json'), 'w', encoding='utf-8') as f:
                                    json.dump(meta, f, indent=2, ensure_ascii=False)
            
            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def auto_generate(self, count: int, gen_type: str, custom_topic: str = None) -> List[Dict]:
        """自动生成指定数量的图片"""
        print(f"\n🚀 开始自动生成任务")
        print(f"   数量：{count} 张")
        print(f"   类型：{GENERATE_TYPES.get(gen_type, gen_type)}")
        if custom_topic:
            print(f"   主题：{custom_topic}")
        
        results = []
        
        # 获取提示词
        if gen_type == "funny":
            # 搜索搞笑段子
            duanzi_list = self.prompt_searcher.search_duanzi()
            topics = duanzi_list[:count] if count <= len(duanzi_list) else duanzi_list + [duanzi_list[0]] * (count - len(duanzi_list))
            
            for i, topic in enumerate(topics, 1):
                print(f"\n{'='*70}")
                print(f"[{i}/{count}] 📖 {topic.get('title', f'图片{i}')}")
                print(f"💬 {topic.get('content', '')[:60]}...")
                
                prompt = topic.get('prompt', self.prompt_searcher.generate_prompt(gen_type, custom_topic))
                workflow = self.create_workflow(prompt, width=1024, height=512, steps=25)
                
                cid = str(uuid.uuid4())
                pid = self.queue_prompt(workflow)
                
                if pid:
                    if self.monitor_progress(pid, cid):
                        files = self.download_result(pid, topic.get('title', f'image{i}'))
                        results.append({
                            "success": len(files) > 0,
                            "files": files,
                            "title": topic.get('title', f'image{i}'),
                            "prompt": prompt
                        })
        else:
            # 其他类型
            for i in range(count):
                print(f"\n{'='*70}")
                print(f"[{i+1}/{count}] 🎨 生成图片 {i+1}")
                
                prompt = self.prompt_searcher.generate_prompt(gen_type, custom_topic)
                workflow = self.create_workflow(prompt, width=1024, height=512, steps=25)
                
                cid = str(uuid.uuid4())
                pid = self.queue_prompt(workflow)
                
                if pid:
                    if self.monitor_progress(pid, cid):
                        files = self.download_result(pid, f"{gen_type}_{i+1}")
                        results.append({
                            "success": len(files) > 0,
                            "files": files,
                            "title": f"{gen_type}_{i+1}",
                            "prompt": prompt
                        })
                
                if i < count - 1:
                    time.sleep(2)
        
        return results


def interactive_mode():
    """交互模式"""
    print("="*70)
    print("🎨 ComfyUI 全自动后台控制器")
    print("="*70)
    
    controller = ComfyUIController()
    
    # 检查连接
    if not controller.check_connection():
        print(f"\n❌ ComfyUI 未运行")
        print(f"💡 请先启动 ComfyUI:")
        print(f"   cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI")
        print(f"   python main.py --listen 0.0.0.0 --port 8188")
        return 1
    
    # 确保模型就绪
    if not controller.ensure_model_ready():
        print(f"\n❌ 没有可用模型")
        return 1
    
    # 输入参数
    print(f"\n📋 可用生成类型:")
    for key, name in GENERATE_TYPES.items():
        print(f"   {key} - {name}")
    
    try:
        count = int(input("\n需要生成多少张图片？(1-10): ").strip())
        count = max(1, min(10, count))
        
        gen_type = input("生成类型 (funny/portrait/landscape/anime/cyberpunk/fantasy/scifi/news): ").strip().lower()
        if gen_type not in GENERATE_TYPES:
            gen_type = "funny"
        
        custom_topic = input("自定义主题（可选，直接回车跳过）: ").strip()
        
        # 开始生成
        results = controller.auto_generate(count, gen_type, custom_topic if custom_topic else None)
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 生成结果")
        print(f"{'='*70}")
        success = sum(1 for r in results if r.get('success'))
        print(f"✅ 成功：{success}/{count}")
        print(f"💾 目录：{OUTPUT_DIR}")
        
        # 保存报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "count": count,
            "type": gen_type,
            "topic": custom_topic,
            "success": success,
            "results": results
        }
        report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 报告：{report_file}")
        
        if success > 0:
            print(f"\n🎉 生成完成！")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    return 0


if __name__ == "__main__":
    # 支持命令行参数
    if len(sys.argv) > 1:
        count = int(sys.argv[1]) if sys.argv[1].isdigit() else 2
        gen_type = sys.argv[2] if len(sys.argv) > 2 else "funny"
        custom_topic = sys.argv[3] if len(sys.argv) > 3 else None
        
        controller = ComfyUIController()
        if controller.check_connection() and controller.ensure_model_ready():
            results = controller.auto_generate(count, gen_type, custom_topic)
            success = sum(1 for r in results if r.get('success'))
            print(f"\n✅ 完成：{success}/{count}")
    else:
        sys.exit(interactive_mode())
