#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw Things 简化控制器
通过文件监控和手动操作指导来使用
"""

import subprocess
import time
from pathlib import Path
from datetime import datetime

class DrawThingsSimpleController:
    """简化版控制器 - 手动操作指导"""
    
    def __init__(self):
        self.app_name = "Draw Things"
        self.output_dir = Path.home() / "Movies/Draw Things"
    
    def open_app(self):
        """打开 Draw Things"""
        print("🚀 打开 Draw Things...")
        subprocess.run(['open', '-a', 'Draw Things'])
        time.sleep(3)
        print("✅ Draw Things 已打开")
    
    def show_instructions(self):
        """显示操作指南"""
        print("\n" + "="*60)
        print("📋 Draw Things LTX-2 视频生成指南")
        print("="*60)
        print("""
请在 Draw Things 中按以下步骤操作:

1️⃣ 选择模型
   - 点击模型选择器
   - 搜索 "LTX-Video" 或 "LTX-2"
   - 点击下载并加载

2️⃣ 输入提示词
   - 在提示词框输入:
   "A beautiful young girl performing elegant ballet dance, 
    graceful movements, pink tutu, spotlight on stage, 
    cinematic lighting, high quality"

3️⃣ 设置参数
   - 分辨率：768 x 512
   - 步数：31
   - CFG: 4.0
   - 帧数：97
   - FPS: 25

4️⃣ 开始生成
   - 点击"生成"按钮
   - 等待 3-8 分钟

5️⃣ 保存视频
   - 生成完成后右键点击
   - 选择"导出"或"保存"
   - 保存到：~/Downloads/drawthings_videos/

""")
        print("="*60)
    
    def monitor_output(self, timeout=600):
        """监控输出目录"""
        print(f"\n👀 监控输出目录：{self.output_dir}")
        print(f"⏰ 超时时间：{timeout}秒")
        
        if not self.output_dir.exists():
            print(f"⚠️ 目录不存在，等待创建...")
        
        start = time.time()
        while time.time() - start < timeout:
            if self.output_dir.exists():
                files = list(self.output_dir.glob("*.mp4"))
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    age = time.time() - latest.stat().st_mtime
                    if age < 30:  # 30 秒内的文件
                        print(f"\n✅ 发现新视频：{latest}")
                        print(f"   大小：{latest.stat().st_size / 1024 / 1024:.1f} MB")
                        print(f"   时间：{datetime.fromtimestamp(latest.stat().st_mtime)}")
                        return str(latest)
            time.sleep(2)
        
        print("\n⏰ 监控超时")
        return None
    
    def generate(self, prompt_title="ballet"):
        """执行生成流程"""
        # 1. 打开应用
        self.open_app()
        
        # 2. 显示操作指南
        self.show_instructions()
        
        # 3. 监控输出
        result = self.monitor_output()
        
        if result:
            # 4. 复制到指定目录
            output_dir = Path.home() / f"Downloads/drawthings_videos/{prompt_title}"
            output_dir.mkdir(parents=True, exist_ok=True)
            dest = output_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            
            import shutil
            shutil.copy2(result, dest)
            print(f"\n✅ 视频已保存到：{dest}")
            
            # 5. 打开目录
            subprocess.run(['open', str(output_dir)])
            print(f"✅ 已打开目录：{output_dir}")
            
            return str(dest)
        
        return None


def main():
    """主函数"""
    controller = DrawThingsSimpleController()
    
    print("="*60)
    print("🎬 Draw Things LTX-2 视频生成")
    print("="*60)
    
    result = controller.generate("ballet")
    
    if result:
        print(f"\n✅ 生成成功！")
    else:
        print(f"\n⚠️ 未检测到生成的视频")
        print("   请手动检查 Draw Things 输出目录")


if __name__ == "__main__":
    main()
