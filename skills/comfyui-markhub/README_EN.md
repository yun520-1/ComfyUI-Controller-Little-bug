# ComfyUI MarkHub v1.1

**Universal AI Creation System - Support for All Major ComfyUI Cloud Platforms**

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://clawhub.ai/yun520-1/comfyui-markhub)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-6+-orange.svg)](PLATFORM_GUIDE.md)

---

## ✨ Features

- 🌐 **6+ Platform Support** - RunPod, Vast.ai, Massed, Thinking Machines, Local, etc.
- 🔍 **Auto Detection** - Intelligently identifies available platforms
- 🔄 **Failover** - Automatic platform switching on failure
- 👁️ **Task Monitoring** - Real-time generation progress tracking
- 💾 **Auto Save** - Automatic local save for images and videos
- 🤖 **Smart Workflow** - Automatic best workflow selection

---

## 🚀 Quick Start

### Installation
```bash
# Via ClawHub (Recommended)
openclaw skills install comfyui-markhub

# Or manual installation
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
```

### Configuration
```bash
# Copy config template
cp config.example.json config.json

# Edit config (default local config works out of box)
nano config.json
```

### Usage
```bash
# Generate image
python3 markhub_core.py -p "A beautiful woman, cinematic lighting, 4k"

# Generate video
python3 markhub_core.py -p "A woman dancing gracefully" --video --duration 10

# Auto mode (Recommended)
python3 markhub_core.py -p "A cat playing in garden" --auto

# Specify platform
python3 markhub_core.py -p "..." --platform runpod
```

---

## 🌐 Supported Platforms

| Platform | Type | Price | Rating |
|----------|------|-------|--------|
| **RunPod** | Cloud | $0.35-0.70/h | ⭐⭐⭐⭐⭐ |
| **Vast.ai** | Cloud | $0.10-0.40/h | ⭐⭐⭐⭐ |
| **Massed Compute** | Cloud | $0.30-0.60/h | ⭐⭐⭐⭐ |
| **Thinking Machines** | Cloud | Contact Sales | ⭐⭐⭐⭐⭐ |
| **Local ComfyUI** | Local | Free | ⭐⭐⭐ |

See [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) for detailed configuration.

---

## 📖 Documentation

- [SKILL.md](SKILL.md) - Complete skill documentation
- [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) - Platform configuration guide
- [README.md](README.md) - 中文文档

---

## ⚙️ Configuration

### Basic Config (config.json)
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

### Platform Examples

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

## 🎯 Usage Examples

### High-Quality Image
```bash
python3 markhub_core.py \
  -p "Beautiful landscape, mountains, lake, golden hour, 4k" \
  --image --auto
```

### Dance Video
```bash
python3 markhub_core.py \
  -p "A woman dancing gracefully, flowing dress, cinematic lighting" \
  --video --duration 10
```

### Batch Generation
```bash
python3 markhub_core.py \
  --batch prompts.txt \
  --output-dir ~/Pictures/Batch/
```

---

## 🔧 Command Line Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-p, --prompt` | Prompt text | Required |
| `--image` | Generate image | - |
| `--video` | Generate video | - |
| `--auto` | Auto mode | False |
| `--platform` | Specify platform | auto |
| `--duration` | Video duration (sec) | 10 |
| `--watch` | Enable monitoring | True |
| `--save` | Save locally | True |
| `--list-platforms` | List platforms | - |

---

## 📁 Output Structure

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

## 🐛 Troubleshooting

### Connection Failed
```bash
# Test platform connection
curl -k https://your-platform:40001/system_stats
```

### List Available Platforms
```bash
python3 markhub_core.py -p "test" --list-platforms
```

### Verbose Logging
```bash
python3 markhub_core.py -p "..." --verbose
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file

---

## 🔗 Links

- **ClawHub:** https://clawhub.ai/yun520-1/comfyui-markhub
- **GitHub:** https://github.com/yun520-1/comfyui-markhub
- **Issues:** https://github.com/yun520-1/comfyui-markhub/issues

---

**Version:** 1.1.0  
**Last Updated:** 2026-03-21  
**Author:** 1 号小虫子 (yun520-1)
