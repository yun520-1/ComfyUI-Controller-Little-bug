# ComfyUI 智能控制器 🎨

> 🤖 一个强大的命令行工具，用于控制 ComfyUI 进行 AI 图像/视频生成

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-compatible-green.svg)](https://github.com/comfyanonymous/ComfyUI)

---

## 📖 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [安装](#-安装)
- [使用指南](#-使用指南)
- [工作流管理](#-工作流管理)
- [文件结构](#-文件结构)
- [API 调用](#-api-调用)
- [常见问题](#-常见问题)

---

## ✨ 功能特性

### 🎯 基础功能

| 功能 | 说明 |
|------|------|
| ✅ 文生图 | 文本描述生成图像 |
| ✅ 图生图 | 基于参考图生成 |
| ✅ 实时监控 | 查看生成进度 |
| ✅ 自动下载 | 自动保存生成结果 |
| ✅ 队列管理 | 查看/管理任务队列 |
| ✅ 模型列表 | 查看可用模型 |

### 🚀 智能增强功能

| 功能 | 说明 |
|------|------|
| 🤖 AI 提示词生成 | 输入主题，自动优化成专业提示词 |
| 🎬 视频生成 | 支持 AnimateDiff 视频生成 |
| 📁 智能分类 | 自动分类保存（10+ 类别） |
| 📦 批量任务 | 一次执行多个主题 |
| 📊 元数据记录 | JSON 格式完整记录 |

---

## 🚀 快速开始

### 1️⃣ AI 自动生成提示词 + 跑图

```bash
# 输入主题，AI 自动优化提示词并生成
python3 comfyui_smart_controller.py --subject "一个美丽的女孩" --style portrait

# 指定风格
python3 comfyui_smart_controller.py --subject "赛博朋克城市" --style cyberpunk
```

### 2️⃣ 批量生成

```bash
# 使用示例主题文件（10 个预设主题）
python3 comfyui_smart_controller.py --batch sample_subjects.txt --style realistic

# 批量生成视频
python3 comfyui_smart_controller.py --batch sample_subjects.txt --video
```

### 3️⃣ 生成视频

```bash
python3 comfyui_smart_controller.py --subject "海浪拍打礁石" --video
```

---

## 📦 安装

### 1. 克隆项目

```bash
git clone https://github.com/yun520-1/ComfyUI-Controller-Little-bug.git
cd ComfyUI-Controller-Little-bug
```

### 2. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 启动 ComfyUI

确保 ComfyUI 正在运行并监听网络：

```bash
cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

---

## 📝 使用指南

### 智能控制器参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--subject, -s` | 主题（AI 自动生成提示词） | 必填 |
| `--style` | 风格 | realistic |
| `--batch` | 批量主题文件 | - |
| `--video` | 生成视频 | False |
| `--width` | 宽度 | 512 |
| `--height` | 高度 | 512 |
| `--steps` | 采样步数 | 20 |
| `--organize` | 整理已有文件 | False |

### 可选风格

```
realistic    - 写实风格
portrait     - 人像肖像
landscape    - 风景自然
cyberpunk    - 赛博朋克
anime        - 动漫二次元
fantasy      - 奇幻魔法
scifi        - 科幻太空
```

### 实用示例

#### 生成一组人像

```bash
python3 comfyui_smart_controller.py \
    --subject "一个 25 岁亚洲女性，职场精英，西装" \
    --style portrait \
    --width 512 --height 768 \
    --steps 25
```

#### 批量生成赛博朋克场景

```bash
# 创建主题文件
cat > cyberpunk_subjects.txt << EOF
赛博朋克城市夜景
未来科技实验室
霓虹灯街道
机器人市场
太空港口
EOF

# 批量生成
python3 comfyui_smart_controller.py \
    --batch cyberpunk_subjects.txt \
    --style cyberpunk \
    --width 768 --height 512
```

---

## 🔧 工作流管理

### 工作流管理器

```bash
# 上传工作流
python3 workflow_manager.py upload --file my_workflow.json \
    --name "我的 workflow" --category txt2img

# 查看所有工作流
python3 workflow_manager.py list

# 查看特定分类
python3 workflow_manager.py list --category video

# 查看工作流详情
python3 workflow_manager.py show --id txt2img_my_workflow_20260314_220000

# 删除工作流
python3 workflow_manager.py delete --id txt2img_my_workflow_20260314_220000
```

### 自动工作流执行器

```bash
# 上传工作流并立即执行
python3 auto_workflow_runner.py upload_run \
    --file my_workflow.json \
    --name "精美肖像" \
    --category portrait \
    --prompt "一个美丽的女孩，高清，精致" \
    --steps 30 --cfg 7 \
    --width 512 --height 768

# 执行已上传的工作流
python3 auto_workflow_runner.py run \
    --id txt2img_my_workflow_20260314_220000 \
    --prompt "赛博朋克城市，霓虹灯" \
    --steps 25

# 批量执行
python3 auto_workflow_runner.py batch \
    --ids "workflow_id_1,workflow_id_2,workflow_id_3" \
    --prompt "提示词 1|提示词 2|提示词 3" \
    --steps 20
```

### 工作流分类

| 分类 | 说明 |
|------|------|
| `txt2img` | 文生图 |
| `img2img` | 图生图 |
| `video` | 视频生成 |
| `upscale` | 高清放大 |
| `controlnet` | ControlNet |
| `face` | 人脸增强 |
| `custom` | 自定义 |

---

## 📁 文件结构

### 输出目录

```
~/Downloads/
├── comfyui_output/              # 原始输出
└── comfyui_organized/           # 智能分类
    ├── portrait/                # 人物肖像
    ├── landscape/               # 风景
    ├── cyberpunk/               # 赛博朋克
    ├── anime/                   # 动漫
    ├── fantasy/                 # 奇幻
    ├── scifi/                   # 科幻
    ├── architecture/            # 建筑
    ├── animal/                  # 动物
    ├── food/                    # 美食
    └── uncategorized/           # 未分类
```

### 项目结构

```
ComfyUI-Controller-Little-bug/
├── comfyui_controller.py        # 基础控制器
├── comfyui_smart_controller.py  # 智能控制器
├── workflow_manager.py          # 工作流管理
├── auto_workflow_runner.py      # 自动执行器
├── scheduler.py                 # 任务调度器
├── server.py                    # 服务器
├── requirements.txt             # 依赖
├── sample_subjects.txt          # 示例主题
└── workflows/                   # 工作流库
    ├── registry.json
    ├── txt2img/
    ├── img2img/
    └── video/
```

### 元数据 JSON 示例

```json
{
  "prompt": "一个年轻女性，肖像风格，柔和光线，虚化背景",
  "negative": "模糊，低质量，变形",
  "category": "portrait",
  "subject": "一个美丽的女孩",
  "timestamp": "2026-03-14T21:05:00",
  "seed": 123456789
}
```

---

## 🔌 API 调用

### Python API

```python
from comfyui_smart_controller import ComfyUIIntelligentController

controller = ComfyUIIntelligentController("127.0.0.1:8188")

if controller.check_connection():
    result = controller.auto_generate(
        subject="一个美丽的女孩",
        style="portrait",
        width=512,
        height=768,
        steps=25
    )
    
    if result['success']:
        print(f"生成完成！分类：{result['category']}")
```

### 工作流 API

```python
from auto_workflow_runner import AutoWorkflowRunner
from workflow_manager import WorkflowManager

runner = AutoWorkflowRunner("127.0.0.1:8188")
manager = WorkflowManager()

# 上传并执行
result = runner.upload_and_run(
    workflow_path="my_workflow.json",
    prompt="一个美丽的女孩",
    category="portrait",
    steps=30
)

# 工作流管理
manager.upload_workflow("workflow.json", name="测试", category="txt2img")
workflows = manager.list_workflows()
```

---

## ❓ 常见问题

### 连接失败

**Q:** 连接 ComfyUI 失败？

**A:** 确保 ComfyUI 已启动并使用 `--listen 0.0.0.0` 参数

```bash
python main.py --listen 0.0.0.0 --port 8188
```

### 找不到模型

**Q:** 提示找不到模型？

**A:** 使用以下命令查看可用模型：

```bash
python3 comfyui_controller.py --models
```

确保模型文件在 `ComfyUI/models/checkpoints/` 目录

### 视频生成失败

**Q:** 视频生成报错？

**A:** 确保安装了 AnimateDiff 自定义节点：

1. 在 ComfyUI Manager 中搜索 `AnimateDiff`
2. 安装并重启 ComfyUI
3. 下载运动模型到 `ComfyUI/models/animatediff_models/`

### WebSocket 超时

**Q:** WebSocket 连接超时？

**A:** 检查防火墙设置，确保 8188 端口可访问：

```bash
# macOS
sudo lsof -i :8188

# Linux
netstat -tlnp | grep 8188
```

---

## 📄 许可证

MIT License © 2026 [yun520-1](https://github.com/yun520-1)

---

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的 Stable Diffusion GUI
- [AnimateDiff](https://github.com/guoyww/AnimateDiff) - 视频生成模型

---

<div align="center">

**Made with ❤️ by 小虫子**

[⭐ Star on GitHub](https://github.com/yun520-1/ComfyUI-Controller-Little-bug) | [🐛 Report Issue](https://github.com/yun520-1/ComfyUI-Controller-Little-bug/issues)

</div>
