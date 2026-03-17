#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 自动发现与智能执行系统
自动搜索模型、工作流、读取官方文档、按推荐配置运行
支持 Windows/Mac 跨平台
"""

import os
import sys
import json
import requests
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 跨平台路径配置
class PlatformPaths:
    """跨平台路径配置"""
    
    @staticmethod
    def get_home():
        return Path.home()
    
    @staticmethod
    def get_comfyui_dirs():
        """获取所有可能的 ComfyUI 安装目录"""
        system = platform.system()
        dirs = []
        
        if system == "Darwin":  # macOS
            dirs = [
                Path.home() / "Documents/lmd_data_root/apps/ComfyUI",
                Path.home() / "Documents/ComfyUI",
                Path.home() / "ComfyUI",
                Path("/Applications/ComfyUI"),
            ]
        elif system == "Windows":
            dirs = [
                Path(os.environ.get("USERPROFILE", "")) / "ComfyUI",
                Path(os.environ.get("USERPROFILE", "")) / "Documents/ComfyUI",
                Path("C:/ComfyUI"),
                Path("D:/ComfyUI"),
            ]
        elif system == "Linux":
            dirs = [
                Path.home() / "ComfyUI",
                Path("/opt/ComfyUI"),
                Path("/usr/local/ComfyUI"),
            ]
        
        # 添加环境变量指定的路径
        env_path = os.environ.get("COMFYUI_PATH")
        if env_path:
            dirs.append(Path(env_path))
        
        return [d for d in dirs if d.exists()]
    
    @staticmethod
    def get_model_dirs(base_dir: Path) -> Dict[str, Path]:
        """获取模型目录"""
        return {
            "unet": base_dir / "models/unet",
            "clip": base_dir / "models/clip",
            "vae": base_dir / "models/vae",
            "loras": base_dir / "models/loras",
            "checkpoints": base_dir / "models/checkpoints",
            "controlnet": base_dir / "models/controlnet",
            "embeddings": base_dir / "models/embeddings",
            "upscale_models": base_dir / "models/upscale_models",
        }
    
    @staticmethod
    def get_workflow_dirs(base_dir: Path) -> List[Path]:
        """获取工作流目录"""
        return [
            base_dir / "user/default/workflows",
            base_dir / "output/workflows",
            base_dir / "workflows",
        ]


class ModelRegistry:
    """模型注册表 - 从官网和社区获取模型信息"""
    
    # 官方模型信息源
    OFFICIAL_SOURCES = {
        "z_image_turbo": {
            "name": "Z-Image-Turbo",
            "type": "unet",
            "description": "高速图像生成模型",
            "recommended_workflow": "z_image_turbo_gguf.json",
            "recommended_settings": {
                "sampler": "euler",
                "scheduler": "simple",
                "steps": 20,
                "cfg": 7.0,
                "resolution": "1024x512"
            },
            "prompt_template": "You are an assistant creating high quality images.\n\n<Prompt Start>\n{prompt}",
            "negative_template": "blurry ugly bad",
            "docs_url": "https://huggingface.co/comfyanonymous/Z-Image-Turbo",
        },
        "ltx2": {
            "name": "LTX-Video (LTX-2-19B)",
            "type": "video",
            "description": "视频生成模型",
            "recommended_workflow": "ltx2_t2v_gguf.json",
            "recommended_settings": {
                "sampler": "euler_ancestral",
                "steps": 31,
                "cfg": 4.0,
                "resolution": "768x512",
                "frames": 97,
                "fps": 25
            },
            "prompt_template": "{prompt}",
            "negative_template": "blurry, low quality, still frame, frames, watermark, overlay, titles",
            "docs_url": "https://huggingface.co/Lightricks/LTX-Video",
        },
        "flux": {
            "name": "FLUX.1",
            "type": "unet",
            "description": "高质量图像生成",
            "recommended_workflow": "flux_dev_gguf.json",
            "recommended_settings": {
                "sampler": "euler",
                "scheduler": "simple",
                "steps": 20,
                "cfg": 3.5,
                "resolution": "1024x1024"
            },
            "docs_url": "https://huggingface.co/black-forest-labs/FLUX.1-dev",
        },
    }
    
    @classmethod
    def get_model_info(cls, model_name: str) -> Optional[Dict]:
        """获取模型信息"""
        # 模糊匹配
        for key, info in cls.OFFICIAL_SOURCES.items():
            if key in model_name.lower():
                return info
        return None
    
    @classmethod
    def fetch_from_huggingface(cls, repo_id: str) -> Optional[Dict]:
        """从 HuggingFace 获取模型信息"""
        try:
            api_url = f"https://huggingface.co/api/models/{repo_id}"
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": data.get("id", repo_id),
                    "downloads": data.get("downloads", 0),
                    "likes": data.get("likes", 0),
                    "tags": data.get("tags", []),
                    "pipeline_tag": data.get("pipeline_tag", ""),
                }
        except Exception as e:
            print(f"⚠️ 无法获取 HuggingFace 信息：{e}")
        return None
    
    @classmethod
    def fetch_from_civitai(cls, model_id: str) -> Optional[Dict]:
        """从 Civitai 获取模型信息"""
        try:
            api_url = f"https://civitai.com/api/v1/models/{model_id}"
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": data.get("name", ""),
                    "description": data.get("description", "")[:500],
                    "type": data.get("type", ""),
                    "tags": [t.get("name") for t in data.get("tags", [])],
                }
        except Exception as e:
            print(f"⚠️ 无法获取 Civitai 信息：{e}")
        return None


class WorkflowAnalyzer:
    """工作流分析器"""
    
    @staticmethod
    def analyze_workflow(wf_path: Path) -> Dict:
        """分析工作流文件"""
        try:
            with open(wf_path, 'r', encoding='utf-8') as f:
                wf = json.load(f)
            
            nodes = wf.get('nodes', [])
            links = wf.get('links', [])
            
            # 统计节点类型
            from collections import Counter
            node_types = Counter(n.get('type') for n in nodes)
            
            # 识别工作流类型
            workflow_type = "unknown"
            if any('LTX' in t or 'ltx' in t.lower() for t in node_types):
                workflow_type = "video"
            elif any('KSampler' in t for t in node_types):
                workflow_type = "image"
            elif any('Audio' in t or 'audio' in t.lower() for t in node_types):
                workflow_type = "audio"
            
            # 提取关键节点
            key_nodes = {}
            for node in nodes:
                ntype = node.get('type')
                if ntype in ['UnetLoaderGGUF', 'LoaderGGUF', 'DualCLIPLoaderGGUF', 
                            'KSampler', 'VAELoader', 'CLIPTextEncode', 'SaveImage',
                            'SaveVideo', 'EmptyLTXVLatentVideo', 'EmptySD3LatentImage']:
                    key_nodes[ntype] = node
            
            return {
                "file": str(wf_path),
                "name": wf_path.stem,
                "type": workflow_type,
                "node_count": len(nodes),
                "link_count": len(links),
                "node_types": dict(node_types),
                "key_nodes": list(key_nodes.keys()),
                "settings": WorkflowAnalyzer.extract_settings(key_nodes),
            }
        except Exception as e:
            return {"error": str(e), "file": str(wf_path)}
    
    @staticmethod
    def extract_settings(key_nodes: Dict) -> Dict:
        """提取工作流设置"""
        settings = {}
        
        # KSampler 设置
        if 'KSampler' in key_nodes:
            node = key_nodes['KSampler']
            widgets = node.get('widgets_values', [])
            if len(widgets) >= 7:
                settings['sampler'] = widgets[4] if len(widgets) > 4 else None
                settings['scheduler'] = widgets[5] if len(widgets) > 5 else None
                settings['steps'] = widgets[1] if len(widgets) > 1 else None
        
        # 分辨率设置
        for ntype, node in key_nodes.items():
            if 'Empty' in ntype and 'Latent' in ntype:
                widgets = node.get('widgets_values', [])
                if len(widgets) >= 2:
                    settings['width'] = widgets[0]
                    settings['height'] = widgets[1]
                if len(widgets) >= 3:
                    settings['frames'] = widgets[2]
        
        return settings


class ComfyUIDiscovery:
    """ComfyUI 自动发现系统"""
    
    def __init__(self):
        self.comfyui_dirs = PlatformPaths.get_comfyui_dirs()
        self.models = {}
        self.workflows = {}
        self.server = "127.0.0.1:8188"
    
    def discover_models(self) -> Dict[str, List[str]]:
        """发现所有模型"""
        print("🔍 扫描模型...")
        
        all_models = {}
        
        for base_dir in self.comfyui_dirs:
            print(f"  扫描：{base_dir}")
            model_dirs = PlatformPaths.get_model_dirs(base_dir)
            
            for model_type, model_dir in model_dirs.items():
                if model_dir.exists():
                    models = []
                    for f in model_dir.rglob("*"):
                        if f.suffix.lower() in ['.gguf', '.safetensors', '.ckpt', '.pt', '.pth']:
                            models.append(f.name)
                            # 获取模型信息
                            model_info = ModelRegistry.get_model_info(f.name)
                            if model_info:
                                self.models[f.name] = {
                                    "path": str(f),
                                    "type": model_type,
                                    "info": model_info,
                                }
                    
                    if models:
                        all_models[model_type] = models
                        print(f"    {model_type}: {len(models)} 个模型")
        
        return all_models
    
    def discover_workflows(self) -> List[Dict]:
        """发现所有工作流"""
        print("🔍 扫描工作流...")
        
        all_workflows = []
        
        for base_dir in self.comfyui_dirs:
            workflow_dirs = PlatformPaths.get_workflow_dirs(base_dir)
            
            for wf_dir in workflow_dirs:
                if wf_dir.exists():
                    for wf_file in wf_dir.glob("*.json"):
                        print(f"  分析：{wf_file.name}")
                        analysis = WorkflowAnalyzer.analyze_workflow(wf_file)
                        analysis['base_dir'] = str(base_dir)
                        all_workflows.append(analysis)
                        self.workflows[analysis['name']] = analysis
        
        return all_workflows
    
    def check_server(self) -> bool:
        """检查 ComfyUI 服务器"""
        try:
            r = requests.get(f"http://{self.server}/system_stats", timeout=5)
            return r.status_code == 200
        except:
            return False
    
    def get_available_nodes(self) -> List[str]:
        """获取可用节点列表"""
        try:
            r = requests.get(f"http://{self.server}/object_info", timeout=10)
            if r.status_code == 200:
                return list(r.json().keys())
        except:
            pass
        return []
    
    def generate_report(self) -> str:
        """生成发现报告"""
        report = []
        report.append("=" * 60)
        report.append("📊 ComfyUI 自动发现报告")
        report.append(f"⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"💻 系统：{platform.system()} {platform.release()}")
        report.append("=" * 60)
        
        report.append(f"\n📁 ComfyUI 安装目录：{len(self.comfyui_dirs)} 个")
        for d in self.comfyui_dirs:
            report.append(f"  - {d}")
        
        report.append(f"\n🎯 发现的模型：{len(self.models)} 个")
        model_types = {}
        for name, info in self.models.items():
            mtype = info.get('type', 'unknown')
            model_types[mtype] = model_types.get(mtype, 0) + 1
        for mtype, count in model_types.items():
            report.append(f"  {mtype}: {count} 个")
        
        report.append(f"\n📄 发现的工作流：{len(self.workflows)} 个")
        workflow_types = {}
        for name, info in self.workflows.items():
            wtype = info.get('type', 'unknown')
            workflow_types[wtype] = workflow_types.get(wtype, 0) + 1
        for wtype, count in workflow_types.items():
            report.append(f"  {wtype}: {count} 个")
        
        report.append(f"\n🔌 ComfyUI 服务器：{'✅ 在线' if self.check_server() else '❌ 离线'}")
        
        if self.check_server():
            nodes = self.get_available_nodes()
            report.append(f"   可用节点：{len(nodes)} 个")
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 ComfyUI 自动发现与智能执行系统")
    print("=" * 60)
    print()
    
    discovery = ComfyUIDiscovery()
    
    # 发现模型
    models = discovery.discover_models()
    print()
    
    # 发现工作流
    workflows = discovery.discover_workflows()
    print()
    
    # 生成报告
    report = discovery.generate_report()
    print(report)
    
    # 保存报告
    report_file = Path.home() / ".jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/发现报告.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 报告已保存：{report_file}")
    
    # 显示推荐的模型和工作流组合
    print("\n💡 推荐的模型 + 工作流组合:")
    for wf_name, wf_info in discovery.workflows.items():
        if wf_info.get('type') in ['image', 'video']:
            print(f"\n  {wf_name} ({wf_info['type']})")
            print(f"    节点数：{wf_info.get('node_count', '?')}")
            print(f"    关键节点：{', '.join(wf_info.get('key_nodes', [])[:5])}")
            settings = wf_info.get('settings', {})
            if settings:
                print(f"    设置：{settings}")


if __name__ == "__main__":
    main()
