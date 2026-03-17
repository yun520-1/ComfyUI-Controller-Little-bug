# ComfyUI 超级控制器 - 增强版

在原有功能基础上，新增了以下核心功能：

## 🆕 新增功能

### 1. 本地资源管理
- ✅ 自动扫描本地 ComfyUI 安装的模型
- ✅ 自动扫描本地工作流文件
- ✅ 检测系统配置（GPU、内存、存储）
- ✅ 推荐合适的模型和工作流

### 2. 智能模型匹配
- ✅ **优先使用本地模型**，无需重复下载
- ✅ 本地没有时，自动推荐并下载合适的模型
- ✅ 根据系统配置推荐模型（显存、内存智能匹配）
- ✅ 支持国内镜像源（ModelScope、Wisemodel、HF 镜像）

### 3. 系统配置检测
- ✅ 自动检测操作系统、CPU、GPU、内存、存储
- ✅ 显存评估与模型兼容性检查
- ✅ 生成详细的系统报告

### 4. 工作流自动匹配
- ✅ 读取本地工作流文件
- ✅ 自动替换提示词
- ✅ 根据系统配置调整参数（分辨率、步数等）

## 📦 安装

```bash
cd ComfyUI-Controller-Little-bug
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 🚀 快速开始

### 1. 扫描本地资源

```bash
# 扫描本地 ComfyUI 安装、模型、工作流
python3 comfyui_super_controller.py --scan

# 生成详细系统报告
python3 comfyui_super_controller.py --report
```

### 2. 智能生成（自动选择最佳模型）

```bash
# 自动检测本地模型，没有则下载合适的
python3 comfyui_super_controller.py \
  --subject "一个美丽的女孩" \
  --style portrait

# 指定模型（优先本地查找）
python3 comfyui_super_controller.py \
  --subject "赛博朋克城市" \
  --model "SDXL 1.0" \
  --style cyberpunk
```

### 3. 使用本地工作流

```bash
# 运行本地工作流文件
python3 comfyui_super_controller.py \
  --workflow /path/to/my_workflow.json \
  --subject "一个美丽的女孩" \
  --steps 30
```

### 4. 批量生成

```bash
# 创建主题文件
cat > subjects.txt << EOF
赛博朋克城市夜景
未来科技实验室
霓虹灯街道
机器人市场
太空港口
EOF

# 批量生成（自动管理模型）
python3 comfyui_super_controller.py \
  --batch subjects.txt \
  --style cyberpunk \
  --width 1024 \
  --height 512
```

## 📊 系统配置检测示例

运行扫描后，你会看到类似输出：

```
💻 检测系统配置...

📊 系统配置:
   操作系统：Darwin 25.4.0
   CPU: 10 核心
   内存：32.0 GB
   GPU: Apple Silicon (Unified Memory)
   显存：22.4 GB (估计)
   可用存储：450 GB
   CUDA: ❌ 不支持

💡 推荐模型:
   - SDXL 1.0 (6-7GB)
   - SD 1.5 (2-4GB)
   - Flux.1 (12-16GB)
```

## 🔍 模型匹配逻辑

```
1. 检查本地是否有指定模型
   ├─ 有 → 直接使用本地模型 ✅
   └─ 无 → 继续步骤 2

2. 检查本地是否有任何模型
   ├─ 有 → 使用第一个本地模型
   └─ 无 → 继续步骤 3

3. 根据系统配置推荐模型
   ├─ 显存 >= 16GB → 推荐 SDXL 1.0 或 Flux.1
   ├─ 显存 >= 8GB  → 推荐 SDXL Turbo
   ├─ 显存 >= 6GB  → 推荐 SD 2.1
   └─ 显存 < 6GB   → 推荐 SD 1.5

4. 询问用户是否下载
   ├─ 是 → 开始下载（带进度显示）
   └─ 否 → 返回错误
```

## 📁 文件结构

```
ComfyUI-Controller-Little-bug/
├── comfyui_super_controller.py    # ⭐ 新增：超级智能控制器
├── local_resource_manager.py      # ⭐ 新增：本地资源管理器
├── comfyui_smart_controller.py    # 原有：智能控制器
├── auto_workflow_runner.py        # 原有：自动执行器
├── workflow_manager.py            # 原有：工作流管理器
├── workflows/                     # 工作流库
│   ├── registry.json
│   └── txt2img/
└── README_ENHANCED.md             # ⭐ 新增：本文档
```

## 🛠️ 核心类说明

### LocalComfyUIManager
本地资源管理器，负责：
- 查找 ComfyUI 安装路径
- 检测系统配置
- 扫描本地模型和工作流
- 检查模型兼容性
- 生成扫描报告

### ModelDownloader
智能模型下载器，负责：
- 检查模型是否已存在
- 下载模型（带进度显示）
- 根据系统配置推荐模型
- 支持多个下载源（优先国内）

### ComfyUISuperController
超级智能控制器，整合所有功能：
- 初始化时自动检测系统和 ComfyUI
- 智能选择最佳模型（优先本地）
- 自动调整参数适配系统配置
- 支持运行本地工作流文件

## 💡 使用技巧

### 1. 首次使用
```bash
# 先扫描，了解本地资源情况
python3 comfyui_super_controller.py --scan

# 查看推荐配置
python3 comfyui_super_controller.py --report
```

### 2. 指定模型
```bash
# 支持模糊匹配
python3 comfyui_super_controller.py \
  --subject "测试" \
  --model "SDXL"  # 会自动匹配 SDXL 1.0、SDXL Turbo 等
```

### 3. 使用本地工作流
```bash
# 工作流文件会自动查找提示词节点并替换
python3 comfyui_super_controller.py \
  --workflow /path/to/workflow.json \
  --subject "新的提示词" \
  --steps 30
```

### 4. 批量任务
```bash
# 创建主题文件（每行一个主题）
cat > prompts.txt << EOF
美丽的海滩日落
雪山风景
未来城市
森林小屋
EOF

# 批量生成
python3 comfyui_super_controller.py \
  --batch prompts.txt \
  --style landscape \
  --width 1024 \
  --height 512
```

## 🔧 常见问题

### Q: 找不到 ComfyUI 安装路径？
A: 可以通过以下方式指定：
```bash
# 方法 1：环境变量
export COMFYUI_PATH=/path/to/ComfyUI

# 方法 2：修改代码
# 在 local_resource_manager.py 中添加你的路径到 POSSIBLE_PATHS 列表
```

### Q: 下载模型太慢？
A: 使用国内镜像源：
- ModelScope（阿里）：https://modelscope.cn
- Wisemodel（始智）：https://wisemodel.cn
- HuggingFace 镜像：https://hf-mirror.com

### Q: 显存不足怎么办？
A: 
1. 降低分辨率（--width 512 --height 512）
2. 减少采样步数（--steps 15）
3. 使用更小的模型（SD 1.5 代替 SDXL）
4. 使用 LCM 或 Turbo 模型（快速生成）

### Q: 如何查看已下载的模型？
A: 
```bash
# 扫描本地模型
python3 comfyui_super_controller.py --scan

# 或查看报告
cat comfyui_scan_report_*.json | jq '.available_models'
```

## 📈 性能对比

| 场景 | 原版本 | 增强版 |
|------|--------|--------|
| 首次运行 | 手动下载模型 | 自动检测 + 推荐下载 |
| 二次运行 | 手动指定模型 | 自动使用本地模型 ✅ |
| 系统适配 | 固定参数 | 根据配置自动调整 ✅ |
| 工作流 | 需手动编辑 | 自动替换提示词 ✅ |
| 批量任务 | 容易超显存 | 智能调整参数 ✅ |

## 🎯 最佳实践

1. **首次使用先扫描**：了解本地资源和系统配置
2. **优先本地模型**：避免重复下载
3. **根据显存选择模型**：不要盲目使用大模型
4. **批量任务分批执行**：每次 10-20 个，避免队列拥堵
5. **定期清理输出**：使用整理功能分类保存

## 📝 更新日志

### v2.0 - 增强版
- ✅ 新增本地资源管理器
- ✅ 新增系统配置检测
- ✅ 新增智能模型匹配
- ✅ 新增自动下载功能
- ✅ 新增工作流自动替换
- ✅ 优化参数自动调整
- ✅ 支持国内镜像源

### v1.0 - 原版
- 基础文生图功能
- 批量任务支持
- 工作流管理
- 文件自动整理

## 📄 License

MIT License © 2026

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的 Stable Diffusion GUI
- [ModelScope](https://modelscope.cn) - 阿里模型开放平台
- [Wisemodel](https://wisemodel.cn) - 始智 AI 模型平台

---

**一句话说明：**

直接把文件扔给小龙虾，告诉它你要什么，它自动帮你批量生成图片！现在更智能，会自动使用本地模型，无需重复下载！🦞🎨
