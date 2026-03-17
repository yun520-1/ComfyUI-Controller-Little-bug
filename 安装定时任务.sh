#!/bin/bash
# 安装 GitHub 自动更新定时任务
# 每 2 小时执行一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/run_updater.sh"

echo "=========================================="
echo "⏰ 安装 GitHub 自动更新定时任务"
echo "=========================================="
echo ""

# 检查 crontab
if ! command -v crontab &> /dev/null; then
    echo "❌ crontab 未安装"
    exit 1
fi

# 创建 cron 表达式 (每 2 小时)
CRON_EXPR="0 */2 * * *"

# 添加到 crontab
(crontab -l 2>/dev/null | grep -v "run_updater.sh"; echo "$CRON_EXPR $CRON_SCRIPT >> $SCRIPT_DIR/更新日志/cron.log 2>&1") | crontab -

echo "✅ 定时任务已安装"
echo ""
echo "配置信息:"
echo "  频率：每 2 小时"
echo "  脚本：$CRON_SCRIPT"
echo "  日志：$SCRIPT_DIR/更新日志/cron.log"
echo ""
echo "查看定时任务:"
echo "  crontab -l"
echo ""
echo "删除定时任务:"
echo "  crontab -l | grep -v run_updater.sh | crontab -"
echo ""
echo "=========================================="

# 显示当前 crontab
echo "当前 crontab:"
crontab -l 2>/dev/null | grep run_updater || echo "(无)"
