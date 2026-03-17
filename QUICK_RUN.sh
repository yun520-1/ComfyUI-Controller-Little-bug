#!/bin/bash
# LTX2 仙人古装新闻视频 - 快速运行脚本

echo "============================================================"
echo "🎬 LTX2 仙人古装新闻视频生成器"
echo "============================================================"
echo ""
echo "✅ 已确认资源:"
echo "   - 模型：LTX-2-19B-GGUF (Q3_K_S)"
echo "   - 工作流：ltx2_t2v_gguf.json"
echo "   - ComfyUI: 运行在 8189 端口"
echo ""
echo "📋 仙人古装新闻主题 (5 个):"
echo "   1. 两会召开 - 仙界大会，众仙朝拜"
echo "   2. 汪峰演唱会 - 仙界音乐盛会"
echo "   3. 海洋经济 - 东海龙宫，蛟龙出海"
echo "   4. 西湖马拉松 - 仙人御剑飞行比赛"
echo "   5. 人工智能 - 仙界炼丹炉，AI 仙法阵"
echo ""
echo "============================================================"
echo "🚀 使用方法"
echo "============================================================"
echo ""
echo "方法 1: ComfyUI Web 界面 (推荐)"
echo "--------------------------------"
echo "1. 打开：http://localhost:8189"
echo "2. 点击 'Load' 按钮"
echo "3. 选择文件:"
echo "   ~/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"
echo ""
echo "4. 找到提示词节点 (CLIPTextEncode)，双击编辑:"
echo "   正向：仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人"
echo "   负面：blurry, low quality, still frame, modern clothes"
echo ""
echo "5. 点击 'Queue Prompt' 开始生成"
echo ""
echo "方法 2: 使用 comfy-cli (如果已安装)"
echo "------------------------------------"
echo "comfy run --workflow ltx2_t2v_gguf.json"
echo ""
echo "方法 3: Python 脚本 (需要修复工作流转换)"
echo "------------------------------------------"
echo "python3 run_ltx2_xianxia.py"
echo ""
echo "============================================================"
echo "📁 输出目录"
echo "============================================================"
echo "~/Downloads/xianxia_ltx2_news/"
echo ""
echo "============================================================"
echo "📝 提示词列表"
echo "============================================================"
cat << 'EOF'

【两会召开】
正向：仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感
负面：blurry, low quality, still frame, modern clothes, suit, watermark

【汪峰演唱会】
正向：仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，动态表演
负面：blurry, low quality, still frame, modern clothes, microphone

【海洋经济】
正向：东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感
负面：blurry, low quality, still frame, modern ship, boat

【西湖马拉松】
正向：仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态飞行
负面：blurry, low quality, still frame, modern clothes, running

【人工智能】
正向：仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文
负面：blurry, low quality, still frame, computer, modern tech

EOF

echo "============================================================"
echo "💡 建议"
echo "============================================================"
echo "由于工作流包含自定义节点，建议直接使用 ComfyUI Web 界面运行"
echo ""
echo "打开浏览器访问：http://localhost:8189"
echo "============================================================"
