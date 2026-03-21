# 🚀 ComfyUI MarkHub v1.1.0 快速上传指南

**更新时间:** 2026-03-21 12:40

---

## ✅ 浏览器已打开！

### 步骤 1: GitHub 上传（当前页面）

**你现在的页面:** https://github.com/new

**填写信息:**
```
Repository name: comfyui-markhub
Description:     Universal AI Creation System for ComfyUI - Support for all major cloud platforms
Visibility:      ✅ Public (公开)
```

**不要勾选:**
- ❌ Add a README file
- ❌ .gitignore
- ❌ Choose a license

**点击:** "Create repository"

**创建完成后，在终端执行:**
```bash
cd /Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub

# 添加远程仓库（替换为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/comfyui-markhub.git

# 推送代码
git branch -M main
git push -u origin main
```

---

### 步骤 2: ClawHub 上传

**打开页面:** https://clawhub.ai/create

**填写信息:**
| 字段 | 内容 |
|------|------|
| **Name** | `comfyui-markhub` |
| **Display Name** | `ComfyUI MarkHub` |
| **Version** | `1.1.0` |
| **Description** | `Universal AI Creation System - Support for all major ComfyUI cloud platforms` |
| **Author** | `yun520-1` |
| **License** | `MIT` |
| **Tags** | `comfyui, ai-art, image-generation, video-generation, cloud-platform` |

**上传:** 选择文件夹 `/Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub`

**点击:** "Publish"

---

## 📋 一键执行命令

### GitHub 推送
```bash
cd ~/.jvs/.openclaw/workspace/skills/comfyui-markhub
git remote add origin https://github.com/yun520-1/comfyui-markhub.git
git branch -M main
git push -u origin main
```

### 验证上传
```bash
# GitHub
open https://github.com/yun520-1/comfyui-markhub

# ClawHub
open https://clawhub.ai/yun520-1/comfyui-markhub
```

---

## 🎯 快速检查清单

### GitHub
- [ ] 仓库已创建
- [ ] 代码已推送
- [ ] README 显示正常
- [ ] Release v1.1.0 已创建

### ClawHub
- [ ] 技能已发布
- [ ] 详情页正常
- [ ] 安装命令可用

---

## 📢 发布后宣传

### Twitter/X
```
🎉 Released ComfyUI MarkHub v1.1.0!

✨ 6+ platform support
🔍 Auto detection
👁️ Real-time monitoring
📚 Multi-language docs

🔗 https://github.com/yun520-1/comfyui-markhub

#ComfyUI #AIArt #StableDiffusion
```

### Reddit
```
[Release] ComfyUI MarkHub v1.1.0 - Universal Multi-Platform AI Creation System

Supports 6+ cloud platforms (RunPod, Vast.ai, Massed, etc.) with auto-detection!

GitHub: https://github.com/yun520-1/comfyui-markhub
```

---

## 🆘 遇到问题？

### 推送失败 "Authentication failed"
```bash
# 使用 Personal Access Token
# 1. 访问：https://github.com/settings/tokens
# 2. 生成 token (选择 repo, workflow)
# 3. 使用 token 推送
git remote set-url origin https://<TOKEN>@github.com/yun520-1/comfyui-markhub.git
git push -u origin main
```

### ClawHub 上传失败
- 确认包含 `clawhub.json`
- 确认 `config.example.json` 存在
- 不要上传 `config.json`

---

**需要帮助？** 告诉我哪一步遇到问题！
