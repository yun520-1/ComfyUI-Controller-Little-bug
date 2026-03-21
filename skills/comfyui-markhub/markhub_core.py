#!/usr/bin/env python3
"""
ComfyUI MarkHub v1.0 - 云平台智能创作系统

功能:
- 连接云平台 ComfyUI
- 自动读取和选择工作流
- 任务监督系统
- 自动保存图片和视频到本地
"""

import requests
import json
import uuid
import time
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import urllib.request
import ssl

# 忽略 SSL 证书验证
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class TaskWatcher:
    """任务监督器"""
    
    def __init__(self, comfy_client, prompt_id: str, timeout: int = 600):
        self.comfy = comfy_client
        self.prompt_id = prompt_id
        self.timeout = timeout
        self.start_time = time.time()
        self.last_status = None
        
    def watch(self) -> Dict:
        """监督任务直到完成"""
        print(f"\n👁️ 开始监督任务 {self.prompt_id[:12]}...")
        print(f"   超时时间：{self.timeout}秒")
        
        while time.time() - self.start_time < self.timeout:
            elapsed = int(time.time() - self.start_time)
            
            # 获取任务状态
            history = self.comfy.get_history(self.prompt_id)
            
            if not history:
                print(f"  ⏳ {elapsed}s - 等待中...")
                time.sleep(5)
                continue
            
            task_info = history.get(self.prompt_id, {})
            status = task_info.get('status', {})
            
            # 检查是否完成
            if status.get('completed', False):
                print(f"  ✅ {elapsed}s - 任务完成！")
                return {
                    'status': 'success',
                    'elapsed': elapsed,
                    'outputs': task_info.get('outputs', {})
                }
            
            # 检查是否失败
            if status.get('failed', False):
                error_msg = status.get('messages', ['未知错误'])[0]
                print(f"  ❌ {elapsed}s - 任务失败：{error_msg}")
                return {
                    'status': 'failed',
                    'error': error_msg,
                    'elapsed': elapsed
                }
            
            # 显示进度
            messages = status.get('messages', [])
            for msg in messages:
                if msg[0] == 'execution_cached':
                    nodes_done = len(msg[1].get('nodes', []))
                    print(f"  ⏳ {elapsed}s - 已缓存 {nodes_done} 个节点")
                elif msg[0] == 'executing':
                    node_id = msg[1].get('node', '...')
                    print(f"  ⏳ {elapsed}s - 执行节点 {node_id}")
            
            time.sleep(5)
        
        # 超时
        print(f"  ⚠️ 任务超时 ({self.timeout}秒)")
        return {
            'status': 'timeout',
            'elapsed': elapsed
        }


class ComfyUIMarkHub:
    """ComfyUI MarkHub v1.0 - 全平台智能创作系统"""
    
    # 预定义平台配置
    PLATFORMS = {
        'custom': {
            'name': 'Custom Platform',
            'base_url': 'YOUR_COMFYUI_URL',
            'verify_ssl': False,
            'api_path': '/object_info',
            'auth_required': False
        },
        'runpod': {
            'name': 'RunPod',
            'base_url': 'https://api.runpod.ai/v2/{pod_id}/comfyui',
            'verify_ssl': True,
            'api_path': '/object_info',
            'auth_required': True,
            'auth_header': 'Authorization'
        },
        'vast': {
            'name': 'Vast.ai',
            'base_url': 'https://console.vast.ai/api/v2/comfyui/{instance_id}',
            'verify_ssl': False,
            'api_path': '/object_info',
            'auth_required': True,
            'auth_header': 'Authorization'
        },
        'massed': {
            'name': 'Massed Compute',
            'base_url': 'https://massedcompute.com:40001',
            'verify_ssl': False,
            'api_path': '/object_info',
            'auth_required': False
        },
        'thinkingmachines': {
            'name': 'Thinking Machines',
            'base_url': 'https://api.thinkingmachines.ai/comfyui',
            'verify_ssl': True,
            'api_path': '/object_info',
            'auth_required': True
        },
        'local': {
            'name': '本地 ComfyUI',
            'base_url': 'http://127.0.0.1:8188',
            'verify_ssl': False,
            'api_path': '/object_info',
            'auth_required': False
        }
    }
    
    def __init__(self, config_path: str = None, platform: str = 'custom'):
        """初始化"""
        self.config = self.load_config(config_path)
        self.platform_name = platform
        
        # 加载平台配置
        platform_config = self.PLATFORMS.get(platform, self.PLATFORMS['custom'])
        self.base_url = self.config.get('comfyui', {}).get('base_url', platform_config['base_url'])
        self.verify_ssl = self.config.get('comfyui', {}).get('verify_ssl', platform_config['verify_ssl'])
        self.api_token = self.config.get('comfyui', {}).get('api_token', None)
        self.auth_header = platform_config.get('auth_header', 'Authorization')
        
        self.client_id = str(uuid.uuid4())
        self.session = requests.Session()
        if not self.verify_ssl:
            self.session.verify = False
        
        # 配置认证
        if self.api_token and platform_config.get('auth_required'):
            self.session.headers[self.auth_header] = f"Bearer {self.api_token}"
        
        self.object_info = None
        self.workflows = None
        self.platform_info = None
        
        # 输出目录
        self.image_dir = Path(self.config['output']['images']).expanduser()
        self.video_dir = Path(self.config['output']['videos']).expanduser()
        
        # 创建输出目录
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ ComfyUI MarkHub v1.0 已初始化")
        print(f"   平台：{platform_config['name']}")
        print(f"   地址：{self.base_url}")
        print(f"   认证：{'已配置' if self.api_token else '无需认证'}")
        print(f"   图片输出：{self.image_dir}")
        print(f"   视频输出：{self.video_dir}")
    
    def load_config(self, config_path: str = None) -> Dict:
        """加载配置"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认配置
        return {
            'comfyui': {
                'base_url': 'http://127.0.0.1:8188',  # 默认本地 ComfyUI
                'verify_ssl': False,
                'timeout': 300,
                'max_retries': 3
            },
            'output': {
                'images': '~/Pictures/MarkHub',
                'videos': '~/Videos/MarkHub',
                'save_meta': True,
                'organize_by_date': True
            },
            'watcher': {
                'enabled': True,
                'timeout': 600,
                'poll_interval': 5,
                'auto_retry': True
            },
            'optimizer': {
                'auto_resolution': True,
                'auto_steps': True,
                'auto_cfg': True,
                'quality_preset': 'balanced'
            }
        }
    
    def get_object_info(self, force_refresh: bool = False) -> Dict:
        """获取节点信息"""
        if self.object_info and not force_refresh:
            return self.object_info
        
        try:
            print(f"📚 获取节点信息...")
            resp = self.session.get(f"{self.base_url}/object_info", timeout=30)
            self.object_info = resp.json()
            print(f"✅ 获取到 {len(self.object_info)} 个节点")
            return self.object_info
        except Exception as e:
            print(f"❌ 获取节点信息失败：{e}")
            return {}
    
    def detect_platform(self) -> str:
        """自动检测云平台类型"""
        print(f"\n🔍 自动检测平台...")
        
        # 测试各个平台
        for platform_id, platform_config in self.PLATFORMS.items():
            if platform_id == 'custom':
                continue
            
            try:
                base_url = platform_config['base_url']
                if '{' in base_url:  # 需要参数的 URL 跳过
                    continue
                
                test_url = f"{base_url}{platform_config['api_path']}"
                resp = requests.get(test_url, verify=platform_config['verify_ssl'], timeout=5)
                
                if resp.status_code == 200:
                    print(f"✅ 检测到平台：{platform_config['name']} ({base_url})")
                    return platform_id
            except Exception:
                continue
        
        # 默认使用自定义配置
        print(f"⚠️ 未检测到预定义平台，使用自定义配置")
        return 'custom'
    
    def get_platform_info(self) -> Dict:
        """获取平台详细信息"""
        if self.platform_info:
            return self.platform_info
        
        try:
            # 获取系统信息
            system_stats = self.get_system_stats()
            
            # 获取队列信息
            queue = self.get_queue()
            
            self.platform_info = {
                'platform': self.platform_name,
                'base_url': self.base_url,
                'system': system_stats,
                'queue': queue,
                'timestamp': datetime.now().isoformat()
            }
            
            return self.platform_info
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_stats(self) -> Dict:
        """获取系统状态"""
        try:
            resp = self.session.get(f"{self.base_url}/system_stats", timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取系统状态失败：{e}")
            return {}
    
    def get_queue(self) -> Dict:
        """获取队列状态"""
        try:
            resp = self.session.get(f"{self.base_url}/queue", timeout=10)
            return resp.json()
        except Exception as e:
            return {}
    
    def get_history(self, prompt_id: str) -> Dict:
        """获取生成历史"""
        try:
            resp = self.session.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            return resp.json()
        except Exception as e:
            return {}
    
    def queue_prompt(self, prompt: Dict) -> Optional[Dict]:
        """提交提示词"""
        try:
            payload = {
                "prompt": prompt,
                "client_id": self.client_id
            }
            resp = self.session.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=30
            )
            result = resp.json()
            if 'prompt_id' in result:
                print(f"✅ 任务已提交：{result['prompt_id'][:12]}...")
                return result
            else:
                print(f"❌ 提交失败：{result}")
                return None
        except Exception as e:
            print(f"提交失败：{e}")
            return None
    
    def download_output(self, filename: str, subfolder: str = "", output_type: str = "images") -> Optional[str]:
        """下载输出文件"""
        try:
            if subfolder:
                url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}"
            else:
                url = f"{self.base_url}/view?filename={filename}"
            
            print(f"  ⬇️ 下载：{filename}")
            resp = self.session.get(url, timeout=300)
            
            if resp.status_code == 200 and len(resp.content) > 1000:
                # 按日期组织目录
                today = datetime.now()
                if output_type == "images":
                    save_dir = self.image_dir / f"{today.year}-{today.month:02d}" / f"{today.day:02d}"
                else:
                    save_dir = self.video_dir / f"{today.year}-{today.month:02d}" / f"{today.day:02d}"
                
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / filename
                
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                
                file_size = len(resp.content) / 1024 / 1024
                print(f"  ✅ 已保存：{save_path} ({file_size:.2f} MB)")
                return str(save_path)
            else:
                print(f"  ❌ 下载失败：{resp.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ 下载异常：{e}")
            return None
    
    def save_metadata(self, prompt_id: str, prompt: Dict, output_paths: List[str]):
        """保存元数据"""
        today = datetime.now()
        meta_dir = self.image_dir / f"{today.year}-{today.month:02d}" / f"{today.day:02d}"
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        meta = {
            'prompt_id': prompt_id,
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'config': self.config,
            'outputs': output_paths
        }
        
        meta_path = meta_dir / f"meta_{prompt_id[:12]}.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        
        print(f"  📝 元数据已保存：{meta_path}")
    
    def select_best_workflow(self, task_type: str, prompt: str) -> Dict:
        """智能选择最佳工作流"""
        print(f"\n🤖 智能选择工作流...")
        print(f"   任务类型：{task_type}")
        
        # 获取节点信息
        object_info = self.get_object_info()
        
        # 根据任务类型选择
        if task_type == "txt2img":
            # 文生图工作流
            workflow = self.create_txt2img_workflow(prompt)
        elif task_type == "txt2video":
            # 文生视频工作流
            workflow = self.create_txt2video_workflow(prompt)
        else:
            # 默认文生图
            workflow = self.create_txt2img_workflow(prompt)
        
        return workflow
    
    def create_txt2img_workflow(self, prompt: str) -> Dict:
        """创建文生图工作流"""
        # 简化版 SDXL 工作流
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sd_xl_base_1.0.safetensors"
                }
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1]
                }
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "nsfw, low quality, worst quality",
                    "clip": ["1", 1]
                }
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 1024,
                    "height": 1024,
                    "batch_size": 1
                }
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": int(time.time() * 1000) % 1000000,
                    "steps": 30,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0]
                }
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2]
                }
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "MarkHub",
                    "images": ["6", 0]
                }
            }
        }
        
        print(f"✅ 文生图工作流已创建 (7 节点)")
        return workflow
    
    def create_txt2video_workflow(self, prompt: str, duration: int = 10) -> Dict:
        """创建文生视频工作流"""
        # LTX-Video 工作流
        workflow = {
            "1": {
                "class_type": "LTXVLoader",
                "inputs": {
                    "model_name": "ltx-video-2b-v0.9.safetensors"
                }
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1]
                }
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "worst quality, low quality",
                    "clip": ["1", 1]
                }
            },
            "4": {
                "class_type": "EmptyLTXVLatentVideo",
                "inputs": {
                    "width": 768,
                    "height": 512,
                    "length": 97,
                    "batch_size": 1
                }
            },
            "5": {
                "class_type": "LTXVScheduler",
                "inputs": {
                    "steps": 30,
                    "max_shift": 2.05,
                    "base_shift": 0.95,
                    "latent": ["4", 0]
                }
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": int(time.time() * 1000) % 1000000,
                    "steps": 30,
                    "cfg": 4.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0]
                }
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["1", 2]
                }
            },
            "8": {
                "class_type": "SaveVideo",
                "inputs": {
                    "filename_prefix": "MarkHub_Video",
                    "video": ["7", 0]
                }
            }
        }
        
        print(f"✅ 文生视频工作流已创建 (8 节点)")
        return workflow
    
    def generate(self, prompt: str, task_type: str = "auto", 
                 watch: bool = True, save: bool = True) -> Dict:
        """生成图片或视频"""
        print(f"\n{'='*60}")
        print(f"🎨 ComfyUI MarkHub v1.0 - 云平台智能创作")
        print(f"{'='*60}")
        print(f"提示词：{prompt[:100]}...")
        
        # 自动判断任务类型
        if task_type == "auto":
            if "video" in prompt.lower() or "motion" in prompt.lower() or "dance" in prompt.lower():
                task_type = "txt2video"
                print(f"🎬 自动识别：视频生成")
            else:
                task_type = "txt2img"
                print(f"🖼️ 自动识别：图片生成")
        
        # 选择工作流
        workflow = self.select_best_workflow(task_type, prompt)
        
        # 提交任务
        result = self.queue_prompt(workflow)
        if not result:
            return {'status': 'failed', 'error': '提交失败'}
        
        prompt_id = result['prompt_id']
        
        # 监督任务
        if watch:
            watcher = TaskWatcher(self, prompt_id, timeout=600)
            watch_result = watcher.watch()
            
            if watch_result['status'] != 'success':
                return watch_result
            
            # 下载输出
            if save and 'outputs' in watch_result:
                output_paths = []
                for node_id, output in watch_result['outputs'].items():
                    if 'images' in output:
                        for img in output['images']:
                            path = self.download_output(
                                img['filename'],
                                img.get('subfolder', ''),
                                "images"
                            )
                            if path:
                                output_paths.append(path)
                    if 'videos' in output:
                        for vid in output['videos']:
                            path = self.download_output(
                                vid['filename'],
                                vid.get('subfolder', ''),
                                "videos"
                            )
                            if path:
                                output_paths.append(path)
                
                # 保存元数据
                self.save_metadata(prompt_id, workflow, output_paths)
                
                return {
                    'status': 'success',
                    'prompt_id': prompt_id,
                    'outputs': output_paths
                }
        
        return {'status': 'success', 'prompt_id': prompt_id}


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ComfyUI MarkHub v1.0')
    parser.add_argument('-p', '--prompt', type=str, required=True, help='提示词')
    parser.add_argument('--image', action='store_true', help='生成图片')
    parser.add_argument('--video', action='store_true', help='生成视频')
    parser.add_argument('--auto', action='store_true', help='自动模式')
    parser.add_argument('--duration', type=int, default=10, help='视频时长 (秒)')
    parser.add_argument('--url', type=str, help='ComfyUI 地址')
    parser.add_argument('--watch', action='store_true', default=True, help='启用任务监督')
    parser.add_argument('--save', action='store_true', default=True, help='保存到本地')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--platform', type=str, default='auto', 
                       help='平台：auto/custom/runpod/vast/massed/thinkingmachines/local')
    parser.add_argument('--list-platforms', action='store_true', help='列出所有平台')
    
    args = parser.parse_args()
    
    # 列出平台
    if args.list_platforms:
        print("\n=== 支持的平台 ===\n")
        for pid, pinfo in ComfyUIMarkHub.PLATFORMS.items():
            print(f"  {pid:20} - {pinfo['name']}")
            print(f"                     URL: {pinfo['base_url']}")
            print(f"                     认证：{'需要' if pinfo.get('auth_required') else '无需'}")
            print()
        sys.exit(0)
    
    # 初始化
    markhub = ComfyUIMarkHub(config_path=args.config)
    
    # 确定任务类型
    if args.image:
        task_type = "txt2img"
    elif args.video:
        task_type = "txt2video"
    elif args.auto:
        task_type = "auto"
    else:
        task_type = "txt2img"
    
    # 生成
    result = markhub.generate(
        prompt=args.prompt,
        task_type=task_type,
        watch=args.watch,
        save=args.save
    )
    
    # 输出结果
    print(f"\n{'='*60}")
    if result['status'] == 'success':
        print(f"✅ 生成成功！")
        print(f"   Prompt ID: {result['prompt_id']}")
        if 'outputs' in result:
            print(f"   输出文件:")
            for path in result['outputs']:
                print(f"     - {path}")
    else:
        print(f"❌ 生成失败：{result.get('error', '未知错误')}")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
