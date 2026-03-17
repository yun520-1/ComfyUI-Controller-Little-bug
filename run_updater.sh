#!/bin/bash
# GitHub 自动更新器启动脚本
# 每 2 小时执行一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="python3"
UPDATER="$SCRIPT_DIR/github_auto_updater.py"
LOG_DIR="$SCRIPT_DIR/更新日志"

# 创建日志目录
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "🔄 GitHub 自动更新器"
echo "=========================================="
echo "启动时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "工作目录：$SCRIPT_DIR"
echo ""

# 执行一次更新周期
echo "🚀 执行更新周期..."
$PYTHON "$UPDATER" --once 2>&1 | tee "$LOG_DIR/update_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo "=========================================="
echo "✅ 更新周期完成"
echo "完成时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
