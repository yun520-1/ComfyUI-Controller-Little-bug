#!/bin/bash
# 安装 GitHub 自动更新定时任务 (新版)
# 白天 6 小时一次，晚上 4 小时一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/run_updater.sh"

echo "=========================================="
echo "⏰ 安装定时任务 (新版频率)"
echo "=========================================="
echo ""

# 删除旧任务
(crontab -l 2>/dev/null | grep -v "run_updater.sh") | crontab -
echo "✅ 已删除旧任务"

# 白天：6:00, 12:00, 18:00
# 晚上：22:00, 2:00
(crontab -l 2>/dev/null; 
 echo "# ComfyUI 自动更新 - 白天 (6 小时一次)"
 echo "0 6,12,18 * * * $CRON_SCRIPT >> $SCRIPT_DIR/更新日志/cron_day.log 2>&1"
 echo "# ComfyUI 自动更新 - 晚上 (4 小时一次)"
 echo "0 2,22 * * * $CRON_SCRIPT >> $SCRIPT_DIR/更新日志/cron_night.log 2>&1"
) | crontab -

echo ""
echo "✅ 新频率已设置"
echo ""
echo "执行时间:"
echo "  白天：6:00, 12:00, 18:00 (每 6 小时)"
echo "  晚上：22:00, 2:00 (每 4 小时)"
echo "  每天共 5 次"
echo ""
echo "查看：crontab -l"
echo "=========================================="
crontab -l 2>/dev/null | grep run_updater
