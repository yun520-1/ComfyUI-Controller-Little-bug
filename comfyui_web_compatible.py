#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能控制器 - 网页端兼容版
直接查询 ComfyUI 实际可用模型
不强制下载任何模型
网页端能用的，这里就能用！
"""

import json, uuid, time, requests, websocket, sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SmartModelScanner:
    """智能模型扫描器 - 查询 ComfyUI 实际可用模型"""

    def __init__(self, server):
        self.server = server
        self.base_url = f"http://{server}"
        self.available_workflows = []

    def scan(self) -> Dict:
        """扫描 ComfyUI 实际可用的模型"""
        print(f"\n🔍 查询 ComfyUI 实际可用模型...")

        # 1. 获取系统信息
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                sys_info = resp.json()
                print(f"✅ ComfyUI: {self.server}")
        except:
            print(f"❌ 无法连接 ComfyUI")
            return {}

        # 2. 查询可用节点
        try:
            resp = requests.get(f"{self.base_url}/object_info", timeout=10)
            if resp.status_code == 200:
                object_info = resp.json()

                # 检查可用的模型加载器
                print(f"\n📦 可用模型加载器:")

                workflows = []

                # 检查 UnetLoaderGGUF
                if "UnetLoaderGGUF" in object_info:
                    unet_info = object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"][0]
                    print(f"   ✅ UnetLoaderGGUF: {len(unet_info)} 个模型")
                    for m in unet_info[:5]:
                        print(f"      - {m}")

                    workflows.append({
                        "type": "gguf_unet",
                        "name": "GGUF UNet 工作流",
                        "models": unet_info,
                        "ready": True
                    })

                # 检查 CLIPLoader
                if "CLIPLoader" in object_info:
                    clip_info = object_info["CLIPLoader"]["input"]["required"]["clip_name"][0]
                    print(f"   ✅ CLIPLoader: {len(clip_info)} 个 CLIP")
                    for m in clip_info[:5]:
                        print(f"      - {m}")

                # 检查 VAELoader
                if "VAELoader" in object_info:
                    vae_info = object_info["VAELoader"]["input"]["required"]["vae_name"][0]
                    print(f"   ✅ VAELoader: {len(vae_info)} 个 VAE")
                    for m in vae_info[:5]:
                        print(f"      - {m}")

                # 检查 CheckpointLoaderSimple
                if "CheckpointLoaderSimple" in object_info:
                    ckpt_info = object_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
                    if ckpt_info:
                        print(f"   ✅ CheckpointLoader: {len(ckpt_info)} 个 Checkpoints")
                        for m in ckpt_info[:5]:
                            print(f"      - {m}")

                        workflows.append({
                            "type": "checkpoint",
                            "name": "SD Checkpoint 工作流",
                            "models": ckpt_info,
                            "ready": True
                        })

                # 推荐最佳工作流
                if workflows:
                    print(f"\n💡 推荐方案：{workflows[0]['name']}")
                    if workflows[0].get('models'):
                        print(f"   可用模型：{workflows[0]['models'][0]}")

                return {
                    "object_info": object_info,
                    "workflows": workflows,
                    "recommended": workflows[0] if workflows else None
                }

        except Exception as e:
            print(f"❌ 查询失败：{e}")
            return {}

        return {}


class WebCompatibleController:
    """网页端兼容控制器 - 网页能用的这里就能用"""

    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.scanner = SmartModelScanner(server)
        self.system_info = {}
        self.recommended_workflow = None

    def initialize(self) -> bool:
        """初始化 - 查询 ComfyUI 实际配置"""
        # 扫描
        result = self.scanner.scan()

        if not result:
            return False

        self.system_info = result
        self.recommended_workflow = result.get('recommended')

        if not self.recommended_workflow:
            print(f"\n❌ 没有可用的工作流")
            return False

        return True

    def create_workflow_gguf(self, prompt: str, unet_model: str,
                            clip_model: str = None, vae_model: str = None,
                            negative: str = "", width: int = 1024, height: int = 512,
                            steps: int = 20, cfg: float = 7, seed: int = None) -> Dict:
        """创建 GGUF UNet 工作流"""

        # 自动选择 CLIP 和 VAE
        object_info = self.system_info.get('object_info', {})

        # 获取可用 CLIP
        if clip_model is None:
            if "CLIPLoader" in object_info:
                clips = object_info["CLIPLoader"]["input"]["required"]["clip_name"][0]
                clip_model = clips[0] if clips else "clip_l.safetensors"

        # 获取可用 VAE
        if vae_model is None:
            if "VAELoader" in object_info:
                vaes = object_info["VAELoader"]["input"]["required"]["vae_name"][0]
                # 优先选择 ae.safetensors
                vae_model = next((v for v in vaes if "ae.safetensors" in v), vaes[0] if vaes else "ae.safetensors")

        if seed is None:
            seed = int(time.time() * 1000) % 1000000

        if not negative:
            negative = "blurry, low quality, ugly, duplicate"

        # 根据实际可用节点创建工作流
        workflow = {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": unet_model}
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": clip_model, "type": "sd1x"}
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": vae_model}
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": prompt}
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": negative}
            },
            "6": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": height, "width": width}
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": cfg, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0],
                    "negative": ["5", 0], "positive": ["4", 0],
                    "sampler_name": "euler_ancestral", "scheduler": "normal",
                    "seed": seed, "steps": steps
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["3", 0]}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"ComfyUI_Smart_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "images": ["8", 0]
                }
            }
        }

        print(f"\n📝 创建工作流:")
        print(f"   UNet: {unet_model}")
        print(f"   CLIP: {clip_model}")
        print(f"   VAE: {vae_model}")
        print(f"   分辨率：{width}x{height}")

        return workflow

    def queue_and_monitor(self, workflow: Dict, timeout: int = 300) -> bool:
        """提交并监控"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=30
            )

            if resp.status_code == 200:
                pid = resp.json().get('prompt_id')
                print(f"✅ 已提交 (ID: {pid})")

                # 监控
                ws = websocket.WebSocket()
                ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)

                print(f"⏳ 生成中...", end=" ", flush=True)
                start = time.time()
                last_pct = -1

                while time.time() - start < timeout:
                    try:
                        msg = json.loads(ws.recv())
                        if msg.get('type') == 'progress':
                            pct = int(msg['data'].get('value', 0) / msg['data'].get('max', 100) * 100)
                            if pct != last_pct:
                                print(f"{pct}% ", end="", flush=True)
                                last_pct = pct
                        elif msg.get('type') == 'executing' and msg['data'].get('node') is None:
                            print("✅")
                            ws.close()
                            return True
                    except: continue

                ws.close()
                return False
            else:
                print(f"❌ 提交失败：{resp.status_code}")
                try:
                    err = resp.json()
                    print(f"错误：{str(err)[:500]}")

                    # 如果是 CLIP 问题，尝试其他 CLIP
                    if "clip_name" in str(err):
                        print(f"\n💡 尝试使用其他 CLIP 模型...")
                        return False
                except: pass
                return False

        except Exception as e:
            print(f"❌ 错误：{e}")
            return False

    def download_result(self, prompt_id: str, title: str = "") -> List[str]:
        """下载结果"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            history = resp.json()

            if prompt_id not in history:
                return []

            outputs = history[prompt_id].get('outputs', {})
            downloaded = []

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
                                filepath = OUTPUT_DIR / f"{ts}_{title.replace(' ', '_') if title else 'image'}.png"

                                with open(filepath, 'wb') as f:
                                    f.write(resp.content)

                                print(f"  ✅ {filepath.name}")
                                downloaded.append(str(filepath))

            return downloaded
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []


class PromptGenerator:
    """提示词生成器"""

    def get_funny_prompts(self) -> List[Dict]:
        """获取搞笑段子提示词"""
        return [
            {"title": "上班迟到", "prompt": "funny cartoon style, office worker pointing at Ferrari, car owner pushing car, exaggerated expressions, humor, bright colors", "negative": "blurry, low quality, dark, serious"},
            {"title": "减肥失败", "prompt": "funny cartoon style, gym scene, fat person asking coach, coach pointing at food, humor, bright", "negative": "blurry, low quality, dark"},
            {"title": "相亲经历", "prompt": "funny cartoon style, camping scene, tent and bicycle, humor, outdoor, bright colors", "negative": "blurry, low quality"},
            {"title": "程序员", "prompt": "funny cartoon style, programmer at computer, multiple monitors, exhausted, humor, office", "negative": "blurry, low quality"},
            {"title": "健身卡", "prompt": "funny cartoon style, gym locker room, person with towel, humor, bright", "negative": "blurry, low quality"}
        ]

    def get_type_prompt(self, gen_type: str) -> str:
        """根据类型获取提示词"""
        prompts = {
            "funny": "funny cartoon style, humor, exaggerated, bright colors",
            "portrait": "portrait photography, professional lighting, bokeh, high quality",
            "landscape": "beautiful landscape, nature, mountains, golden hour, high quality",
            "anime": "anime style, Japanese animation, colorful, detailed",
            "cyberpunk": "cyberpunk city, neon lights, futuristic, night scene",
            "fantasy": "fantasy world, magic, dragon, castle, epic",
            "scifi": "science fiction, spaceship, alien planet, futuristic",
            "news": "news illustration, professional, high quality"
        }
        return prompts.get(gen_type, prompts["funny"])


def main():
    print("="*70)
    print("🎨 ComfyUI 智能控制器 - 网页端兼容版")
    print("💡 网页端能用的，这里就能用！")
    print("="*70)

    controller = WebCompatibleController()
    prompt_gen = PromptGenerator()

    # 初始化（查询实际可用模型）
    if not controller.initialize():
        return 1

    # 选择生成类型
    print(f"\n📋 生成类型:")
    types = ["funny", "portrait", "landscape", "anime", "cyberpunk", "fantasy", "scifi", "news"]
    for i, t in enumerate(types, 1):
        print(f"  {i}. {t}")

    try:
        type_choice = input("\n选择类型 (1-8): ").strip()
        gen_type = types[int(type_choice)-1] if type_choice.isdigit() and 1 <= int(type_choice) <= 8 else "funny"

        count = int(input("生成数量 (1-5): ").strip())
        count = max(1, min(5, count))

        # 获取提示词
        if gen_type == "funny":
            topics = prompt_gen.get_funny_prompts()[:count]
        else:
            base_prompt = prompt_gen.get_type_prompt(gen_type)
            topics = [{"title": f"{gen_type}_{i+1}", "prompt": base_prompt, "negative": ""} for i in range(count)]

        # 获取推荐模型
        rec = controller.recommended_workflow
        unet_model = rec['models'][0] if rec and rec.get('models') else "z_image_turbo-Q8_0.gguf"

        print(f"\n🚀 开始生成...")
        print(f"   类型：{gen_type}")
        print(f"   数量：{count}")
        print(f"   模型：{unet_model}")

        results = []
        for i, topic in enumerate(topics, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{count}] {topic['title']}")
            print(f"📝 {topic['prompt'][:60]}...")

            # 创建工作流
            workflow = controller.create_workflow_gguf(
                prompt=topic['prompt'],
                unet_model=unet_model,
                negative=topic.get('negative', ''),
                width=1024, height=512,
                steps=25
            )

            # 提交并监控
            if controller.queue_and_monitor(workflow):
                # 下载
                files = controller.download_result("last", topic['title'])
                results.append({"success": len(files) > 0, "title": topic['title']})

            if i < count:
                time.sleep(2)

        # 汇总
        print(f"\n{'='*70}")
        print("📊 结果")
        print(f"{'='*70}")
        success = sum(1 for r in results if r.get('success'))
        print(f"✅ 成功：{success}/{count}")
        print(f"💾 {OUTPUT_DIR}")

    except KeyboardInterrupt:
        print(f"\n\n⚠️  中断")
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        sys.exit(1)
