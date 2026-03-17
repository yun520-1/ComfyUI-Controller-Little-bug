#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 智能监控器
实时监控任务队列、生成进度、系统资源
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path

SERVER = "127.0.0.1:8188"
LOG_DIR = Path.home() / ".jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/监控日志"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class ComfyUIMonitor:
    """ComfyUI 智能监控器"""
    
    def __init__(self, server="127.0.0.1:8188"):
        self.server = server
        self.last_prompt_id = None
        self.start_time = None
    
    def get_system_stats(self):
        """获取系统状态"""
        try:
            r = requests.get(f"http://{self.server}/system_stats", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def get_queue(self):
        """获取队列状态"""
        try:
            r = requests.get(f"http://{self.server}/queue", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def get_history(self, limit=10):
        """获取最近生成历史"""
        try:
            r = requests.get(f"http://{self.server}/history", timeout=5)
            if r.status_code == 200:
                history = r.json()
                items = list(history.items())[-limit:]
                return dict(items)
        except:
            pass
        return None
    
    def get_task_progress(self, prompt_id):
        """获取任务进度"""
        try:
            r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if prompt_id in data:
                    return data[prompt_id]
        except:
            pass
        return None
    
    def format_size(self, size_bytes):
        """格式化大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    def status_report(self):
        """生成状态报告"""
        report = []
        report.append("=" * 60)
        report.append("📊 ComfyUI 状态报告")
        report.append(f"⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        
        # 系统状态
        stats = self.get_system_stats()
        if stats:
            device = stats.get('devices', [{}])[0]
            vram_total = device.get('vram_total', 0)
            vram_free = device.get('vram_free', 0)
            vram_used = vram_total - vram_free
            
            report.append("\n💻 系统信息:")
            report.append(f"  ComfyUI 版本：{stats.get('system', {}).get('comfyui_version', '?')}")
            report.append(f"  PyTorch 版本：{stats.get('system', {}).get('pytorch_version', '?')}")
            report.append(f"  设备：{device.get('type', '?')}")
            report.append(f"  VRAM: {self.format_size(vram_used)} / {self.format_size(vram_total)} ({vram_used*100//vram_total if vram_total else 0}%)")
            
            ram = stats.get('system', {})
            report.append(f"  RAM: {self.format_size(ram.get('ram_total', 0) - ram.get('ram_free', 0))} / {self.format_size(ram.get('ram_total', 0))}")
        
        # 队列状态
        queue = self.get_queue()
        if queue:
            running = queue.get('queue_running', [])
            pending = queue.get('queue_pending', [])
            
            report.append(f"\n📋 队列状态:")
            report.append(f"  运行中：{len(running)} 个任务")
            report.append(f"  等待中：{len(pending)} 个任务")
            
            if running:
                for item in running:
                    prompt_id = item[1]
                    outputs = item[2]
                    
                    # 提取关键信息
                    prompt_node = outputs.get('5', {})
                    prompt_text = prompt_node.get('inputs', {}).get('text', '')[:60]
                    
                    latent_node = outputs.get('14', {})
                    latent_inputs = latent_node.get('inputs', {})
                    width = latent_inputs.get('width', '?')
                    height = latent_inputs.get('height', '?')
                    frames = latent_inputs.get('length', '?')
                    
                    report.append(f"\n  🎬 当前任务:")
                    report.append(f"    ID: {prompt_id[:12]}...")
                    report.append(f"    提示词：{prompt_text}...")
                    report.append(f"    规格：{width}x{height}x{frames} 帧")
        
        # 最近历史
        history = self.get_history(5)
        if history:
            report.append(f"\n📜 最近任务:")
            for pid, data in reversed(list(history.items())):
                status = data.get('status', {}).get('status_str', 'unknown')
                status_icon = '✅' if status == 'success' else '❌' if status == 'error' else '⏳'
                
                outputs = data.get('outputs', {})
                has_video = any('videos' in v for v in outputs.values())
                has_image = any('images' in v for v in outputs.values())
                media_type = '🎬视频' if has_video else '🖼️图片' if has_image else '?'
                
                report.append(f"  {status_icon} {pid[:10]}... {media_type}")
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)
    
    def watch_current_task(self, prompt_id, callback=None):
        """监控当前任务"""
        print(f"⏳ 监控任务：{prompt_id}")
        self.start_time = time.time()
        last_report = 0
        
        while True:
            progress = self.get_task_progress(prompt_id)
            if not progress:
                print("❌ 无法获取任务进度")
                return False
            
            status = progress.get('status', {})
            
            if status.get('completed', False):
                print("✅ 任务完成!")
                
                # 计算耗时
                elapsed = time.time() - self.start_time
                print(f"⏱️ 总耗时：{elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
                
                # 获取输出
                outputs = progress.get('outputs', {})
                for nid, out in outputs.items():
                    for vid in out.get('videos', []):
                        fn = vid.get('filename')
                        if fn:
                            print(f"🎬 视频：{fn}")
                    for img in out.get('images', []):
                        fn = img.get('filename')
                        if fn:
                            print(f"🖼️ 图片：{fn}")
                
                return True
            
            if status.get('status_str') == 'error':
                print("❌ 任务失败")
                messages = status.get('messages', [])
                for msg in messages:
                    if len(msg) > 1 and msg[0] == 'execution_error':
                        err = msg[1]
                        print(f"错误：{err.get('exception_message', '')[:200]}")
                return False
            
            # 定期报告
            elapsed = int(time.time() - self.start_time)
            if elapsed - last_report >= 30:
                print(f"   已运行 {elapsed}秒...")
                last_report = elapsed
            
            if callback:
                callback(progress)
            
            time.sleep(2)
        
        return False
    
    def save_log(self, content, filename=None):
        """保存监控日志"""
        if filename is None:
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        filepath = LOG_DIR / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath


def main():
    monitor = ComfyUIMonitor()
    
    # 状态报告
    print(monitor.status_report())
    
    # 检查是否有运行中的任务
    queue = monitor.get_queue()
    if queue and queue.get('queue_running'):
        prompt_id = queue['queue_running'][0][1]
        print(f"\n🔍 监控运行中的任务：{prompt_id}")
        monitor.watch_current_task(prompt_id)
    else:
        print("\n✅ 没有运行中的任务")


if __name__ == "__main__":
    main()
