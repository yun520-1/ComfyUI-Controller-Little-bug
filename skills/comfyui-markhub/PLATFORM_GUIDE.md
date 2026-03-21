# 全平台配置指南

ComfyUI MarkHub v1.0 支持所有主流 ComfyUI 部署平台。

## 🌐 支持的平台

### 预定义平台 (6 个)

| 平台 ID | 名称 | 类型 | 认证 | 推荐场景 |
|--------|------|------|------|----------|
| `custom` | 自定义平台 | 云端 | 可选 | 默认配置 |
| `runpod` | RunPod | 云端 | 必需 | ⭐⭐⭐⭐⭐ 初学者 |
| `vast` | Vast.ai | 云端 | 必需 | ⭐⭐⭐⭐ 性价比 |
| `massed` | Massed Compute | 云端 | 可选 | ⭐⭐⭐⭐ 企业 |
| `thinkingmachines` | Thinking Machines | 云端 | 必需 | ⭐⭐⭐⭐⭐ 企业级 |
| `local` | 本地 ComfyUI | 本地 | 无需 | ⭐⭐⭐ 开发测试 |

## 🚀 快速配置

### 方法 1: 自动检测（推荐）
```bash
python3 markhub_core.py -p "A beautiful woman" --platform auto
```
系统会自动检测并连接可用的平台。

### 方法 2: 手动指定
```bash
# 使用 RunPod
python3 markhub_core.py -p "..." --platform runpod

# 使用 Vast.ai
python3 markhub_core.py -p "..." --platform vast

# 使用本地
python3 markhub_core.py -p "..." --platform local
```

### 方法 3: 修改配置文件
编辑 `config.json`:
```json
{
  "platform": {
    "type": "runpod",
    "runpod": {
      "pod_id": "your-pod-id",
      "api_token": "your-api-key"
    }
  }
}
```

## 📋 各平台详细配置

### 1. RunPod ⭐⭐⭐⭐⭐
**适合**: 初学者、快速部署

**步骤**:
1. 注册 https://runpod.io
2. 部署 ComfyUI 模板
3. 复制 Pod ID 和 API Key
4. 配置:
```json
{
  "platform": "runpod",
  "runpod": {
    "pod_id": "abc123xyz",
    "api_token": "your-api-key-here"
  }
}
```

**价格**: $0.35-0.70/小时

### 2. Vast.ai ⭐⭐⭐⭐
**适合**: 预算有限、高级用户

**步骤**:
1. 注册 https://vast.ai
2. 租用 GPU 实例
3. 部署 ComfyUI
4. 配置:
```json
{
  "platform": "vast",
  "vast": {
    "instance_id": "12345",
    "api_token": "your-api-key"
  }
}
```

**价格**: $0.10-0.40/小时

### 3. Massed Compute ⭐⭐⭐⭐
**适合**: 企业用户

**配置**:
```json
{
  "platform": "massed",
  "massed": {
    "base_url": "https://massedcompute.com:40001"
  }
}
```

**价格**: $0.30-0.60/小时

### 4. Thinking Machines ⭐⭐⭐⭐⭐
**适合**: 企业级应用

**配置**:
```json
{
  "platform": "thinkingmachines",
  "thinkingmachines": {
    "api_token": "your-enterprise-token"
  }
}
```

**价格**: 联系销售

### 5. 本地 ComfyUI ⭐⭐⭐
**适合**: 开发测试、有 GPU

**配置**:
```json
{
  "platform": "local"
}
```

**价格**: 免费（需自备 GPU）

## 🔧 高级配置

### 多平台故障转移
```json
{
  "platforms": {
    "auto_detect": true,
    "fallback_order": ["runpod", "vast", "local"],
    "health_check_interval": 60
  }
}
```

### 自定义平台
```json
{
  "platform": "custom",
  "custom": {
    "base_url": "https://your-server.com:40001",
    "verify_ssl": false,
    "api_token": "optional-token"
  }
}
```

## 📊 平台对比

| 特性 | RunPod | Vast | Massed | Local |
|------|--------|------|--------|-------|
| 易用性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 价格 | 中等 | 低廉 | 中等 | 免费 |
| 性能 | 高 | 高 | 高 | 取决于硬件 |
| 启动时间 | 1-2 分钟 | 5-10 分钟 | 即时 | 即时 |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

## 🐛 故障排除

### 列出所有平台
```bash
python3 markhub_core.py --list-platforms
```

### 测试平台连接
```bash
# 测试 RunPod
curl -H "Authorization: Bearer TOKEN" \
  https://api.runpod.ai/v2/POD_ID/comfyui/object_info

# 测试本地
curl http://127.0.0.1:8188/object_info
```

### 查看详细日志
```bash
python3 markhub_core.py -p "test" --platform auto --verbose
```

## 💡 最佳实践

1. **开发阶段**: 使用本地 ComfyUI
2. **生产环境**: 使用 RunPod 或 Thinking Machines
3. **预算有限**: 使用 Vast.ai
4. **企业用户**: 使用 Thinking Machines 或 Massed

## 📚 相关文档

- [SKILL.md](./SKILL.md) - 完整技能文档
- [README.md](./README.md) - 快速入门
- [config.json](./config.json) - 配置示例
