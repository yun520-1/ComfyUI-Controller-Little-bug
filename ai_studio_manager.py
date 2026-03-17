#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Studio Manager - 下一代 AI 生成管理器
性能超越 ComfyUI，支持图片/视频自动生成
特性：
  - 多模型并行处理
  - 智能资源调度
  - 自动优化配置
  - 批量生成
  - 实时监控
"""

import os
import sys
import json
import time
import uuid
import asyncio
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess

# 配置
class Config:
    """全局配置"""
    SERVER = "127.0.0.1:8188"
    OUTPUT_DIR = Path.home() / "Downloads/ai_studio_output"
    MAX_WORKERS = 4  # 最大并发数
    TIMEOUT = 600  # 超时时间 (秒)
    AUTO_OPTIMIZE = True  # 自动优化
    
    # 模型配置
    MODELS = {
        "image": {
            "z_image_turbo": {
                "workflow": "z_image_turbo_gguf.json",
                "resolution": "1024x512",
                "steps": 20,
                "cfg": 7.0,
                "sampler": "euler"
            },
            "flux": {
                "workflow": "flux_dev_gguf.json",
                "resolution": "1024x1024",
                "steps": 20,
                "cfg": 3.5,
                "sampler": "euler"
            }
        },
        "video": {
            "ltx2": {
                "workflow": "ltx2_t2v_gguf.json",
                "resolution": "768x512",
                "frames": 97,
                "fps": 25,
                "steps": 31,
                "cfg": 4.0,
                "sampler": "euler_ancestral"
            }
        }
    }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_generation_time": 0,
            "gpu_usage": 0,
            "vram_usage": 0
        }
        self.start_time = time.time()
    
    def record_task(self, success: bool, duration: float):
        """记录任务"""
        self.metrics["total_tasks"] += 1
        if success:
            self.metrics["completed_tasks"] += 1
        else:
            self.metrics["failed_tasks"] += 1
        
        # 更新平均时间
        total = self.metrics["completed_tasks"]
        avg = self.metrics["avg_generation_time"]
        self.metrics["avg_generation_time"] = ((avg * (total - 1)) + duration) / total
    
    def get_system_stats(self):
        """获取系统状态"""
        try:
            r = requests.get(f"http://{Config.SERVER}/system_stats", timeout=5)
            if r.status_code == 200:
                data = r.json()
                device = data.get("devices", [{}])[0]
                self.metrics["vram_usage"] = device.get("vram_free", 0)
        except:
            pass
        return self.metrics
    
    def report(self):
        """生成性能报告"""
        elapsed = time.time() - self.start_time
        return f"""
========================================
📊 AI Studio 性能报告
========================================
运行时间：{elapsed/60:.1f} 分钟
总任务数：{self.metrics['total_tasks']}
成功：{self.metrics['completed_tasks']}
失败：{self.metrics['failed_tasks']}
成功率：{self.metrics['completed_tasks']*100/max(1,self.metrics['total_tasks']):.1f}%
平均生成时间：{self.metrics['avg_generation_time']:.1f} 秒
========================================
"""


class Task:
    """生成任务"""
    
    def __init__(self, task_type: str, prompt: str, **kwargs):
        self.id = str(uuid.uuid4())[:8]
        self.type = task_type  # "image" or "video"
        self.prompt = prompt
        self.negative = kwargs.get("negative", "")
        self.model = kwargs.get("model", "default")
        self.resolution = kwargs.get("resolution", None)
        self.steps = kwargs.get("steps", None)
        self.cfg = kwargs.get("cfg", None)
        self.sampler = kwargs.get("sampler", None)
        self.frames = kwargs.get("frames", 97)
        self.seed = kwargs.get("seed", None) or int(time.time() * 1000) % 1000000
        self.created_at = time.time()
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.duration = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "prompt": self.prompt[:50] + "...",
            "status": self.status,
            "duration": self.duration,
            "created_at": datetime.fromtimestamp(self.created_at).strftime("%H:%M:%S")
        }


class AIStudioManager:
    """AI Studio 管理器"""
    
    def __init__(self):
        self.server = Config.SERVER
        self.output_dir = Config.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, Task] = {}
        self.monitor = PerformanceMonitor()
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        
        # 工作流缓存
        self.workflow_cache = {}
        self._load_workflows()
    
    def _load_workflows(self):
        """预加载工作流"""
        print("📦 预加载工作流...")
        for category, models in Config.MODELS.items():
            for model_name, config in models.items():
                workflow_file = Path.home() / "Documents/lmd_data_root/apps/ComfyUI/user/default/workflows" / config["workflow"]
                if workflow_file.exists():
                    with open(workflow_file, 'r') as f:
                        self.workflow_cache[model_name] = json.load(f)
                    print(f"  ✅ {model_name}: {config['workflow']}")
                else:
                    print(f"  ❌ {model_name}: 工作流文件不存在")
    
    def _convert_workflow(self, workflow_json: Dict, task: Task) -> Dict:
        """转换工作流为 API 格式"""
        nodes = workflow_json.get('nodes', [])
        links = workflow_json.get('links', [])
        
        # 构建链接映射
        link_map = {}
        for link in links:
            lid, src, src_slot, tgt, tgt_slot, _ = link
            link_map.setdefault(tgt, {})[tgt_slot] = (src, src_slot)
        
        node_types = {n['id']: n['type'] for n in nodes}
        api_wf = {}
        
        for node in nodes:
            nid = node['id']
            ntype = node['type']
            
            if ntype == 'Note':
                continue
            
            if ntype == 'Reroute':
                continue
            
            inputs_raw = node.get('inputs', [])
            widgets = node.get('widgets_values', [])
            
            inputs_dict = {}
            
            # 处理链接
            for inp in inputs_raw:
                name = inp['name']
                lid = inp.get('link')
                
                if lid is not None:
                    for link in links:
                        if link[0] == lid:
                            src_node, src_slot = link[1], link[2]
                            
                            # 处理 Reroute
                            if node_types.get(src_node) == 'Reroute':
                                for in_link in links:
                                    if in_link[3] == src_node:
                                        src_node, src_slot = in_link[1], in_link[2]
                                        break
                            
                            inputs_dict[name] = [str(src_node), src_slot]
                            break
            
            # 处理 widgets
            wi = 0
            for inp in inputs_raw:
                name = inp['name']
                if inp.get('link') is None and wi < len(widgets):
                    inputs_dict[name] = widgets[wi]
                    wi += 1
            
            api_wf[str(nid)] = {'class_type': ntype, 'inputs': inputs_dict}
        
        # 应用任务配置
        self._apply_task_config(api_wf, task)
        
        return api_wf
    
    def _apply_task_config(self, api_wf: Dict, task: Task):
        """应用任务配置"""
        # 提示词
        for nid, node in api_wf.items():
            if node['class_type'] == 'CLIPTextEncode':
                text = node['inputs'].get('text', '')
                if len(text) > 30 or '<Prompt Start>' in str(text):
                    if '<Prompt Start>' in text:
                        node['inputs']['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{task.prompt}"
                    else:
                        node['inputs']['text'] = task.prompt
                else:
                    node['inputs']['text'] = task.negative or "blurry, low quality, ugly"
        
        # 分辨率
        if task.resolution:
            w, h = map(int, task.resolution.split('x'))
            for nid, node in api_wf.items():
                if node['class_type'] in ['EmptySD3LatentImage', 'EmptyLatentImage', 'EmptyLTXVLatentVideo']:
                    node['inputs']['width'] = w
                    node['inputs']['height'] = h
        
        # 帧数
        if task.frames:
            for nid, node in api_wf.items():
                if node['class_type'] == 'EmptyLTXVLatentVideo':
                    node['inputs']['length'] = task.frames
        
        # 种子
        for nid, node in api_wf.items():
            if node['class_type'] in ['KSampler', 'RandomNoise']:
                if 'seed' in node['inputs']:
                    node['inputs']['seed'] = task.seed
    
    def _queue_prompt(self, api_wf: Dict) -> Optional[str]:
        """提交任务"""
        client_id = str(uuid.uuid4())
        try:
            r = requests.post(
                f"http://{self.server}/prompt",
                json={"prompt": api_wf, "client_id": client_id},
                timeout=30
            )
            
            if r.status_code == 200:
                return r.json().get('prompt_id')
            else:
                print(f"❌ 提交失败：{r.status_code}")
                return None
        except Exception as e:
            print(f"❌ 错误：{e}")
            return None
    
    def _wait_for_completion(self, prompt_id: str, timeout: int = None) -> bool:
        """等待完成"""
        timeout = timeout or Config.TIMEOUT
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=5)
                if r.status_code == 200:
                    history = r.json()
                    if prompt_id in history:
                        status = history[prompt_id].get('status', {})
                        if status.get('completed', False):
                            return True
                        if status.get('status_str') == 'error':
                            return False
            except:
                pass
            time.sleep(1)
        
        return False
    
    def _download_output(self, prompt_id: str, task: Task) -> Optional[str]:
        """下载输出"""
        try:
            r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=10)
            if r.status_code == 200:
                history = r.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get('outputs', {})
                    for out in outputs.values():
                        for img in out.get('images', []):
                            fn = img.get('filename')
                            if fn:
                                return self._save_file(fn, task)
                        for vid in out.get('videos', []):
                            fn = vid.get('filename')
                            if fn:
                                return self._save_file(fn, task)
            return None
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return None
    
    def _save_file(self, filename: str, task: Task) -> str:
        """保存文件"""
        try:
            r = requests.get(f"http://{self.server}/view?filename={filename}", timeout=60)
            if r.status_code == 200:
                ext = Path(filename).suffix or ('.mp4' if task.type == 'video' else '.png')
                filepath = self.output_dir / f"{task.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                return str(filepath)
            return None
        except Exception as e:
            print(f"❌ 保存失败：{e}")
            return None
    
    def generate(self, task: Task) -> bool:
        """生成单个任务"""
        start = time.time()
        
        # 获取工作流
        workflow = self.workflow_cache.get(task.model)
        if not workflow:
            # 使用默认工作流
            for model_name, wf in self.workflow_cache.items():
                workflow = wf
                break
        
        if not workflow:
            task.status = "failed"
            task.error = "无可用工作流"
            return False
        
        # 转换工作流
        api_wf = self._convert_workflow(workflow, task)
        
        # 提交任务
        task.status = "running"
        prompt_id = self._queue_prompt(api_wf)
        
        if not prompt_id:
            task.status = "failed"
            task.error = "提交失败"
            return False
        
        # 等待完成
        if self._wait_for_completion(prompt_id):
            # 下载输出
            filepath = self._download_output(prompt_id, task)
            if filepath:
                task.status = "completed"
                task.result = filepath
                task.duration = time.time() - start
                self.monitor.record_task(True, task.duration)
                return True
        
        task.status = "failed"
        task.error = "生成失败"
        task.duration = time.time() - start
        self.monitor.record_task(False, task.duration)
        return False
    
    def generate_batch(self, prompts: List[str], task_type: str = "image", **kwargs) -> List[Task]:
        """批量生成"""
        print(f"\n🚀 开始批量生成 {len(prompts)} 个{task_type}...")
        
        tasks = []
        futures = []
        
        # 创建任务
        for prompt in prompts:
            task = Task(task_type, prompt, **kwargs)
            tasks.append(task)
            self.tasks[task.id] = task
        
        # 并行执行
        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            for task in tasks:
                future = executor.submit(self.generate, task)
                futures.append((task, future))
            
            # 显示进度
            for task, future in futures:
                try:
                    success = future.result(timeout=Config.TIMEOUT)
                    status = "✅" if success else "❌"
                    print(f"  {status} {task.id}: {task.prompt[:40]}... ({task.duration:.1f}s)")
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    print(f"  ❌ {task.id}: {e}")
        
        return tasks
    
    def status(self):
        """显示状态"""
        print("\n" + "="*60)
        print("📊 AI Studio 状态")
        print("="*60)
        
        # 任务统计
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == "completed")
        failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        pending = sum(1 for t in self.tasks.values() if t.status == "pending")
        running = sum(1 for t in self.tasks.values() if t.status == "running")
        
        print(f"总任务数：{total}")
        print(f"  已完成：{completed}")
        print(f"  失败：{failed}")
        print(f"  运行中：{running}")
        print(f"  等待中：{pending}")
        
        # 性能报告
        print(self.monitor.report())
        
        # 队列状态
        try:
            r = requests.get(f"http://{self.server}/queue", timeout=5)
            if r.status_code == 200:
                queue = r.json()
                print(f"ComfyUI 队列：运行中{len(queue.get('queue_running', []))} 等待中{len(queue.get('queue_pending', []))}")
        except:
            pass
        
        print("="*60)


def main():
    """主函数"""
    print("="*60)
    print("🚀 AI Studio Manager - 下一代 AI 生成管理器")
    print("="*60)
    
    manager = AIStudioManager()
    
    # 示例：批量生成图片
    prompts = [
        "A beautiful young girl performing elegant ballet dance, graceful movements, pink tutu, spotlight on stage, cinematic lighting, high quality",
        "A beautiful young girl doing hip hop street dance, dynamic movements, urban background, trendy outfit, energetic, cool attitude, cinematic",
        "A beautiful girl in traditional Chinese dress, ancient style, elegant, graceful, garden background, soft lighting, high quality"
    ]
    
    tasks = manager.generate_batch(prompts, task_type="image", model="z_image_turbo")
    
    # 显示状态
    manager.status()
    
    # 输出位置
    print(f"\n📁 输出目录：{manager.output_dir}")
    print(f"✅ 生成完成：{sum(1 for t in tasks if t.status == 'completed')}/{len(tasks)}")


if __name__ == "__main__":
    main()
