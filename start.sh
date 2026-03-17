#!/bin/bash
# ComfyUI 全自动控制器 - 一键启动（带模型下载）

echo "============================================================"
echo "🎨 ComfyUI 全自动后台控制器 - 一键启动"
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

echo "✅ ComfyUI 运行正常"
echo ""

# 检查模型
MODEL_FILE="/Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints/v1-5-pruned-emaonly.ckpt"
if [ ! -f "$MODEL_FILE" ] || [ $(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null) -lt 1000000000 ]; then
    echo "⚠️  需要下载 SD 1.5 模型 (4.27GB)"
    echo ""
    echo "请选择:"
    echo "  1. 现在下载（约 5-15 分钟）"
    echo "  2. 手动下载（稍后运行）"
    echo "  3. 退出"
    echo ""
    read -p "输入选择 (1/2/3): " choice
    
    case $choice in
        1)
            echo ""
            echo "📥 开始下载..."
            mkdir -p /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints
            cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints
            
            # 使用国内镜像
            curl -L -# -o v1-5-pruned-emaonly.ckpt \
              "https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
            
            if [ -f "v1-5-pruned-emaonly.ckpt" ] && [ $(stat -f%z "v1-5-pruned-emaonly.ckpt") -gt 1000000000 ]; then
                echo ""
                echo "✅ 下载完成！"
                ls -lh v1-5-pruned-emaonly.ckpt
            else
                echo ""
                echo "❌ 下载失败"
                exit 1
            fi
            ;;
        2)
            echo ""
            echo "💡 手动下载命令:"
            echo "   cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints"
            echo "   curl -L -o v1-5-pruned-emaonly.ckpt \\"
            echo "     https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
            echo ""
            exit 0
            ;;
        3)
            exit 0
            ;;
        *)
            echo "无效选择"
            exit 1
            ;;
    esac
else
    echo "✅ SD 1.5 模型已存在"
    ls -lh "$MODEL_FILE"
fi

echo ""
echo "============================================================"
echo "🚀 启动控制器"
echo "============================================================"
echo ""

cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_auto_controller.py "$@"
