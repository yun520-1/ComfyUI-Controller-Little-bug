#!/bin/bash
# LTX2 仙人古装新闻视频 - 最简单运行方式
# 直接在 ComfyUI 目录执行

cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI

echo "============================================================"
echo "🎬 LTX2 仙人古装新闻视频生成"
echo "============================================================"
echo ""
echo "📁 工作流目录："
ls -lh user/default/workflows/ltx2_t2v_gguf.json
echo ""
echo "📝 提示词文件："
cat ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/xianxia_prompts.txt
echo ""
echo "============================================================"
echo "运行方式:"
echo "============================================================"
echo ""
echo "方法 1: 使用 comfy-cli (如果已安装)"
echo "  comfy run --workflow user/default/workflows/ltx2_t2v_gguf.json"
echo ""
echo "方法 2: 使用 Python 直接执行"
echo "  python3 execute_workflow.py --workflow ltx2_t2v_gguf.json"
echo ""
echo "方法 3: Web 界面"
echo "  打开 http://localhost:8189"
echo "  加载工作流 ltx2_t2v_gguf.json"
echo "  修改提示词，点击 Queue Prompt"
echo ""
echo "============================================================"
