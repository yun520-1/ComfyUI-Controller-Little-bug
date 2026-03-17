#!/bin/bash
# 搞笑美女图片生成脚本

echo "============================================================"
echo "😂 搞笑美女图片生成器"
echo "============================================================"
echo ""

# 检查 ComfyUI
if curl -s http://127.0.0.1:8188/system_stats > /dev/null; then
    echo "✅ ComfyUI 已连接"
else
    echo "❌ ComfyUI 未运行"
    echo "请启动：cd ~/ComfyUI && python main.py"
    exit 1
fi

echo ""
echo "📐 尺寸：1024x512"
echo "🎯 模型：Z-Image-Turbo GGUF"
echo ""
echo "============================================================"
echo "⚠️  请使用网页版生成 (工作流已验证可用)"
echo "============================================================"
echo ""
echo "步骤:"
echo "1. 打开 http://127.0.0.1:8188"
echo ""
echo "2. 设置尺寸 (EmptyLatentImage 节点):"
echo "   - width: 1024"
echo "   - height: 512"
echo ""
echo "3. 输入提示词:"
echo ""
echo "   第一张 - 化妆前后:"
echo "   funny cartoon style, beautiful girl comparing makeup before"
echo "   and after, exaggerated contrast, humor, bright colors,"
echo "   comic style, 4k"
echo ""
echo "   第二张 - 自拍 vs 他拍:"
echo "   funny cartoon style, beautiful girl taking selfie vs"
echo "   someone else taking photo, funny awkward angle,"
echo "   exaggerated expressions, humor, bright, comic"
echo ""
echo "4. 负面提示词:"
echo "   blurry, low quality, ugly, deformed, nsfw"
echo ""
echo "5. 点击 Queue Prompt"
echo ""
echo "图片将保存到：~/ComfyUI/output/"
echo ""
