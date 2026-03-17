#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw Things LTX-2 视频生成控制器
通过 AppleScript 控制 Draw Things 自动生成视频
"""

import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

class DrawThingsController:
    """Draw Things 控制器"""
    
    def __init__(self):
        self.app_name = "Draw Things"
        self.output_dir = Path.home() / "Movies/Draw Things"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def is_running(self):
        """检查 Draw Things 是否运行"""
        result = subprocess.run(
            ['pgrep', '-x', 'Draw Things'],
            capture_output=True
        )
        return result.returncode == 0
    
    def launch(self):
        """启动 Draw Things"""
        subprocess.run(['open', '-a', 'Draw Things'])
        time.sleep(3)  # 等待启动
    
    def run_applescript(self, script):
        """运行 AppleScript"""
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def load_ltx2_model(self):
        """加载 LTX-2 模型"""
        script = f'''tell application "{self.app_name}"
    activate
    try
        set current model to "LTX-Video"
        return "OK"
    on error
        return "ERROR"
    end try
end tell'''
        return self.run_applescript(script)
    
    def generate_video(self, prompt, negative="", width=768, height=512, frames=97):
        """生成视频"""
        script = f'''tell application "{self.app_name}"
    activate
    try
        set current model to "LTX-Video"
        set positive prompt to "{prompt}"
        generate video with {{prompt:positive prompt, width:{width}, height:{height}, frames:{frames}}}
        return "STARTED"
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell'''
        return self.run_applescript(script)
    
    def wait_for_completion(self, timeout=600):
        """等待生成完成"""
        print(f"⏳ 等待视频生成完成... (最多{timeout}秒)")
        start = time.time()
        
        while time.time() - start < timeout:
            # 检查输出目录是否有新文件
            files = list(self.output_dir.glob("*.mp4"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                if time.time() - latest.stat().st_mtime < 10:
                    print(f"✅ 视频已生成：{latest}")
                    return str(latest)
            time.sleep(2)
        
        print("⏰ 超时")
        return None
    
    def quick_generate(self, prompt, title="video"):
        """快速生成"""
        print(f"🎬 生成视频：{prompt[:50]}...")
        
        # 确保 Draw Things 运行
        if not self.is_running():
            print("  启动 Draw Things...")
            self.launch()
        
        # 加载模型
        print("  加载 LTX-2 模型...")
        ok, out, err = self.load_ltx2_model()
        if not ok:
            print(f"  ❌ 模型加载失败：{err}")
            return None
        
        # 生成视频
        print("  开始生成...")
        ok, out, err = self.generate_video(prompt)
        if not ok or "ERROR" in out:
            print(f"  ❌ 生成失败：{out or err}")
            return None
        
        print("  ✅ 任务已提交")
        
        # 等待完成
        filepath = self.wait_for_completion()
        if filepath:
            # 移动到指定目录
            output_dir = Path.home() / f"Downloads/drawthings_videos/{title}"
            output_dir.mkdir(parents=True, exist_ok=True)
            dest = output_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            Path(filepath).rename(dest)
            print(f"  ✅ 已保存：{dest}")
            return str(dest)
        
        return None


def main():
    """主函数"""
    controller = DrawThingsController()
    
    # 示例：生成视频
    result = controller.quick_generate(
        "A beautiful young girl performing elegant ballet dance, graceful movements, pink tutu, spotlight on stage, cinematic lighting, high quality",
        title="ballet_dance"
    )
    
    if result:
        print(f"\n✅ 视频生成成功：{result}")
    else:
        print("\n❌ 视频生成失败")


if __name__ == "__main__":
    main()
