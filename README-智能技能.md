# 🚀 ComfyUI 智能控制器技能

全自动模型发现、工作流分析、智能执行的 ComfyUI 控制技能。

## ✨ 核心功能

### 1. 自动发现系统
- ✅ **跨平台支持**: Windows / macOS / Linux
- ✅ **自动扫描**: 模型、工作流、节点
- ✅ **智能识别**: 工作流类型 (图片/视频/音频)
- ✅ **官方文档**: 自动查询 HuggingFace/Civitai

### 2. 智能执行系统
- ✅ **最佳工作流选择**: 根据任务类型自动选择
- ✅ **推荐配置**: 按官网建议使用参数
- ✅ **自动转换**: 工作流 JSON → API 格式
- ✅ **错误处理**: 详细错误报告和定位

### 3. 实时监控
- ✅ **系统状态**: VRAM/RAM/设备信息
- ✅ **任务队列**: 运行中/等待中任务
- ✅ **进度跟踪**: 实时生成进度
- ✅ **自动日志**: 保存监控数据

## 📦 安装

### 方法 1: ClawHub (推荐)
```bash
# 安装技能
clawhub install comfyui-controller
```

### 方法 2: 手动安装
```bash
# 克隆到技能目录
git clone https://github.com/your-repo/comfyui-controller.git
cd comfyui-controller

# 安装依赖
pip install requests
```

## 🎯 快速开始

### Python API

```python
from comfyui_smart_executor import SmartExecutor

# 创建执行器 (自动发现模型和工作流)
executor = SmartExecutor()

# 快速生成图片
image = executor.quick_image(
    prompt="beautiful girl, cartoon style",
    width=1024,
    height=512
)

# 快速生成视频
video = executor.quick_video(
    prompt="girl dancing, cinematic",
    width=768,
    height=512,
    frames=97
)
```

### 命令行

```bash
# 查看发现报告
python3 comfyui_auto_discovery.py

# 使用智能执行器
python3 comfyui_smart_executor.py

# 监控系统状态
python3 comfyui_monitor.py
```

## 📚 使用示例

### 示例 1: 生成搞笑美女图片

```python
from comfyui_smart_executor import SmartExecutor

executor = SmartExecutor()

# 自动生成图片
result = executor.quick_image(
    prompt="funny cartoon style, beautiful girl comparing makeup before and after",
    width=1024,
    height=512
)

print(f"图片已保存：{result}")
```

### 示例 2: 生成跳舞视频

```python
# 生成视频
result = executor.quick_video(
    prompt="A beautiful young girl performing elegant ballet dance",
    width=768,
    height=512,
    frames=97  # ~4 秒@25fps
)

print(f"视频已保存：{result}")
```

### 示例 3: 自定义工作流

```python
# 找到最佳工作流
workflow = executor.find_best_workflow("image")
print(f"推荐工作流：{workflow['name']}")

# 自定义配置执行
mods = {
    'prompt': 'your prompt here',
    'negative': 'blurry, ugly',
    'width': 1024,
    'height': 512,
    'seed': 12345
}

pid = executor.execute(workflow['name'], mods)
result = executor.wait_and_download(pid)
```

### 示例 4: 监控系统

```python
from comfyui_monitor import ComfyUIMonitor

monitor = ComfyUIMonitor()

# 生成状态报告
print(monitor.status_report())

# 监控当前任务
queue = monitor.get_queue()
if queue and queue.get('queue_running'):
    prompt_id = queue['queue_running'][0][1]
    monitor.watch_current_task(prompt_id)
```

## 🔧 高级功能

### 模型发现

```python
from comfyui_auto_discovery import ComfyUIDiscovery, ModelRegistry

discovery = ComfyUIDiscovery()

# 扫描所有模型
models = discovery.discover_models()

# 查询模型信息
info = ModelRegistry.get_model_info("z_image_turbo")
print(info)

# 从 HuggingFace 获取信息
hf_info = ModelRegistry.fetch_from_huggingface("black-forest-labs/FLUX.1-dev")
```

### 工作流分析

```python
from comfyui_auto_discovery import WorkflowAnalyzer
from pathlib import Path

# 分析工作流
analysis = WorkflowAnalyzer.analyze_workflow(
    Path("workflows/z_image_turbo_gguf.json")
)

print(f"类型：{analysis['type']}")
print(f"节点数：{analysis['node_count']}")
print(f"设置：{analysis['settings']}")
```

### 跨平台支持

```python
from comfyui_auto_discovery import PlatformPaths

# 获取所有 ComfyUI 安装目录
dirs = PlatformPaths.get_comfyui_dirs()

# 获取模型目录
model_dirs = PlatformPaths.get_model_dirs(dirs[0])
```

## 📊 发现报告示例

```
============================================================
📊 ComfyUI 自动发现报告
============================================================

📁 ComfyUI 安装目录：3 个
  - /Users/apple/Documents/lmd_data_root/apps/ComfyUI
  - /Users/apple/Documents/ComfyUI
  - /Users/apple/ComfyUI

🎯 发现的模型：10 个
  unet: 3 个
  vae: 4 个
  loras: 3 个

📄 发现的工作流：6 个
  image: 5 个
  video: 1 个

🔌 ComfyUI 服务器：✅ 在线
   可用节点：905 个
```

## 🎯 支持的工作流

### 图片生成
| 工作流 | 模型 | 推荐设置 |
|--------|------|----------|
| z_image_turbo_gguf | Z-Image-Turbo-Q8_0 | 1024x512, euler, 20 steps |
| flux_dev_gguf | FLUX.1-dev | 1024x1024, euler, 20 steps |
| AWPortrait | Z-Image-Turbo | 1024x1024, res_multistep |

### 视频生成
| 工作流 | 模型 | 推荐设置 |
|--------|------|----------|
| ltx2_t2v_gguf | LTX-2-19B | 768x512x97, euler_ancestral, 31 steps |

## 🔍 自动文档查询

技能会自动查询以下来源获取模型信息：

1. **HuggingFace API**: 模型信息、下载量、标签
2. **Civitai API**: 模型详情、示例图片
3. **内置知识库**: 官方推荐设置

```python
# 查询 HuggingFace
hf_info = ModelRegistry.fetch_from_huggingface("Lightricks/LTX-Video")

# 查询 Civitai
civitai_info = ModelRegistry.fetch_from_civitai("12345")
```

## 📁 文件结构

```
ComfyUI-Controller-Little-bug/
├── comfyui_auto_discovery.py      # 自动发现系统
├── comfyui_smart_executor.py      # 智能执行器
├── comfyui_monitor.py             # 监控器
├── comfyui_smart_controller_fixed.py  # 控制器 (兼容版)
├── funny_beauty_final_run.py      # 图片生成示例
├── ltx2_dance_fixed.py            # 视频生成示例
├── README-智能技能.md              # 本文档
├── SKILL.md                       # 技能说明
├── 发现报告.md                    # 自动发现报告
└── 监控日志/                      # 监控日志
```

## 🐛 故障排除

### 常见问题

**Q: 找不到模型/工作流？**
```bash
# 检查 ComfyUI 路径
export COMFYUI_PATH=/path/to/ComfyUI
python3 comfyui_auto_discovery.py
```

**Q: 任务提交失败？**
```bash
# 检查 ComfyUI 是否运行
curl http://127.0.0.1:8188/system_stats

# 检查节点是否安装
python3 -c "from comfyui_auto_discovery import ComfyUIDiscovery; d=ComfyUIDiscovery(); print(d.get_available_nodes())"
```

**Q: 视频生成失败？**
- 确保帧数一致 (97 帧)
- 检查 VRAM 是否足够 (建议 16GB+)
- 使用官方工作流模板

### 日志位置

- 发现报告：`发现报告.md`
- 监控日志：`监控日志/YYYYMMDD_HHMMSS.md`
- 输出文件：`~/Downloads/comfyui_output/`

## 🚀 发布到 ClawHub/GitHub

```bash
# 发布到 ClawHub
node publish-clawhub.js

# 或手动发布
clawhub publish ./ComfyUI-Controller-Little-bug
```

## 📝 更新日志

### v2.0.0 (2026-03-17)
- ✅ 新增自动发现系统
- ✅ 新增智能执行器
- ✅ 跨平台支持 (Windows/Mac/Linux)
- ✅ 自动查询官方文档
- ✅ 工作流自动分析
- ✅ 最佳配置推荐

### v1.0.0
- ✅ 基础控制器
- ✅ 图片生成支持
- ✅ 视频生成支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

- GitHub: https://github.com/your-repo/comfyui-controller
- ClawHub: comfyui-controller

## 📄 许可证

MIT License

## 🙏 致谢

- ComfyUI 团队
- HuggingFace
- Civitai
- 所有模型作者
