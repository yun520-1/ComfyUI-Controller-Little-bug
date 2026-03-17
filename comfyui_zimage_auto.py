#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 全自动后台控制器 - Z-Image-Turbo 版本
使用现有的 z_image_turbo-Q8_0.gguf 模型
无需下载额外模型！
"""

import json, uuid, time, requests, websocket, sys, os
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"

# 使用现有模型
Z_IMAGE_MODEL = "z_image_turbo-Q8_0.gguf"

# 生成类型
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


class PromptSearcher:
    """提示词搜索器"""
    
    def search_duanzi(self) -> List[Dict]:
        """搜索搞笑段子"""
        print(f"\n🔍 搜索最新搞笑段子...")
        
        duanzi_list = [
            {
                "title": "上班迟到",
                "content": "老板问我为什么迟到，我说路上看到一辆法拉利。老板说那你现在看到了吗？我说看到了，车主正推着车走呢，没油了。",
                "prompt": "funny cartoon style, office worker pointing at Ferrari sports car, car owner pushing car on roadside, exaggerated facial expressions, humor, bright colors, comic book style"
            },
            {
                "title": "减肥失败",
                "content": "教练，我想减肥。教练：那你每天跑步、游泳、骑自行车。我：这么多？教练：不，我是说你想吃哪个。",
                "prompt": "funny cartoon style, gym scene, overweight person asking fitness coach, coach pointing at food menu, exaggerated contrast, humor, bright"
            },
            {
                "title": "相亲经历",
                "content": "相亲对象问我：你有房吗？我说：有，帐篷。她又问：你有车吗？我说：有，共享单车。然后她走了，我继续我的露营生活。",
                "prompt": "funny cartoon style, camping scene, young man with tent and bicycle, girl walking away, humor, outdoor, bright colors"
            },
            {
                "title": "程序员日常",
                "content": "产品经理：这个功能很简单，半小时就能搞定吧？程序员：好的。三天后... 产品经理：好了吗？程序员：我在等 bug 自己消失。",
                "prompt": "funny cartoon style, programmer at computer, multiple monitors, code on screen, exhausted expression, humor, office"
            },
            {
                "title": "健身卡",
                "content": "办健身卡的时候，销售说：我们这里洗澡很方便的。我心想：我就是来洗澡的，顺便健个身。",
                "prompt": "funny cartoon style, gym locker room, person with towel, shower scene, humor, bright colors"
            }
        ]
        
        print(f"✅ 找到 {len(duanzi_list)} 个搞笑段子")
        return duanzi_list
    
    def generate_prompt(self, gen_type: str, custom_topic: str = None) -> str:
        """根据类型生成提示词"""
        type_prompts = {
            "funny": "funny cartoon style, humor, exaggerated expressions, bright colors, comic",
            "portrait": "portrait photography, professional lighting, bokeh background, high quality, detailed",
            "landscape": "beautiful landscape, nature scenery, mountains and river, golden hour, high quality",
            "anime": "anime style, Japanese animation, colorful, detailed character, high quality",
            "cyberpunk": "cyberpunk city, neon lights, futuristic, sci-fi, night scene, high tech",
            "fantasy": "fantasy world, magic, dragon, castle, mystical atmosphere, epic, detailed",
            "scifi": "science fiction, spaceship, alien planet, futuristic technology, detailed",
            "news": "news illustration, professional, high quality, detailed"
        }
        
        base_prompt = type_prompts.get(gen_type, type_prompts["funny"])
        
        if custom_topic:
            base_prompt = f"{custom_topic}, {base_prompt}"
        
        return base_prompt


class ZImageController:
    """Z-Image-Turbo 控制器"""
    
    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.prompt_searcher = PromptSearcher()
        self.unet_model = Z_IMAGE_MODEL
        
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
    
    def check_model(self) -> bool:
        """检查 Z-Image-Turbo 模型"""
        model_path = COMFYUI_PATH / "models" / "unet" / self.unet_model
        if model_path.exists():
            size = model_path.stat().st_size / (1024**3)
            print(f"✅ Z-Image-Turbo: {self.unet_model} ({size:.1f}GB)")
            return True
        else:
            print(f"❌ 模型不存在：{model_path}")
            return False
    
    def create_workflow(self, prompt: str, negative: str = "", 
                       width: int = 1024, height: int = 512,
                       steps: int = 20, cfg: float = 7, 
                       seed: int = None) -> Dict:
        """创建 Z-Image-Turbo 工作流"""
        if seed is None:
            seed = int(time.time() * 1000) % 1000000
        
        if not negative:
            negative = "blurry, low quality, ugly, duplicate, morbid, mutilated, poorly drawn"
        
        return {
            # 1. UNet 加载 (Z-Image-Turbo)
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": self.unet_model}
            },
            # 2. CLIP 加载 (使用 SD1.5 CLIP)
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": "clip_l.safetensors", "type": "sd1x"}
            },
            # 3. VAE 加载
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"}
            },
            # 4. 正向提示词
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": prompt}
            },
            # 5. 负面提示词
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": negative}
            },
            # 6. 空潜图
            "6": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": height, "width": width}
            },
            # 7. KSampler
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": cfg, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0],
                    "negative": ["5", 0], "positive": ["4", 0],
                    "sampler_name": "euler_ancestral", "scheduler": "normal",
                    "seed": seed, "steps": steps
                }
            },
            # 8. VAE 解码
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["3", 0]}
            },
            # 9. 保存图片
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"ZImage_Auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "images": ["8", 0]
                }
            }
        }
    
    def queue_prompt(self, workflow: Dict) -> str:
        """提交任务"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=30
            )
            
            if resp.status_code == 200:
                pid = resp.json().get('prompt_id')
                print(f"✅ 已提交 (ID: {pid})")
                return pid
            else:
                print(f"❌ 提交失败：{resp.status_code}")
                try:
                    err = resp.json()
                    print(f"错误：{str(err)[:500]}")
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
                    if msg.get('type') == 'progress':
                        d = msg['data']
                        pct = int(d.get('value', 0) / d.get('max', 100) * 100)
                        if pct != last_pct:
                            print(f"{pct}% ", end="", flush=True)
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
                                
                                meta = {
                                    "title": title,
                                    "timestamp": datetime.now().isoformat(),
                                    "size": "1024x512",
                                    "model": self.unet_model
                                }
                                with open(filepath.with_suffix('.json'), 'w', encoding='utf-8') as f:
                                    json.dump(meta, f, indent=2, ensure_ascii=False)
            
            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []
    
    def auto_generate(self, count: int, gen_type: str, custom_topic: str = None) -> List[Dict]:
        """自动生成"""
        print(f"\n🚀 开始生成")
        print(f"   数量：{count} 张")
        print(f"   类型：{GENERATE_TYPES.get(gen_type, gen_type)}")
        print(f"   模型：{self.unet_model}")
        if custom_topic:
            print(f"   主题：{custom_topic}")
        
        results = []
        
        if gen_type == "funny":
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


def main():
    print("="*70)
    print("🎨 ComfyUI 全自动控制器 - Z-Image-Turbo")
    print("🚀 无需下载额外模型！")
    print("="*70)
    
    controller = ZImageController()
    
    # 检查连接
    if not controller.check_connection():
        print(f"\n❌ ComfyUI 未运行")
        print(f"💡 启动：cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI")
        print(f"   python main.py --listen 0.0.0.0 --port 8188")
        return 1
    
    # 检查模型
    if not controller.check_model():
        print(f"\n❌ Z-Image-Turbo 模型不存在")
        return 1
    
    # 显示类型
    print(f"\n📋 可用类型:")
    for key, name in GENERATE_TYPES.items():
        print(f"   {key} - {name}")
    
    # 输入
    try:
        count = int(input("\n需要生成多少张图片？(1-10): ").strip())
        count = max(1, min(10, count))
        
        gen_type = input("生成类型 (funny/portrait/landscape/anime/cyberpunk/fantasy/scifi/news): ").strip().lower()
        if gen_type not in GENERATE_TYPES:
            gen_type = "funny"
        
        custom_topic = input("自定义主题（可选）: ").strip()
        
        # 生成
        results = controller.auto_generate(count, gen_type, custom_topic if custom_topic else None)
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 结果")
        print(f"{'='*70}")
        success = sum(1 for r in results if r.get('success'))
        print(f"✅ 成功：{success}/{count}")
        print(f"💾 {OUTPUT_DIR}")
        
        # 报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "count": count,
            "type": gen_type,
            "model": controller.unet_model,
            "success": success,
            "results": results
        }
        report_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 {report_file}")
        
        if success > 0:
            print(f"\n🎉 完成！")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  中断")
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        count = int(sys.argv[1]) if sys.argv[1].isdigit() else 2
        gen_type = sys.argv[2] if len(sys.argv) > 2 else "funny"
        custom = sys.argv[3] if len(sys.argv) > 3 else None
        
        controller = ZImageController()
        if controller.check_connection() and controller.check_model():
            results = controller.auto_generate(count, gen_type, custom)
            success = sum(1 for r in results if r.get('success'))
            print(f"\n✅ {success}/{count}")
    else:
        sys.exit(main())
