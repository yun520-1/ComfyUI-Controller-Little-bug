#!/bin/bash
# ComfyUI 网页控制器 - 一键启动

echo "============================================================"
echo "🎨 ComfyUI 网页控制器"
echo "============================================================"
echo ""

# 检查 ComfyUI
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "❌ ComfyUI 未运行"
    echo ""
    echo "💡 请先启动 ComfyUI:"
    echo "   cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI"
    echo "   python main.py --listen 0.0.0.0 --port 8188"
    echo ""
    exit 1
fi

echo "✅ ComfyUI: 127.0.0.1:8188"
echo ""

# 检查是否已在运行
if curl -s http://127.0.0.1:8189 > /dev/null 2>&1; then
    echo "ℹ️  网页控制器已在运行"
    echo ""
    echo "🌐 访问地址：http://127.0.0.1:8189"
    echo ""
    echo "💡 停止服务：pkill -f comfyui_web_simple.py"
    echo "============================================================"
    open http://127.0.0.1:8189
    exit 0
fi

# 启动
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug

echo "🚀 启动网页控制器..."
nohup python3 comfyui_web_simple.py > /tmp/comfyui_web.log 2>&1 &
PID=$!

echo "   PID: $PID"
echo ""

# 等待启动
sleep 3

# 检查是否成功
if curl -s http://127.0.0.1:8189 > /dev/null 2>&1; then
    echo "✅ 启动成功！"
    echo ""
    echo "🌐 访问地址：http://127.0.0.1:8189"
    echo ""
    echo "💡 停止服务：pkill -f comfyui_web_simple.py"
    echo "============================================================"
    echo ""
    
    # 自动打开浏览器
    open http://127.0.0.1:8189
    
    echo "🌐 已自动打开浏览器"
else
    echo "❌ 启动失败"
    echo ""
    echo "查看日志：cat /tmp/comfyui_web.log"
    echo "============================================================"
fi
