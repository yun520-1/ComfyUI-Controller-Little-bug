# 📰 新闻图片生成指南

**生成规格**: 1024x512 (新闻横幅尺寸)  
**更新时间**: 2026-03-17 13:32

---

## 🎯 快速生成

### 方法 1: 使用 ComfyUI Web 界面（推荐）

1. **访问 ComfyUI**
   ```
   http://127.0.0.1:8188
   ```

2. **加载工作流**
   - 打开默认工作流
   - 或加载预设的新闻图片工作流

3. **设置参数**
   - **尺寸**: 1024 x 512
   - **Steps**: 20-25
   - **CFG**: 7
   - **Sampler**: Euler 或 DPM++ 2M Karras

4. **输入提示词**

   **新闻演播室**:
   ```
   professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic
   ```

   **新闻标题背景**:
   ```
   digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K
   ```

5. **点击 "Queue Prompt" 生成**

---

### 方法 2: 使用 API 脚本

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 generate_news_images.py
```

**前提条件**:
- ComfyUI 正在运行
- 已安装 requests: `pip install requests`

---

### 方法 3: 使用浏览器自动化

```bash
# 安装 playwright
pip install playwright
playwright install chromium

# 运行生成脚本
python3 browser_news_gen.py
```

---

## 📊 推荐设置

### SDXL 模型

| 参数 | 推荐值 |
|------|--------|
| **尺寸** | 1024 x 512 |
| **Steps** | 20-25 |
| **CFG** | 7 |
| **Sampler** | Euler / DPM++ 2M Karras |
| **Scheduler** | Normal / Karras |

### Flux 模型

| 参数 | 推荐值 |
|------|--------|
| **尺寸** | 1024 x 512 |
| **Steps** | 15-20 |
| **Guidance** | 3.5 |
| **Sampler** | Euler |

---

## 🎨 提示词模板

### 新闻演播室

**正面提示词**:
```
professional news broadcast studio, modern TV anchor desk, 
breaking news banner, 4K ultra realistic, broadcast quality lighting, 
cinematic, highly detailed, sharp focus
```

**负面提示词**:
```
blurry, low quality, distorted, ugly, deformed, 
watermark, text, signature, blurry, worst quality
```

### 新闻标题背景

**正面提示词**:
```
digital news headline background, futuristic screen display, 
latest news ticker, blue and red theme, professional broadcast studio, 
4K, highly detailed, cinematic lighting
```

**负面提示词**:
```
blurry, low quality, distorted, ugly, deformed, 
watermark, text, signature, blurry, worst quality
```

---

## 📁 输出位置

生成的图片保存在:
```
~/ComfyUI/output/news_*.png
```

---

## 🔧 故障排查

### Q: ComfyUI 未响应？
**A**: 
```bash
# 检查 ComfyUI 是否运行
curl http://127.0.0.1:8188/system_stats

# 启动 ComfyUI
cd ~/ComfyUI
python main.py
```

### Q: 模型不存在？
**A**: 
```bash
# 检查可用模型
ls ~/ComfyUI/models/checkpoints/

# 下载 SDXL 模型
# 从 https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
```

### Q: 输出尺寸不对？
**A**: 确保 EmptyLatentImage 节点设置为 1024x512

---

## 📝 备注

- **生成时间**: 约 10-30 秒/张（取决于 GPU）
- **推荐 GPU**: ≥8GB VRAM
- **批量生成**: 可调整 batch_size 一次生成多张

---

**最后更新**: 2026-03-17 13:32  
**作者**: mac 小虫子 · 严谨专业版
