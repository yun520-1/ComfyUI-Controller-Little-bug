# 网页上传指南 - ComfyUI MarkHub v1.1.0

**创建时间:** 2026-03-21 12:35  
**版本:** 1.1.0

---

## 🚀 快速上传（2 步完成）

### 步骤 1: 上传到 GitHub

#### 1.1 创建仓库

1. **访问:** https://github.com/new
2. **填写信息:**
   - **Repository name:** `comfyui-markhub`
   - **Description:** `Universal AI Creation System for ComfyUI - Support for all major cloud platforms`
   - **Visibility:** ✅ Public (公开)
   - ❌ 不要勾选 "Add a README file"
   - ❌ 不要勾选 ".gitignore"
   - ❌ 不要勾选 "Choose a license"

3. **点击:** "Create repository"

#### 1.2 推送代码

在终端执行以下命令：

```bash
cd /Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub

# 配置 Git 用户信息（首次使用需要）
git config user.name "yun520-1"
git config user.email "yun520-1@users.noreply.github.com"

# 添加远程仓库（替换为你的 GitHub 用户名）
git remote add origin https://github.com/yun520-1/comfyui-markhub.git

# 推送代码
git branch -M main
git push -u origin main
```

**如果遇到认证错误：**

使用 Personal Access Token：
```bash
# 1. 访问：https://github.com/settings/tokens
# 2. 点击 "Generate new token (classic)"
# 3. 选择 scopes: repo, workflow
# 4. 生成后复制 token
# 5. 使用 token 推送：
git remote set-url origin https://<YOUR_TOKEN>@github.com/yun520-1/comfyui-markhub.git
git push -u origin main
```

#### 1.3 创建 Release

1. **访问:** https://github.com/yun520-1/comfyui-markhub/releases
2. **点击:** "Create a new release"
3. **填写:**
   - **Tag version:** `v1.1.0`
   - **Release title:** `ComfyUI MarkHub v1.1.0`
   - **Description:** 复制以下内容：

```markdown
## 🎉 ComfyUI MarkHub v1.1.0

Universal AI Creation System - Support for all major ComfyUI cloud platforms

### ✨ Features

- 🌐 6+ Platform Support (RunPod, Vast.ai, Massed, Thinking Machines, Local)
- 🔍 Auto Platform Detection
- 🔄 Automatic Failover
- 👁️ Real-time Task Monitoring
- 💾 Auto Save to Local
- 🤖 Smart Workflow Selection
- 📚 Multi-language Docs (CN/EN)

### 🚀 Quick Start

```bash
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
python3 markhub_core.py -p "A beautiful woman" --auto
```

### 📖 Documentation

- [README.md](README.md) - English
- [README_CN.md](README.md) - 中文
- [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) - Platform Configuration

### 🔧 Installation

```bash
# Via ClawHub
openclaw skills install comfyui-markhub

# Or manual
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
```

### 📄 License

MIT License
```

4. **点击:** "Publish release"

---

### 步骤 2: 上传到 ClawHub

#### 2.1 登录 ClawHub

1. **访问:** https://clawhub.ai
2. **点击:** "Login" 或 "Sign In"
3. **使用 GitHub 账号登录**（推荐）或邮箱登录

#### 2.2 发布技能

**方法 A: 使用发布向导**

1. **访问:** https://clawhub.ai/create
2. **点击:** "Create New Skill"
3. **填写信息:**

| 字段 | 填写内容 |
|------|----------|
| **Name** | `comfyui-markhub` |
| **Display Name** | `ComfyUI MarkHub` |
| **Version** | `1.1.0` |
| **Description** | `Universal AI Creation System - Support for all major ComfyUI cloud platforms (RunPod, Vast.ai, Massed, Thinking Machines, Local)` |
| **Author** | `yun520-1` |
| **License** | `MIT` |
| **Tags** | `comfyui, ai-art, image-generation, video-generation, cloud-platform, runpod, vast-ai` |

4. **上传文件:**
   - 选择文件夹：`/Users/apple/.jvs/.openclaw/workspace/skills/comfyui-markhub`
   - 或直接拖拽整个文件夹

5. **点击:** "Publish" 或 "Submit"

**方法 B: 从 GitHub 导入**

1. **访问:** https://clawhub.ai/import
2. **选择:** "Import from GitHub"
3. **授权 ClawHub 访问 GitHub**
4. **选择仓库:** `yun520-1/comfyui-markhub`
5. **选择分支:** `main`
6. **点击:** "Import"
7. **填写元数据**（同方法 A）
8. **点击:** "Publish"

#### 2.3 验证发布

1. **访问:** https://clawhub.ai/yun520-1/comfyui-markhub
2. **检查:**
   - ✅ 技能信息正确
   - ✅ 文件完整
   - ✅ 文档可访问
   - ✅ 安装命令可用

---

## ✅ 上传后验证

### GitHub 验证

```bash
# 克隆测试
cd /tmp
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
ls -la
# 应该看到所有文件
```

**检查清单:**
- [ ] 仓库可见（Public）
- [ ] 所有文件已上传
- [ ] README 显示正常
- [ ] LICENSE 存在
- [ ] Release v1.1.0 已创建

### ClawHub 验证

```bash
# 搜索技能
clawhub search comfyui-markhub

# 查看技能
clawhub view comfyui-markhub

# 测试安装
clawhub install comfyui-markhub
```

**检查清单:**
- [ ] 技能可搜索
- [ ] 详情页显示正常
- [ ] 安装命令可用
- [ ] 文档完整

---

## 📊 发布后任务

### 立即执行（发布后 1 小时内）

- [ ] 在 GitHub 给仓库加 Star
- [ ] 在 ClawHub 给技能点赞
- [ ] 分享到社交媒体

### 24 小时内

- [ ] 回复用户 Issues
- [ ] 收集用户反馈
- [ ] 更新 README（如有问题）

### 每周

- [ ] 检查 Issues 和 PRs
- [ ] 更新文档
- [ ] 性能优化

---

## 📢 宣传模板

### Twitter/X

```
🎉 Released ComfyUI MarkHub v1.1.0!

✨ Features:
- 6+ cloud platform support (RunPod, Vast.ai, etc.)
- Auto platform detection
- Real-time task monitoring
- Multi-language docs

🔗 GitHub: https://github.com/yun520-1/comfyui-markhub
🔗 ClawHub: https://clawhub.ai/yun520-1/comfyui-markhub

#ComfyUI #AIArt #StableDiffusion #AI #OpenSource
```

### Reddit (r/StableDiffusion)

**Title:**
```
[Release] ComfyUI MarkHub v1.1.0 - Universal Multi-Platform AI Creation System
```

**Body:**
```markdown
Hi everyone! I'm excited to share ComfyUI MarkHub v1.1.0, a tool that supports 6+ ComfyUI cloud platforms with auto-detection and failover.

✨ Features:
- 6+ platform support (RunPod, Vast.ai, Massed, Thinking Machines, Local)
- Auto platform detection
- Real-time task monitoring
- Auto save to local
- Smart workflow selection
- Multi-language docs (CN/EN)

🚀 Quick Start:
```bash
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
python3 markhub_core.py -p "A beautiful woman" --auto
```

🔗 GitHub: https://github.com/yun520-1/comfyui-markhub
🔗 ClawHub: https://clawhub.ai/yun520-1/comfyui-markhub

Would love to hear your feedback! 😊
```

### Discord (ComfyUI Server)

```
🎉 New Release: ComfyUI MarkHub v1.1.0

Support for 6+ cloud platforms (RunPod, Vast.ai, Massed, etc.) with auto-detection!

GitHub: https://github.com/yun520-1/comfyui-markhub
ClawHub: https://clawhub.ai/yun520-1/comfyui-markhub

Features:
- Multi-platform support
- Auto detection
- Task monitoring
- Auto save

Feedback welcome! 🙏
```

---

## 🆘 常见问题

### Q1: GitHub 推送失败 "Authentication failed"

**解决:**
```bash
# 使用 Personal Access Token
git remote set-url origin https://<TOKEN>@github.com/yun520-1/comfyui-markhub.git
git push -u origin main
```

### Q2: ClawHub 上传失败 "Invalid package"

**解决:**
- 确认包含 `clawhub.json` 文件
- 确认 `config.example.json` 存在
- 不要上传 `config.json`（包含敏感信息）

### Q3: 技能搜索不到

**解决:**
- 等待 5-10 分钟让索引更新
- 刷新页面
- 检查技能是否 Public

### Q4: 安装失败

**解决:**
```bash
# 手动安装测试
cd /tmp
git clone https://github.com/yun520-1/comfyui-markhub.git
cd comfyui-markhub
bash install.sh
python3 markhub_core.py -p "test" --list-platforms
```

---

## 📈 统计数据

| 项目 | 目标 |
|------|------|
| GitHub Stars | 100+ (首月) |
| ClawHub Downloads | 500+ (首月) |
| Issues Resolved | 100% |
| Response Time | <24h |

---

## 🔗 相关链接

- **GitHub:** https://github.com/yun520-1/comfyui-markhub
- **ClawHub:** https://clawhub.ai/yun520-1/comfyui-markhub
- **Issues:** https://github.com/yun520-1/comfyui-markhub/issues
- **Releases:** https://github.com/yun520-1/comfyui-markhub/releases

---

**最后更新:** 2026-03-21 12:35  
**状态:** ✅ 准备上传
