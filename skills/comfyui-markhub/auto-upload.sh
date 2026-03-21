#!/bin/bash
# ComfyUI MarkHub 自动上传脚本
# 用法：bash auto-upload.sh

set -e

SKILL_DIR="/Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub"
GITHUB_USER="yun520-1"
REPO_NAME="comfyui-markhub"
VERSION="1.1.0"

echo "======================================"
echo "  ComfyUI MarkHub v${VERSION} 自动上传"
echo "======================================"
echo ""

cd "$SKILL_DIR"

# ========== GitHub 上传 ==========
echo "📦 步骤 1: 上传到 GitHub"
echo ""

# 检查 Git 仓库
if [ ! -d ".git" ]; then
    echo "  初始化 Git 仓库..."
    git init
    git add -A
    git commit -m "Initial release v${VERSION}"
fi

# 检查远程仓库
if ! git remote | grep -q origin; then
    echo ""
    echo "  ⚠️  请先在 GitHub 创建仓库："
    echo "  1. 访问：https://github.com/new"
    echo "  2. 仓库名：${REPO_NAME}"
    echo "  3. 可见性：Public"
    echo "  4. 不要初始化（我们已有代码）"
    echo ""
    read -p "  创建完成后按回车继续..."
fi

# 添加远程仓库（如果未添加）
if ! git remote | grep -q origin; then
    echo "  添加远程仓库..."
    git remote add origin https://github.com/${GITHUB_USER}/${REPO_NAME}.git
fi

# 推送到 GitHub
echo ""
echo "  推送到 GitHub..."
git branch -M main 2>/dev/null || true
git push -u origin main 2>&1 || {
    echo ""
    echo "  ⚠️  推送失败，可能需要 GitHub 认证"
    echo "  请使用以下命令配置认证："
    echo "  git remote set-url origin https://<TOKEN>@github.com/${GITHUB_USER}/${REPO_NAME}.git"
    echo "  或使用 SSH: git remote set-url origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
    echo ""
    echo "  跳过 GitHub 上传，继续 ClawHub 上传..."
}

echo ""
echo "  ✅ GitHub 上传完成（或已跳过）"
echo ""

# ========== ClawHub 上传 ==========
echo "📦 步骤 2: 上传到 ClawHub"
echo ""

# 尝试 CLI 上传
echo "  尝试使用 CLI 上传..."
if command -v clawhub &> /dev/null; then
    if clawhub publish "$SKILL_DIR" --changelog "v${VERSION} - Added 6+ platform support" 2>&1; then
        echo "  ✅ ClawHub CLI 上传成功！"
    else
        echo ""
        echo "  ⚠️  CLI 上传失败，请使用网页上传"
        echo ""
    fi
else
    echo "  ⚠️  clawhub 命令未找到"
    echo ""
fi

# 网页上传指引
echo "======================================"
echo "  ClawHub 网页上传指引"
echo "======================================"
echo ""
echo "  1. 访问：https://clawhub.ai"
echo "  2. 登录你的账号"
echo "  3. 点击 'Create New Skill' 或 '发布技能'"
echo "  4. 填写信息："
echo "     - Name: comfyui-markhub"
echo "     - Version: ${VERSION}"
echo "     - Description: Universal AI Creation System for ComfyUI"
echo "  5. 上传文件夹：${SKILL_DIR}"
echo "  6. 点击 'Publish'"
echo ""
echo "  或直接访问：https://clawhub.ai/yun520-1/comfyui-markhub"
echo ""

# ========== 完成 ==========
echo "======================================"
echo "  上传完成！"
echo "======================================"
echo ""
echo "📊 发布状态:"
echo "  - GitHub: https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo "  - ClawHub: https://clawhub.ai/yun520-1/${REPO_NAME}"
echo ""
echo "📝 下一步:"
echo "  1. 在 GitHub 创建 Release"
echo "  2. 在社交媒体分享"
echo "  3. 回复用户 Issues"
echo ""
echo "✅ 发布完成！"
echo ""
