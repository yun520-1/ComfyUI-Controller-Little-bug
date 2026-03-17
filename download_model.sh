#!/bin/bash
# 模型下载脚本 - 仙人古装新闻生成器
# 下载 SD 1.5 模型到 ComfyUI

set -e

# 配置
COMFYUI_PATH="/Users/apple/Documents/lmd_data_root/apps/ComfyUI"
MODEL_DIR="$COMFYUI_PATH/models/checkpoints"
MODEL_FILE="v1-5-pruned-emaonly.ckpt"
MODEL_URL="https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"

# 备用下载源（国内）
MIRROR_URL="https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"

echo "============================================================"
echo "📥 ComfyUI 模型下载脚本"
echo "============================================================"
echo ""
echo "目标目录：$MODEL_DIR"
echo "模型文件：$MODEL_FILE"
echo "文件大小：约 4.27 GB"
echo ""

# 创建目录
echo "1️⃣ 创建目录..."
mkdir -p "$MODEL_DIR"
echo "   ✅ 目录已创建"

# 检查是否已存在
if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo ""
    echo "✅ 模型已存在：$MODEL_DIR/$MODEL_FILE"
    ls -lh "$MODEL_DIR/$MODEL_FILE"
    echo ""
    echo "是否需要重新下载？(y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "已跳过下载"
        exit 0
    fi
fi

# 选择下载源
echo ""
echo "2️⃣ 选择下载源:"
echo "  1. HuggingFace (官方)"
echo "  2. HuggingFace 镜像 (国内推荐)"
echo ""
read -r -p "请输入选择 (1/2): " choice

if [ "$choice" = "2" ]; then
    DOWNLOAD_URL="$MIRROR_URL"
    echo "   使用镜像源：$MIRROR_URL"
else
    DOWNLOAD_URL="$MODEL_URL"
    echo "   使用官方源：$MODEL_URL"
fi

# 下载
echo ""
echo "3️⃣ 开始下载..."
echo "   这可能需要 5-10 分钟，取决于网络速度"
echo ""

cd "$MODEL_DIR"

# 使用 curl 下载（带进度条）
curl -L -# -o "$MODEL_FILE" "$DOWNLOAD_URL"

# 检查下载结果
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 下载完成！"
    echo ""
    ls -lh "$MODEL_FILE"
    echo ""
    
    # 验证文件大小
    FILE_SIZE=$(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null)
    if [ "$FILE_SIZE" -gt 1000000000 ]; then
        echo "✅ 文件大小正常 (>1GB)"
    else
        echo "⚠️  文件可能下载不完整"
    fi
    
    echo ""
    echo "============================================================"
    echo "📋 下一步操作"
    echo "============================================================"
    echo ""
    echo "1. 重启 ComfyUI 或点击界面中的 'Refresh' 按钮"
    echo "2. 运行生成器："
    echo "   python3 ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/generate_xianxia_news.py"
    echo ""
else
    echo ""
    echo "❌ 下载失败"
    echo ""
    echo "可能的原因:"
    echo "  - 网络连接问题"
    echo "  - 磁盘空间不足"
    echo "  - 下载源不可用"
    echo ""
    echo "建议:"
    echo "  - 尝试使用另一个下载源"
    echo "  - 手动下载：访问 https://modelscope.cn/models/AI-ModelScope/stable-diffusion-v1-5"
    echo ""
    exit 1
fi
