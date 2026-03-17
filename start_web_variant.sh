#!/bin/bash
# ComfyUI 智能变体控制器 - 一键启动

echo "============================================================"
echo "🎨 ComfyUI 智能变体控制器"
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

# 检查是否已在运行
if curl -s http://127.0.0.1:8190 > /dev/null 2>&1; then
    echo "ℹ️  变体控制器已在运行"
    echo ""
    echo "🌐 访问地址：http://127.0.0.1:8190"
    echo ""
    echo "💡 停止服务：pkill -f comfyui_web_variant.py"
    echo "============================================================"
    open http://127.0.0.1:8190
    exit 0
fi

# 启动
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug

echo "🚀 启动智能变体控制器..."
echo "   端口：8190"
echo "   功能：智能变体（每个任务不同提示词）"
echo "   变体模板：269,568+ 种组合"
echo ""

nohup python3 comfyui_web_variant.py > /tmp/comfyui_web_variant.log 2>&1 &
PID=$!

echo "✅ PID: $PID"
echo ""

# 等待启动
sleep 3

# 检查是否成功
if curl -s http://127.0.0.1:8190 > /dev/null 2>&1; then
    echo "✅ 启动成功！"
    echo ""
    echo "🌐 访问地址：http://127.0.0.1:8190"
    echo ""
    echo "💡 停止服务：pkill -f comfyui_web_variant.py"
    echo "============================================================"
    echo ""
    
    # 自动打开浏览器
    open http://127.0.0.1:8190
    
    echo "🌐 已自动打开浏览器"
else
    echo "❌ 启动失败"
    echo ""
    echo "查看日志：cat /tmp/comfyui_web_variant.log"
    echo "============================================================"
fi
