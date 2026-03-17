# ComfyUI Controller 技能

版本：2.0.0

# ComfyUI Controller 技能

智能控制 ComfyUI 进行图片和视频生成，支持 Z-Image-Turbo 和 LTX2 模型。

## 功能

### 1. 图片生成 (Z-Image-Turbo)
- 使用 `z_image_turbo_gguf.json` 工作流
- 模型：`z_image_turbo-Q8_0.gguf` + `Qwen3-4B-Q8_0.gguf`
- 支持自定义提示词、尺寸、种子
- 输出：1024x512 或自定义分辨率

### 2. 视频生成 (LTX2)
- 使用 `ltx2_t2v_gguf.json` 工作流
- 模型：`ltx-2-19b-dev-Q3_K_S.gguf`
- 支持文生视频
- 输出：768x512x97 帧 (~4 秒@25fps)

### 3. 智能监控
- 实时任务队列监控
- 系统资源监控 (VRAM/RAM)
- 生成进度跟踪
- 错误检测和报告

## 使用方法

### Python API

```python
from comfyui_smart_controller_fixed import ComfyUIController

controller = ComfyUIController()

# 检查连接
if controller.check_connection():
    print("ComfyUI 在线")

# 生成图片
image_path = controller.generate_image(
    prompt="beautiful girl, cartoon style",
    negative="blurry, ugly",
    width=1024,
    height=512,
    workflow="z_image_turbo_gguf.json"
)

# 生成视频
video_path = controller.generate_video(
    prompt="girl dancing, cinematic",
    negative="blurry, low quality",
    width=768,
    height=512,
    frames=97,
    workflow="ltx2_t2v_gguf.json"
)
```

### 监控器

```bash
# 运行监控器
python3 comfyui_monitor.py

# 查看状态报告
# - 系统信息 (ComfyUI 版本、VRAM、RAM)
# - 队列状态 (运行中、等待中任务)
# - 最近历史 (成功/失败任务)
# - 实时任务进度
```

### 快捷脚本

```bash
# 图片生成
python3 funny_beauty_final_run.py

# 视频生成
python3 ltx2_dance_fixed.py
```

## 工作流配置

### Z-Image-Turbo (图片)
| 组件 | 模型 |
|------|------|
| UNet | z_image_turbo-Q8_0.gguf |
| CLIP | Qwen3-4B-Q8_0.gguf |
| VAE | ae.safetensors |

### LTX2 (视频)
| 组件 | 模型 |
|------|------|
| UNet | ltx-2-19b-dev-Q3_K_S.gguf |
| CLIP | gemma-3-12b-it-qat-Q3_K_S.gguf + ltx-2-19b-dev_embeddings_connectors.safetensors |
| VAE (视频) | ltx-2-19b-dev_video_vae.safetensors |
| VAE (音频) | ltx-2-19b-dev_audio_vae.safetensors |

## 文件结构

```
ComfyUI-Controller-Little-bug/
├── comfyui_smart_controller_fixed.py  # 主控制器
├── comfyui_monitor.py                 # 监控器
├── funny_beauty_final_run.py          # 图片生成脚本
├── ltx2_dance_fixed.py                # 视频生成脚本
├── SKILL.md                           # 本文档
├── 成功案例总结.md                     # 成功案例
├── 任务进度报告.md                     # 任务进度
└── 监控日志/                          # 监控日志
```

## 输出位置

- 图片：`~/Downloads/comfyui_images/` 或 `~/Downloads/funny_beauty_images/`
- 视频：`~/Downloads/comfyui_videos/` 或 `~/Downloads/ltx2_dance_videos/`
- 日志：`~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/监控日志/`

## 故障排除

### 常见错误

1. **"Node 'Reroute' not found"**
   - 解决：控制器已自动处理 Reroute 节点映射

2. **"Sizes of tensors must match"**
   - 解决：确保帧数在所有节点中一致 (97 帧)

3. **"CLIP dimension mismatch"**
   - 解决：使用正确的 CLIP 加载器配置

4. **ComfyUI 未响应**
   - 检查：`http://127.0.0.1:8188/system_stats`
   - 重启：ComfyUI 服务

### 性能优化

- VRAM 不足时：减小分辨率或帧数
- 生成慢：减少 steps 或使用 distillation 模型
- 队列堵塞：检查是否有卡住的任务

## API 端点

| 端点 | 说明 |
|------|------|
| `/system_stats` | 系统状态 |
| `/queue` | 队列状态 |
| `/history` | 生成历史 |
| `/history/{prompt_id}` | 特定任务历史 |
| `/prompt` | 提交生成任务 (POST) |
| `/view?filename={fn}` | 查看生成的文件 |

## 提示词建议

### 图片 (Z-Image-Turbo)
```
funny cartoon style, beautiful girl, [场景描述], humor, bright colors, comic style, 4k
```

### 视频 (LTX2)
```
A beautiful young girl [动作描述], graceful movements, cinematic lighting, high quality, detailed
```

### 负面提示词
```
blurry, low quality, still frame, frames, watermark, overlay, titles
```
