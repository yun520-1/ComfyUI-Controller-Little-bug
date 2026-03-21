# ComfyUI MarkHub v1.1

**全平台智能创作系统 - 支持所有主流 ComfyUI 云平台**

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://clawhub.ai/yun520-1/comfyui-markhub)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-6+-orange.svg)](PLATFORM_GUIDE.md)

---

## ✨ 特性

- 🌐 **6+ 平台支持** - RunPod, Vast.ai, Massed, Thinking Machines, 本地等
- 🔍 **自动检测** - 智能识别可用平台
- 🔄 **故障转移** - 平台失败自动切换
- 👁️ **任务监督** - 实时监控生成进度
- 💾 **自动保存** - 图片和视频自动保存到本地
- 🤖 **智能工作流** - 自动选择最佳工作流

---

## 🚀 快速开始

### 安装
```bash
# 通过 ClawHub 安装（推荐）
openclaw skills install comfyui-markhub

# 或手动安装
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
```

### 配置
```bash
# 复制配置模板
cp config.example.json config.json

# 编辑配置（使用默认本地配置可直接使用）
nano config.json
```

### 使用
```bash
# 生成图片
python3 markhub_core.py -p "A beautiful woman, cinematic lighting, 4k"

# 生成视频
python3 markhub_core.py -p "A woman dancing gracefully" --video --duration 10

# 自动模式（推荐）
python3 markhub_core.py -p "A cat playing in garden" --auto

# 指定平台
python3 markhub_core.py -p "..." --platform runpod
```

---

## 🌐 支持的平台

| 平台 | 类型 | 价格 | 推荐度 |
|------|------|------|--------|
| **RunPod** | 云端 | $0.35-0.70/h | ⭐⭐⭐⭐⭐ |
| **Vast.ai** | 云端 | $0.10-0.40/h | ⭐⭐⭐⭐ |
| **Massed Compute** | 云端 | $0.30-0.60/h | ⭐⭐⭐⭐ |
| **Thinking Machines** | 云端 | 联系销售 | ⭐⭐⭐⭐⭐ |
| **本地 ComfyUI** | 本地 | 免费 | ⭐⭐⭐ |

详细配置见 [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md)

---

## 📖 文档

- [SKILL.md](SKILL.md) - 完整技能文档
- [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) - 平台配置指南
- [README_EN.md](README_EN.md) - English Documentation

---

## ⚙️ 配置说明

### 基本配置 (config.json)
```json
{
  "platform": {
    "type": "auto"
  },
  "comfyui": {
    "base_url": "http://127.0.0.1:8188",
    "verify_ssl": false
  },
  "output": {
    "images": "~/Pictures/MarkHub",
    "videos": "~/Videos/MarkHub"
  }
}
```

### 平台配置示例

**RunPod:**
```json
{
  "platform": "runpod",
  "runpod": {
    "pod_id": "your-pod-id",
    "api_token": "your-api-key"
  }
}
```

**Vast.ai:**
```json
{
  "platform": "vast",
  "vast": {
    "instance_id": "your-instance-id",
    "api_token": "your-api-key"
  }
}
```

---

## 🎯 使用示例

### 高质量图片
```bash
python3 markhub_core.py \
  -p "Beautiful landscape, mountains, lake, golden hour, 4k" \
  --image --auto
```

### 舞蹈视频
```bash
python3 markhub_core.py \
  -p "A woman dancing gracefully, flowing dress, cinematic lighting" \
  --video --duration 10
```

### 批量生成
```bash
python3 markhub_core.py \
  --batch prompts.txt \
  --output-dir ~/Pictures/Batch/
```

---

## 🔧 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-p, --prompt` | 提示词 | 必需 |
| `--image` | 生成图片 | - |
| `--video` | 生成视频 | - |
| `--auto` | 自动模式 | False |
| `--platform` | 指定平台 | auto |
| `--duration` | 视频时长 (秒) | 10 |
| `--watch` | 启用监督 | True |
| `--save` | 保存本地 | True |
| `--list-platforms` | 列出平台 | - |

---

## 📁 输出结构

```
~/Pictures/MarkHub/
├── 2026-03/
│   └── 21/
│       ├── MarkHub_20260321_120000.png
│       └── meta_abc123.json

~/Videos/MarkHub/
├── 2026-03/
│   └── 21/
│       ├── MarkHub_Video_20260321_120000.mp4
│       └── meta_abc123.json
```

---

## 🐛 故障排除

### 连接失败
```bash
# 测试平台连接
curl -k https://your-platform:40001/system_stats
```

### 列出可用平台
```bash
python3 markhub_core.py -p "test" --list-platforms
```

### 查看详细日志
```bash
python3 markhub_core.py -p "..." --verbose
```

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🔗 链接

- **ClawHub:** https://clawhub.ai/yun520-1/comfyui-markhub
- **GitHub:** https://github.com/yun520-1/comfyui-markhub
- **问题反馈:** https://github.com/yun520-1/comfyui-markhub/issues

---

**版本:** 1.1.0  
**更新日期:** 2026-03-21  
**作者:** 1 号小虫子 (yun520-1)
