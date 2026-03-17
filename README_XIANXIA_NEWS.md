# 仙人古装新闻视频生成器 - 使用说明

## 📊 当前状态

### ✅ 已完成
- ComfyUI 连接正常（端口 8189）
- 系统配置检测完成（Apple Silicon, 32GB 内存）
- 本地资源扫描完成
- 仙人古装风格工作流创建
- 新闻主题收集（5 个最新新闻）

### ⚠️ 需要安装模型

当前 ComfyUI 缺少 checkpoints 模型文件，需要下载至少一个模型才能生成图片/视频。

## 🎯 新闻主题（2026 年 3 月最新）

已收集 5 个最新新闻主题，将转换为仙人古装风格：

| 序号 | 新闻标题 | 仙人古装风格描述 |
|------|----------|------------------|
| 1 | 两会召开 | 仙界大会，众仙朝拜，仙山楼阁，祥云缭绕 |
| 2 | 汪峰演唱会 | 仙界音乐盛会，古装仙人抚琴，仙乐飘飘 |
| 3 | 海洋经济高质量发展 | 东海龙宫，蛟龙出海，古装仙人御海 |
| 4 | 西湖马拉松 | 仙人御剑飞行比赛，西湖仙境，古装仙人竞速 |
| 5 | 人工智能发展 | 仙界炼丹炉，AI 仙法阵，仙术科技融合 |

## 📥 模型下载（必需）

### 推荐模型（选择其一即可）

#### 选项 1：SD 1.5（推荐，最小）
- **文件大小**: 4.27 GB
- **最低显存**: 4GB
- **下载链接**: 
  - 阿里 ModelScope: https://modelscope.cn/models/AI-ModelScope/stable-diffusion-v1-5
  - HuggingFace: https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt

#### 选项 2：SDXL 1.0（高质量）
- **文件大小**: 6.94 GB
- **最低显存**: 8GB
- **下载链接**:
  - 阿里 ModelScope: https://modelscope.cn/models/stabilityai/stable-diffusion-xl-base-1.0
  - HuggingFace: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

### 下载步骤

```bash
# 1. 创建模型目录
mkdir -p /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints

# 2. 下载 SD 1.5（使用 curl）
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints
curl -L -o v1-5-pruned-emaonly.ckpt \
  "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"

# 或使用阿里 ModelScope（国内更快）
# 访问 https://modelscope.cn/models/AI-ModelScope/stable-diffusion-v1-5 手动下载
```

### 快速下载脚本

```bash
#!/bin/bash
# 下载 SD 1.5 模型
MODEL_DIR="/Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints"
mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

echo "📥 正在下载 SD 1.5 模型..."
curl -L -o v1-5-pruned-emaonly.ckpt \
  "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"

echo "✅ 下载完成！"
ls -lh v1-5-pruned-emaonly.ckpt
```

保存为 `download_model.sh`，然后运行：
```bash
chmod +x download_model.sh
./download_model.sh
```

## 🚀 使用方法

### 安装模型后运行

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug

# 方法 1：使用简化生成器
python3 generate_xianxia_news.py

# 方法 2：使用完整版（带交互）
python3 xianxia_news_generator.py
```

### 输出目录
生成的图片将保存到：`~/Downloads/xianxia_news/`

### 图片规格
- **分辨率**: 1024x512（视频比例）
- **风格**: 仙人古装 + 中国风
- **格式**: PNG
- **元数据**: 每个图片附带 JSON 元数据文件

## 🎨 仙人古装风格提示词

每个新闻主题都配备了专门的仙人古装风格提示词：

### 1. 两会召开
```
仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观
```

### 2. 汪峰演唱会
```
仙界音乐盛会，古装仙人抚琴，仙乐飘飘，霓虹仙灯，仙侠演唱会，华丽舞台，音乐仙境
```

### 3. 海洋经济
```
东海龙宫，蛟龙出海，仙侠风格，古装仙人御海，蓝色仙法，海浪翻滚，史诗感
```

### 4. 西湖马拉松
```
仙人御剑飞行比赛，西湖仙境，古装仙人竞速，桃花盛开，仙侠风格，动态感
```

### 5. 人工智能
```
仙界炼丹炉，AI 仙法阵，古装仙人操控仙术科技，仙侠与科技融合，神秘符文
```

## 📁 文件结构

```
ComfyUI-Controller-Little-bug/
├── generate_xianxia_news.py      # 简化生成器（推荐）
├── xianxia_news_generator.py     # 完整版生成器
├── README_XIANXIA_NEWS.md        # 本文档
└── ...

~/Downloads/xianxia_news/
├── 20260315_193xxx_两会召开_xxxx.png
├── 20260315_193xxx_两会召开_xxxx.json
├── 20260315_193xxx_汪峰演唱会_xxxx.png
├── ...
└── report_20260315_193xxx.json   # 生成报告
```

## ⚡ 快速开始（3 步）

### 步骤 1：下载模型（5-10 分钟）
```bash
curl -L -o /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints/v1-5-pruned-emaonly.ckpt \
  "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
```

### 步骤 2：重启 ComfyUI（让模型生效）
```bash
# 找到 ComfyUI 进程并重启
# 或在 ComfyUI 界面点击"Refresh"按钮
```

### 步骤 3：运行生成器
```bash
python3 ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/generate_xianxia_news.py
```

## 🎬 预期输出

生成完成后，你将看到：

```
============================================================
📊 生成结果汇总
============================================================
✅ 成功：5/5
💾 目录：/Users/apple/Downloads/xianxia_news
📄 报告：/Users/apple/Downloads/xianxia_news/report_xxx.json
```

每个新闻主题生成一张仙人古装风格的图片（1024x512），保存在 `~/Downloads/xianxia_news/` 目录。

## 🔧 故障排除

### 问题 1：连接失败
```
❌ 无法连接 ComfyUI
```
**解决**: 确保 ComfyUI 正在运行在 8189 端口
```bash
ps aux | grep comfyui
# 应该看到：--port 8189
```

### 问题 2：模型未找到
```
❌ 提交失败：Invalid checkpoint name
```
**解决**: 下载模型并刷新 ComfyUI
```bash
# 下载模型（见上方）
# 然后在 ComfyUI 界面点击"Refresh"或重启 ComfyUI
```

### 问题 3：显存不足
```
❌ CUDA out of memory
```
**解决**: 降低分辨率或使用更小的模型
```python
# 修改 generate_xianxia_news.py 中的分辨率
width=512, height=512  # 从 1024x512 降低到 512x512
```

## 📞 技术支持

- 查看 `USAGE.md` 获取详细使用说明
- 查看 `OPTIMIZATION_SUMMARY.md` 了解项目优化内容
- 运行测试脚本：`python3 test_enhanced_features.py`

---

**创建时间**: 2026-03-15 19:36  
**版本**: v1.0  
**风格**: 仙人古装 + 最新新闻
