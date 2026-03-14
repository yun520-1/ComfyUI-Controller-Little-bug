#!/bin/bash
# ComfyUI 控制器快速启动脚本

echo "🎨 ComfyUI 控制器"
echo "================"
echo ""

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import websocket" 2>/dev/null || {
    echo "   安装 websocket-client..."
    pip3 install websocket-client -i https://pypi.tuna.tsinghua.edu.cn/simple -q
}

python3 -c "import requests" 2>/dev/null || {
    echo "   安装 requests..."
    pip3 install requests -i https://pypi.tuna.tsinghua.edu.cn/simple -q
}

python3 -c "import flask" 2>/dev/null || {
    echo "   安装 flask..."
    pip3 install flask -i https://pypi.tuna.tsinghua.edu.cn/simple -q
}

echo "   ✅ 依赖检查完成"
echo ""

# 检查 ComfyUI 连接
echo "🔌 检查 ComfyUI 连接..."
if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "   ✅ ComfyUI 已连接 (127.0.0.1:8188)"
else
    echo "   ⚠️  未检测到 ComfyUI"
    echo ""
    echo "   请先启动 ComfyUI:"
    echo "   cd /path/to/ComfyUI"
    echo "   python main.py --listen 0.0.0.0 --port 8188"
    echo ""
fi

echo ""
echo "📋 使用方式:"
echo ""
echo "1️⃣  命令行方式:"
echo "   python3 comfyui_controller.py --prompt \"一个美丽的女孩\""
echo ""
echo "2️⃣  Web 界面方式:"
echo "   python3 server.py"
echo "   然后访问：http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "3️⃣  查看帮助:"
echo "   python3 comfyui_controller.py --help"
echo ""
