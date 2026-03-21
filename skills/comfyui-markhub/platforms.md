# 支持的平台配置指南

ComfyUI MarkHub v1.0 支持所有主流 ComfyUI 云平台。

## 预定义平台

### 1. 自定义平台 (Custom)
**默认配置**
```json
{
  "platform": "custom",
  "base_url": "https://wp08.unicorn.org.cn:40001",
  "verify_ssl": false
}
```

### 2. RunPod
**特点**: GPU 租赁平台，按需付费

**配置步骤**:
1. 登录 https://runpod.io
2. 部署 ComfyUI 模板
3. 获取 Pod ID 和 API Key
4. 配置:
```json
{
  "platform": "runpod",
  "pod_id": "your-pod-id",
  "api_token": "your-api-key"
}
```

**URL 格式**: `https://api.runpod.ai/v2/{pod_id}/comfyui`

### 3. Vast.ai
**特点**: 去中心化 GPU 市场，价格优惠

**配置步骤**:
1. 登录 https://vast.ai
2. 租用实例并部署 ComfyUI
3. 获取 Instance ID 和 API Key
4. 配置:
```json
{
  "platform": "vast",
  "instance_id": "your-instance-id",
  "api_token": "your-api-key"
}
```

**URL 格式**: `https://console.vast.ai/api/v2/comfyui/{instance_id}`

### 4. Massed Compute
**特点**: 专业 AI 计算平台

**配置**:
```json
{
  "platform": "massed",
  "base_url": "https://massedcompute.com:40001",
  "verify_ssl": false
}
```

### 5. Thinking Machines
**特点**: 企业级 AI 平台

**配置**:
```json
{
  "platform": "thinkingmachines",
  "base_url": "https://api.thinkingmachines.ai/comfyui",
  "api_token": "your-api-token"
}
```

### 6. 本地 ComfyUI (Local)
**特点**: 本地部署，完全控制

**配置**:
```json
{
  "platform": "local",
  "base_url": "http://127.0.0.1:8188",
  "verify_ssl": false
}
```

## 自动检测

启用自动检测平台:
```bash
python3 markhub_core.py -p "test" --platform auto
```

系统会自动尝试连接所有预定义平台，选择第一个可用的。

## 手动指定平台

```bash
# 使用 RunPod
python3 markhub_core.py -p "..." --platform runpod

# 使用 Vast.ai
python3 markhub_core.py -p "..." --platform vast

# 使用本地
python3 markhub_core.py -p "..." --platform local
```

## 平台对比

| 平台 | 价格 | 易用性 | 推荐场景 |
|------|------|--------|----------|
| RunPod | 中等 | ⭐⭐⭐⭐⭐ | 初学者、快速部署 |
| Vast.ai | 低廉 | ⭐⭐⭐⭐ | 预算有限、高级用户 |
| Massed | 中等 | ⭐⭐⭐⭐ | 企业用户 |
| Thinking Machines | 较高 | ⭐⭐⭐⭐⭐ | 企业级应用 |
| 本地 | 免费 | ⭐⭐⭐ | 开发测试、有 GPU |

## 平台切换

编辑 `config.json`:
```json
{
  "platform": {
    "type": "runpod",  // 改为其他平台
    "runpod": {
      "pod_id": "xxx",
      "api_token": "xxx"
    }
  }
}
```

## 多平台配置

可以配置多个平台，自动故障转移:
```json
{
  "platforms": {
    "auto_detect": true,
    "fallback_order": ["runpod", "vast", "local"],
    "health_check_interval": 60
  }
}
```

## 安全建议

1. **API Token** - 不要提交到版本控制
2. **SSL 验证** - 生产环境建议启用
3. **访问控制** - 使用防火墙限制访问
4. **定期更新** - 保持 ComfyUI 最新版本

## 故障排除

### 连接失败
```bash
# 测试平台连接
curl -k https://your-platform:40001/system_stats
```

### 认证失败
```bash
# 检查 API Token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-platform:40001/system_stats
```

### 平台检测
```bash
# 查看详细日志
python3 markhub_core.py -p "test" --platform auto --verbose
```
