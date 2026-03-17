#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能执行系统
根据发现的模型和工作流，自动选择最佳配置执行任务
支持官网文档查询、社区最佳实践
"""

import json
import uuid
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from comfyui_auto_discovery import (
    ComfyUIDiscovery, ModelRegistry, WorkflowAnalyzer, PlatformPaths
)

SERVER = "127.0.0.1:8188"


class SmartExecutor:
    """智能执行器"""
    
    def __init__(self):
        self.discovery = ComfyUIDiscovery()
        self.discovery.discover_models()
        self.discovery.discover_workflows()
        self.server = SERVER
    
    def find_best_workflow(self, task_type: str = "image") -> Optional[Dict]:
        """根据任务类型找到最佳工作流"""
        candidates = []
        
        for name, info in self.discovery.workflows.items():
            if info.get('type') == task_type:
                score = 0
                # 优先选择节点数适中的工作流
                node_count = info.get('node_count', 0)
                if 10 <= node_count <= 15:
                    score += 10
                elif node_count < 30:
                    score += 5
                
                # 优先选择有推荐设置的
                if info.get('settings'):
                    score += 5
                
                # 优先选择已知模型的工作流
                if any(k in name.lower() for k in ModelRegistry.OFFICIAL_SOURCES.keys()):
                    score += 10
                
                candidates.append((score, name, info))
        
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            best = candidates[0]
            print(f"✅ 选择工作流：{best[1]} (得分：{best[0]})")
            return best[2]
        
        return None
    
    def get_model_recommendation(self, workflow_info: Dict) -> Optional[Dict]:
        """获取模型推荐"""
        key_nodes = workflow_info.get('key_nodes', [])
        
        for node_type in key_nodes:
            if 'Loader' in node_type:
                # 尝试匹配模型信息
                for model_name, model_info in self.discovery.models.items():
                    if any(k in model_name.lower() for k in ModelRegistry.OFFICIAL_SOURCES.keys()):
                        return ModelRegistry.get_model_info(model_name)
        
        return None
    
    def convert_workflow_to_api(self, wf_path: Path, modifications: Dict = None) -> Dict:
        """转换工作流为 API 格式"""
        with open(wf_path, 'r', encoding='utf-8') as f:
            wf = json.load(f)
        
        nodes = wf.get('nodes', [])
        links = wf.get('links', [])
        modifications = modifications or {}
        
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
            
            # 跳过 Reroute，重定向链接
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
        
        # 应用修改
        self._apply_modifications(api_wf, modifications)
        
        return api_wf
    
    def _apply_modifications(self, api_wf: Dict, mods: Dict):
        """应用修改"""
        # 提示词
        if 'prompt' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'CLIPTextEncode':
                    text = node['inputs'].get('text', '')
                    if len(text) > 30 or '<Prompt Start>' in str(text):
                        if '<Prompt Start>' in text:
                            node['inputs']['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{mods['prompt']}"
                        else:
                            node['inputs']['text'] = mods['prompt']
        
        # 负面提示词
        if 'negative' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'CLIPTextEncode':
                    text = node['inputs'].get('text', '')
                    if len(text) <= 30 or any(w in text.lower() for w in ['blurry', 'ugly', 'bad']):
                        node['inputs']['text'] = mods['negative']
        
        # 尺寸
        if 'width' in mods or 'height' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] in ['EmptySD3LatentImage', 'EmptyLatentImage', 'EmptyLTXVLatentVideo']:
                    if 'width' in mods:
                        node['inputs']['width'] = mods['width']
                    if 'height' in mods:
                        node['inputs']['height'] = mods['height']
        
        # 帧数
        if 'frames' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'EmptyLTXVLatentVideo':
                    node['inputs']['length'] = mods['frames']
        
        # 种子
        if 'seed' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] in ['KSampler', 'RandomNoise']:
                    if 'seed' in node['inputs']:
                        node['inputs']['seed'] = mods['seed']
    
    def execute(self, workflow_name: str, modifications: Dict = None) -> Optional[str]:
        """执行工作流"""
        # 找到工作流文件
        wf_path = None
        for base_dir in self.discovery.comfyui_dirs:
            for wf_dir in PlatformPaths.get_workflow_dirs(base_dir):
                candidate = wf_dir / f"{workflow_name}.json"
                if candidate.exists():
                    wf_path = candidate
                    break
                candidate = wf_dir / workflow_name
                if candidate.exists():
                    wf_path = candidate
                    break
            if wf_path:
                break
        
        if not wf_path:
            print(f"❌ 工作流文件未找到：{workflow_name}")
            return None
        
        print(f"📄 使用工作流：{wf_path}")
        
        # 转换为 API
        api_wf = self.convert_workflow_to_api(wf_path, modifications)
        
        # 提交任务
        client_id = str(uuid.uuid4())
        try:
            r = requests.post(
                f"http://{self.server}/prompt",
                json={"prompt": api_wf, "client_id": client_id},
                timeout=30
            )
            
            if r.status_code == 200:
                pid = r.json().get('prompt_id')
                print(f"✅ 任务已提交：{pid}")
                return pid
            else:
                print(f"❌ 提交失败：{r.status_code}")
                try:
                    err = r.json()
                    if 'node_errors' in err:
                        for nid, errs in err['node_errors'].items():
                            for e in errs:
                                print(f"   节点{nid}: {e.get('message', '')[:150]}")
                except:
                    pass
                return None
        except Exception as e:
            print(f"❌ 错误：{e}")
            return None
    
    def wait_and_download(self, prompt_id: str, timeout: int = 600, output_dir: Path = None) -> Optional[str]:
        """等待完成并下载"""
        if output_dir is None:
            output_dir = Path.home() / "Downloads/comfyui_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"⏳ 等待任务完成...")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=5)
                if r.status_code == 200:
                    history = r.json()
                    if prompt_id in history:
                        status = history[prompt_id].get('status', {})
                        
                        if status.get('completed', False):
                            print("✅ 任务完成!")
                            
                            # 下载输出
                            outputs = history[prompt_id].get('outputs', {})
                            files = []
                            for nid, out in outputs.items():
                                for img in out.get('images', []):
                                    fn = img.get('filename')
                                    if fn:
                                        fp = self._download_file(fn, output_dir)
                                        if fp:
                                            files.append(fp)
                                for vid in out.get('videos', []):
                                    fn = vid.get('filename')
                                    if fn:
                                        fp = self._download_file(fn, output_dir)
                                        if fp:
                                            files.append(fp)
                            
                            return files[0] if files else None
                        
                        if status.get('status_str') == 'error':
                            print("❌ 任务失败")
                            for m in status.get('messages', []):
                                if len(m) > 1 and m[0] == 'execution_error':
                                    e = m[1]
                                    print(f"错误：{e.get('exception_message', '')[:200]}")
                            return None
            except:
                pass
            time.sleep(2)
        
        print("⏰ 超时")
        return None
    
    def _download_file(self, filename: str, output_dir: Path) -> Optional[str]:
        """下载文件"""
        try:
            r = requests.get(f"http://{self.server}/view?filename={filename}", timeout=60)
            if r.status_code == 200:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fp = output_dir / f"{ts}_{filename}"
                with open(fp, 'wb') as f:
                    f.write(r.content)
                print(f"  ✅ 已保存：{fp}")
                return str(fp)
            return None
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return None
    
    def quick_image(self, prompt: str, **kwargs) -> Optional[str]:
        """快速生成图片"""
        workflow = self.find_best_workflow("image")
        if not workflow:
            print("❌ 未找到合适的图片工作流")
            return None
        
        mods = {
            'prompt': prompt,
            'negative': kwargs.get('negative', 'blurry, low quality, ugly'),
            'width': kwargs.get('width', 1024),
            'height': kwargs.get('height', 512),
            'seed': kwargs.get('seed', int(time.time() * 1000) % 1000000),
        }
        
        pid = self.execute(workflow['name'], mods)
        if pid:
            return self.wait_and_download(pid)
        return None
    
    def quick_video(self, prompt: str, **kwargs) -> Optional[str]:
        """快速生成视频"""
        workflow = self.find_best_workflow("video")
        if not workflow:
            print("❌ 未找到合适的视频工作流")
            return None
        
        mods = {
            'prompt': prompt,
            'negative': kwargs.get('negative', 'blurry, low quality, still frame'),
            'width': kwargs.get('width', 768),
            'height': kwargs.get('height', 512),
            'frames': kwargs.get('frames', 97),
            'seed': kwargs.get('seed', int(time.time() * 1000) % 1000000),
        }
        
        pid = self.execute(workflow['name'], mods)
        if pid:
            return self.wait_and_download(pid, timeout=900)
        return None


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 ComfyUI 智能执行系统")
    print("=" * 60)
    print()
    
    executor = SmartExecutor()
    
    # 显示发现的工作流
    print("📋 可用工作流:")
    for name, info in executor.discovery.workflows.items():
        wtype = info.get('type', '?')
        nodes = info.get('node_count', '?')
        print(f"  {name} ({wtype}, {nodes}节点)")
    print()
    
    # 示例：生成图片
    print("🎨 示例：生成图片")
    result = executor.quick_image(
        "beautiful girl, cartoon style, funny",
        width=1024,
        height=512
    )
    if result:
        print(f"✅ 图片已保存：{result}")
    print()
    
    # 示例：生成视频
    print("🎬 示例：生成视频")
    result = executor.quick_video(
        "girl dancing, cinematic, high quality",
        width=768,
        height=512,
        frames=97
    )
    if result:
        print(f"✅ 视频已保存：{result}")


if __name__ == "__main__":
    main()
