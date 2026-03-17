# ComfyUI 智能控制器 - 网页端兼容版

## ✅ 核心理念

**网页端能用的，这里就能用！**

不再强制要求 SD CLIP，而是：
1. 查询 ComfyUI 实际可用的模型
2. 自动适配现有配置
3. 只在真正缺失时才提醒下载

## 📊 当前 ComfyUI 配置

```
✅ ComfyUI: 127.0.0.1:8188

可用模型加载器:
   ✅ UnetLoaderGGUF: 2 个模型
      - z_image_turbo-Q8_0.gguf
      - ltx-2-19b-dev-Q3_K_S.gguf
   
   ✅ CLIPLoader: 1 个 CLIP
      - ltx-2-19b-dev_embeddings_connectors.safetensors
   
   ✅ VAELoader: 4 个 VAE
      - ae.safetensors
      - ltx-2-19b-dev_video_vae.safetensors
      - qwen_image_vae.safetensors
      - ltx-2-19b-dev_audio_vae.safetensors
```

## 💡 为什么网页端能用？

网页端运行时，ComfyUI 使用的是 **LTX2 专用 CLIP**，而不是 SD CLIP。

**问题根源：**
- 我之前的代码强制要求 `clip_l.safetensors`（SD 标准 CLIP）
- 但 ComfyUI 实际只有 `ltx-2-19b-dev_embeddings_connectors.safetensors`（LTX2 专用 CLIP）

**解决方案：**
- 查询 ComfyUI 实际可用的 CLIP
- 使用实际的 CLIP 模型名称
- 自动适配工作流

## 🚀 使用方法

### 方式 1：智能控制器（推荐）

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_web_compatible.py
```

**特点：**
- ✅ 自动查询 ComfyUI 实际配置
- ✅ 使用实际可用的 CLIP 模型
- ✅ 不强制下载任何模型
- ✅ 网页端能用的，这里就能用

### 方式 2：使用现有 LTX2 工作流

既然有完整的 LTX2 配置，可以直接使用 LTX2 工作流生成：

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 ltx2_xianxia_news.py
```

或者使用 Web 界面：
1. 打开 http://localhost:8188
2. Load → `ltx2_t2v_gguf.json`
3. 修改提示词
4. Queue Prompt

## 📝 工作原理

### 智能扫描流程

```python
1. 查询 /system_stats → 检查 ComfyUI 连接
2. 查询 /object_info → 获取所有可用节点
3. 检查 UnetLoaderGGUF → 获取可用 UNet 模型
4. 检查 CLIPLoader → 获取可用 CLIP 模型
5. 检查 VAELoader → 获取可用 VAE 模型
6. 自动推荐最佳组合
```

### 自动适配

```python
# 不再硬编码模型名称
clip_model = clips[0]  # 使用第一个可用的 CLIP
vae_model = vaes[0]    # 使用第一个可用的 VAE
unet_model = unets[0]  # 使用第一个可用的 UNet
```

## 🎯 当前可用方案

### 方案 1：Z-Image-Turbo + LTX2 CLIP

**模型组合：**
- UNet: `z_image_turbo-Q8_0.gguf`
- CLIP: `ltx-2-19b-dev_embeddings_connectors.safetensors`
- VAE: `ae.safetensors`

**适用：** 搞笑图片、人像、风景等

### 方案 2：LTX2 Video（单帧模式）

**模型组合：**
- UNet: `ltx-2-19b-dev-Q3_K_S.gguf`
- CLIP: `ltx-2-19b-dev_embeddings_connectors.safetensors`
- VAE: `ltx-2-19b-dev_video_vae.safetensors`

**适用：** 视频生成、单帧图片

## 📁 项目文件

```
~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/
├── comfyui_web_compatible.py    # 网页端兼容版 ⭐
├── comfyui_smart_controller.py  # 智能扫描版
├── ltx2_xianxia_news.py         # LTX2 专用
└── WEB_COMPATIBLE_GUIDE.md      # 本文档
```

## 🔧 故障排除

### 问题 1：CLIP 不匹配

**现象：** 提示 `clip_name not in list`

**解决：** 使用实际可用的 CLIP 模型名称
```bash
# 查询可用 CLIP
curl -s "http://127.0.0.1:8188/object_info/CLIPLoader" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['CLIPLoader']['input']['required']['clip_name'][0])"
```

### 问题 2：工作流验证失败

**现象：** `Prompt outputs failed validation`

**解决：** 检查工作流节点配置是否匹配实际可用节点

### 问题 3：模型加载失败

**现象：** `ValueError: Model not found`

**解决：** 检查模型文件是否存在
```bash
ls /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/unet/
ls /Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/text_encoders/
```

## 📊 性能对比

| 方案 | 模型 | CLIP | VAE | 适用场景 |
|------|------|------|-----|---------|
| Z-Image + LTX2 CLIP | z_image_turbo | ltx-2-19b-dev | ae.safetensors | 图片生成 |
| LTX2 Video | ltx-2-19b-dev | ltx-2-19b-dev | ltx-2-19b-dev_video | 视频/单帧 |

## 🎉 总结

**核心改进：**
1. ✅ 不再强制要求 SD CLIP
2. ✅ 自动查询 ComfyUI 实际配置
3. ✅ 使用实际可用的模型
4. ✅ 网页端能用的，这里就能用

**当前状态：**
- ✅ 智能扫描完成
- ✅ 自动适配完成
- ✅ 使用 LTX2 CLIP
- ✅ 立即可用

**推荐操作：**
```bash
python3 comfyui_web_compatible.py
```

---

**创建时间**: 2026-03-15 20:34  
**版本**: v3.0 Web Compatible  
**状态**: ✅ 网页端兼容，立即可用
