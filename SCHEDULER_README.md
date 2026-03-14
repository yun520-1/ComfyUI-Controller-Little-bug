# ComfyUI 自动调度器 ⏰

## 功能

- ✅ **快速生成** - 一键生成图片/视频
- ✅ **定时任务** - 指定时间自动执行
- ✅ **定量任务** - 一次生成 N 张
- ✅ **批量任务** - 从文件读取多个主题
- ✅ **任务队列** - 管理待执行任务
- ✅ **自动启停** - 自动启动/停止 ComfyUI
- ✅ **任务日志** - 记录所有执行历史
- ✅ **后台调度** - 持续运行监控定时任务

---

## 快速开始

### 1️⃣ 一键生成（最简单）

```bash
cd /home/admin/openclaw/workspace/comfyui-controller

# 生成 1 张图片
python3 scheduler.py --generate "一个美丽的女孩"

# 生成 5 张图片
python3 scheduler.py --generate "赛博朋克城市" --count 5

# 生成视频
python3 scheduler.py --generate "海浪拍打礁石" --video
```

### 2️⃣ 添加任务到队列

```bash
# 添加单个任务
python3 scheduler.py --add "古风美人" --style portrait

# 添加定时任务（指定时间执行）
python3 scheduler.py --add "风景" --schedule "2026-03-15T08:00:00"

# 添加批量任务
python3 scheduler.py --batch sample_subjects.txt --style cyberpunk
```

### 3️⃣ 管理任务

```bash
# 列出所有任务
python3 scheduler.py --list

# 执行指定任务
python3 scheduler.py --run task_20260314210000_0

# 执行所有任务
python3 scheduler.py --run-all

# 删除任务
python3 scheduler.py --remove task_20260314210000_0

# 禁用任务
python3 scheduler.py --disable task_20260314210000_0

# 启用任务
python3 scheduler.py --enable task_20260314210000_0
```

### 4️⃣ 启动调度器（后台运行）

```bash
# 启动调度器（每 60 秒检查一次）
python3 scheduler.py --start

# 指定检查间隔（30 秒）
python3 scheduler.py --start --interval 30

# 后台运行（nohup）
nohup python3 scheduler.py --start > /tmp/scheduler.log 2>&1 &
```

### 5️⃣ 查看日志

```bash
# 显示最近 10 条执行记录
python3 scheduler.py --log

# 查看原始日志文件
cat task_log.json | jq '.history[-10:]'
```

---

## 完整示例

### 示例 1：每天上午 10 点生成一张图

```bash
# 添加定时任务
python3 scheduler.py --add "每日风景" \
    --schedule "2026-03-15T10:00:00" \
    --style landscape

# 启动调度器（后台）
nohup python3 scheduler.py --start --interval 60 > /tmp/scheduler.log 2>&1 &
```

### 示例 2：批量生成 10 个主题

```bash
# 使用预设主题文件
python3 scheduler.py --batch sample_subjects.txt \
    --style realistic \
    --count 2  # 每个主题生成 2 张

# 执行所有任务
python3 scheduler.py --run-all
```

### 示例 3：生成视频并定时执行

```bash
# 添加视频任务
python3 scheduler.py --add "赛博朋克城市动画" \
    --video \
    --schedule "2026-03-15T12:00:00" \
    --width 512 --height 512

# 列出任务确认
python3 scheduler.py --list
```

### 示例 4：完整工作流

```bash
# 1. 启动 ComfyUI（可选，调度器会自动启动）
python3 scheduler.py --start-comfyui

# 2. 添加多个任务
python3 scheduler.py --add "人物 1" --style portrait --count 3
python3 scheduler.py --add "风景 1" --style landscape --count 2
python3 scheduler.py --batch sample_subjects.txt --style cyberpunk

# 3. 查看任务列表
python3 scheduler.py --list

# 4. 执行所有任务
python3 scheduler.py --run-all

# 5. 查看执行日志
python3 scheduler.py --log

# 6. 完成后停止 ComfyUI
python3 scheduler.py --stop-comfyui
```

---

## 参数说明

### 操作模式

| 参数 | 说明 |
|------|------|
| `--generate, -g` | 快速生成（主题） |
| `--add` | 添加任务到队列 |
| `--batch` | 添加批量任务（文件） |
| `--list` | 列出所有任务 |
| `--run` | 执行指定任务 |
| `--run-all` | 执行所有任务 |
| `--remove` | 删除任务 |
| `--enable` | 启用任务 |
| `--disable` | 禁用任务 |
| `--log` | 显示任务日志 |
| `--start` | 启动调度器 |
| `--start-comfyui` | 启动 ComfyUI |
| `--stop-comfyui` | 停止 ComfyUI |

### 任务参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--style` | 风格 | realistic |
| `--count, -n` | 生成数量 | 1 |
| `--video` | 生成视频 | False |
| `--width` | 宽度 | 512 |
| `--height` | 高度 | 512 |
| `--steps` | 采样步数 | 20 |
| `--schedule` | 定时时间（ISO 格式） | - |
| `--interval` | 调度器检查间隔（秒） | 60 |

### 可选风格

- `realistic` - 写实
- `portrait` - 人像
- `landscape` - 风景
- `cyberpunk` - 赛博朋克
- `anime` - 动漫
- `fantasy` - 奇幻
- `scifi` - 科幻

---

## 配置文件

### 任务配置 (scheduler_config.json)

```json
[
  {
    "id": "task_20260314210000_0",
    "name": "一个美丽的女孩_task_...",
    "type": "single",
    "subject": "一个美丽的女孩",
    "style": "portrait",
    "count": 3,
    "width": 512,
    "height": 768,
    "steps": 25,
    "is_video": false,
    "schedule": null,
    "enabled": true,
    "created_at": "2026-03-14T21:00:00",
    "last_run": "2026-03-14T21:05:00",
    "next_run": null,
    "total_runs": 1
  }
]
```

### 任务日志 (task_log.json)

```json
{
  "history": [
    {
      "task_id": "task_20260314210000_0",
      "task_name": "一个美丽的女孩_task_...",
      "timestamp": "2026-03-14T21:05:00",
      "status": "success",
      "count": 3
    }
  ]
}
```

---

## 定时任务格式

### ISO 时间格式

```bash
# 2026 年 3 月 15 日上午 10 点
--schedule "2026-03-15T10:00:00"

# 2026 年 3 月 15 日下午 3 点 30 分
--schedule "2026-03-15T15:30:00"
```

### Cron 表达式（需要扩展）

```bash
# 每天上午 10 点
0 10 * * *

# 每小时
0 * * * *

# 每 5 分钟
*/5 * * * *
```

---

## 后台运行

### 使用 nohup

```bash
# 启动调度器（后台）
nohup python3 scheduler.py --start --interval 60 > /tmp/scheduler.log 2>&1 &

# 查看进程
ps aux | grep scheduler

# 停止进程
pkill -f "scheduler.py --start"
```

### 使用 systemd（推荐生产环境）

```ini
# /etc/systemd/system/comfyui-scheduler.service
[Unit]
Description=ComfyUI Task Scheduler
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/openclaw/workspace/comfyui-controller
ExecStart=/usr/bin/python3 /home/admin/openclaw/workspace/comfyui-controller/scheduler.py --start --interval 60
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl enable comfyui-scheduler
sudo systemctl start comfyui-scheduler

# 查看状态
sudo systemctl status comfyui-scheduler

# 查看日志
sudo journalctl -u comfyui-scheduler -f
```

---

## 注意事项

### ComfyUI 路径

修改脚本中的 `COMFYUI_PATH` 变量：

```python
COMFYUI_PATH = Path("/home/admin/ComfyUI")  # 改为你的实际路径
```

### 资源管理

- 视频生成耗时较长，建议定量任务不要设置过大
- 批量任务建议分批执行，避免显存溢出
- 调度器后台运行时注意日志文件大小

### 错误处理

- 任务失败会自动记录到日志
- ComfyUI 未运行时会自动尝试启动
- 超时任务（10 分钟）会自动终止

---

## API 调用

```python
from scheduler import ComfyUIScheduler

scheduler = ComfyUIScheduler()

# 快速生成
scheduler.quick_generate(
    subject="一个美丽的女孩",
    count=3,
    style="portrait",
    is_video=False
)

# 添加任务
scheduler.add_task(
    subject="赛博朋克城市",
    style="cyberpunk",
    count=5,
    schedule_time="2026-03-15T10:00:00"
)

# 执行所有任务
scheduler.run_all_tasks()

# 查看日志
scheduler.show_log(limit=20)
```

---

## 许可证

MIT License
