# ComfyUI 全自动控制器 - Z-Image-Turbo 版本

## ✅ 已完成

使用现有的 `z_image_turbo-Q8_0.gguf` 模型，**无需下载 SD 1.5**！

## ⚠️ 当前问题

**缺少 CLIP 模型**：系统只有 LTX2 的 CLIP (`ltx-2-19b-dev_embeddings_connectors.safetensors`)，没有标准 SD CLIP。

## ✅ 解决方案

### 方案 1：使用 LTX2 工作流生成单帧图片

LTX2 工作流已经配置好所有模型，可以生成单帧（length=1）作为图片使用。

**使用 Web 界面：**
1. 打开 http://localhost:8188
2. Load → `ltx2_t2v_gguf.json`
3. 设置 length=1（生成单帧）
4. 输入搞笑段子提示词
5. Queue Prompt

### 方案 2：下载 SD CLIP 模型（推荐）

```bash
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/text_encoders
curl -L -o clip_l.safetensors \
  "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/clip_l.safetensors"
```

然后运行：
```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_zimage_auto.py
```

### 方案 3：使用 LTX2 视频生成

既然有完整的 LTX2 配置，可以直接生成短视频（1-2 秒）：

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 ltx2_xianxia_news.py
```

## 📝 快速命令

### 使用 LTX2 工作流（Web 界面）
```bash
# 打开浏览器
open http://localhost:8188

# Load → ltx2_t2v_gguf.json
# 修改提示词为搞笑段子
# 设置 length=1
# Queue Prompt
```

### 下载 SD CLIP 后使用 Z-Image
```bash
# 下载 CLIP
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/text_encoders
curl -L -o clip_l.safetensors \
  "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/clip_l.safetensors"

# 运行控制器
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_zimage_auto.py 2 funny
```

## 📊 本地模型清单

**可用：**
- ✅ z_image_turbo-Q8_0.gguf (6.7GB) - UNet
- ✅ ltx-2-19b-dev_embeddings_connectors.safetensors - CLIP (LTX2专用)
- ✅ ltx-2-19b-dev_video_vae.safetensors - VAE
- ✅ ae.safetensors - VAE

**缺失：**
- ❌ clip_l.safetensors - SD 标准 CLIP

## 🎯 推荐方案

**最简单：使用 LTX2 Web 界面**
1. 打开 http://localhost:8188
2. Load → ltx2_t2v_gguf.json
3. 修改提示词
4. Queue Prompt

**最自动化：下载 SD CLIP 后使用控制器**
```bash
# 1. 下载 CLIP (约 5 分钟)
curl -L -o ~/Documents/lmd_data_root/apps/ComfyUI/models/text_encoders/clip_l.safetensors \
  "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/clip_l.safetensors"

# 2. 运行控制器
python3 comfyui_zimage_auto.py 2 funny
```

---

**创建时间**: 2026-03-15 20:31  
**状态**: ⚠️ 需要 SD CLIP 或使用 LTX2 Web 界面
