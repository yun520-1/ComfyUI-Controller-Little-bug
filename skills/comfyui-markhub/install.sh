#!/bin/bash
# ComfyUI MarkHub v1.0 安装脚本

echo "======================================"
echo "  ComfyUI MarkHub v1.0 安装程序"
echo "======================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 创建虚拟环境（可选）
# python3 -m venv venv
# source venv/bin/activate

# 安装依赖
echo ""
echo "📦 安装依赖..."
pip3 install requests websocket-client Pillow

# 设置执行权限
chmod +x markhub_core.py

# 创建输出目录
echo ""
echo "📁 创建输出目录..."
mkdir -p ~/Pictures/MarkHub
mkdir -p ~/Videos/MarkHub

# 测试连接
echo ""
echo "🔗 测试 ComfyUI 连接..."
python3 -c "
import requests
try:
    resp = requests.get('https://wp08.unicorn.org.cn:40001/system_stats', verify=False, timeout=10)
    if resp.status_code == 200:
        print('✅ ComfyUI 连接成功')
    else:
        print('⚠️ ComfyUI 响应异常')
except Exception as e:
    print(f'⚠️ ComfyUI 连接失败：{e}')
"

# 完成
echo ""
echo "======================================"
echo "  ✅ 安装完成！"
echo "======================================"
echo ""
echo "使用方法:"
echo "  # 生成图片"
echo "  python3 markhub_core.py -p \"A beautiful woman\""
echo ""
echo "  # 生成视频"
echo "  python3 markhub_core.py -p \"A dancing woman\" --video"
echo ""
echo "  # 自动模式"
echo "  python3 markhub_core.py -p \"A cat playing\" --auto"
echo ""
echo "配置文件：config.json"
echo "输出目录：~/Pictures/MarkHub, ~/Videos/MarkHub"
echo ""
