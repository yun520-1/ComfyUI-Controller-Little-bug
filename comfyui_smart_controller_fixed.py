#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能控制器 - 修复版
支持图片生成 (Z-Image-Turbo) 和视频生成 (LTX2)
基于官方工作流文件自动转换
"""

import json
import uuid
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

SERVER = "127.0.0.1:8188"
WORKFLOWS_DIR = Path.home() / "Documents/lmd_data_root/apps/ComfyUI/user/default/workflows"


class ComfyUIController:
    """ComfyUI 智能控制器"""

    def __init__(self, server: str = "127.0.0.1:8188"):
        self.server = server
        self.workflows_dir = WORKFLOWS_DIR

    def check_connection(self) -> bool:
        """检查 ComfyUI 连接"""
        try:
            r = requests.get(f"http://{self.server}/system_stats", timeout=5)
            return r.status_code == 200
        except:
            return False

    def load_workflow(self, workflow_name: str) -> Optional[Dict]:
        """加载工作流 JSON 文件"""
        wf_path = self.workflows_dir / workflow_name
        if not wf_path.exists():
            print(f"❌ 工作流文件不存在：{wf_path}")
            return None

        with open(wf_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def convert_to_api(self, wf_json: Dict, modifications: Dict = None) -> Dict:
        """
        将 ComfyUI 工作流 JSON 转换为 API 格式

        Args:
            wf_json: 工作流 JSON
            modifications: 修改配置，包含:
                - prompt: 正向提示词
                - negative: 负面提示词
                - width: 宽度
                - height: 高度
                - frames: 帧数 (视频)
                - seed: 种子
                - node_overrides: 节点覆盖配置
        """
        nodes = wf_json.get('nodes', [])
        links = wf_json.get('links', [])
        modifications = modifications or {}

        # 构建链接映射
        link_map = {}
        for link in links:
            link_id, src, src_slot, tgt, tgt_slot, _ = link
            link_map.setdefault(tgt, {})[tgt_slot] = [str(src), src_slot]

        api_wf = {}
        for node in nodes:
            nid = str(node['id'])
            ntype = node['type']

            # 跳过 Note 节点
            if ntype == 'Note':
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
                            inputs_dict[name] = [str(link[1]), link[2]]
                            break

            # 处理 widgets
            wi = 0
            for inp in inputs_raw:
                name = inp['name']
                if inp.get('link') is None and wi < len(widgets):
                    inputs_dict[name] = widgets[wi]
                    wi += 1

            api_wf[nid] = {'class_type': ntype, 'inputs': inputs_dict}

        # 应用修改
        self._apply_modifications(api_wf, modifications)

        return api_wf

    def _apply_modifications(self, api_wf: Dict, mods: Dict):
        """应用用户修改"""
        # 提示词修改
        if 'prompt' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'CLIPTextEncode':
                    inputs = node['inputs']
                    text = inputs.get('text', '')
                    # 正向提示词 (通常包含示例文本或较长)
                    if len(text) > 20 or '<Prompt Start>' in str(text):
                        if '<Prompt Start>' in text:
                            inputs['text'] = f"You are an assistant creating high quality images.\n\n<Prompt Start>\n{mods['prompt']}"
                        else:
                            inputs['text'] = mods['prompt']

        # 负面提示词
        if 'negative' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'CLIPTextEncode':
                    inputs = node['inputs']
                    text = inputs.get('text', '')
                    # 负面提示词 (通常较短)
                    if len(text) <= 20 or any(word in text.lower() for word in ['blurry', 'ugly', 'bad', 'low quality']):
                        inputs['text'] = mods['negative']

        # 尺寸修改
        if 'width' in mods or 'height' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] in ['EmptySD3LatentImage', 'EmptyLatentImage', 'EmptyLTXVLatentVideo']:
                    inputs = node['inputs']
                    if 'width' in mods:
                        inputs['width'] = mods['width']
                    if 'height' in mods:
                        inputs['height'] = mods['height']

        # 帧数修改 (视频)
        if 'frames' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'EmptyLTXVLatentVideo':
                    inputs = node['inputs']
                    inputs['length'] = mods['frames']

        # 种子修改
        if 'seed' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] in ['KSampler', 'RandomNoise']:
                    inputs = node['inputs']
                    if 'seed' in inputs:
                        inputs['seed'] = mods['seed']

        # KSampler 参数修复
        if 'sampler_name' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'KSampler':
                    node['inputs']['sampler_name'] = mods['sampler_name']
        if 'scheduler' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'KSampler':
                    node['inputs']['scheduler'] = mods['scheduler']
        if 'steps' in mods:
            for nid, node in api_wf.items():
                if node['class_type'] == 'KSampler':
                    node['inputs']['steps'] = mods['steps']

    def queue_prompt(self, api_wf: Dict, client_id: str = None) -> Optional[str]:
        """提交生成任务"""
        if client_id is None:
            client_id = str(uuid.uuid4())

        try:
            r = requests.post(
                f"http://{self.server}/prompt",
                json={"prompt": api_wf, "client_id": client_id},
                timeout=30
            )

            if r.status_code == 200:
                result = r.json()
                pid = result.get('prompt_id')
                print(f"✅ Prompt ID: {pid}")
                return pid
            else:
                print(f"❌ 状态码：{r.status_code}")
                try:
                    error = r.json()
                    if 'node_errors' in error:
                        for nid, errs in error['node_errors'].items():
                            for err in errs:
                                print(f"   节点{nid}: {err.get('message', '')[:150]}")
                except:
                    pass
                return None
        except Exception as e:
            print(f"❌ 错误：{e}")
            return None

    def wait_for_completion(self, prompt_id: str, timeout: int = 300, poll_interval: int = 2) -> bool:
        """等待生成完成"""
        print(f"⏳ 等待完成... (最多{timeout}秒)")
        start = time.time()

        while time.time() - start < timeout:
            try:
                r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=5)
                if r.status_code == 200:
                    history = r.json()
                    if prompt_id in history:
                        status = history[prompt_id].get('status', {})

                        if status.get('completed', False):
                            print("✅ 完成!")
                            return True

                        if status.get('status_str') == 'error':
                            messages = status.get('messages', [])
                            for msg in messages:
                                if len(msg) > 1 and msg[0] == 'execution_error':
                                    err = msg[1]
                                    print(f"❌ 节点{err.get('node_id')}: {err.get('exception_message', '')[:200]}")
                            return False
            except:
                pass
            time.sleep(poll_interval)

        print("⏰ 超时")
        return False

    def get_history(self, prompt_id: str) -> Optional[Dict]:
        """获取生成历史"""
        try:
            r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=10)
            if r.status_code == 200:
                history = r.json()
                return history.get(prompt_id)
            return None
        except:
            return None

    def download_output(self, prompt_id: str, output_dir: Path) -> List[str]:
        """下载生成的图片或视频"""
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = []

        try:
            history = self.get_history(prompt_id)
            if not history:
                return []

            outputs = history.get('outputs', {})
            for node_id, output in outputs.items():
                # 下载图片
                for img in output.get('images', []):
                    filename = img.get('filename')
                    if filename:
                        filepath = self._download_file(filename, output_dir)
                        if filepath:
                            saved_files.append(filepath)

                # 下载视频
                for vid in output.get('videos', []):
                    filename = vid.get('filename')
                    if filename:
                        filepath = self._download_file(filename, output_dir)
                        if filepath:
                            saved_files.append(filepath)
        except Exception as e:
            print(f"❌ 下载错误：{e}")

        return saved_files

    def _download_file(self, filename: str, output_dir: Path) -> Optional[str]:
        """下载单个文件"""
        try:
            r = requests.get(f"http://{self.server}/view?filename={filename}", timeout=60)
            if r.status_code == 200:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = output_dir / f"{timestamp}_{filename}"
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                print(f"  ✅ 已保存：{filepath}")
                return str(filepath)
            return None
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return None

    def generate_image(self, prompt: str, negative: str = "blurry, low quality, ugly",
                       width: int = 1024, height: int = 512, seed: int = None,
                       workflow: str = "z_image_turbo_gguf.json",
                       output_dir: Path = None) -> Optional[str]:
        """生成图片"""
        if output_dir is None:
            output_dir = Path.home() / "Downloads/comfyui_images"

        print(f"🎨 生成图片：{prompt[:50]}...")

        wf_json = self.load_workflow(workflow)
        if not wf_json:
            return None

        api_wf = self.convert_to_api(wf_json, {
            'prompt': prompt,
            'negative': negative,
            'width': width,
            'height': height,
            'seed': seed or int(time.time() * 1000) % 1000000,
            'sampler_name': 'euler',
            'scheduler': 'simple',
            'steps': 20
        })

        pid = self.queue_prompt(api_wf)
        if not pid:
            return None

        if self.wait_for_completion(pid, timeout=300):
            files = self.download_output(pid, output_dir)
            if files:
                return files[0]

        return None

    def generate_video(self, prompt: str, negative: str = "blurry, low quality, still frame",
                       width: int = 768, height: int = 512, frames: int = 97, seed: int = None,
                       workflow: str = "ltx2_t2v_gguf.json",
                       output_dir: Path = None) -> Optional[str]:
        """生成视频"""
        if output_dir is None:
            output_dir = Path.home() / "Downloads/comfyui_videos"

        print(f"🎬 生成视频：{prompt[:50]}...")

        wf_json = self.load_workflow(workflow)
        if not wf_json:
            return None

        api_wf = self.convert_to_api(wf_json, {
            'prompt': prompt,
            'negative': negative,
            'width': width,
            'height': height,
            'frames': frames,
            'seed': seed or int(time.time() * 1000) % 1000000
        })

        pid = self.queue_prompt(api_wf)
        if not pid:
            return None

        # 视频生成需要更长时间
        if self.wait_for_completion(pid, timeout=900):
            files = self.download_output(pid, output_dir)
            if files:
                return files[0]

        return None


# 快捷函数
def quick_image(prompt: str, title: str = "image", **kwargs):
    """快速生成图片"""
    controller = ComfyUIController()
    if not controller.check_connection():
        print("❌ ComfyUI 未运行")
        return None

    output_dir = Path.home() / "Downloads/comfyui_images" / title
    return controller.generate_image(prompt, output_dir=output_dir, **kwargs)


def quick_video(prompt: str, title: str = "video", **kwargs):
    """快速生成视频"""
    controller = ComfyUIController()
    if not controller.check_connection():
        print("❌ ComfyUI 未运行")
        return None

    output_dir = Path.home() / "Downloads/comfyui_videos" / title
    return controller.generate_video(prompt, output_dir=output_dir, **kwargs)


if __name__ == "__main__":
    # 测试
    controller = ComfyUIController()

    if controller.check_connection():
        print("✅ ComfyUI 连接正常")
        print(f"📁 工作流目录：{controller.workflows_dir}")
    else:
        print("❌ ComfyUI 未运行")
