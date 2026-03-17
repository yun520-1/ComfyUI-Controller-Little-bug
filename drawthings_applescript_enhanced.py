#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw Things 增强版 AppleScript 控制器
尝试多种 AppleScript 方法
"""

import subprocess
import time
from pathlib import Path
from datetime import datetime


def run_applescript(script):
    """运行 AppleScript"""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)


def check_support():
    """检查 Draw Things AppleScript 支持"""
    print("🔍 检查 Draw Things AppleScript 支持...")
    
    # 测试 1: 基本连接
    ok, out, err = run_applescript('tell application "Draw Things" to name')
    print(f"  基本连接：{'✅' if ok else '❌'} {out or err}")
    
    # 测试 2: 获取属性
    ok, out, err = run_applescript('tell application "Draw Things" to properties')
    if ok:
        print(f"  属性列表：✅")
        print(f"    {out[:200]}")
    
    # 测试 3: 激活
    ok, out, err = run_applescript('tell application "Draw Things" to activate')
    print(f"  激活应用：{'✅' if ok else '❌'}")
    
    # 测试 4: System Events UI 控制
    ok, out, err = run_applescript('''
        tell application "System Events"
            if exists process "Draw Things" then
                return "EXISTS"
            else
                return "NOT_EXISTS"
            end if
        end tell
    ''')
    print(f"  UI 元素访问：{'✅' if ok and 'EXISTS' in out else '❌'} {err}")


def ui_control_menu():
    """通过 System Events 控制菜单"""
    script = '''
    tell application "Draw Things"
        activate
    end tell
    
    delay 1
    
    tell application "System Events"
        tell process "Draw Things"
            -- 尝试点击文件菜单
            if exists menu bar item 1 of menu bar 1 then
                click menu bar item 1 of menu bar 1
                return "MENU_CLICKED"
            else
                return "NO_MENU"
            end if
        end tell
    end tell
    '''
    return run_applescript(script)


def generate_via_ui(prompt):
    """通过 UI 生成"""
    # 1. 激活应用
    run_applescript('tell application "Draw Things" to activate')
    time.sleep(2)
    
    # 2. 使用键盘导航
    import pyautogui
    
    # Tab 切换到模型选择
    print("  选择模型...")
    for _ in range(5):
        pyautogui.press('tab')
        time.sleep(0.3)
    pyautogui.write("LTX")
    time.sleep(1)
    pyautogui.press('enter')
    time.sleep(2)
    
    # Tab 切换到提示词
    print("  输入提示词...")
    for _ in range(3):
        pyautogui.press('tab')
        time.sleep(0.3)
    pyautogui.write(prompt, interval=0.05)
    time.sleep(1)
    
    # Cmd+G 生成
    print("  开始生成...")
    pyautogui.hotkey('command', 'g')
    
    return True


def main():
    """主函数"""
    print("="*60)
    print("🎨 Draw Things AppleScript 增强控制器")
    print("="*60)
    
    # 检查支持
    check_support()
    
    print("\n" + "="*60)
    print("📋 控制方法:")
    print("="*60)
    print("""
方法 1: AppleScript 直接控制 (如果支持)
  tell application "Draw Things"
    activate
    set current model to "LTX-Video"
  end tell

方法 2: System Events UI 控制 (需要辅助功能权限)
  - 模拟菜单点击
  - 模拟键盘输入
  - 模拟鼠标操作

方法 3: pyautogui 完全控制
  - 完全模拟用户操作
  - 需要安装：pip3 install pyautogui
  - 需要辅助功能权限

方法 4: 文件监控 + 手动操作
  - 手动在 Draw Things 中操作
  - 自动监控输出
  - 自动保存结果
""")
    
    print("\n" + "="*60)
    print("⚠️  权限要求:")
    print("="*60)
    print("""
1. 辅助功能权限:
   系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能
   添加 Terminal 或 Python

2. 自动化权限:
   系统偏好设置 → 安全性与隐私 → 隐私 → 自动化
   允许 System Events 控制 Draw Things
""")


if __name__ == "__main__":
    main()
