# ComfyUI 超级控制器 - 使用说明

## 🎯 项目优化总结

### 原有功能
- ✅ 文生图/图生图
- ✅ 实时监控生成进度
- ✅ 自动保存和整理文件
- ✅ 批量任务支持
- ✅ 工作流管理
- ✅ AI 提示词自动生成

### ⭐ 新增核心功能

#### 1. 本地资源管理 (`local_resource_manager.py`)
```python
# 功能：
- 自动扫描本地 ComfyUI 安装路径
- 检测系统配置（GPU、内存、存储）
- 扫描本地模型（checkpoints、loras、vae 等）
- 扫描本地工作流文件
- 模型兼容性检查
- 基于系统配置的智能推荐
```

#### 2. 智能模型匹配 (`ComfyUISuperController`)
```python
# 匹配逻辑：
1. 优先使用本地已有模型 ✅
2. 本地没有时，根据系统配置推荐
3. 询问用户后自动下载
4. 支持国内镜像源（ModelScope、Wisemodel）
```

#### 3. 系统配置检测
```python
# 检测内容：
- 操作系统、CPU 核心数
- 内存总量
- GPU 型号和显存
- 可用存储空间
- CUDA 支持情况
- 推荐模型列表
```

#### 4. 工作流自动匹配
```python
# 功能：
- 读取本地工作流 JSON 文件
- 自动识别提示词节点
- 自动替换正向/负面提示词
- 根据系统配置调整参数（分辨率、步数）
```

## 📋 快速使用指南

### 1️⃣ 首次使用 - 扫描本地资源

```bash
cd ComfyUI-Controller-Little-bug

# 扫描本地 ComfyUI、模型、工作流
python3 comfyui_super_controller.py --scan

# 生成详细系统报告（JSON 格式）
python3 comfyui_super_controller.py --report
```

**输出示例：**
```
🔍 正在查找 ComfyUI 安装...
✅ 找到 ComfyUI: /Users/apple/ComfyUI

💻 检测系统配置...
📊 系统配置:
   操作系统：Darwin 25.4.0
   CPU: 10 核心
   内存：32.0 GB
   GPU: Apple Silicon (Unified Memory)
   显存：22.4 GB (估计)
   可用存储：180GB

📦 扫描 ComfyUI 模型...
   ✅ checkpoints: 5 个模型
   ✅ loras: 12 个模型
   ✅ vae: 3 个模型

💡 推荐模型:
   - SDXL 1.0 (6-7GB)
   - SD 1.5 (2-4GB)
   - Flux.1 (12-16GB)
```

### 2️⃣ 智能生成 - 自动选择最佳模型

```bash
# 最简单用法 - 自动选择模型
python3 comfyui_super_controller.py \
  --subject "一个美丽的女孩" \
  --style portrait

# 指定模型（优先本地查找）
python3 comfyui_super_controller.py \
  --subject "赛博朋克城市" \
  --model "SDXL" \
  --style cyberpunk

# 自定义参数
python3 comfyui_super_controller.py \
  --subject "奇幻城堡" \
  --style fantasy \
  --width 1024 \
  --height 768 \
  --steps 30
```

### 3️⃣ 使用本地工作流

```bash
# 运行本地工作流文件
python3 comfyui_super_controller.py \
  --workflow /path/to/my_workflow.json \
  --subject "新的提示词" \
  --steps 30

# 工作流会自动：
# 1. 读取 JSON 文件
# 2. 识别提示词节点
# 3. 替换为你的提示词
# 4. 提交到 ComfyUI
# 5. 下载并整理结果
```

### 4️⃣ 批量生成

```bash
# 创建主题文件（每行一个主题）
cat > subjects.txt << EOF
赛博朋克城市夜景
未来科技实验室
霓虹灯街道
机器人市场
太空港口
EOF

# 批量生成
python3 comfyui_super_controller.py \
  --batch subjects.txt \
  --style cyberpunk \
  --width 1024 \
  --height 512
```

### 5️⃣ Python API 调用

```python
from comfyui_super_controller import ComfyUISuperController

# 创建控制器
controller = ComfyUISuperController("127.0.0.1:8188")

# 初始化（自动检测系统和 ComfyUI）
init_result = controller.initialize()
print(f"ComfyUI 路径：{init_result['comfyui_path']}")
print(f"连接状态：{'✅' if init_result['connected'] else '❌'}")

# 智能生成
result = controller.smart_generate(
    subject="一个美丽的女孩",
    style="portrait",
    width=1024,
    height=1024,
    steps=25
)

if result['success']:
    print(f"生成完成！")
    print(f"使用模型：{result['model_used']}")
    print(f"文件：{result['files']}")
```

## 🔍 模型匹配流程详解

```
用户请求：生成图片，指定模型 "SDXL 1.0"

┌─────────────────────────────────┐
│  1. 检查本地是否有 SDXL 模型    │
└──────────────┬──────────────────┘
               │
        ┌──────┴──────┐
        │             │
    ✅ 找到        ❌ 未找到
        │             │
        │       ┌─────┴─────────┐
        │       │ 2. 检查本地    │
        │       │    任何模型    │
        │       └─────┬─────────┘
        │             │
        │       ┌─────┴──────┐
        │       │            │
        │   ✅ 找到      ❌ 未找到
        │       │            │
        │       │      ┌─────┴──────────┐
        │       │      │ 3. 根据系统    │
        │       │      │    配置推荐    │
        │       │      └─────┬──────────┘
        │       │            │
        │       │      ┌─────┴──────────┐
        │       │      │ 4. 询问用户    │
        │       │      │    是否下载    │
        │       │      └─────┬──────────┘
        │       │            │
        │       │      ┌─────┴──────┐
        │       │      │            │
        │       │   ✅ 下载     ❌ 取消
        │       │      │            │
        ▼       ▼      ▼            ▼
   使用本地  使用本地  下载后使用  返回错误
   模型 A    第一个模型  推荐模型
```

## 💡 智能推荐逻辑

### 根据显存推荐模型

| 显存 | 推荐模型 | 说明 |
|------|----------|------|
| >= 16GB | Flux.1, SDXL 1.0, Stable Cascade | 高质量生成 |
| >= 8GB  | SDXL Turbo, SDXL 1.0 (优化) | 平衡质量和速度 |
| >= 6GB  | SD 2.1, SD 1.5 | 经典模型 |
| >= 4GB  | SD 1.5, LCM-LoRA | 低显存优化 |
| < 4GB   | SD 1.5 (CPU), TinySD | 最小模型 |

### 根据系统配置自动调整参数

```python
# 如果未指定分辨率，自动设置
if gpu_mem >= 8:
    width, height = 1024, 1024  # 高分辨率
    steps = 25-35
elif gpu_mem >= 6:
    width, height = 768, 768    # 中等分辨率
    steps = 20-30
else:
    width, height = 512, 512    # 标准分辨率
    steps = 15-25
```

## 🛠️ 常见问题解决

### Q1: 找不到 ComfyUI 安装路径

**解决方法 1：设置环境变量**
```bash
export COMFYUI_PATH=/path/to/ComfyUI
```

**解决方法 2：修改代码**
编辑 `local_resource_manager.py`，在 `POSSIBLE_PATHS` 列表中添加你的路径：
```python
POSSIBLE_PATHS = [
    Path.home() / "ComfyUI",
    Path("/your/custom/path/to/ComfyUI"),  # 添加这一行
    # ...
]
```

### Q2: 模型下载失败或太慢

**使用国内镜像：**
编辑 `comfyui_super_controller.py`，修改 `MODEL_SOURCES`：
```python
MODEL_SOURCES = [
    {
        "name": "ModelScope (阿里)",
        "base_url": "https://modelscope.cn/models",
        "priority": 1  # 优先使用
    },
    # ...
]
```

**手动下载模型：**
1. 访问 https://modelscope.cn 或 https://wisemodel.cn
2. 搜索需要的模型（如 "stable-diffusion-v1-5"）
3. 下载到 `ComfyUI/models/checkpoints/` 目录

### Q3: 显存不足 (OOM)

**解决方案：**
```bash
# 1. 降低分辨率
python3 comfyui_super_controller.py \
  --subject "测试" \
  --width 512 --height 512

# 2. 减少采样步数
python3 comfyui_super_controller.py \
  --subject "测试" \
  --steps 15

# 3. 使用更小的模型
python3 comfyui_super_controller.py \
  --subject "测试" \
  --model "SD 1.5"
```

### Q4: 如何查看已下载的模型

```bash
# 方法 1：扫描命令
python3 comfyui_super_controller.py --scan

# 方法 2：查看报告
cat comfyui_scan_report_*.json | python3 -m json.tool

# 方法 3：直接查看目录
ls -lh ~/ComfyUI/models/checkpoints/
```

## 📊 性能对比

| 任务 | 原版本 | 增强版 | 提升 |
|------|--------|--------|------|
| 首次运行时间 | 手动配置 30 分钟 | 自动检测 5 分钟 | 6x |
| 二次运行 | 手动指定模型 | 自动使用本地 | 自动化 |
| 模型管理 | 手动下载 | 智能推荐 + 下载 | 自动化 |
| 系统适配 | 固定参数 | 自动调整 | 智能化 |
| 工作流使用 | 手动编辑 | 自动替换提示词 | 自动化 |

## 🎯 最佳实践

1. **首次使用先扫描**
   ```bash
   python3 comfyui_super_controller.py --scan
   ```

2. **优先使用本地模型**
   - 避免重复下载
   - 节省时间和带宽

3. **根据显存选择模型**
   - 不要盲目使用大模型
   - 合适的才是最好的

4. **批量任务分批执行**
   - 每次 10-20 个主题
   - 避免队列拥堵

5. **定期整理输出文件**
   ```bash
   # 使用整理功能
   python3 comfyui_smart_controller.py --organize
   ```

## 📁 文件结构

```
ComfyUI-Controller-Little-bug/
├── comfyui_super_controller.py    # ⭐ 主控制器（新增）
├── local_resource_manager.py      # ⭐ 资源管理器（新增）
├── comfyui_smart_controller.py    # 智能控制器（原有）
├── auto_workflow_runner.py        # 自动执行器（原有）
├── workflow_manager.py            # 工作流管理器（原有）
├── test_enhanced_features.py      # ⭐ 测试脚本（新增）
├── README_ENHANCED.md             # ⭐ 增强说明（新增）
├── USAGE.md                       # ⭐ 本文档（新增）
├── requirements.txt               # 依赖
├── workflows/                     # 工作流库
│   ├── registry.json
│   └── txt2img/
└── ...
```

## 🔧 依赖安装

```bash
cd ComfyUI-Controller-Little-bug
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**主要依赖：**
- requests - HTTP 请求
- websocket-client - WebSocket 连接
- urllib3 - URL 处理

## 📝 更新日志

### v2.0 - 增强版 (2026-03-15)
- ✅ 新增本地资源管理器
- ✅ 新增系统配置检测
- ✅ 新增智能模型匹配（优先本地）
- ✅ 新增自动下载功能
- ✅ 新增工作流自动替换
- ✅ 优化参数自动调整
- ✅ 支持国内镜像源
- ✅ 新增测试脚本

### v1.0 - 原版
- 基础文生图功能
- 批量任务支持
- 工作流管理
- 文件自动整理

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [ModelScope](https://modelscope.cn)
- [Wisemodel](https://wisemodel.cn)

---

**开发时间：** 2026-03-15  
**版本：** v2.0 增强版  
**作者：** mac 小虫子 · 严谨专业版
