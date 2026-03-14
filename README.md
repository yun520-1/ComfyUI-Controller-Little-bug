# ComfyUI 智能控制器 🎨

一个命令行工具，用于控制 ComfyUI 进行 AI 图像/视频生成。

## 功能

### 基础功能
- ✅ 文生图（txt2img）
- ✅ 图生图（img2img，需导入工作流）
- ✅ 实时监控生成进度
- ✅ 自动下载生成的图片
- ✅ 查看队列状态
- ✅ 查看可用模型列表

### 🆕 智能功能（增强版）
- 🤖 **AI 自动生成提示词** - 输入主题，自动优化成专业提示词
- 🎬 **视频生成支持** - 支持生成短视频（需 AnimateDiff）
- 📁 **智能文件整理** - 自动分类保存（人物/风景/赛博朋克等 10 类）
- 📦 **批量任务** - 一次跑多个主题，自动生成报告
- 📊 **元数据记录** - 每个文件保存 JSON 元数据（提示词/参数/时间）

---

## 安装依赖

```bash
cd /home/admin/openclaw/workspace/comfyui-controller
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 启动 ComfyUI

确保 ComfyUI 正在运行并监听网络：

```bash
cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

---

## 🚀 快速入门（推荐新手）

### 1️⃣ AI 自动生成提示词 + 跑图

```bash
# 输入主题，AI 自动优化提示词并生成
python3 comfyui_smart_controller.py --subject "一个美丽的女孩" --style portrait

# 指定风格
python3 comfyui_smart_controller.py --subject "赛博朋克城市" --style cyberpunk
```

### 2️⃣ 批量生成（一次跑多个）

```bash
# 使用示例主题文件（10 个预设主题）
python3 comfyui_smart_controller.py --batch sample_subjects.txt --style realistic

# 批量生成视频
python3 comfyui_smart_controller.py --batch sample_subjects.txt --video
```

### 3️⃣ 生成视频

```bash
python3 comfyui_smart_controller.py --subject "赛博朋克城市" --video
```

### 4️⃣ 整理已有文件

```bash
python3 comfyui_smart_controller.py --organize
```

---

## 📝 传统方式（老用户）

### 1. 快速生成（文生图）

```bash
python3 comfyui_controller.py --prompt "一个美丽的女孩，高清，精致" --negative "模糊，低质量"
```

### 2. 指定模型和参数

```bash
python3 comfyui_controller.py \
    --prompt "赛博朋克城市，霓虹灯，未来感" \
    --model "v1-5-pruned-emaonly.ckpt" \
    --width 768 --height 512 \
    --steps 30 --cfg 7 \
    --seed 12345
```

### 3. 使用自定义工作流

```bash
python3 comfyui_controller.py --workflow my_workflow.json
```

### 4. 查看队列状态

```bash
python3 comfyui_controller.py --queue
```

### 5. 查看可用模型

```bash
python3 comfyui_controller.py --models
```

---

## 📊 智能控制器参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--subject, -s` | 主题（AI 自动生成提示词） | 必填 |
| `--style` | 风格 | realistic |
| `--batch` | 批量主题文件（每行一个） | - |
| `--video` | 生成视频 | False |
| `--width` | 宽度 | 512 |
| `--height` | 高度 | 512 |
| `--steps` | 采样步数 | 20 |
| `--organize` | 整理已有文件 | False |
| `--server` | ComfyUI 服务器 | 127.0.0.1:8188 |

### 可选风格

- `realistic` - 写实风格
- `portrait` - 人像肖像
- `landscape` - 风景自然
- `cyberpunk` - 赛博朋克
- `anime` - 动漫二次元
- `fantasy` - 奇幻魔法
- `scifi` - 科幻太空

---

## 📁 文件整理结构

```
/home/admin/Downloads/
├── comfyui_output/              # 原始输出（所有文件）
└── comfyui_organized/           # 智能分类整理
    ├── portrait/                # 人物肖像
    │   └── 2026-03-14/
    │       ├── 20260314_210500_美丽的女孩_xxx.png
    │       └── 20260314_210500_美丽的女孩_xxx.json  (元数据)
    ├── landscape/               # 风景
    ├── cyberpunk/               # 赛博朋克
    ├── anime/                   # 动漫
    ├── fantasy/                 # 奇幻
    ├── scifi/                   # 科幻
    ├── architecture/            # 建筑
    ├── animal/                  # 动物
    ├── food/                    # 美食
    └── uncategorized/           # 未分类
```

### 元数据 JSON 示例

```json
{
  "prompt": "一个年轻女性，肖像风格，柔和光线，虚化背景，高清，精致，高质量",
  "negative": "模糊，低质量，变形，丑陋，多余的手指",
  "category": "portrait",
  "subject": "一个美丽的女孩",
  "timestamp": "2026-03-14T21:05:00",
  "seed": 123456789
}
```

---

## 💡 实用示例

### 示例 1：生成一组人像

```bash
python3 comfyui_smart_controller.py \
    --subject "一个 25 岁亚洲女性，职场精英，西装" \
    --style portrait \
    --width 512 --height 768 \
    --steps 25
```

### 示例 2：批量生成 10 个赛博朋克场景

```bash
# 创建主题文件
cat > cyberpunk_subjects.txt << EOF
赛博朋克城市夜景
未来科技实验室
霓虹灯街道
机器人市场
太空港口
EOF

# 批量生成
python3 comfyui_smart_controller.py \
    --batch cyberpunk_subjects.txt \
    --style cyberpunk \
    --width 768 --height 512
```

### 示例 3：生成短视频

```bash
python3 comfyui_smart_controller.py \
    --subject "海浪拍打礁石" \
    --video \
    --width 512 --height 512
```

### 示例 4：Python API 调用

```python
from comfyui_smart_controller import ComfyUIIntelligentController

controller = ComfyUIIntelligentController("127.0.0.1:8188")

if controller.check_connection():
    # 一键全自动
    result = controller.auto_generate(
        subject="一个美丽的女孩",
        style="portrait",
        width=512,
        height=768,
        steps=25,
        is_video=False
    )
    
    if result['success']:
        print(f"生成完成！")
        print(f"分类：{result['category']}")
        print(f"文件：{result['files']}")
        print(f"提示词：{result['prompt']}")
```

---

## 🎯 完整工作流示例

```bash
# 1. 确保 ComfyUI 运行
cd /path/to/ComfyUI && python main.py --listen 0.0.0.0 --port 8188

# 2. 批量生成 10 个主题
cd /home/admin/openclaw/workspace/comfyui-controller
python3 comfyui_smart_controller.py --batch sample_subjects.txt --style realistic

# 3. 等待完成后整理文件
python3 comfyui_smart_controller.py --organize

# 4. 查看生成的报告
cat /home/admin/Downloads/comfyui_organized/batch_report_*.json
```

---

## ⚠️ 注意事项

### 视频生成
- 需要 ComfyUI 安装 AnimateDiff 或类似视频节点
- 生成时间较长（每帧都需要渲染）
- 建议先用小尺寸测试

### 批量任务
- 建议任务间添加延迟，避免队列拥堵
- 大量任务建议分批执行
- 定期检查生成报告

### 文件管理
- 原始文件保存在 `comfyui_output/`
- 分类整理在 `comfyui_organized/`
- 元数据 JSON 方便后续检索

---

## 🔧 常见问题

### Q: 连接失败
A: 确保 ComfyUI 已启动并使用 `--listen 0.0.0.0` 参数

### Q: 找不到模型
A: 使用 `--models` 查看可用模型名称，确保模型文件在 ComfyUI 的 `models/checkpoints/` 目录

### Q: WebSocket 连接超时
A: 检查防火墙设置，确保 8188 端口可访问

### Q: 视频生成失败
A: 确保安装了 AnimateDiff 自定义节点，并加载了相应的运动模型

### Q: 提示词生成不理想
A: 可以手动编辑 `PROMPT_TEMPLATES` 字典，自定义提示词模板

---

## 📄 许可证

MIT License

---

## 🔥 工作流管理功能（NEW!）

### 工作流管理器

使用 `workflow_manager.py` 管理工作流库：

```bash
# 上传工作流
python3 workflow_manager.py upload --file my_workflow.json --name "我的 workflow" --category txt2img

# 查看所有工作流
python3 workflow_manager.py list

# 查看特定分类的工作流
python3 workflow_manager.py list --category video

# 查看工作流详情
python3 workflow_manager.py show --id txt2img_my_workflow_20260314_220000

# 删除工作流
python3 workflow_manager.py delete --id txt2img_my_workflow_20260314_220000

# 查看统计
python3 workflow_manager.py stats
```

### 自动工作流执行器

使用 `auto_workflow_runner.py` 上传并自动执行工作流：

```bash
# 上传工作流并立即执行
python3 auto_workflow_runner.py upload_run \
    --file my_workflow.json \
    --name "精美肖像" \
    --category portrait \
    --prompt "一个美丽的女孩，高清，精致" \
    --negative "模糊，低质量" \
    --steps 30 \
    --cfg 7 \
    --width 512 \
    --height 768

# 执行已上传的工作流
python3 auto_workflow_runner.py run \
    --id txt2img_my_workflow_20260314_220000 \
    --prompt "赛博朋克城市，霓虹灯" \
    --steps 25

# 批量执行多个工作流
python3 auto_workflow_runner.py batch \
    --ids "workflow_id_1,workflow_id_2,workflow_id_3" \
    --prompt "提示词 1|提示词 2|提示词 3" \
    --steps 20

# 查看所有工作流
python3 auto_workflow_runner.py list
```

### 工作流分类

支持以下分类：
- `txt2img` - 文生图
- `img2img` - 图生图
- `video` - 视频生成
- `upscale` - 高清放大
- `controlnet` - ControlNet
- `face` - 人脸增强
- `custom` - 自定义

### Python API 使用

```python
from auto_workflow_runner import AutoWorkflowRunner
from workflow_manager import WorkflowManager

# 初始化
runner = AutoWorkflowRunner("127.0.0.1:8188")

# 检查连接
if runner.check_connection():
    # 上传并执行
    result = runner.upload_and_run(
        workflow_path="my_workflow.json",
        prompt="一个美丽的女孩",
        category="portrait",
        steps=30,
        cfg=7,
        width=512,
        height=768
    )
    
    if result['success']:
        print(f"生成完成！文件：{result['files']}")
    
    # 执行已上传的工作流
    result = runner.run_workflow(
        workflow_id="txt2img_my_workflow_20260314_220000",
        prompt="赛博朋克城市",
        steps=25
    )
    
    # 批量执行
    results = runner.batch_run(
        workflow_ids=["id1", "id2", "id3"],
        prompts=["提示词 1", "提示词 2", "提示词 3"],
        steps=20
    )

# 工作流管理
manager = WorkflowManager()

# 上传
manager.upload_workflow("workflow.json", name="测试", category="txt2img")

# 列出所有
workflows = manager.list_workflows()

# 获取详情
workflow = manager.get_workflow("workflow_id")

# 加载工作流数据
workflow_data = manager.load_workflow("workflow_id")

# 替换提示词
modified = manager.replace_prompts(workflow_data, "新提示词", "负面提示词")

# 更新参数
modified = manager.update_parameters(workflow_data, steps=30, cfg=8, width=768)

# 删除
manager.delete_workflow("workflow_id")
```

### 完整工作流示例

```bash
# 1. 从 ComfyUI 导出工作流
# 在 ComfyUI 界面点击 "保存 (API 格式)" 导出 workflow.json

# 2. 上传并测试
python3 auto_workflow_runner.py upload_run \
    --file workflow.json \
    --name "测试工作流" \
    --category txt2img \
    --prompt "测试提示词" \
    --steps 20

# 3. 如果效果满意，以后可以直接使用 ID 执行
python3 auto_workflow_runner.py run \
    --id txt2img_测试工作流_20260314_220000 \
    --prompt "新的提示词"

# 4. 批量生成不同风格
python3 auto_workflow_runner.py batch \
    --ids "id1,id2,id3" \
    --prompt "肖像风格|风景风格|赛博朋克风格" \
    --steps 25
```

### 工作流目录结构

```
comfyui-controller/
└── workflows/
    ├── registry.json              # 工作流注册表
    ├── txt2img/                   # 文生图工作流
    │   └── txt2img_xxx.json
    ├── img2img/                   # 图生图工作流
    ├── video/                     # 视频工作流
    ├── upscale/                   # 放大工作流
    ├── controlnet/                # ControlNet 工作流
    ├── face/                      # 人脸增强工作流
    └── custom/                    # 自定义工作流
```

---
