#!/usr/bin/env python3
# -*- utf-8 -*-
"""
ComfyUI 自动工作流执行器
功能：
- 上传工作流后自动执行
- 批量处理多个工作流
- 自动替换提示词
- 自动下载和整理结果
"""

import json
import time
import argparse
import websocket
import requests
import urllib.request
import urllib.parse
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import uuid

# 导入工作流管理器
from workflow_manager import WorkflowManager

# ============ 配置 ============
COMFYUI_SERVER = "127.0.0.1:8188"
OUTPUT_DIR = Path.home() / "Downloads" / "comfyui_output"
ORGANIZED_DIR = Path.home() / "Downloads" / "comfyui_organized"


class AutoWorkflowRunner:
    """自动工作流执行器"""

    def __init__(self, server=COMFYUI_SERVER):
        self.server = server
        self.base_url = f"http://{server}"
        self.ws_url = f"ws://{server}/ws"
        self.client_id = str(uuid.uuid4())
        self.workflow_manager = WorkflowManager()

    def check_connection(self) -> bool:
        """检查 ComfyUI 连接"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                print(f"✅ 已连接到 ComfyUI ({self.server})")
                return True
        except Exception as e:
            print(f"❌ 无法连接 ComfyUI: {e}")
        return False

    def upload_and_run(self, workflow_path: str, prompt: str = None,
                      negative: str = None, category: str = "custom",
                      name: str = None, **kwargs) -> Dict:
        """
        上传工作流并执行

        Args:
            workflow_path: 工作流文件路径
            prompt: 正向提示词（可选，自动替换）
            negative: 负面提示词（可选）
            category: 工作流分类
            name: 工作流名称
            **kwargs: 其他参数（steps, cfg, width, height 等）

        Returns:
            执行结果
        """
        print(f"\n🚀 上传并执行工作流...")
        print(f"   文件：{workflow_path}")
        print(f"   分类：{category}")

        # 1. 上传工作流
        upload_result = self.workflow_manager.upload_workflow(
            workflow_path,
            name=name,
            category=category
        )

        if not upload_result.get("success"):
            return {"success": False, "error": upload_result.get("error")}

        workflow_info = upload_result["workflow"]
        workflow_id = workflow_info["id"]

        # 2. 加载工作流
        workflow = self.workflow_manager.load_workflow(workflow_id)
        if not workflow:
            return {"success": False, "error": "加载工作流失败"}

        # 3. 替换提示词（如果提供）
        if prompt:
            print(f"   替换提示词：{prompt[:50]}...")
            workflow = self.workflow_manager.replace_prompts(
                workflow,
                prompt,
                negative if negative else ""
            )

        # 4. 更新参数（如果提供）
        if kwargs:
            print(f"   更新参数：{kwargs}")
            workflow = self.workflow_manager.update_parameters(workflow, **kwargs)

        # 5. 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交任务失败"}

        # 6. 监控进度
        success = self.monitor_progress(prompt_id)

        # 7. 下载结果
        if success:
            downloaded = self.download_and_organize(prompt_id, category)
            return {
                "success": True,
                "prompt_id": prompt_id,
                "workflow_id": workflow_id,
                "files": downloaded
            }
        else:
            return {"success": False, "error": "生成失败"}

    def run_workflow(self, workflow_id: str, prompt: str = None,
                    negative: str = None, **kwargs) -> Dict:
        """
        执行已上传的工作流

        Args:
            workflow_id: 工作流 ID
            prompt: 正向提示词（可选）
            negative: 负面提示词（可选）
            **kwargs: 其他参数

        Returns:
            执行结果
        """
        print(f"\n🚀 执行工作流...")
        print(f"   ID: {workflow_id}")

        # 1. 加载工作流
        workflow = self.workflow_manager.load_workflow(workflow_id)
        if not workflow:
            return {"success": False, "error": "工作流不存在"}

        # 2. 替换提示词
        if prompt:
            print(f"   提示词：{prompt[:50]}...")
            workflow = self.workflow_manager.replace_prompts(
                workflow,
                prompt,
                negative if negative else ""
            )

        # 3. 更新参数
        if kwargs:
            print(f"   参数：{kwargs}")
            workflow = self.workflow_manager.update_parameters(workflow, **kwargs)

        # 4. 提交任务
        prompt_id = self.queue_prompt(workflow)
        if not prompt_id:
            return {"success": False, "error": "提交失败"}

        # 5. 监控进度
        success = self.monitor_progress(prompt_id)

        # 6. 下载结果
        if success:
            workflow_info = self.workflow_manager.get_workflow(workflow_id)
            category = workflow_info.get("category", "custom")
            downloaded = self.download_and_organize(prompt_id, category)
            return {
                "success": True,
                "prompt_id": prompt_id,
                "workflow_id": workflow_id,
                "files": downloaded
            }
        else:
            return {"success": False, "error": "生成失败"}

    def batch_run(self, workflow_ids: List[str], prompts: List[str] = None,
                  **kwargs) -> List[Dict]:
        """
        批量执行工作流

        Args:
            workflow_ids: 工作流 ID 列表
            prompts: 提示词列表（可选，每个工作流一个）
            **kwargs: 其他参数

        Returns:
            执行结果列表
        """
        results = []

        for i, workflow_id in enumerate(workflow_ids):
            prompt = prompts[i] if prompts and i < len(prompts) else None

            print(f"\n{'='*60}")
            print(f"任务 {i+1}/{len(workflow_ids)}")
            print(f"{'='*60}")

            result = self.run_workflow(workflow_id, prompt=prompt, **kwargs)
            results.append(result)

            # 任务间延迟
            if i < len(workflow_ids) - 1:
                print(f"\n⏳ 等待 2 秒...")
                time.sleep(2)

        return results

    def queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交任务到 ComfyUI"""
        try:
            resp = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get('prompt_id')
                print(f"✅ 任务已提交 (ID: {prompt_id})")
                return prompt_id
        except Exception as e:
            print(f"❌ 提交失败：{e}")
        return None

    def monitor_progress(self, prompt_id: str, timeout: int = 300) -> bool:
        """监控任务进度"""
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(f"{self.ws_url}?clientId={self.client_id}", timeout=10)

            print(f"\n⏳ 生成中...")
            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    print("⏰ 超时!")
                    break

                try:
                    msg = json.loads(self.ws.recv())
                    msg_type = msg.get('type')
                    data = msg.get('data', {})

                    if msg_type == 'progress':
                        step = data.get('value', 0)
                        total = data.get('max', 100)
                        percent = int(step / total * 100)
                        print(f"   进度：{percent}% ({step}/{total})")

                    elif msg_type == 'executing':
                        if data.get('node') is None:
                            print(f"✅ 完成!")
                            return True
                except:
                    continue

        except Exception as e:
            print(f"❌ 监控失败：{e}")
        finally:
            if self.ws:
                self.ws.close()
        return False

    def download_and_organize(self, prompt_id: str, category: str = "custom",
                             subject: str = "") -> List[str]:
        """下载并整理生成的文件"""
        history_url = f"{self.base_url}/history/{prompt_id}"
        try:
            resp = requests.get(history_url, timeout=5)
            history = resp.json()

            if prompt_id not in history:
                print("❌ 未找到历史记录")
                return []

            outputs = history[prompt_id].get('outputs', {})
            downloaded = []

            # 创建分类目录
            category_dir = ORGANIZED_DIR / category / datetime.now().strftime("%Y-%m-%d")
            category_dir.mkdir(parents=True, exist_ok=True)

            # 同时保存到原始目录
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            for node_id, output in outputs.items():
                if 'images' in output:
                    for image in output['images']:
                        if image.get('type') == 'output':
                            # 构建图片 URL
                            params = {
                                'filename': image['filename'],
                                'subfolder': image.get('subfolder', ''),
                                'type': image['type']
                            }
                            url = f"{self.base_url}/view?{urllib.parse.urlencode(params)}"

                            # 生成文件名
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{timestamp}_{subject if subject else 'output'}_{image['filename']}"

                            # 保存到分类目录
                            dest_path = category_dir / filename
                            urllib.request.urlretrieve(url, dest_path)
                            downloaded.append(str(dest_path))

                            # 保存到原始目录
                            orig_path = OUTPUT_DIR / filename
                            urllib.request.urlretrieve(url, orig_path)

                            # 保存元数据
                            meta = {
                                "prompt_id": prompt_id,
                                "category": category,
                                "timestamp": datetime.now().isoformat(),
                                "filename": filename
                            }
                            meta_path = category_dir / f"{filename.replace('.png', '.json')}"
                            with open(meta_path, 'w', encoding='utf-8') as f:
                                json.dump(meta, f, ensure_ascii=False, indent=2)

            if downloaded:
                print(f"\n📁 已下载 {len(downloaded)} 个文件:")
                for f in downloaded:
                    print(f"   {f}")
                print(f"\n📂 分类目录：{category_dir}")

            return downloaded

        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return []

    def list_workflows(self):
        """列出所有工作流"""
        workflows = self.workflow_manager.list_workflows()
        print(f"\n📋 工作流列表 (共 {len(workflows)} 个):\n")
        for w in workflows:
            print(f"  ID: {w['id']}")
            print(f"  名称：{w['name']}")
            print(f"  分类：{w['category']}")
            print(f"  描述：{w['description']}")
            print()


# 命令行工具
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ComfyUI 自动工作流执行器")
    parser.add_argument("action", choices=["upload_run", "run", "list", "batch"],
                       help="操作类型")
    parser.add_argument("--file", "-f", help="工作流文件路径")
    parser.add_argument("--id", help="工作流 ID")
    parser.add_argument("--ids", help="工作流 ID 列表（逗号分隔）")
    parser.add_argument("--prompt", "-p", help="正向提示词")
    parser.add_argument("--negative", "-n", help="负面提示词")
    parser.add_argument("--category", "-c", default="custom",
                       choices=["txt2img", "img2img", "video", "upscale", "controlnet", "face", "custom"],
                       help="工作流分类")
    parser.add_argument("--name", help="工作流名称")
    parser.add_argument("--steps", type=int, default=20, help="采样步数")
    parser.add_argument("--cfg", type=float, default=7, help="CFG 值")
    parser.add_argument("--width", type=int, default=512, help="宽度")
    parser.add_argument("--height", type=int, default=512, help="高度")
    parser.add_argument("--batch-size", type=int, default=1, help="批量大小")
    parser.add_argument("--seed", type=int, help="随机种子")

    args = parser.parse_args()

    runner = AutoWorkflowRunner()

    if not runner.check_connection():
        exit(1)

    if args.action == "upload_run":
        if not args.file:
            print("❌ 请指定工作流文件 (--file)")
            exit(1)

        result = runner.upload_and_run(
            args.file,
            prompt=args.prompt,
            negative=args.negative,
            category=args.category,
            name=args.name,
            steps=args.steps,
            cfg=args.cfg,
            width=args.width,
            height=args.height,
            batch_size=args.batch_size,
            seed=args.seed
        )
        print(f"\n结果：{json.dumps(result, ensure_ascii=False, indent=2)}")

    elif args.action == "run":
        if not args.id:
            print("❌ 请指定工作流 ID (--id)")
            exit(1)

        result = runner.run_workflow(
            args.id,
            prompt=args.prompt,
            negative=args.negative,
            steps=args.steps,
            cfg=args.cfg,
            width=args.width,
            height=args.height,
            batch_size=args.batch_size,
            seed=args.seed
        )
        print(f"\n结果：{json.dumps(result, ensure_ascii=False, indent=2)}")

    elif args.action == "list":
        runner.list_workflows()

    elif args.action == "batch":
        if not args.ids:
            print("❌ 请指定工作流 ID 列表 (--ids)")
            exit(1)

        workflow_ids = [id.strip() for id in args.ids.split(',')]
        prompts = [p.strip() for p in args.prompt.split('|')] if args.prompt and '|' in args.prompt else None

        results = runner.batch_run(
            workflow_ids,
            prompts=prompts,
            steps=args.steps,
            cfg=args.cfg,
            width=args.width,
            height=args.height
        )
        print(f"\n批量执行完成:")
        for i, r in enumerate(results):
            print(f"  任务 {i+1}: {'✅' if r['success'] else '❌'}")
