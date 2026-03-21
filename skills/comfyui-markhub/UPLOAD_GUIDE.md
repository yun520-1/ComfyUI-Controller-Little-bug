# ComfyUI MarkHub 上传指南

**版本:** 1.1.0  
**日期:** 2026-03-21

---

## 📦 发布前检查清单

### ✅ 已完成
- [x] 清理敏感信息（API keys, passwords, URLs）
- [x] 创建 config.example.json（占位符版本）
- [x] 创建中英文 README
- [x] 创建 LICENSE 文件
- [x] 创建 .gitignore
- [x] 创建 clawhub.json
- [x] 创建 RELEASE_NOTES.md

### ⚠️ 用户需要配置
- [ ] 登录 ClawHub 账号
- [ ] 登录 GitHub 账号
- [ ] 配置 Git 凭据

---

## 🚀 上传到 ClawHub

### 方法 1: 使用 CLI（推荐）

```bash
# 1. 登录 ClawHub
clawhub login

# 2. 发布技能
clawhub publish /Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub \
  --changelog "v1.1.0 - Added 6+ platform support, auto detection, failover, multi-language docs"

# 3. 验证发布
clawhub view comfyui-markhub
```

### 方法 2: 网页上传

1. 访问 https://clawhub.ai
2. 登录账号
3. 点击 "Create New Skill"
4. 上传技能文件夹
5. 填写元数据：
   - Name: comfyui-markhub
   - Version: 1.1.0
   - Description: Universal AI Creation System
   - Tags: comfyui, ai-art, cloud-platform

---

## 🐙 上传到 GitHub

### 步骤 1: 创建仓库

```bash
# 在 GitHub 上创建新仓库
# 访问：https://github.com/new
# 仓库名：comfyui-markhub
# 可见性：Public
# 不要初始化（我们已经本地初始化了）
```

### 步骤 2: 推送代码

```bash
cd /Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub

# 提交代码
git add -A
git commit -m "Initial release v1.1.0 - Universal AI Creation System"

# 重命名分支为 main（可选）
git branch -M main

# 添加远程仓库（替换为你的 GitHub 用户名）
git remote add origin https://github.com/yun520-1/comfyui-markhub.git

# 推送
git push -u origin main
```

### 步骤 3: 创建 Release

```bash
# 在 GitHub 网页上：
# 1. 访问 https://github.com/yun520-1/comfyui-markhub/releases
# 2. 点击 "Create a new release"
# 3. Tag version: v1.1.0
# 4. Release title: ComfyUI MarkHub v1.1.0
# 5. Description: 复制 RELEASE_NOTES.md 内容
# 6. 点击 "Publish release"
```

---

## 📝 GitHub 仓库描述

### 仓库名称
```
comfyui-markhub
```

### 简短描述
```
Universal AI Creation System for ComfyUI - Support for all major cloud platforms (RunPod, Vast.ai, Massed, Thinking Machines, Local)
```

### 详细 README 顶部
```markdown
# ComfyUI MarkHub v1.1

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-6+-orange.svg)](PLATFORM_GUIDE.md)

**Universal AI Creation System - Support for All Major ComfyUI Cloud Platforms**

- 🌐 6+ Platform Support (RunPod, Vast.ai, Massed, Thinking Machines, Local)
- 🔍 Auto Platform Detection
- 🔄 Automatic Failover
- 👁️ Real-time Task Monitoring
- 💾 Auto Save to Local
- 🤖 Smart Workflow Selection

## Quick Start

```bash
# Install
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh

# Usage
python3 markhub_core.py -p "A beautiful woman" --auto
```

## Documentation

- [README.md](README.md) - English
- [README_CN.md](README.md) - 中文
- [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) - Platform Configuration
```

---

## 🔒 安全检查

### 发布前确认

```bash
# 检查是否有敏感信息
cd /Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub

# 搜索 API keys
grep -r "api_key\|api_token\|secret\|password" *.json *.py *.md 2>/dev/null | grep -v "example\|YOUR_\|your-"

# 搜索具体 URL
grep -r "wp08.unicorn.org.cn" *.py *.json *.md 2>/dev/null

# 应该没有输出（除了示例文件）
```

### 已清理的项目

- ✅ config.json → config.example.json（占位符）
- ✅ markhub_core.py 中的硬编码 URL 已替换
- ✅ 无个人 API keys
- ✅ 无个人密码
- ✅ 无私人服务器地址

---

## 📊 发布后验证

### ClawHub 验证

```bash
# 搜索技能
clawhub search comfyui-markhub

# 查看技能详情
clawhub view comfyui-markhub

# 安装测试
clawhub install comfyui-markhub
```

### GitHub 验证

```bash
# 克隆测试
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
python3 markhub_core.py -p "test" --list-platforms
```

---

## 🎯 标签和分类

### ClawHub 标签
```
comfyui, ai-art, image-generation, video-generation, 
cloud-platform, runpod, vast-ai, stable-diffusion, 
ai-creation, multi-platform
```

### GitHub Topics
```
comfyui
ai-art
image-generation
video-generation
cloud-computing
runpod
vast-ai
stable-diffusion
ai-tools
python
```

---

## 📈 推广建议

### 发布渠道

1. **ClawHub** - 主要发布平台
2. **GitHub** - 代码托管和版本控制
3. **Reddit** - r/StableDiffusion, r/aiArt
4. **Discord** - ComfyUI 官方 Discord
5. **Twitter/X** - #ComfyUI #AIArt #StableDiffusion

### 发布文案示例

```
🎉 Released ComfyUI MarkHub v1.1.0!

✨ Features:
- 6+ cloud platform support (RunPod, Vast.ai, etc.)
- Auto platform detection
- Real-time task monitoring
- Multi-language docs

🔗 GitHub: https://github.com/yun520-1/comfyui-markhub
🔗 ClawHub: https://clawhub.ai/yun520-1/comfyui-markhub

#ComfyUI #AIArt #StableDiffusion #AI
```

---

## 📄 必需文件清单

发布前确认以下文件存在：

- [x] markhub_core.py (核心脚本)
- [x] install.sh (安装脚本)
- [x] config.example.json (配置模板)
- [x] README.md (英文文档)
- [x] README.md (中文文档)
- [x] SKILL.md (技能文档)
- [x] PLATFORM_GUIDE.md (平台指南)
- [x] LICENSE (许可证)
- [x] .gitignore (Git 忽略规则)
- [x] clawhub.json (ClawHub 元数据)
- [x] RELEASE_NOTES.md (发布说明)

---

## 🆘 常见问题

### Q: ClawHub 登录失败
A: 检查网络连接，或尝试网页上传

### Q: GitHub 推送失败
A: 确认仓库已创建，检查 Git 凭据

### Q: 发布后找不到技能
A: 等待几分钟让索引更新，或刷新页面

---

**准备完成时间:** 2026-03-21 12:15  
**状态:** ✅ 准备就绪，等待上传
