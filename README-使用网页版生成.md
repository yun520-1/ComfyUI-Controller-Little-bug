# 📰 使用网页版生成新闻图片

**说明时间**: 2026-03-17 14:08  
**原因**: 网页版能正常使用，说明工作流配置完整

---

## ✅ 为什么使用网页版

**当前检测**:
- ✅ ComfyUI 服务正常
- ✅ 有 905+ 个可用节点
- ✅ 网页版能正常生成图片

**问题**:
- ❌ GGUFCheckpointLoader 节点未安装
- ❌ 没有标准 Checkpoint 模型
- ❌ API 工作流配置复杂

**结论**: 网页版已经配置好完整的工作流，直接使用是最简单的方式！

---

## 🎯 快速生成步骤

### 步骤 1: 打开网页版

浏览器访问:
```
http://127.0.0.1:8188
```

### 步骤 2: 设置尺寸

找到 **EmptyLatentImage** 节点，设置:
- **width**: `1024`
- **height**: `512`
- **batch_size**: `1`

### 步骤 3: 输入提示词

找到 **Positive Prompt** 节点，输入:

**第一张 - 新闻演播室**:
```
professional news broadcast studio, modern TV anchor desk, breaking news banner, 4K ultra realistic, broadcast quality lighting, cinematic, highly detailed
```

**第二张 - 新闻标题背景**:
```
digital news headline background, futuristic screen display, latest news ticker, blue and red theme, professional broadcast studio, 4K, highly detailed
```

**Negative Prompt** 节点:
```
blurry, low quality, distorted, ugly, deformed, watermark, text, signature, worst quality, lowres
```

### 步骤 4: 点击生成

点击 **"Queue Prompt"** 按钮

### 步骤 5: 查看结果

等待 10-30 秒，图片保存在:
```
~/ComfyUI/output/
```

或
```
~/Downloads/comfyui_output/
```

---

## 🎨 更多提示词

### 突发新闻
```
breaking news banner, red alert theme, urgent news background, dramatic lighting, 4K
```

### 财经新闻
```
financial news studio, stock market ticker, business theme, green and gold, professional
```

### 体育新闻
```
sports news background, stadium lights, dynamic action, energetic theme, 4K
```

### 天气预报
```
weather forecast studio, weather map background, blue sky theme, professional
```

---

## 📁 文件管理

### 保存位置
- **默认**: `~/ComfyUI/output/`
- **可能**: `~/Downloads/comfyui_output/`

### 查找最新图片
```bash
# macOS Finder
open ~/ComfyUI/output/

# 或按时间排序
ls -lt ~/ComfyUI/output/ | head
```

---

## 🔧 批量生成技巧

### 方法 1: 设置 batch_size
在 EmptyLatentImage 节点设置:
- **batch_size**: `2` (一次生成 2 张)

### 方法 2: 使用 Queue Batch
1. 点击右侧 **"Queue"** 标签
2. 设置 **Batch Count**: `2`
3. 点击 **"Queue Batch"**

### 方法 3: 保存工作流
1. 配置好工作流
2. 点击 **"Save"** 保存为 JSON
3. 下次直接 **"Load"** 加载

---

## 📊 性能参考

| 尺寸 | Steps | 时间 | 推荐度 |
|------|-------|------|--------|
| 1024x512 | 20 | ~15 秒 | ⭐⭐⭐⭐⭐ |
| 1024x512 | 25 | ~20 秒 | ⭐⭐⭐⭐ |
| 1024x512 | 30 | ~25 秒 | ⭐⭐⭐ |

---

## 💡 提示

1. **保存工作流**: 配置好后保存，下次直接使用
2. **使用预设**: 如果有预设工作流，直接加载
3. **调整种子**: 改变 seed 值可以生成不同变体
4. **实时预览**: 开启 Preview 可以实时查看进度

---

## ❓ 常见问题

### Q: 找不到 EmptyLatentImage 节点？
**A**: 
- 按 `Ctrl+F` 或 `Cmd+F` 搜索 "EmptyLatent"
- 或双击空白处，输入 "EmptyLatent"

### Q: 图片太暗/太亮？
**A**: 
- 调整 CFG 值 (7-9 之间)
- 或调整 steps (20-30 之间)

### Q: 生成速度慢？
**A**: 
- 降低 steps 到 15-20
- 或降低尺寸到 512x256

---

**助手**: mac 小虫子 · 严谨专业版  
**更新**: 2026-03-17 14:08
