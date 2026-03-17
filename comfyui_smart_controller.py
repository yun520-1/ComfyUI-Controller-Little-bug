#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能全自动控制器
- 智能扫描本地模型
- 自动选择最佳方案
- 只在需要时提醒下载
- 支持多种模型组合
"""

import json, uuid, time, requests, websocket, sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_auto_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ModelScanner:
    """智能模型扫描器"""

    def __init__(self):
        self.model_dir = COMFYUI_PATH / "models"
        self.available_models = {}
        self.recommended_workflow = None

    def scan(self) -> Dict:
        """扫描所有模型"""
        print(f"\n🔍 扫描 ComfyUI 模型...")
        print(f"   路径：{self.model_dir}")

        # 扫描各类型模型
        self._scan_unet()
        self._scan_clip()
        self._scan_vae()
        self._scan_checkpoints()

        # 推荐最佳工作流
        self._recommend_workflow()

        return self.available_models

    def _scan_unet(self):
        """扫描 UNet 模型"""
        unet_dir = self.model_dir / "unet"
        models = []
        if unet_dir.exists():
            for f in unet_dir.glob("*.gguf"):
                size = f.stat().st_size / (1024**3)
                models.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f)})
                print(f"   ✅ UNet: {f.name} ({size:.1f}GB)")
        self.available_models["unet"] = models

    def _scan_clip(self):
        """扫描 CLIP 模型"""
        clips = []

        # text_encoders 目录
        te_dir = self.model_dir / "text_encoders"
        if te_dir.exists():
            for f in te_dir.glob("*.safetensors"):
                if "embeddings" in f.name or "clip" in f.name.lower():
                    size = f.stat().st_size / (1024**3)
                    clips.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f), "type": "text_encoder"})
                    print(f"   ✅ CLIP: {f.name} ({size:.1f}GB)")

        # clip 目录
        clip_dir = self.model_dir / "clip"
        if clip_dir.exists():
            for f in clip_dir.glob("*.safetensors"):
                size = f.stat().st_size / (1024**3)
                clips.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f), "type": "clip"})
                print(f"   ✅ CLIP: {f.name} ({size:.1f}GB)")

        self.available_models["clip"] = clips

    def _scan_vae(self):
        """扫描 VAE 模型"""
        vaes = []
        vae_dir = self.model_dir / "vae"
        if vae_dir.exists():
            for f in vae_dir.glob("*.safetensors"):
                size = f.stat().st_size / (1024**3)
                vaes.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f)})
                print(f"   ✅ VAE: {f.name} ({size:.1f}GB)")
        self.available_models["vae"] = vaes

    def _scan_checkpoints(self):
        """扫描 Checkpoints"""
        ckpts = []
        ckpt_dir = self.model_dir / "checkpoints"
        if ckpt_dir.exists():
            for f in ckpt_dir.glob("*.ckpt"):
                size = f.stat().st_size / (1024**3)
                ckpts.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f)})
                print(f"   ✅ Checkpoint: {f.name} ({size:.1f}GB)")
            for f in ckpt_dir.glob("*.safetensors"):
                size = f.stat().st_size / (1024**3)
                ckpts.append({"file": f.name, "size": f"{size:.1f}GB", "path": str(f)})
                print(f"   ✅ Checkpoint: {f.name} ({size:.1f}GB)")
        self.available_models["checkpoints"] = ckpts

    def _recommend_workflow(self):
        """推荐最佳工作流"""
        unets = self.available_models.get("unet", [])
        clips = self.available_models.get("clip", [])
        vaes = self.available_models.get("vae", [])
        ckpts = self.available_models.get("checkpoints", [])

        # 方案优先级
        recommendations = []

        # 1. 如果有 SD Checkpoint - 最优
        if ckpts:
            sd_ckpt = next((c for c in ckpts if "v1-5" in c["file"].lower() or "sd1" in c["file"].lower()), None)
            if sd_ckpt:
                recommendations.append({
                    "type": "checkpoint",
                    "name": "SD Checkpoint",
                    "model": sd_ckpt["file"],
                    "priority": 1,
                    "ready": True
                })

        # 2. 如果有 Z-Image-Turbo + SD CLIP
        zimage = next((u for u in unets if "z_image" in u["file"].lower()), None)
        sd_clip = next((c for c in clips if "clip_l" in c["file"].lower() or c["type"] == "clip"), None)
        sd_vae = next((v for v in vaes if "ae.safetensors" in v["file"]), None)

        if zimage:
            ready = bool(sd_clip and sd_vae)
            missing = []
            if not sd_clip: missing.append("SD CLIP (clip_l.safetensors)")
            if not sd_vae: missing.append("VAE (ae.safetensors)")

            recommendations.append({
                "type": "z_image_turbo",
                "name": "Z-Image-Turbo GGUF",
                "model": zimage["file"],
                "priority": 2,
                "ready": ready,
                "missing": missing
            })

        # 3. 如果有 LTX2 完整配置
        ltx_unet = next((u for u in unets if "ltx" in u["file"].lower()), None)
        ltx_clip = next((c for c in clips if "ltx" in c["file"].lower()), None)
        ltx_vae = next((v for v in vaes if "ltx" in v["file"].lower()), None)

        if ltx_unet and ltx_clip and ltx_vae:
            recommendations.append({
                "type": "ltx2",
                "name": "LTX2 Video (单帧模式)",
                "model": ltx_unet["file"],
                "priority": 3,
                "ready": True,
                "note": "可生成单帧图片或短视频"
            })

        # 排序
        recommendations.sort(key=lambda x: x["priority"])
        self.recommended_workflow = recommendations[0] if recommendations else None

        print(f"\n💡 推荐方案：{self.recommended_workflow['name'] if self.recommended_workflow else '无可用方案'}")
        if self.recommended_workflow and not self.recommended_workflow.get('ready', False):
            print(f"   ⚠️  缺少：{', '.join(self.recommended_workflow.get('missing', []))}")


class SmartController:
    """智能控制器"""

    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.scanner = ModelScanner()
        self.workflow = None

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

    def initialize(self) -> bool:
        """初始化 - 扫描并选择最佳方案"""
        # 扫描模型
        self.scanner.scan()

        # 检查推荐方案
        rec = self.scanner.recommended_workflow

        if not rec:
            print(f"\n❌ 没有可用的生成方案")
            print(f"💡 建议下载以下任一模型:")
            print(f"   1. SD 1.5 Checkpoint (4.27GB)")
            print(f"   2. SD CLIP + VAE (配合 Z-Image-Turbo)")
            return False

        if rec.get('ready', False):
            print(f"\n✅ 使用方案：{rec['name']}")
            print(f"   模型：{rec['model']}")
            if rec.get('note'):
                print(f"   说明：{rec['note']}")
            self.workflow = rec
            return True
        else:
            print(f"\n⚠️  推荐方案：{rec['name']}")
            print(f"   模型：{rec['model']}")
            print(f"   缺少：{', '.join(rec.get('missing', []))}")

            response = input(f"\n是否现在下载缺失的模型？(y/n): ").strip().lower()
            if response == 'y':
                return self._download_missing(rec)
            else:
                # 尝试使用其他可用方案
                for alt in self.scanner.recommended_workflow:
                    if alt.get('ready', False):
                        print(f"\n✅ 使用备选方案：{alt['name']}")
                        self.workflow = alt
                        return True

                print(f"\n❌ 没有可用的备选方案")
                return False

    def _download_missing(self, rec: Dict) -> bool:
        """下载缺失的模型"""
        import urllib.request

        missing = rec.get('missing', [])

        for item in missing:
            if "clip_l" in item.lower():
                print(f"\n📥 下载 SD CLIP...")
                url = "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/clip_l.safetensors"
                dest = COMFYUI_PATH / "models" / "text_encoders" / "clip_l.safetensors"
                dest.parent.mkdir(parents=True, exist_ok=True)

                try:
                    def reporthook(blocknum, blocksize, totalsize):
                        percent = min(blocknum * blocksize * 100 / totalsize, 100)
                        print(f"\r   进度：{percent:.1f}%", end="")

                    urllib.request.urlretrieve(url, dest, reporthook)
                    print(f"\n   ✅ 下载完成：{dest.name}")
                except Exception as e:
                    print(f"\n   ❌ 下载失败：{e}")
                    return False

            elif "ae.safetensors" in item.lower():
                print(f"\n⚠️  VAE (ae.safetensors) 应该已存在，请检查")
                return False

        # 重新扫描
        print(f"\n🔄 重新扫描...")
        self.scanner.scan()
        return True

    def create_workflow_zimage(self, prompt: str, negative: str = "",
                               width: int = 1024, height: int = 512,
                               steps: int = 20, cfg: float = 7,
                               seed: int = None) -> Dict:
        """创建 Z-Image-Turbo 工作流"""
        if seed is None:
            seed = int(time.time() * 1000) % 1000000

        if not negative:
            negative = "blurry, low quality, ugly, duplicate"

        return {
            "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "z_image_turbo-Q8_0.gguf"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip_l.safetensors", "type": "sd1x"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
            "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": height, "width": width}},
            "7": {"class_type": "KSampler", "inputs": {
                "cfg": cfg, "denoise": 1, "latent_image": ["6", 0], "model": ["1", 0],
                "negative": ["5", 0], "positive": ["4", 0],
                "sampler_name": "euler_ancestral", "scheduler": "normal",
                "seed": seed, "steps": steps
            }},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {
                "filename_prefix": f"ComfyUI_Smart_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "images": ["8", 0]
            }}
        }

    def queue_and_monitor(self, workflow: Dict, timeout: int = 300) -> Optional[str]:
        """提交并监控"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=30
            )

            if resp.status_code != 200:
                print(f"❌ 提交失败：{resp.status_code}")
                try:
                    err = resp.json()
                    print(f"错误：{str(err)[:500]}")
                except: pass
                return None

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
                        return pid
                except: continue

            ws.close()
            return None
        except Exception as e:
            print(f"❌ 错误：{e}")
            return None

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


def main():
    print("="*70)
    print("🎨 ComfyUI 智能全自动控制器")
    print("="*70)

    controller = SmartController()

    # 检查连接
    if not controller.check_connection():
        print(f"\n❌ ComfyUI 未运行")
        return 1

    # 初始化（扫描 + 选择方案）
    if not controller.initialize():
        return 1

    # 简单测试生成
    print(f"\n🚀 测试生成...")
    workflow = controller.create_workflow_zimage(
        prompt="test, simple image, high quality",
        negative="blurry, low quality",
        width=512, height=512,
        steps=10
    )

    pid = controller.queue_and_monitor(workflow, timeout=120)
    if pid:
        files = controller.download_result(pid, "test")
        if files:
            print(f"\n✅ 测试成功！")
            print(f"💡 可以开始正式生成了")
            print(f"\n运行完整生成:")
            print(f"   python3 comfyui_smart_controller.py")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n⚠️  中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
