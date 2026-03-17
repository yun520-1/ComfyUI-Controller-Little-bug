# ComfyUI 网页控制器 - 快速启动指南

## ✅ 已完成

简化稳定版网页控制器，解决无法访问问题！

## 🚀 快速启动

### 方式 1：一键启动（推荐）

```bash
bash ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/run_web.sh
```

### 方式 2：直接运行

```bash
cd ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug
python3 comfyui_web_simple.py
```

**会自动：**
1. ✅ 启动网页服务器（端口 8189）
2. ✅ 自动打开浏览器
3. ✅ 显示控制界面

### 方式 3：手动访问

如果浏览器没有自动打开，手动访问：
```
http://127.0.0.1:8189
```

## 📋 界面功能

### 状态栏
- **ComfyUI** - 在线/离线状态
- **运行中** - 当前运行任务数
- **排队** - 等待任务数
- **已完成** - 完成任务数

### 任务配置
- **生成类型** - 8 种可选（搞笑/人像/风景等）
- **生成数量** - 1-10 张
- **任务间隔** - 0-300 秒（默认 60 秒）

### 任务队列
- 实时显示所有任务
- 状态：等待/运行/完成/失败

### 运行日志
- 实时日志输出
- 颜色区分信息类型

## 💡 使用流程

```
1. 运行启动脚本
   bash run_web.sh

2. 浏览器自动打开 → http://127.0.0.1:8189

3. 配置任务：
   - 类型：搞笑幽默
   - 数量：3
   - 间隔：60 秒

4. 点击"开始生成"

5. 自动执行：
   ✅ 检查 ComfyUI 空闲
   ✅ 提交任务 1
   ✅ 等待完成
   ✅ 等待 60 秒
   ✅ 提交任务 2
   ✅ ...

6. 完成！查看 ~/Downloads/comfyui_auto_images/
```

## 📁 项目文件

```
~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/
├── comfyui_web_simple.py    # 简化稳定版 ⭐
├── comfyui_web_controller.py # 完整版
├── run_web.sh               # 一键启动 ⭐
├── WEB_CONTROLLER_GUIDE.md  # 详细指南
└── QUICK_START_WEB.md       # 本文档
```

## ⚠️ 故障排除

### 问题 1：无法访问 http://127.0.0.1:8189

**检查服务器是否运行：**
```bash
curl http://127.0.0.1:8189
```

**如果没运行，启动：**
```bash
python3 comfyui_web_simple.py
```

### 问题 2：ComfyUI 离线

**检查 ComfyUI：**
```bash
curl http://127.0.0.1:8188/system_stats
```

**启动 ComfyUI：**
```bash
cd /Users/apple/Documents/lmd_data_root/apps/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

### 问题 3：端口被占用

**修改端口：**
编辑 `comfyui_web_simple.py`，修改：
```python
CONTROLLER_PORT = 8190  # 改为其他端口
```

## 🎯 示例配置

### 快速生成 3 张搞笑图片
```
类型：搞笑幽默
数量：3
间隔：60 秒
```

### 生成 5 张风景（快速）
```
类型：风景自然
数量：5
间隔：30 秒
```

## 📊 输出目录

```
~/Downloads/comfyui_auto_images/
```

## 🎉 核心优势

| 特性 | 说明 |
|------|------|
| ✅ 网页界面 | 浏览器打开即可用 |
| ✅ 实时监控 | 显示 ComfyUI 状态 |
| ✅ 自动排队 | 有任务时自动等待 |
| ✅ 任务间隔 | 可自定义间隔时间 |
| ✅ 稳定运行 | 简化版，不易崩溃 |
| ✅ 自动打开 | 启动后自动打开浏览器 |

## 🔧 停止服务

按 `Ctrl+C` 停止网页控制器

---

**创建时间**: 2026-03-15 20:46  
**版本**: v5.0 Simple Stable  
**状态**: ✅ 稳定运行，立即可用

**立即开始:**
```bash
bash ~/.jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug/run_web.sh
```
