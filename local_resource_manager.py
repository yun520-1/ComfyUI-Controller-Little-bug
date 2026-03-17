#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 本地资源管理器
功能：
- 扫描本地 ComfyUI 安装的模型
- 扫描本地工作流
- 检测系统配置（GPU、内存、存储）
- 推荐合适的模型和工作流
"""

import os
import sys
import json
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import requests


class LocalComfyUIManager:
    """本地 ComfyUI 资源管理器"""

    # 常见的 ComfyUI 安装路径
    POSSIBLE_PATHS = [
        Path.home() / "ComfyUI",
        Path.home() / "apps" / "ComfyUI",
        Path.home() / "Documents" / "ComfyUI",
        Path("/opt/ComfyUI"),
        Path("/usr/local/ComfyUI"),
        Path.home() / "sdwebui" / "ComfyUI",
    ]

    # 模型目录映射
    MODEL_DIRS = {
        "checkpoints": "models/checkpoints",
        "loras": "models/loras",
        "vae": "models/vae",
        "upscale_models": "models/upscale_models",
        "controlnet": "models/controlnet",
        "clip": "models/clip",
        "clip_vision": "models/clip_vision",
        "style_models": "models/style_models",
        "diffusers": "models/diffusers",
        "gligen": "models/gligen",
        "hypernetworks": "models/hypernetworks",
        "insightface": "models/insightface",
        "layerstyle": "models/layerstyle",
        "mmdets": "models/mmdets",
        "prompt_expansion": "models/prompt_expansion",
        "reactor": "models/reactor",
        "remgbg": "models/remgbg",
        "sam": "models/sam",
        "sams": "models/sams",
        "ultralytics": "models/ultralytics",
        "animatediff_models": "models/animatediff_models",
        "animatediff_motion_lora": "models/animatediff_motion_lora",
        "video_formats": "models/video_formats",
        "wav2lip": "models/wav2lip",
        "whisper": "models/whisper",
        "inpaint": "models/inpaint",
        "diffusion_models": "models/diffusion_models",
        "unet": "models/unet",
    }

    def __init__(self):
        self.comfyui_path = None
        self.system_info = {}
        self.available_models = {}
        self.available_workflows = {}

    def find_comfyui(self) -> Optional[Path]:
        """查找本地 ComfyUI 安装路径"""
        print("\n🔍 正在查找 ComfyUI 安装...")

        # 检查常见路径
        for path in self.POSSIBLE_PATHS:
            if path.exists() and (path / "main.py").exists():
                print(f"✅ 找到 ComfyUI: {path}")
                self.comfyui_path = path
                return path

        # 检查环境变量
        env_path = os.environ.get("COMFYUI_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists() and (path / "main.py").exists():
                print(f"✅ 通过环境变量找到 ComfyUI: {path}")
                self.comfyui_path = path
                return path

        # 尝试从运行进程查找
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ComfyUI|main.py.*--listen"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    try:
                        # 读取进程的 cwd
                        if platform.system() == "Darwin":  # macOS
                            result = subprocess.run(
                                ["lsof", "-p", pid, "-Fn"],
                                capture_output=True,
                                text=True
                            )
                            # 简化处理，直接返回找到的第一个
                            print(f"⚠️  检测到 ComfyUI 进程 (PID: {pid})，但无法确定路径")
                    except:
                        pass
        except:
            pass

        print("❌ 未找到 ComfyUI 安装")
        return None

    def detect_system_config(self) -> Dict:
        """检测系统配置"""
        print("\n💻 检测系统配置...")

        config = {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
            "gpu": None,
            "gpu_memory": None,
            "total_memory": None,
            "available_storage": None,
            "cuda_available": False,
            "recommended_models": []
        }

        # 内存信息
        try:
            if platform.system() == "Darwin":  # macOS
                # 使用 sysctl 获取内存
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    total_mem = int(result.stdout.strip())
                    config["total_memory"] = f"{total_mem / (1024**3):.1f} GB"

                # 获取存储信息
                result = subprocess.run(
                    ["df", "-h", "/"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            config["available_storage"] = parts[3]

                # 检测 GPU (macOS)
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    output = result.stdout
                    if "Apple M" in output or "Apple Silicon" in output:
                        config["gpu"] = "Apple Silicon (Unified Memory)"
                        # 估算显存
                        if config["total_memory"]:
                            mem_str = config["total_memory"].replace(" GB", "")
                            try:
                                mem_gb = float(mem_str)
                                config["gpu_memory"] = f"{mem_gb * 0.7:.1f} GB (估计)"
                                # 根据内存推荐模型
                                if mem_gb >= 32:
                                    config["recommended_models"] = [
                                        "SDXL 1.0 (6-7GB)",
                                        "SD 1.5 (2-4GB)",
                                        "Flux.1 (12-16GB)"
                                    ]
                                elif mem_gb >= 16:
                                    config["recommended_models"] = [
                                        "SD 1.5 (2-4GB)",
                                        "SDXL Turbo (4-6GB)"
                                    ]
                                else:
                                    config["recommended_models"] = [
                                        "SD 1.5 (2-4GB)",
                                        "TinySD (<2GB)"
                                    ]
                            except:
                                pass
                    elif "NVIDIA" in output:
                        config["gpu"] = "NVIDIA"
                        config["cuda_available"] = True
                    elif "AMD" in output:
                        config["gpu"] = "AMD"

            elif platform.system() == "Linux":
                # Linux 系统
                result = subprocess.run(
                    ["free", "-h"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            config["total_memory"] = parts[1]

                # GPU 信息
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    gpu_info = result.stdout.strip().split("\n")
                    if gpu_info:
                        config["gpu"] = gpu_info[0].split(", ")[0]
                        config["gpu_memory"] = gpu_info[0].split(", ")[1]
                        config["cuda_available"] = True
                else:
                    # 尝试 AMD GPU
                    result = subprocess.run(
                        ["rocm-smi"],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        config["gpu"] = "AMD ROCm"

                # 存储信息
                result = subprocess.run(
                    ["df", "-h", "/"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            config["available_storage"] = parts[3]

            elif platform.system() == "Windows":
                # Windows 系统
                import ctypes
                kernel32 = ctypes.windll.kernel32
                c_ulonglong = ctypes.c_ulonglong

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', c_ulonglong),
                        ('ullAvailPhys', c_ulonglong),
                        ('ullTotalPageFile', c_ulonglong),
                        ('ullAvailPageFile', c_ulonglong),
                        ('ullTotalVirtual', c_ulonglong),
                        ('ullAvailVirtual', c_ulonglong),
                        ('ullAvailExtendedVirtual', c_ulonglong),
                    ]

                memoryStatus = MEMORYSTATUSEX()
                memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus)):
                    config["total_memory"] = f"{memoryStatus.ullTotalPhys / (1024**3):.1f} GB"

                # GPU 信息 (WMI)
                try:
                    import wmi
                    w = wmi.WMI()
                    for gpu in w.Win32_VideoController():
                        config["gpu"] = gpu.Name
                        if hasattr(gpu, 'AdapterRAM') and gpu.AdapterRAM:
                            config["gpu_memory"] = f"{gpu.AdapterRAM / (1024**3):.1f} GB"
                        if "NVIDIA" in gpu.Name or "AMD" in gpu.Name:
                            config["cuda_available"] = "NVIDIA" in gpu.Name
                except:
                    pass

                # 存储信息
                result = subprocess.run(
                    ["wmic", "logicaldisk", "get", "freespace,size"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            free_gb = int(parts[0]) / (1024**3)
                            config["available_storage"] = f"{free_gb:.1f} GB"

        except Exception as e:
            print(f"⚠️  检测系统配置时出错：{e}")

        self.system_info = config

        # 打印配置
        print(f"\n📊 系统配置:")
        print(f"   操作系统：{config['os']} {config['os_version']}")
        print(f"   CPU: {config['cpu_count']} 核心")
        print(f"   内存：{config['total_memory'] or '未知'}")
        print(f"   GPU: {config['gpu'] or '集成显卡'}")
        print(f"   显存：{config['gpu_memory'] or '共享内存'}")
        print(f"   可用存储：{config['available_storage'] or '未知'}")
        print(f"   CUDA: {'✅ 支持' if config['cuda_available'] else '❌ 不支持'}")

        if config['recommended_models']:
            print(f"\n💡 推荐模型:")
            for model in config['recommended_models']:
                print(f"   - {model}")

        return config

    def scan_models(self) -> Dict:
        """扫描本地模型"""
        if not self.comfyui_path:
            print("❌ ComfyUI 路径未设置，无法扫描模型")
            return {}

        print(f"\n📦 扫描 ComfyUI 模型 ({self.comfyui_path})...")

        models = {}

        for model_type, rel_path in self.MODEL_DIRS.items():
            model_dir = self.comfyui_path / rel_path
            if model_dir.exists():
                files = []
                for ext in ["*.ckpt", "*.safetensors", "*.pt", "*.pth"]:
                    files.extend(list(model_dir.glob(ext)))

                if files:
                    models[model_type] = {
                        "path": str(model_dir),
                        "count": len(files),
                        "files": [f.name for f in files[:20]]  # 只列前 20 个
                    }
                    print(f"   ✅ {model_type}: {len(files)} 个模型")

        self.available_models = models
        return models

    def scan_workflows(self) -> Dict:
        """扫描本地工作流"""
        if not self.comfyui_path:
            return {}

        print(f"\n📋 扫描 ComfyUI 工作流...")

        workflows = {
            "embedded": [],  # ComfyUI 内置工作流
            "custom": []     # 用户自定义工作流
        }

        # 扫描用户工作流目录
        workflow_dirs = [
            self.comfyui_path / "workflows",
            self.comfyui_path / "output" / "workflows",
            Path.home() / "ComfyUI" / "workflows",
        ]

        for wf_dir in workflow_dirs:
            if wf_dir.exists():
                for wf_file in wf_dir.glob("*.json"):
                    try:
                        with open(wf_file, 'r', encoding='utf-8') as f:
                            wf_data = json.load(f)
                            workflows["custom"].append({
                                "name": wf_file.stem,
                                "path": str(wf_file),
                                "nodes": len(wf_data) if isinstance(wf_data, dict) else 0
                            })
                    except:
                        pass

        print(f"   找到 {len(workflows['custom'])} 个自定义工作流")

        self.available_workflows = workflows
        return workflows

    def check_model_compatibility(self, model_name: str) -> Dict:
        """检查模型与系统配置的兼容性"""
        if not self.system_info:
            self.detect_system_config()

        # 常见模型大小和配置要求
        model_requirements = {
            "SD 1.5": {"vram": 4, "ram": 8, "storage": 4},
            "SD 2.0": {"vram": 6, "ram": 12, "storage": 5},
            "SD 2.1": {"vram": 6, "ram": 12, "storage": 5},
            "SDXL 1.0": {"vram": 8, "ram": 16, "storage": 7},
            "SDXL Turbo": {"vram": 8, "ram": 16, "storage": 7},
            "Flux.1": {"vram": 16, "ram": 32, "storage": 24},
            "Playground v2.5": {"vram": 8, "ram": 16, "storage": 8},
            "Stable Cascade": {"vram": 12, "ram": 24, "storage": 15},
        }

        # 解析模型名称
        model_key = None
        for key in model_requirements.keys():
            if key.lower() in model_name.lower():
                model_key = key
                break

        if not model_key:
            return {
                "compatible": True,
                "message": "未知模型，无法评估兼容性"
            }

        req = model_requirements[model_key]

        # 检查显存
        gpu_mem = 0
        if self.system_info.get("gpu_memory"):
            try:
                gpu_mem = float(self.system_info["gpu_memory"].replace(" GB", ""))
            except:
                pass

        # 检查内存
        total_ram = 0
        if self.system_info.get("total_memory"):
            try:
                total_ram = float(self.system_info["total_memory"].replace(" GB", ""))
            except:
                pass

        issues = []
        warnings = []

        if gpu_mem < req["vram"]:
            issues.append(f"显存不足：需要 {req['vram']}GB，当前 {gpu_mem}GB")
        elif gpu_mem < req["vram"] * 1.2:
            warnings.append(f"显存紧张：建议 {req['vram']}GB，当前 {gpu_mem}GB")

        if total_ram < req["ram"]:
            issues.append(f"内存不足：需要 {req['ram']}GB，当前 {total_ram}GB")

        return {
            "compatible": len(issues) == 0,
            "model": model_key,
            "requirements": req,
            "issues": issues,
            "warnings": warnings,
            "message": "✅ 兼容" if len(issues) == 0 else "❌ 不兼容"
        }

    def get_recommendations(self) -> Dict:
        """基于系统配置给出推荐"""
        if not self.system_info:
            self.detect_system_config()

        recommendations = {
            "models": [],
            "workflows": [],
            "settings": {}
        }

        # 根据显存推荐模型
        gpu_mem = 0
        if self.system_info.get("gpu_memory"):
            try:
                gpu_mem = float(self.system_info["gpu_memory"].replace(" GB", ""))
            except:
                pass

        if gpu_mem >= 16:
            recommendations["models"] = [
                "Flux.1 Dev/Schnell",
                "SDXL 1.0",
                "Stable Cascade",
                "Playground v2.5"
            ]
            recommendations["settings"] = {
                "resolution": "1024x1024 或更高",
                "batch_size": 2,
                "steps": "20-40"
            }
        elif gpu_mem >= 8:
            recommendations["models"] = [
                "SDXL Turbo",
                "SDXL 1.0 (优化版)",
                "SD 1.5",
                "LCM 模型"
            ]
            recommendations["settings"] = {
                "resolution": "512x512 - 1024x1024",
                "batch_size": 1,
                "steps": "20-30"
            }
        elif gpu_mem >= 4:
            recommendations["models"] = [
                "SD 1.5",
                "SD 2.0 Turbo",
                "LCM-LoRA",
                "TinySD"
            ]
            recommendations["settings"] = {
                "resolution": "512x512",
                "batch_size": 1,
                "steps": "10-20"
            }
        else:
            recommendations["models"] = [
                "SD 1.5 (CPU 优化版)",
                "ONNX 模型",
                "OpenVINO 模型"
            ]
            recommendations["settings"] = {
                "resolution": "512x512 或更低",
                "batch_size": 1,
                "steps": "10-15"
            }

        return recommendations

    def generate_report(self, output_path: str = None) -> str:
        """生成扫描报告"""
        if not output_path:
            output_path = f"comfyui_scan_report_{Path.home().name}.json"

        report = {
            "timestamp": str(datetime.now()),
            "system_info": self.system_info,
            "comfyui_path": str(self.comfyui_path) if self.comfyui_path else None,
            "available_models": self.available_models,
            "available_workflows": self.available_workflows,
            "recommendations": self.get_recommendations()
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n📄 报告已保存：{output_path}")
        return output_path


def main():
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description="ComfyUI 本地资源管理器")
    parser.add_argument("--scan", action="store_true", help="扫描本地资源")
    parser.add_argument("--system", action="store_true", help="只显示系统配置")
    parser.add_argument("--models", action="store_true", help="只显示模型")
    parser.add_argument("--workflows", action="store_true", help="只显示工作流")
    parser.add_argument("--recommend", action="store_true", help="显示推荐配置")
    parser.add_argument("--report", type=str, help="生成报告到指定路径")
    parser.add_argument("--comfyui-path", type=str, help="指定 ComfyUI 路径")

    args = parser.parse_args()

    manager = LocalComfyUIManager()

    # 指定路径
    if args.comfyui_path:
        manager.comfyui_path = Path(args.comfyui_path)
    else:
        manager.find_comfyui()

    # 检测系统配置
    manager.detect_system_config()

    if args.scan or not any([args.system, args.models, args.workflows, args.recommend]):
        # 完整扫描
        manager.scan_models()
        manager.scan_workflows()

        if args.report:
            manager.generate_report(args.report)

    if args.models:
        manager.scan_models()

    if args.workflows:
        manager.scan_workflows()

    if args.recommend:
        recs = manager.get_recommendations()
        print(f"\n💡 推荐配置:")
        print(f"\n模型:")
        for model in recs["models"]:
            print(f"   - {model}")
        print(f"\n设置:")
        for key, value in recs["settings"].items():
            print(f"   {key}: {value}")


if __name__ == "__main__":
    main()
