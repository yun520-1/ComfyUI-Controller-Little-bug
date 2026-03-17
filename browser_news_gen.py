#!/usr/bin/env python3
"""
浏览器自动化 - 新闻图片生成
使用 Playwright 控制 ComfyUI 浏览器界面生成图片
"""

from playwright.sync_api import sync_playwright
import time
import os

def generate_news_images():
    """使用浏览器生成新闻图片"""
    
    print("=" * 60)
    print("📰 浏览器自动化 - 新闻图片生成器")
    print("=" * 60)
    print()
    
    # 两个新闻主题的提示词
    prompts = [
        "professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic",
        "digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K"
    ]
    
    with sync_playwright() as p:
        # 启动浏览器
        print("🌐 启动浏览器...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 访问 ComfyUI
        print("🔗 连接到 ComfyUI...")
        page.goto("http://127.0.0.1:8188", timeout=10000)
        time.sleep(2)
        
        print("✅ 浏览器就绪")
        print()
        
        for i, prompt in enumerate(prompts, 1):
            print(f"[{i}/2] 生成第 {i} 张图片...")
            
            try:
                # 找到提示词输入框
                textareas = page.query_selector_all("textarea")
                if textareas:
                    # 输入提示词
                    textareas[0].fill(prompt)
                    print(f"  ✓ 提示词已输入")
                    time.sleep(1)
                    
                    # 设置尺寸为 1024x512
                    # 找到宽度输入框
                    width_inputs = page.query_selector_all('input[type="number"]')
                    for inp in width_inputs:
                        label = inp.evaluate('el => el.previousElementSibling?.textContent || ""')
                        if 'width' in label.lower() or '宽' in label:
                            inp.fill("1024")
                            print(f"  ✓ 宽度设置为 1024")
                        if 'height' in label.lower() or '高' in label:
                            inp.fill("512")
                            print(f"  ✓ 高度设置为 512")
                    
                    time.sleep(1)
                    
                    # 点击生成按钮
                    buttons = page.query_selector_all("button")
                    for btn in buttons:
                        text = btn.text_content()
                        if 'queue' in text.lower() or '生成' in text or 'prompt' in text.lower():
                            btn.click()
                            print(f"  ✓ 已点击生成按钮")
                            break
                    
                    # 等待生成完成
                    print(f"  ⏳ 等待生成完成...")
                    time.sleep(15)
                    
                    print(f"  ✅ 第 {i} 张图片生成完成")
                else:
                    print(f"  ⚠️ 未找到提示词输入框")
                    
            except Exception as e:
                print(f"  ❌ 错误：{e}")
            
            print()
        
        print("=" * 60)
        print("📊 生成完成")
        print("=" * 60)
        print()
        print("图片位置：~/ComfyUI/output/")
        print()
        
        browser.close()

if __name__ == "__main__":
    try:
        generate_news_images()
    except Exception as e:
        print(f"❌ 错误：{e}")
        print()
        print("请确保:")
        print("1. ComfyUI 正在运行 (http://127.0.0.1:8188)")
        print("2. 已安装 playwright: pip install playwright")
        print("3. 已安装浏览器：playwright install chromium")
