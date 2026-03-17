#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 任务调度器
功能：
- 定时任务（cron 风格）
- 定量任务（生成 N 张）
- 自动启动/停止 ComfyUI
- 任务队列管理
- 邮件/消息通知
"""

import json
import subprocess
import time
import schedule
import argparse
import signal
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import os

# 路径配置
WORKSPACE = Path("/home/admin/openclaw/workspace/comfyui-controller")
# macOS 路径配置（用户：apple）
COMFYUI_PATH = Path("/Users/apple/Documents/lmd_data_root/apps/ComfyUI")
# 或者使用环境变量覆盖：export COMFYUI_PATH="/your/path"
# COMFYUI_PATH = Path(os.environ.get("COMFYUI_PATH", Path.home() / "ComfyUI"))
SCHEDULER_CONFIG = WORKSPACE / "scheduler_config.json"
TASK_LOG = WORKSPACE / "task_log.json"

# 任务配置模板
TASK_TEMPLATE = {
    "id": "",
    "name": "",
    "type": "single",  # single/batch/scheduled
    "subject": "",
    "style": "realistic",
    "count": 1,
    "width": 512,
    "height": 512,
    "steps": 20,
    "is_video": False,
    "schedule": None,  # cron 表达式或时间列表
    "enabled": True,
    "created_at": "",
    "last_run": None,
    "next_run": None,
    "total_runs": 0
}


class ComfyUIScheduler:
    """ComfyUI 任务调度器"""

    def __init__(self):
        self.config_file = SCHEDULER_CONFIG
        self.log_file = TASK_LOG
        self.tasks = []
        self.running = False
        self.comfyui_process = None
        self.load_config()
        self.load_log()

    def load_config(self):
        """加载任务配置"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.tasks = json.load(f)
        else:
            self.tasks = []
            self.save_config()

    def save_config(self):
        """保存任务配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def load_log(self):
        """加载任务日志"""
        if self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                self.task_log = json.load(f)
        else:
            self.task_log = {"history": []}

    def save_log(self):
        """保存任务日志"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.task_log, f, ensure_ascii=False, indent=2)

    def start_comfyui(self, wait=True):
        """启动 ComfyUI"""
        print(f"\n🚀 启动 ComfyUI...")

        if not COMFYUI_PATH.exists():
            print(f"⚠️  ComfyUI 路径不存在：{COMFYUI_PATH}")
            print(f"   请修改脚本中的 COMFYUI_PATH 变量")
            return False

        try:
            cmd = [
                "python", "main.py",
                "--listen", "0.0.0.0",
                "--port", "8188"
            ]

            self.comfyui_process = subprocess.Popen(
                cmd,
                cwd=str(COMFYUI_PATH),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            print(f"✅ ComfyUI 已启动 (PID: {self.comfyui_process.pid})")

            if wait:
                print(f"   等待 ComfyUI 就绪...")
                time.sleep(5)  # 等待启动

            return True

        except Exception as e:
            print(f"❌ 启动失败：{e}")
            return False

    def stop_comfyui(self):
        """停止 ComfyUI"""
        if self.comfyui_process:
            print(f"\n🛑 停止 ComfyUI...")
            self.comfyui_process.terminate()
            self.comfyui_process.wait()
            print(f"✅ ComfyUI 已停止")
            self.comfyui_process = None

    def check_comfyui_running(self) -> bool:
        """检查 ComfyUI 是否运行"""
        import requests
        try:
            resp = requests.get("http://127.0.0.1:8188/system_stats", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def add_task(self, subject: str, style: str = "realistic",
                count: int = 1, is_video: bool = False,
                width: int = 512, height: int = 512,
                steps: int = 20, schedule_time: str = None) -> Dict:
        """添加任务"""
        task = TASK_TEMPLATE.copy()
        task["id"] = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.tasks)}"
        task["name"] = f"{subject[:20]}_{task['id']}"
        task["subject"] = subject
        task["style"] = style
        task["count"] = count
        task["width"] = width
        task["height"] = height
        task["steps"] = steps
        task["is_video"] = is_video
        task["created_at"] = datetime.now().isoformat()

        if schedule_time:
            task["type"] = "scheduled"
            task["schedule"] = schedule_time
            task["next_run"] = schedule_time

        self.tasks.append(task)
        self.save_config()

        print(f"✅ 任务已添加：{task['name']}")
        return task

    def add_batch_task(self, subjects_file: str, style: str = "realistic",
                      is_video: bool = False, schedule_time: str = None):
        """添加批量任务"""
        with open(subjects_file, 'r', encoding='utf-8') as f:
            subjects = [line.strip() for line in f if line.strip()]

        print(f"\n📦 添加批量任务：{len(subjects)} 个主题")

        for subject in subjects:
            self.add_task(
                subject=subject,
                style=style,
                count=1,
                is_video=is_video,
                schedule_time=schedule_time
            )

    def run_task(self, task: Dict) -> bool:
        """执行单个任务"""
        print(f"\n{'='*60}")
        print(f"🎨 执行任务：{task['name']}")
        print(f"{'='*60}")
        print(f"   主题：{task['subject']}")
        print(f"   风格：{task['style']}")
        print(f"   数量：{task['count']}")
        print(f"   类型：{'视频' if task['is_video'] else '图片'}")
        print(f"   尺寸：{task['width']}x{task['height']}")
        print(f"{'='*60}")

        # 检查 ComfyUI
        if not self.check_comfyui_running():
            print(f"⚠️  ComfyUI 未运行，尝试启动...")
            if not self.start_comfyui():
                print(f"❌ 无法启动 ComfyUI，任务跳过")
                return False

        # 构建命令
        cmd = [
            "python3", "comfyui_smart_controller.py",
            "--subject", task["subject"],
            "--style", task["style"],
            "--width", str(task["width"]),
            "--height", str(task["height"]),
            "--steps", str(task["steps"])
        ]

        if task["is_video"]:
            cmd.append("--video")

        # 执行任务
        try:
            for i in range(task["count"]):
                print(f"\n[{i+1}/{task['count']}] 生成中...")
                result = subprocess.run(
                    cmd,
                    cwd=str(WORKSPACE),
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 分钟超时
                )

                if result.returncode == 0:
                    print(f"✅ 第 {i+1} 张完成")
                else:
                    print(f"❌ 第 {i+1} 张失败：{result.stderr}")

                # 任务间等待
                if i < task["count"] - 1:
                    time.sleep(5)

            # 更新任务状态
            task["last_run"] = datetime.now().isoformat()
            task["total_runs"] += 1

            # 记录日志
            log_entry = {
                "task_id": task["id"],
                "task_name": task["name"],
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "count": task["count"]
            }
            self.task_log["history"].append(log_entry)
            self.save_log()

            print(f"\n✅ 任务完成：{task['name']}")
            return True

        except subprocess.TimeoutExpired:
            print(f"❌ 任务超时")
            return False
        except Exception as e:
            print(f"❌ 任务失败：{e}")
            return False

    def run_all_tasks(self):
        """执行所有启用的任务"""
        print(f"\n🚀 开始执行所有任务")

        for task in self.tasks:
            if task["enabled"]:
                self.run_task(task)

    def run_scheduled_tasks(self):
        """执行到期的定时任务"""
        now = datetime.now()

        for task in self.tasks:
            if task["enabled"] and task["type"] == "scheduled":
                next_run = task.get("next_run")
                if next_run:
                    next_run_dt = datetime.fromisoformat(next_run)
                    if now >= next_run_dt:
                        self.run_task(task)

                        # 更新下次运行时间（如果是重复任务）
                        # 这里可以扩展 cron 表达式解析
                        task["next_run"] = None  # 一次性任务
                        self.save_config()

    def list_tasks(self):
        """列出所有任务"""
        print(f"\n📋 任务列表")
        print(f"{'='*80}")

        if not self.tasks:
            print(f"   暂无任务")
            return

        for i, task in enumerate(self.tasks, 1):
            status = "✅" if task["enabled"] else "❌"
            task_type = "定时" if task["type"] == "scheduled" else "普通"
            video_tag = "🎬" if task["is_video"] else "🖼️"

            print(f"{i}. {status} [{task_type}] {video_tag} {task['name']}")
            print(f"   主题：{task['subject'][:40]}...")
            print(f"   风格：{task['style']} | 数量：{task['count']}")
            print(f"   尺寸：{task['width']}x{task['height']} | 步数：{task['steps']}")
            print(f"   创建：{task['created_at']}")
            if task.get("next_run"):
                print(f"   下次运行：{task['next_run']}")
            print()

    def remove_task(self, task_id: str):
        """删除任务"""
        for i, task in enumerate(self.tasks):
            if task["id"] == task_id:
                removed = self.tasks.pop(i)
                self.save_config()
                print(f"✅ 任务已删除：{removed['name']}")
                return
        print(f"❌ 未找到任务：{task_id}")

    def enable_task(self, task_id: str, enabled: bool = True):
        """启用/禁用任务"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["enabled"] = enabled
                self.save_config()
                status = "启用" if enabled else "禁用"
                print(f"✅ 任务已{status}：{task['name']}")
                return
        print(f"❌ 未找到任务：{task_id}")

    def show_log(self, limit: int = 10):
        """显示任务日志"""
        print(f"\n📊 任务日志（最近 {limit} 条）")
        print(f"{'='*80}")

        history = self.task_log.get("history", [])[-limit:]

        for entry in reversed(history):
            status = "✅" if entry["status"] == "success" else "❌"
            print(f"{status} {entry['timestamp'][:19]} | {entry['task_name']} | 数量：{entry.get('count', 1)}")

    def start_scheduler(self, interval: int = 60):
        """启动调度器（后台运行）"""
        print(f"\n⏰ 启动调度器...")
        print(f"   检查间隔：{interval} 秒")
        print(f"   按 Ctrl+C 停止")

        self.running = True

        def signal_handler(sig, frame):
            print(f"\n\n🛑 收到停止信号")
            self.running = False
            self.stop_comfyui()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        while self.running:
            self.run_scheduled_tasks()
            time.sleep(interval)

    def quick_generate(self, subject: str, count: int = 1, style: str = "realistic",
                      is_video: bool = False, auto_start_comfyui: bool = True):
        """快速生成（一键执行）"""
        print(f"\n🎨 快速生成模式")
        print(f"   主题：{subject}")
        print(f"   数量：{count}")
        print(f"   风格：{style}")
        print(f"   类型：{'视频' if is_video else '图片'}")

        # 检查/启动 ComfyUI
        if auto_start_comfyui:
            if not self.check_comfyui_running():
                if not self.start_comfyui():
                    print(f"❌ 无法启动 ComfyUI")
                    return

        # 创建临时任务
        task = TASK_TEMPLATE.copy()
        task["id"] = f"quick_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task["subject"] = subject
        task["style"] = style
        task["count"] = count
        task["is_video"] = is_video

        # 执行
        self.run_task(task)


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 任务调度器")

    # 操作模式
    parser.add_argument("--generate", "-g", type=str, help="快速生成（主题）")
    parser.add_argument("--add", type=str, help="添加任务（主题）")
    parser.add_argument("--batch", type=str, help="添加批量任务（主题文件）")
    parser.add_argument("--list", action="store_true", help="列出任务")
    parser.add_argument("--run", type=str, help="执行指定任务（task_id）")
    parser.add_argument("--run-all", action="store_true", help="执行所有任务")
    parser.add_argument("--remove", type=str, help="删除任务（task_id）")
    parser.add_argument("--enable", type=str, help="启用任务（task_id）")
    parser.add_argument("--disable", type=str, help="禁用任务（task_id）")
    parser.add_argument("--log", action="store_true", help="显示任务日志")
    parser.add_argument("--start", action="store_true", help="启动调度器")

    # 任务参数
    parser.add_argument("--style", type=str, default="realistic", help="风格")
    parser.add_argument("--count", "-n", type=int, default=1, help="生成数量")
    parser.add_argument("--video", action="store_true", help="生成视频")
    parser.add_argument("--width", type=int, default=512, help="宽度")
    parser.add_argument("--height", type=int, default=512, help="高度")
    parser.add_argument("--steps", type=int, default=20, help="步数")
    parser.add_argument("--schedule", type=str, help="定时时间（ISO 格式）")

    # 系统控制
    parser.add_argument("--start-comfyui", action="store_true", help="启动 ComfyUI")
    parser.add_argument("--stop-comfyui", action="store_true", help="停止 ComfyUI")
    parser.add_argument("--interval", type=int, default=60, help="调度器检查间隔（秒）")

    args = parser.parse_args()

    scheduler = ComfyUIScheduler()

    # 系统控制
    if args.start_comfyui:
        scheduler.start_comfyui()
        return 0

    if args.stop_comfyui:
        scheduler.stop_comfyui()
        return 0

    # 快速生成
    if args.generate:
        scheduler.quick_generate(
            subject=args.generate,
            count=args.count,
            style=args.style,
            is_video=args.video
        )
        return 0

    # 添加任务
    if args.add:
        scheduler.add_task(
            subject=args.add,
            style=args.style,
            count=args.count,
            is_video=args.video,
            width=args.width,
            height=args.height,
            steps=args.steps,
            schedule_time=args.schedule
        )
        return 0

    # 批量任务
    if args.batch:
        scheduler.add_batch_task(
            subjects_file=args.batch,
            style=args.style,
            is_video=args.video,
            schedule_time=args.schedule
        )
        return 0

    # 列出任务
    if args.list:
        scheduler.list_tasks()
        return 0

    # 执行任务
    if args.run:
        for task in scheduler.tasks:
            if task["id"] == args.run:
                scheduler.run_task(task)
                return 0
        print(f"❌ 未找到任务：{args.run}")
        return 1

    # 执行所有
    if args.run_all:
        scheduler.run_all_tasks()
        return 0

    # 删除任务
    if args.remove:
        scheduler.remove_task(args.remove)
        return 0

    # 启用/禁用
    if args.enable:
        scheduler.enable_task(args.enable, True)
        return 0

    if args.disable:
        scheduler.enable_task(args.disable, False)
        return 0

    # 显示日志
    if args.log:
        scheduler.show_log()
        return 0

    # 启动调度器
    if args.start:
        scheduler.start_scheduler(args.interval)
        return 0

    # 默认显示帮助
    parser.print_help()
    print(f"\n{'='*60}")
    print(f"💡 快速示例:")
    print(f"")
    print(f"  # 快速生成 1 张图片")
    print(f"  python3 {__file__} --generate '一个美丽的女孩'")
    print(f"")
    print(f"  # 快速生成 5 张图片")
    print(f"  python3 {__file__} --generate '赛博朋克城市' --count 5")
    print(f"")
    print(f"  # 添加定时任务")
    print(f"  python3 {__file__} --add '风景' --schedule '2026-03-15T08:00:00'")
    print(f"")
    print(f"  # 添加批量任务")
    print(f"  python3 {__file__} --batch sample_subjects.txt --style cyberpunk")
    print(f"")
    print(f"  # 列出所有任务")
    print(f"  python3 {__file__} --list")
    print(f"")
    print(f"  # 启动调度器（后台运行）")
    print(f"  python3 {__file__} --start")
    print(f"")
    print(f"  # 查看任务日志")
    print(f"  python3 {__file__} --log")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    exit(main())
