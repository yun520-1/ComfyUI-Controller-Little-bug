---
name: comfyui-markhub
description: ComfyUI MarkHub v1.0 - 全平台智能创作系统，支持 RunPod/Vast.ai/本地等所有平台
metadata:
  {
    "openclaw":
      {
        "requires": {
          "bins": ["python3", "curl"],
          "python_packages": ["requests", "websocket-client", "Pillow"]
        }
      }
  }
---

# ComfyUI MarkHub v1.0 - 全平台智能创作系统

**全自动 AI 创作 - 支持所有云平台 · 智能工作流 · 任务监督 · 自动保存**

## 核心功能

### 🌐 全平台支持
- **6+ 云平台** - RunPod, Vast.ai, Massed, Thinking Machines 等
- **本地部署** - 支持本地 ComfyUI
- **自动检测** - 智能识别可用平台
- **故障转移** - 平台失败自动切换
- **HTTPS 安全** - 支持 SSL/TLS 加密传输

### 🤖 智能工作流选择
- **自动读取工作流** - 智能发现所有可用工作流
- **任务类型识别** - 根据需求自动选择最佳工作流
- **参数自动优化** - 智能调整分辨率、步数、CFG 等

### 👁️ 任务监督系统
- **实时监控** - 跟踪生成进度
- **超时保护** - 自动处理超时和失败
- **错误恢复** - 智能重试和降级处理
- **日志记录** - 完整的执行日志

### 💾 自动保存
- **图片保存** - 自动保存到 `~/Pictures/MarkHub/`
- **视频保存** - 自动保存到 `~/Videos/MarkHub/`
- **元数据记录** - 保存生成参数和历史
- **分类整理** - 按日期和类型自动分类

## 快速开始

### 安装
```bash
cd ~/.jvs/.openclaw/workspace/skills/comfyui-markhub
bash install.sh
```

### 配置
编辑 `config.json`:
```json
{
  "comfyui": {
    "base_url": "https://wp08.unicorn.org.cn:40001",
    "verify_ssl": false
  },
  "output": {
    "images": "~/Pictures/MarkHub",
    "videos": "~/Videos/MarkHub"
  }
}
```

### 生成图片
```bash
python3 markhub_core.py -p "A beautiful woman, cinematic lighting, 4k"
```

### 生成视频
```bash
python3 markhub_core.py -p "A woman dancing gracefully" --video --duration 10
```

### 自动模式（推荐）
```bash
python3 markhub_core.py -p "A cat playing in garden" --auto
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--url` | ComfyUI 地址 | 配置文件 |
| `-p, --prompt` | 提示词 | 必需 |
| `-m, --model` | 模型名称 | 自动选择 |
| `-n, --negative` | 负面提示词 | 空 |
| `--image` | 生成图片 | - |
| `--video` | 生成视频 | - |
| `--auto` | 自动模式 | False |
| `--duration` | 视频时长 (秒) | 10 |
| `--width` | 图片宽度 | 自动 |
| `--height` | 图片高度 | 自动 |
| `--steps` | 采样步数 | 自动 |
| `--cfg` | CFG 值 | 自动 |
| `--seed` | 随机种子 | 随机 |
| `--watch` | 启用任务监督 | True |
| `--save` | 保存到本地 | True |

## 输出目录

```
~/Pictures/MarkHub/          # 图片输出
├── 2026-03/
│   ├── 21/
│   │   ├── MarkHub_20260321_114500.png
│   │   └── MarkHub_20260321_114500_meta.json
│   └── ...

~/Videos/MarkHub/            # 视频输出
├── 2026-03/
│   ├── 21/
│   │   ├── MarkHub_Video_20260321_114500.mp4
│   │   └── MarkHub_Video_20260321_114500_meta.json
│   └── ...
```

## 智能特性

### 1. 云平台工作流自动发现
```python
# 自动扫描 ComfyUI 所有工作流
workflows = comfy.get_available_workflows()
# 识别类型：txt2img, img2img, txt2video, img2video
```

### 2. 任务类型智能识别
```python
# 根据提示词自动判断
if "video" in prompt or "motion" in prompt:
    workflow_type = "txt2video"
else:
    workflow_type = "txt2img"
```

### 3. 工作流自动选择
```python
# 选择最佳工作流
best_workflow = select_best_workflow(
    task_type="txt2img",
    quality="high",
    speed="balanced"
)
```

### 4. 任务监督系统
```python
# 实时监控生成进度
watcher = TaskWatcher(prompt_id, timeout=600)
status = watcher.watch()  # 返回：success/failed/timeout
```

### 5. 参数自动优化
```python
# 根据模型自动调整参数
params = optimize_parameters(
    model="sd_xl",
    resolution="auto",
    quality="high"
)
```

## 配置示例

### config.json
```json
{
  "comfyui": {
    "base_url": "https://wp08.unicorn.org.cn:40001",
    "verify_ssl": false,
    "timeout": 300,
    "max_retries": 3
  },
  "output": {
    "images": "~/Pictures/MarkHub",
    "videos": "~/Videos/MarkHub",
    "save_meta": true,
    "organize_by_date": true
  },
  "watcher": {
    "enabled": true,
    "timeout": 600,
    "poll_interval": 5,
    "auto_retry": true
  },
  "optimizer": {
    "auto_resolution": true,
    "auto_steps": true,
    "auto_cfg": true,
    "quality_preset": "balanced"
  }
}
```

## 使用示例

### 1. 高质量风景图片
```bash
python3 markhub_core.py \
  -p "Beautiful landscape, mountains, lake, golden hour, 4k, highly detailed" \
  --image \
  --auto
```

### 2. 人物舞蹈视频
```bash
python3 markhub_core.py \
  -p "A woman dancing gracefully, flowing dress, cinematic lighting" \
  --video \
  --duration 10 \
  --auto
```

### 3. 批量生成
```bash
python3 markhub_core.py \
  --batch prompts.txt \
  --output-dir ~/Pictures/Batch/
```

### 4. 指定工作流
```bash
python3 markhub_core.py \
  -p "Cyberpunk city, neon lights" \
  --workflow "txt2img_sdxl" \
  --width 1024 \
  --height 1024
```

## 任务监督

### 启用监督
```bash
python3 markhub_core.py -p "..." --watch
```

### 监督功能
- ✅ 实时进度跟踪
- ✅ 超时自动处理
- ✅ 失败自动重试
- ✅ 完整日志记录
- ✅ 结果验证

### 监督日志
```
⏳ 任务监督中...
  Prompt ID: abc123...
  状态：处理中 (3/30 步)
  预计剩余：45 秒
✅ 任务完成！
  输出：~/Pictures/MarkHub/2026-03/21/MarkHub_*.png
  耗时：52 秒
```

## 错误处理

### 自动重试
- 网络错误：自动重试 3 次
- 超时：自动重试 2 次
- 队列满：等待后重试

### 降级策略
- 高分辨率失败 → 降低分辨率重试
- 高质量失败 → 降低质量重试
- 模型不可用 → 使用备用模型

## API 参考

### ComfyUI MarkHub 类
```python
from markhub import ComfyUIMarkHub

markhub = ComfyUIMarkHub(
    base_url="https://wp08.unicorn.org.cn:40001",
    config_path="config.json"
)

# 生成图片
result = markhub.generate_image(
    prompt="A beautiful woman",
    auto_optimize=True
)

# 生成视频
result = markhub.generate_video(
    prompt="A dancing woman",
    duration=10,
    auto_optimize=True
)

# 保存结果
markhub.save_result(result, output_dir="~/Pictures/MarkHub/")
```

## 性能优化

### 并发控制
- 最大并发任务：4
- 队列监控：实时
- 资源限制：自动检测

### 缓存策略
- 工作流缓存：5 分钟
- 模型列表缓存：10 分钟
- 节点信息缓存：15 分钟

## 故障排除

### 常见问题

**Q: 连接失败**
```bash
# 检查 ComfyUI 是否可访问
curl -k https://wp08.unicorn.org.cn:40001/system_stats
```

**Q: 工作流找不到**
```bash
# 列出所有可用工作流
python3 markhub_core.py --list-workflows
```

**Q: 生成失败**
```bash
# 查看详细日志
python3 markhub_core.py -p "..." --verbose
```

## 更新日志

### v1.0 (2026-03-21)
- ✅ 云平台 ComfyUI 集成
- ✅ 智能工作流选择
- ✅ 任务监督系统
- ✅ 自动保存到本地
- ✅ 参数自动优化
- ✅ 错误自动恢复

## 许可证

MIT License

## 支持

- GitHub: https://github.com/yun520-1/markhub-skill
- 问题反馈：创建 Issue
