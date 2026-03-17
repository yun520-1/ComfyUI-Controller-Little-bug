#!/bin/bash
# ComfyUI 网页控制器 - 一键启动

echo "============================================================"
echo "🎨 ComfyUI 网页版智能控制器"
echo "============================================================"
echo ""

# 检查 ComfyUI
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "❌ ComfyUI 未运行"
    echo ""
    echo "💡 启动 ComfyUI:"
    echo "   cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI"
    echo "   python main.py --listen 0.0.0.0 --port 8188"
    echo ""
    exit 1
fi

echo "✅ ComfyUI: 127.0.0.1:8188"
echo ""

# 启动网页控制器
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug

echo "🚀 启动网页控制器..."
echo "   访问地址：http://127.0.0.1:8189"
echo ""
echo "💡 按 Ctrl+C 停止"
echo "============================================================"
echo ""

python3 comfyui_web_controller.py
