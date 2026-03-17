# ComfyUI 智能变体控制器 - 完全指南

## ✅ 核心功能

### 🎭 智能变体模式

**每个任务自动生成不同提示词！**

生成 5 个图片，每个都是独特的：
- ✅ 基于新闻自动变化
- ✅ 基于搜索关键词变化
- ✅ 基于预设模板变化
- ✅ 风格、灯光、氛围、构图都不同

### 📐 23 种尺寸选择

标准、横版、竖版、超宽、社交媒体全覆盖

### 🌐 新闻读取 + 搜索

- 5 大新闻类别
- 网络搜索丰富提示词

### 🎨 自动模型检测

自动扫描 ComfyUI 可用模型

## 🚀 快速启动

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
bash start_web_variant.sh
```

或手动：
```bash
python3 comfyui_web_variant.py
```

访问：
```
http://127.0.0.1:8190
```

## 💡 使用示例

### 示例 1：基于新闻生成 5 个不同图片

```
1. 打开 http://127.0.0.1:8190
2. 点击"🔄 刷新新闻"
   - 两会 2026
   - 汪峰演唱会
   - 海洋经济
   - 西湖马拉松
   - 人工智能
3. 点击"📰 使用新闻（自动变体）"
   会自动填入所有新闻提示词
4. 勾选"启用智能变体"
5. 数量：5
6. 尺寸：1920x1080
7. 间隔：20 秒
8. 点击"🚀 开始生成（智能变体）"

结果：
- 变体 1: 两会召开，realistic photography, golden hour...
- 变体 2: 汪峰演唱会，digital art, neon lights...
- 变体 3: 海洋经济，oil painting style, soft natural light...
- 变体 4: 西湖马拉松，cinematic, dramatic lighting...
- 变体 5: 人工智能，3D render, volumetric lighting...
```

### 示例 2：搜索关键词生成变体

```
1. 搜索框输入：赛博朋克 城市 夜景
2. 点击"搜索"
3. 基础提示词会自动填入
4. 勾选"启用智能变体"
5. 附加要求：霓虹灯、人群、蒸汽
6. 数量：5
7. 点击"开始生成"

结果：
- 变体 1: 赛博朋克城市夜景，anime style, daytime scene...
- 变体 2: 赛博朋克城市夜景，cyberpunk style, night scene...
- 变体 3: 赛博朋克城市夜景，concept art, sunset scene...
- 变体 4: 赛博朋克城市夜景，digital art, morning light...
- 变体 5: 赛博朋克城市夜景，cinematic, evening atmosphere...
```

### 示例 3：单个提示词生成多个变体

```
1. 基础提示词：美丽的女孩
2. 勾选"启用智能变体"
3. 数量：5
4. 点击"开始生成"

结果（自动添加不同元素）：
- 变体 1: 美丽的女孩，realistic photography, golden hour, peaceful...
- 变体 2: 美丽的女孩，digital art, studio lighting, dynamic...
- 变体 3: 美丽的女孩，oil painting style, soft natural light, mysterious...
- 变体 4: 美丽的女孩，portrait photography, cinematic lighting, romantic...
- 变体 5: 美丽的女孩，fantasy art, volumetric lighting, epic...
```

## 🎭 变体模板

系统使用以下模板自动生成变体：

### 风格（13 种）
- realistic photography
- digital art
- oil painting style
- watercolor style
- anime style
- comic book style
- cinematic
- 3D render
- concept art
- impressionist style
- cyberpunk style
- steampunk style
- fantasy art

### 灯光（12 种）
- golden hour lighting
- soft natural light
- dramatic lighting
- studio lighting
- neon lights
- cinematic lighting
- volumetric lighting
- rim lighting
- backlit
- ambient light
- warm lighting
- cool lighting

### 氛围（12 种）
- peaceful atmosphere
- dynamic atmosphere
- mysterious atmosphere
- energetic vibe
- romantic atmosphere
- epic atmosphere
- serene mood
- dramatic mood
- cheerful mood
- melancholic mood
- hopeful atmosphere
- intense atmosphere

### 质量（12 种）
- ultra high quality
- masterpiece
- award winning
- professional grade
- highly detailed
- photorealistic
- stunning visuals
- exceptional quality
- pristine quality
- flawless detail
- crystal clear
- premium quality

### 构图（12 种）
- rule of thirds
- centered composition
- wide angle view
- close-up shot
- panoramic view
- bird's eye view
- low angle shot
- dynamic angle
- symmetrical composition
- leading lines
- depth of field
- bokeh background

**组合总数：13 × 12 × 12 × 12 × 12 = 269,568 种可能！**

## 📋 界面功能

### 基础配置
- **生成模式** - 图片/视频
- **选择模型** - 自动检测
- **尺寸** - 23 种可选
- **数量** - 1-20 个
- **任务间隔** - 0-300 秒
- **启用智能变体** - 勾选后每个任务不同提示词

### 最新新闻
- **刷新新闻** - 获取 5 个新闻主题
- **使用新闻** - 一键使用所有新闻（自动变体）
- **单个新闻** - 点击使用单个新闻

### 提示词配置
- **快速选择** - 8 种预设
- **基础提示词** - 主要描述
- **负面提示词** - 排除内容
- **附加要求** - 额外元素
- **网络搜索** - 搜索丰富

### 任务队列
- 显示每个变体的提示词片段
- 实时状态更新
- 变体编号和风格信息

### 运行日志
- 实时日志
- 变体信息
- 成功/失败状态

## 🔧 变体逻辑

### 模式 1：多个基础提示词
```
输入：新闻 1; 新闻 2; 新闻 3
结果：
- 变体 1: 新闻 1
- 变体 2: 新闻 2
- 变体 3: 新闻 3
```

### 模式 2：单个提示词 + 新闻
```
输入：新闻插画风格
结果：
- 变体 1: 新闻 1 + 随机风格 + 随机灯光 + 随机氛围
- 变体 2: 新闻 2 + 随机风格 + 随机灯光 + 随机氛围
- 变体 3: 新闻 3 + 随机风格 + 随机灯光 + 随机氛围
```

### 模式 3：单个提示词 + 搜索
```
输入：赛博朋克
搜索：东京 夜景
结果：
- 变体 1: 赛博朋克 + 东京夜景 + 白天场景 + 详细背景 + 随机风格
- 变体 2: 赛博朋克 + 东京夜景 + 夜晚场景 + 聚焦主体 + 随机风格
- 变体 3: 赛博朋克 + 东京夜景 + 日落场景 + 环境背景 + 随机风格
```

### 模式 4：纯变体
```
输入：美丽的女孩
结果：
- 变体 1: 美丽的女孩 + realistic photography + golden hour + peaceful...
- 变体 2: 美丽的女孩 + digital art + studio lighting + dynamic...
- 变体 3: 美丽的女孩 + oil painting + soft light + mysterious...
```

## 📊 输出示例

### 任务队列显示

```
📋 任务队列 [5]

1. image_变体 1 [⏳等待]
   变体 1: realistic photography
   两会召开，人民大会堂，realistic photography, golden hour lighting...

2. image_变体 2 [⏳等待]
   变体 2: digital art
   汪峰演唱会现场，digital art, neon lights, dynamic atmosphere...

3. image_变体 3 [⏳等待]
   变体 3: oil painting style
   海洋经济论坛，oil painting style, soft natural light, mysterious...

4. image_变体 4 [▶️运行]
   变体 4: cinematic
   西湖马拉松，cinematic, dramatic lighting, epic atmosphere...

5. image_变体 5 [⏳等待]
   变体 5: 3D render
   人工智能大会，3D render, volumetric lighting, futuristic...
```

### 运行日志

```
[21:20:15] 开始：5 个变体 image, 尺寸 1920x1080
[21:20:15] ✅ 智能变体已启用：每个任务将使用不同提示词
[21:20:16] 已创建 5 个变体任务
[21:20:20] [1/5] image_变体 1 - 变体 1: realistic photography
[21:20:20]   ✅ 已提交：abc123
[21:20:40]   ⏳ 等待 20 秒...
[21:21:00] [2/5] image_变体 2 - 变体 2: digital art
[21:21:00]   ✅ 已提交：def456
...
[21:23:00] ✅ 所有变体任务完成
```

## 📁 文件位置

```
~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/
├── comfyui_web_variant.py    # 智能变体版 ⭐
├── start_web_variant.sh      # 启动脚本
├── VARIANT_CONTROLLER_GUIDE.md   # 本文档
└── 其他版本文档
```

## ⚠️ 注意事项

1. **确保 ComfyUI 运行** - 需要 8188 端口
2. **端口** - 变体版使用 **8190** 端口
3. **智能变体** - 默认勾选，可取消
4. **任务间隔** - 建议 20-40 秒
5. **网络连接** - 新闻和搜索需要联网

## 🎯 核心优势

| 功能 | 说明 |
|------|------|
| ✅ 智能变体 | 每个任务自动不同提示词 |
| ✅ 269k+ 组合 | 风格×灯光×氛围×质量×构图 |
| ✅ 新闻驱动 | 基于最新新闻自动变化 |
| ✅ 搜索增强 | 搜索关键词丰富内容 |
| ✅ 23 种尺寸 | 全场景覆盖 |
| ✅ 自动检测 | 智能扫描模型 |
| ✅ 实时显示 | 队列显示变体信息 |
| ✅ 灵活控制 | 可开关变体功能 |

## 🔧 常用命令

```bash
# 启动变体版
bash start_web_variant.sh

# 停止
pkill -f comfyui_web_variant.py

# 查看日志
tail -f /tmp/comfyui_web_variant.log

# 打开浏览器
open http://127.0.0.1:8190
```

---

**创建时间**: 2026-03-15 21:20  
**版本**: v8.0 Smart Variants  
**端口**: 8190  
**状态**: ✅ 运行中

**立即开始:**
```bash
open http://127.0.0.1:8190
```
