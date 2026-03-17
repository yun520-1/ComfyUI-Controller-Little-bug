#!/bin/bash
# ComfyUI 全自动控制器 - 快速启动

echo "============================================================"
echo "🎨 ComfyUI 全自动后台控制器"
echo "============================================================"
echo ""

# 检查 ComfyUI 是否运行
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "❌ ComfyUI 未运行"
    echo ""
    echo "💡 请先启动 ComfyUI:"
    echo "   cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI"
    echo "   python main.py --listen 0.0.0.0 --port 8188"
    echo ""
    echo "或者后台启动:"
    echo "   nohup python main.py --listen 0.0.0.0 --port 8188 > comfyui.log 2>&1 &"
    echo ""
    exit 1
fi

echo "✅ ComfyUI 运行正常"
echo ""

# 运行控制器
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_auto_controller.py "$@"
