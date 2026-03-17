#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw Things UI 自动化控制器
使用 pyautogui 模拟鼠标键盘操作
"""

import subprocess
import time
import pyautogui
from pathlib import Path
from datetime import datetime

# macOS 设置
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


class DrawThingsUIController:
    """Draw Things UI 控制器"""
    
    def __init__(self):
        self.app_name = "Draw Things"
        self.output_dir = Path.home() / "Movies/Draw Things"
    
    def is_running(self):
        """检查是否运行"""
        result = subprocess.run(['pgrep', '-x', 'Draw Things'], capture_output=True)
        return result.returncode == 0
    
    def launch(self):
        """启动应用"""
        print("🚀 启动 Draw Things...")
        subprocess.run(['open', '-a', 'Draw Things'])
        time.sleep(3)
        print("✅ 已启动")
    
    def bring_to_front(self):
        """前置窗口"""
        subprocess.run(['osascript', '-e', f'tell application "{self.app_name}" to activate'])
        time.sleep(1)
    
    def press_key(self, key, times=1):
        """按键"""
        for _ in range(times):
            pyautogui.press(key)
            time.sleep(0.3)
    
    def press_keys(self, keys):
        """组合键"""
        pyautogui.hotkey(*keys)
        time.sleep(0.5)
    
    def click_at(self, x, y, button='left'):
        """点击坐标"""
        pyautogui.click(x, y, button=button)
        time.sleep(0.5)
    
    def type_text(self, text, interval=0.05):
        """输入文本"""
        pyautogui.write(text, interval=interval)
        time.sleep(0.5)
    
    def find_and_click(self, image_path, confidence=0.8):
        """查找并点击图片"""
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                center = pyautogui.center(location)
                pyautogui.click(center)
                print(f"✅ 点击：{image_path}")
                return True
            else:
                print(f"❌ 未找到：{image_path}")
                return False
        except Exception as e:
            print(f"❌ 错误：{e}")
            return False
    
    def generate_video(self, prompt, width=768, height=512, frames=97):
        """生成视频 (通过 UI 操作)"""
        print("\n🎬 开始生成视频...")
        
        # 1. 前置窗口
        self.bring_to_front()
        time.sleep(1)
        
        # 2. 新建项目 (Cmd+N)
        print("  新建项目...")
        self.press_keys(['command', 'n'])
        time.sleep(2)
        
        # 3. 选择模型 (Tab 导航)
        print("  选择 LTX-Video 模型...")
        self.press_key('tab', times=3)
        time.sleep(1)
        self.type_text("LTX-Video")
        self.press_key('enter')
        time.sleep(3)
        
        # 4. 输入提示词
        print("  输入提示词...")
        self.press_key('tab', times=2)
        time.sleep(1)
        self.type_text(prompt)
        time.sleep(1)
        
        # 5. 设置参数
        print("  设置参数...")
        # 宽度
        self.press_key('tab', times=3)
        self.type_text(str(width))
        # 高度
        self.press_key('tab')
        self.type_text(str(height))
        # 帧数
        self.press_key('tab', times=2)
        self.type_text(str(frames))
        
        # 6. 开始生成 (Cmd+G 或点击生成按钮)
        print("  开始生成...")
        time.sleep(1)
        self.press_keys(['command', 'g'])
        
        print("  ✅ 任务已提交")
        return True
    
    def wait_and_save(self, timeout=600):
        """等待完成并保存"""
        print(f"\n⏳ 等待生成完成... (最多{timeout}秒)")
        start = time.time()
        
        while time.time() - start < timeout:
            if self.output_dir.exists():
                files = list(self.output_dir.glob("*.mp4"))
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    age = time.time() - latest.stat().st_mtime
                    if age < 30:
                        print(f"\n✅ 视频已生成：{latest}")
                        
                        # 保存到指定目录
                        output_dir = Path.home() / "Downloads/drawthings_videos"
                        output_dir.mkdir(parents=True, exist_ok=True)
                        dest = output_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        
                        import shutil
                        shutil.copy2(latest, dest)
                        print(f"✅ 已保存：{dest}")
                        
                        # 打开目录
                        subprocess.run(['open', str(output_dir)])
                        return str(dest)
            time.sleep(2)
        
        print("⏰ 超时")
        return None


def main():
    """主函数"""
    print("="*60)
    print("🎨 Draw Things UI 自动化控制器")
    print("="*60)
    
    # 检查权限
    print("\n⚠️  需要辅助功能权限:")
    print("  系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能")
    print("  添加 Terminal 或 Python")
    print()
    
    controller = DrawThingsUIController()
    
    # 确保应用运行
    if not controller.is_running():
        controller.launch()
    else:
        print("✅ Draw Things 已在运行")
    
    # 等待用户确认权限
    input("\n按回车键继续 (请确保已授予辅助功能权限)...")
    
    # 生成视频
    prompt = "A beautiful young girl performing elegant ballet dance, graceful movements, pink tutu, spotlight on stage, cinematic lighting, high quality"
    
    if controller.generate_video(prompt):
        result = controller.wait_and_save()
        if result:
            print(f"\n✅ 生成成功！")
        else:
            print(f"\n⚠️  未检测到生成的视频")


if __name__ == "__main__":
    main()
