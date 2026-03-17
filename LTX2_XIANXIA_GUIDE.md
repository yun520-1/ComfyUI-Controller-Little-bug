# LTX2 仙人古装新闻视频生成 - 最终方案

## ✅ 已确认的本地资源

### 模型文件
- ✅ **LTX-2-19B-GGUF**: `/Users/apple/Documents/lmd_data_root/apps/ComfyUI/models/unet/ltx-2-19b-dev-Q3_K_S.gguf` (8.8GB)
- ✅ **Text Encoder**: `gemma-3-12b-it-qat-Q3_K_S.gguf` (5.1GB)
- ✅ **VAE Video**: `ltx-2-19b-dev_video_vae.safetensors`
- ✅ **VAE Audio**: `ltx-2-19b-dev_audio_vae.safetensors`
- ✅ **LoRA**: `ltx-2-19b-distilled-lora-384.safetensors`
- ✅ **LoRA Camera**: `ltx-2-19b-lora-camera-control-dolly-left.safetensors`
- ✅ **Upscaler**: `ltx-2-spatial-upscaler-x2-1.0.safetensors`

### 工作流
- ✅ **LTX2 工作流**: `/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json`
- ✅ **ComfyUI 运行中**: 端口 8189

## ⚠️ 遇到的问题

工作流包含自定义节点（如 `Reroute`），直接通过 API 提交时需要完整的节点依赖。

## ✅ 解决方案

### 方案 1：使用 ComfyUI Web 界面（推荐）

1. **打开 ComfyUI 界面**: http://localhost:8189
2. **加载工作流**: 点击 "Load" → 选择 `ltx2_t2v_gguf.json`
3. **修改提示词**: 
   - 找到提示词节点（CLIPTextEncode）
   - 使用以下仙人古装提示词：

```
正向提示词:
仙界大会，众仙朝拜，仙山楼阁，祥云缭绕，仙侠风格，古装仙人，白色长袍，仙风道骨，宏伟壮观，电影感

负面提示词:
blurry, low quality, still frame, modern clothes, suit, watermark, titles, subtitles
```

4. **点击 "Queue Prompt" 生成**

### 方案 2：使用 Python 脚本批量生成

已创建脚本：`ltx2_xianxia_simple.py`

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 ltx2_xianxia_simple.py
```

**新闻主题列表：**

| 序号 | 新闻 | 仙人古装提示词 |
|------|------|---------------|
| 1 | 两会召开 | 仙界大会，众仙朝拜，仙山楼阁，祥云缭绕 |
| 2 | 汪峰演唱会 | 仙界音乐盛会，古装仙人抚琴，仙乐飘飘 |
| 3 | 海洋经济 | 东海龙宫，蛟龙出海，古装仙人御海 |
| 4 | 西湖马拉松 | 仙人御剑飞行比赛，西湖仙境，古装仙人竞速 |
| 5 | 人工智能 | 仙界炼丹炉，AI 仙法阵，仙术科技融合 |

### 方案 3：使用 ComfyUI CLI 工具

如果安装了 `comfy-cli`：

```bash
comfy run --workflow /Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json \
  --prompt "仙界大会，众仙朝拜，仙山楼阁" \
  --negative "blurry, low quality"
```

## 📁 输出目录

生成的视频将保存到：`~/Downloads/xianxia_ltx2_news/`

## 🎬 预期效果

每个新闻主题生成一个 5-10 秒的仙人古装风格视频：

- **分辨率**: 768x512 或 1024x576
- **帧率**: 24-25 fps
- **时长**: 约 5-7 秒（151 帧）
- **风格**: 中国仙侠、古装、电影感

## 📊 生成时间

- **单个视频**: 约 2-5 分钟（取决于 GPU 性能）
- **5 个视频**: 约 10-25 分钟

## 🔧 故障排除

### 问题 1：找不到节点
```
Node 'Reroute' not found
```
**解决**: 在 ComfyUI Manager 中安装缺失的节点，或直接在 Web 界面运行

### 问题 2：显存不足
```
CUDA out of memory
```
**解决**: 
- 降低分辨率（512x320）
- 减少帧数（97 帧 → 49 帧）
- 使用 Q4_K_M 或更低精度的 GGUF 模型

### 问题 3：生成黑色视频
**解决**: 检查提示词是否过于简单，增加细节描述

## 📝 仙人古装提示词模板

```
[场景描述]，[人物描述]，[动作描述]，[氛围描述]，仙侠风格，古装，电影感

示例:
东海龙宫，蛟龙出海，古装仙人御海，蓝色仙法，海浪翻滚，史诗感，电影感
```

## 🎯 快速开始

**最简单方法：**

1. 打开 http://localhost:8189
2. 加载工作流 `ltx2_t2v_gguf.json`
3. 复制粘贴提示词
4. 点击生成

**批量生成：**

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 ltx2_xianxia_simple.py
# 选择选项 3（测试第一个）
# 或选项 1（生成所有 5 个）
```

---

**创建时间**: 2026-03-15 19:45  
**模型**: LTX-2-19B-GGUF (Q3_K_S)  
**风格**: 仙人古装 + 最新新闻
