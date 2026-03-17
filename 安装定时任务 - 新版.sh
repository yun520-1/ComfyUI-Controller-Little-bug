#!/bin/bash
# 安装 GitHub 自动更新定时任务 (新版)
# 白天 6 小时一次，晚上 4 小时一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/run_updater.sh"

echo "=========================================="
echo "⏰ 安装 GitHub 自动更新定时任务 (新版)"
echo "=========================================="
echo ""

# 检查 crontab
if ! command -v crontab &> /dev/null; then
    echo "❌ crontab 未安装"
    exit 1
fi

# 删除旧任务
(crontab -l 2>/dev/null | grep -v "run_updater.sh") | crontab -
echo "✅ 已删除旧任务"

# 创建新的 cron 配置
# 白天：6:00, 12:00, 18:00 (每 6 小时)
# 晚上：22:00, 2:00 (每 4 小时)
CRON_DAY="0 6,12,18 * * *"
CRON_NIGHT="0 2,22 * * *"

# 添加到 crontab
(crontab -l 2>/dev/null; 
 echo "# ComfyUI 自动更新 - 白天 (6 小时一次)"
 echo "$CRON_DAY $CRON_SCRIPT >> $SCRIPT_DIR/更新日志/cron_day.log 2>&1"
 echo "# ComfyUI 自动更新 - 晚上 (4 小时一次)"
 echo "$CRON_NIGHT $CRON_SCRIPT >> $SCRIPT_DIR/更新日志/cron_night.log 2>&1"
) | crontab -

echo ""
echo "✅ 定时任务已安装"
echo ""
echo "配置信息:"
echo "  白天 (6:00-18:00): 每 6 小时一次"
echo "    执行时间：6:00, 12:00, 18:00"
echo "  晚上 (22:00-2:00): 每 4 小时一次"
echo "    执行时间：22:00, 2:00"
echo "  脚本：$CRON_SCRIPT"
echo "  日志："
echo "    白天：$SCRIPT_DIR/更新日志/cron_day.log"
echo "    晚上：$SCRIPT_DIR/更新日志/cron_night.log"
echo ""
echo "查看定时任务:"
echo "  crontab -l"
echo ""
echo "删除定时任务:"
echo "  crontab -l | grep -v run_updater.sh | crontab -"
echo ""
echo "=========================================="

# 显示当前 crontab
echo "当前 crontab (ComfyUI 相关):"
crontab -l 2>/dev/null | grep run_updater || echo "(无)"
