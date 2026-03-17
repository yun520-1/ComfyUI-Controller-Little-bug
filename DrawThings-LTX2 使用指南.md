# 🎨 Draw Things LTX-2 使用指南

**Draw Things** 是 macOS/iOS 上的 AI 绘画应用，支持 LTX-Video 模型生成视频。

---

## 📋 配置要求

### 系统要求
- **macOS**: 12.0+
- **Draw Things**: 最新版本
- **LTX-Video 模型**: App 内下载

### 硬件要求
- **内存**: 16GB+ (推荐 32GB)
- **显存**: 8GB+ (M 系列芯片)
- **存储**: 10GB+ 可用空间

---

## 🚀 安装步骤

### 1. 安装 Draw Things

```bash
# Mac App Store
open https://apps.apple.com/app/draw-things/id1604208266
```

### 2. 下载 LTX-Video 模型

1. 打开 Draw Things
2. 点击模型选择器
3. 搜索 "LTX-Video"
4. 点击下载

### 3. 配置参数

推荐设置:
- **分辨率**: 768x512
- **帧数**: 97 帧 (~4 秒@25fps)
- **步数**: 31
- **CFG**: 4.0
- **采样器**: Euler Ancestral

---

## 💻 自动化控制

### 方式 1: AppleScript 控制

```applescript
tell application "Draw Things"
    activate
    set current model to "LTX-Video"
    set positive prompt to "A beautiful girl dancing"
    generate video with {
        prompt: positive prompt,
        width: 768,
        height: 512,
        frames: 97,
        fps: 25
    }
end tell
```

### 方式 2: Python 控制器

```python
from drawthings_ltx2_controller import DrawThingsController

controller = DrawThingsController()

# 生成视频
result = controller.quick_generate(
    prompt="A beautiful young girl performing ballet dance",
    title="ballet"
)

print(f"视频已保存：{result}")
```

### 方式 3: 命令行

```bash
# 运行控制器
python3 drawthings_ltx2_controller.py
```

---

## 📊 与 ComfyUI 对比

| 特性 | Draw Things | ComfyUI |
|------|-------------|---------|
| **易用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **自动化** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **自定义** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **速度** | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **质量** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎯 使用场景

### Draw Things 适合:
- ✅ 快速测试提示词
- ✅ 手动调整参数
- ✅ 实时预览效果
- ✅ 简单工作流

### ComfyUI 适合:
- ✅ 批量生成
- ✅ 复杂工作流
- ✅ 自动化任务
- ✅ 自定义节点

---

## 🔧 常见问题

### Q: Draw Things 找不到 LTX-Video 模型？
**A**: 在模型管理器中搜索并下载

### Q: 生成速度慢？
**A**: 降低分辨率或帧数

### Q: 如何导出视频？
**A**: 生成完成后右键选择"导出"

### Q: 可以批量生成吗？
**A**: 使用 Python 脚本自动化

---

## 📁 输出位置

```
~/Movies/Draw Things/
~/Downloads/drawthings_videos/
```

---

## 🤖 自动化集成

### 集成到现有工作流

```python
# 1. 导入控制器
from drawthings_ltx2_controller import DrawThingsController

# 2. 创建实例
controller = DrawThingsController()

# 3. 生成视频
video = controller.quick_generate(
    prompt="your prompt here",
    title="my_video"
)

# 4. 后续处理
# (上传/分享/编辑等)
```

### 与 GitHub 自动更新集成

```python
# 在 github_auto_updater.py 中添加
def generate_promo_video():
    controller = DrawThingsController()
    return controller.quick_generate(
        "AI generated video showcase",
        title="promo"
    )
```

---

## 📞 支持

- **Draw Things 官网**: https://drawthings.ai/
- **文档**: DrawThings-LTX2 使用指南.md
- **控制器**: drawthings_ltx2_controller.py

---

**最后更新**: 2026-03-17 19:41
