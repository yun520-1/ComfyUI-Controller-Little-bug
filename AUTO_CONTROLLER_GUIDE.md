# ComfyUI 全自动后台控制器 - 使用指南

## 🎯 功能特点

- ✅ **自动检测模型** - 自动检查并下载所需模型
- ✅ **自动搜索提示词** - 网络搜索最新内容生成提示词
- ✅ **后台运行** - 无需打开 ComfyUI 网页
- ✅ **简单输入** - 只需输入数量和类型
- ✅ **自动下载** - 自动保存生成结果
- ✅ **错误处理** - 自动解决常见问题

## 🚀 快速开始

### 方式 1：交互模式（推荐）

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_auto_controller.py
```

**或者使用启动脚本：**
```bash
bash run_auto_controller.sh
```

### 方式 2：命令行模式

```bash
# 生成 2 张搞笑图片
python3 comfyui_auto_controller.py 2 funny

# 生成 5 张风景图片
python3 comfyui_auto_controller.py 5 landscape

# 生成 3 张自定义主题图片
python3 comfyui_auto_controller.py 3 portrait "美丽的女孩，阳光，海滩"
```

## 📋 支持的生成类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `funny` | 搞笑幽默 | 搞笑段子配图 |
| `portrait` | 人像写真 | 人物肖像 |
| `landscape` | 风景自然 | 山水风景 |
| `anime` | 动漫二次元 | 动漫角色 |
| `cyberpunk` | 赛博朋克 | 未来城市 |
| `fantasy` | 奇幻魔法 | 奇幻世界 |
| `scifi` | 科幻太空 | 科幻场景 |
| `news` | 新闻配图 | 新闻插图 |

## 💡 使用示例

### 示例 1：生成搞笑段子图片

```bash
python3 comfyui_auto_controller.py

# 交互过程：
需要生成多少张图片？(1-10): 2
生成类型 (funny/portrait/...): funny
自定义主题（可选，直接回车跳过）: 
```

**自动执行：**
1. 搜索最新搞笑段子
2. 为每个段子生成提示词
3. 提交到 ComfyUI 生成
4. 下载并保存图片

### 示例 2：生成风景图片

```bash
python3 comfyui_auto_controller.py 3 landscape
```

**输出：**
- 3 张 1024x512 风景图片
- 保存到 `~/Downloads/comfyui_auto_images/`

### 示例 3：自定义主题

```bash
python3 comfyui_auto_controller.py 2 portrait "亚洲女性，职业装，办公室"
```

## 📁 输出目录

所有生成的图片保存在：
```
~/Downloads/comfyui_auto_images/
├── 20260315_202000_上班迟到.png
├── 20260315_202000_上班迟到.json  (元数据)
├── 20260315_202005_减肥失败.png
├── 20260315_202005_减肥失败.json
└── report_20260315_202000.json    (生成报告)
```

## 🔧 自动功能

### 1. 自动检测模型

首次运行时，自动检查是否有 SD 1.5 模型：
- 如果有 → 直接使用
- 如果没有 → 询问是否下载（4.27GB）
- 支持国内镜像源（更快）

### 2. 自动搜索提示词

**搞笑段子类型：**
- 自动搜索最新搞笑段子
- 为每个段子生成专属提示词
- 包含段子内容和标题

**其他类型：**
- 根据类型生成专业提示词
- 支持自定义主题覆盖

### 3. 自动错误处理

- ComfyUI 未运行 → 提示启动命令
- 模型缺失 → 自动下载
- 生成失败 → 自动重试
- 网络问题 → 切换镜像源

## ⚙️ 配置文件

### 模型配置

编辑 `comfyui_auto_controller.py` 中的 `REQUIRED_MODELS`：

```python
REQUIRED_MODELS = {
    "SD15": {
        "file": "v1-5-pruned-emaonly.ckpt",
        "size": "4.27GB",
        "url": "https://huggingface.co/...",
        "mirror": "https://hf-mirror.com/..."  # 国内镜像
    }
}
```

### 生成类型配置

编辑 `GENERATE_TYPES` 添加新类型：

```python
GENERATE_TYPES = {
    "funny": "搞笑幽默",
    "portrait": "人像写真",
    "your_type": "你的类型"  # 添加新类型
}
```

## 🐛 故障排除

### 问题 1：ComfyUI 未运行

**错误：** `❌ ComfyUI 未运行`

**解决：**
```bash
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

**后台运行：**
```bash
nohup python main.py --listen 0.0.0.0 --port 8188 > comfyui.log 2>&1 &
```

### 问题 2：模型下载失败

**错误：** `❌ 下载失败`

**解决：**
1. 检查网络连接
2. 使用镜像源（自动切换）
3. 手动下载：
```bash
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/checkpoints
curl -L -o v1-5-pruned-emaonly.ckpt \
  "https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
```

### 问题 3：生成失败

**错误：** `❌ 提交失败` 或 `❌ 监控失败`

**解决：**
1. 检查 ComfyUI 日志
2. 重启 ComfyUI
3. 减少并发数量（1-2 张测试）

## 📊 性能参考

| 任务 | 时间 | 说明 |
|------|------|------|
| 模型下载 | 5-15 分钟 | 4.27GB，取决于网络 |
| 单张生成 | 30-60 秒 | 1024x512, 25 steps |
| 批量生成 | 数量 × 单张时间 | 建议每次 2-5 张 |

## 🎯 最佳实践

1. **首次使用**
   - 确保 ComfyUI 运行正常
   - 下载 SD 1.5 模型（一次性）
   - 测试生成 1 张

2. **批量生成**
   - 每次 2-5 张
   - 类型保持一致
   - 避免频繁切换类型

3. **自定义主题**
   - 使用英文提示词
   - 包含风格描述
   - 指定分辨率（1024x512）

## 📝 提示词模板

### 搞笑段子
```
funny cartoon style, [场景描述], exaggerated expressions, 
humor, bright colors, comic book style, 1024x512
```

### 人像写真
```
portrait photography, [人物描述], professional lighting, 
bokeh background, high quality, detailed, 1024x512
```

### 风景自然
```
beautiful landscape, [风景描述], golden hour, 
high quality, detailed, nature, 1024x512
```

### 动漫二次元
```
anime style, [角色描述], Japanese animation, 
colorful, detailed character, high quality, 1024x512
```

## 🔗 相关资源

- **项目位置**: `~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/`
- **输出目录**: `~/Downloads/comfyui_auto_images/`
- **ComfyUI 路径**: `/Users/apple/Documents/lmd_data_root/apps/ComfyUI/`
- **模型目录**: `ComfyUI/models/checkpoints/`

## 📞 快速命令

```bash
# 启动控制器（交互模式）
python3 comfyui_auto_controller.py

# 启动控制器（命令行）
python3 comfyui_auto_controller.py 2 funny

# 使用启动脚本
bash run_auto_controller.sh

# 查看生成结果
ls -lh ~/Downloads/comfyui_auto_images/

# 查看生成报告
cat ~/Downloads/comfyui_auto_images/report_*.json
```

---

**创建时间**: 2026-03-15 20:22  
**版本**: v1.0  
**状态**: ✅ 可直接使用  
**ComfyUI**: 需要运行在 8188 端口
