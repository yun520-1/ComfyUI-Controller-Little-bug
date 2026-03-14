#!/bin/bash
# GitHub 发布脚本

echo "🚀 开始发布到 GitHub..."

cd /Users/apple/Documents/lmd_data_root/apps/comfyui-controller

# 检查 git 状态
echo -e "\n📋 检查文件状态..."
ls -lh *.md

# 初始化 git（如果需要）
if [ ! -d ".git" ]; then
    echo -e "\n🔧 初始化 git 仓库..."
    git init
    git remote add origin https://github.com/YOUR_USERNAME/comfyui-controller.git
fi

# 添加文件
echo -e "\n📦 添加文件..."
git add README.md
git add QUICK_START.md
git add 使用说明.md
git add workflow_manager.py
git add auto_workflow_runner.py
git add server_enhanced.py
git add workflows/

# 查看状态
git status

# 提交
echo -e "\n💾 提交更改..."
read -p "输入提交信息: " commit_message
git commit -m "$commit_message"

# 推送
echo -e "\n📤 推送到 GitHub..."
git push -u origin main

echo -e "\n✅ 发布完成！"
echo "🔗 GitHub 仓库：https://github.com/YOUR_USERNAME/comfyui-controller"
