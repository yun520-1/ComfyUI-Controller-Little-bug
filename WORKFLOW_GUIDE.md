# ComfyUI 工作流管理完全指南 📚

## 快速开始

### 第一步：从 ComfyUI 导出工作流

1. 在 ComfyUI 中搭建或加载你的工作流
2. 点击右侧菜单的 **"保存 (API 格式)"** 按钮
3. 保存为 `workflow.json`

⚠️ **重要**：必须使用"API 格式"，不是普通保存！

### 第二步：上传工作流

```bash
cd /Users/apple/Documents/lmd_data_root/apps/comfyui-controller

# 上传工作流
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python workflow_manager.py upload \
    --file /path/to/your/workflow.json \
    --name "我的精美肖像工作流" \
    --category txt2img \
    --description "用于生成高质量人像的工作流"
```

### 第三步：执行工作流

```bash
# 上传并立即执行
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python auto_workflow_runner.py upload_run \
    --file /path/to/your/workflow.json \
    --name "测试工作流" \
    --category txt2img \
    --prompt "一个美丽的女孩，高清，精致，专业摄影" \
    --negative "模糊，低质量，变形" \
    --steps 30 \
    --cfg 7 \
    --width 512 \
    --height 768
```

### 第四步：重复使用

上传后，以后可以直接用 ID 执行：

```bash
# 查看工作流 ID
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python auto_workflow_runner.py list

# 使用 ID 执行（无需再上传文件）
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python auto_workflow_runner.py run \
    --id txt2img_我的精美肖像工作流_20260314_220000 \
    --prompt "新的提示词" \
    --steps 25
```

---

## 详细功能说明

### 1️⃣ 工作流上传 (`workflow_manager.py upload`)

**完整参数：**

```bash
python3 workflow_manager.py upload \
    --file WORKFLOW.json \        # 必填：工作流文件路径
    --name "名称" \               # 可选：默认使用文件名
    --category 分类 \             # 可选：默认 custom
    --description "描述"          # 可选：工作流说明
```

**支持的分类：**
- `txt2img` - 文生图
- `img2img` - 图生图
- `video` - 视频生成
- `upscale` - 高清放大
- `controlnet` - ControlNet
- `face` - 人脸增强
- `custom` - 自定义（默认）

**示例：**

```bash
# 上传人像工作流
python3 workflow_manager.py upload \
    --file portrait_workflow.json \
    --name "精美肖像" \
    --category txt2img \
    --description "512x768 竖版人像，30 步，CFG 7"

# 上传视频工作流
python3 workflow_manager.py upload \
    --file video_workflow.json \
    --name "AnimateDiff 视频" \
    --category video \
    --description "16 帧，8fps，循环视频"
```

---

### 2️⃣ 查看工作流 (`workflow_manager.py list`)

```bash
# 查看所有工作流
python3 workflow_manager.py list

# 查看特定分类
python3 workflow_manager.py list --category txt2img

# 查看工作流详情
python3 workflow_manager.py show --id txt2img_精美肖像_20260314_220000

# 查看统计
python3 workflow_manager.py stats
```

---

### 3️⃣ 执行工作流 (`auto_workflow_runner.py`)

#### 方式一：上传并执行（适合首次使用）

```bash
python3 auto_workflow_runner.py upload_run \
    --file workflow.json \
    --prompt "正向提示词" \
    --negative "负面提示词" \
    --steps 30 \
    --cfg 7 \
    --width 512 \
    --height 768 \
    --batch-size 1 \
    --seed 12345
```

#### 方式二：使用已上传的工作流（适合重复使用）

```bash
python3 auto_workflow_runner.py run \
    --id txt2img_精美肖像_20260314_220000 \
    --prompt "新的提示词" \
    --steps 25 \
    --cfg 8
```

#### 方式三：批量执行（适合一次跑多个）

```bash
# 执行多个不同的工作流
python3 auto_workflow_runner.py batch \
    --ids "id1,id2,id3" \
    --prompt "提示词 1|提示词 2|提示词 3" \
    --steps 20

# 同一个工作流，不同的提示词
python3 auto_workflow_runner.py batch \
    --ids "id1,id1,id1" \
    --prompt "肖像风格|风景风格|赛博朋克风格" \
    --steps 25
```

---

### 4️⃣ 删除工作流

```bash
# 删除工作流
python3 workflow_manager.py delete --id txt2img_精美肖像_20260314_220000
```

---

## Python API 使用

### 基础示例

```python
from auto_workflow_runner import AutoWorkflowRunner
from workflow_manager import WorkflowManager

# 初始化
runner = AutoWorkflowRunner("127.0.0.1:8188")
manager = WorkflowManager()

# 检查连接
if not runner.check_connection():
    print("ComfyUI 未运行")
    exit(1)

# 1. 上传工作流
result = manager.upload_workflow(
    "my_workflow.json",
    name="测试",
    category="txt2img"
)

if result['success']:
    workflow_id = result['workflow']['id']
    print(f"上传成功：{workflow_id}")

# 2. 执行工作流
result = runner.run_workflow(
    workflow_id=workflow_id,
    prompt="一个美丽的女孩",
    negative="模糊，低质量",
    steps=30,
    cfg=7,
    width=512,
    height=768
)

if result['success']:
    print(f"生成完成！文件：{result['files']}")
else:
    print(f"生成失败：{result['error']}")

# 3. 批量执行
workflow_ids = ["id1", "id2", "id3"]
prompts = ["提示词 1", "提示词 2", "提示词 3"]

results = runner.batch_run(
    workflow_ids=workflow_ids,
    prompts=prompts,
    steps=25
)

for i, r in enumerate(results):
    status = "✅" if r['success'] else "❌"
    print(f"任务 {i+1}: {status}")
```

### 高级示例：动态替换提示词

```python
# 加载工作流
workflow = manager.load_workflow("txt2img_精美肖像_20260314_220000")

# 替换提示词
modified_workflow = manager.replace_prompts(
    workflow,
    prompt="新的正向提示词",
    negative="新的负面提示词"
)

# 更新参数
modified_workflow = manager.update_parameters(
    modified_workflow,
    steps=40,
    cfg=8,
    width=768,
    height=1024
)

# 提交任务
prompt_id = runner.queue_prompt(modified_workflow)

# 监控进度
if runner.monitor_progress(prompt_id):
    # 下载结果
    files = runner.download_and_organize(prompt_id, "portrait")
```

---

## 实用技巧

### 💡 技巧 1：工作流命名规范

建议使用统一的命名格式：
```
{分类}_{用途}_{分辨率}_{日期}.json

示例：
- txt2img_肖像_512x768_20260314.json
- img2img_线稿上色_1024x1024_20260314.json
- video_风景_512x512_16 帧_20260314.json
```

### 💡 技巧 2：建立工作流库

为常用场景创建工作流：

```bash
# 人像摄影
python3 workflow_manager.py upload --file portrait.json --name "肖像 512x768" --category txt2img

# 风景摄影
python3 workflow_manager.py upload --file landscape.json --name "风景 768x512" --category txt2img

# 二次元
python3 workflow_manager.py upload --file anime.json --name "二次元 1024x1024" --category txt2img

# 高清放大
python3 workflow_manager.py upload --file upscale.json --name "4 倍放大" --category upscale
```

### 💡 技巧 3：批量生成系列图

```bash
# 创建主题文件
cat > subjects.txt << EOF
一个 25 岁亚洲女性，职场精英
一个 30 岁欧美男性，摄影师
一个 20 岁日本少女，校服
EOF

# 批量生成
while IFS= read -r subject; do
    python3 auto_workflow_runner.py run \
        --id txt2img_肖像_512x768_20260314_220000 \
        --prompt "$subject, 高清，精致，专业摄影" \
        --steps 30
done < subjects.txt
```

### 💡 技巧 4：工作流版本管理

```bash
# 备份工作流
python3 workflow_manager.py export \
    --id txt2img_肖像_v1_20260314 \
    --output backup/portrait_v1.json

# 更新后重新上传
python3 workflow_manager.py upload \
    --file improved_portrait.json \
    --name "肖像 v2" \
    --category txt2img \
    --description "改进版：更好的光线处理"
```

---

## 文件结构

```
comfyui-controller/
├── workflow_manager.py          # 工作流管理器
├── auto_workflow_runner.py      # 自动执行器
├── comfyui_smart_controller.py  # 智能控制器
├── comfyui_controller.py        # 基础控制器
├── workflows/                   # 工作流目录
│   ├── registry.json           # 注册表
│   ├── txt2img/                # 文生图工作流
│   ├── img2img/                # 图生图工作流
│   ├── video/                  # 视频工作流
│   ├── upscale/                # 放大工作流
│   ├── controlnet/             # ControlNet 工作流
│   ├── face/                   # 人脸增强工作流
│   └── custom/                 # 自定义工作流
├── outputs/                     # 输出文件
│   ├── comfyui_output/         # 原始输出
│   └── comfyui_organized/      # 分类整理
└── README.md
```

---

## 常见问题

### Q1: 工作流上传后找不到？
A: 使用 `python3 workflow_manager.py list` 查看所有工作流和 ID

### Q2: 如何知道工作流 ID？
A: 上传成功后会显示 ID，也可以用 `list` 命令查看

### Q3: 提示词替换不生效？
A: 确保工作流中有 CLIPTextEncode 节点，这是标准提示词节点

### Q4: 批量执行时如何指定不同的提示词？
A: 使用 `|` 分隔多个提示词：`--prompt "提示词 1|提示词 2|提示词 3"`

### Q5: 如何分享工作流给别人？
A: 直接发送 workflows/{category}/{workflow_id}.json 文件

### Q6: 工作流太多如何管理？
A: 使用分类管理，定期删除不用的：`python3 workflow_manager.py delete --id xxx`

---

## 完整示例：从零开始到批量生成

```bash
# 1. 确保 ComfyUI 运行
# http://127.0.0.1:8188

# 2. 上传工作流
cd /Users/apple/Documents/lmd_data_root/apps/comfyui-controller
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python workflow_manager.py upload \
    --file my_workflow.json \
    --name "精美肖像" \
    --category txt2img

# 3. 测试执行
/Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python auto_workflow_runner.py run \
    --id txt2img_精美肖像_20260314_220000 \
    --prompt "一个美丽的女孩，高清，精致" \
    --steps 30

# 4. 批量生成 10 个不同人物
cat > subjects.txt << EOF
25 岁亚洲女性，职场精英，西装
30 岁欧美男性，摄影师，艺术气质
20 岁日本少女，校服，阳光
40 岁中年男性，商人，成熟稳重
28 岁韩国女性，化妆师，时尚
35 岁法国女性，画家，波西米亚
22 岁中国男性，大学生，运动风
45 岁英国男性，教授，学者气质
32 岁巴西女性，舞者，热情
26 岁澳洲女性，冲浪教练，健康
EOF

# 5. 批量执行
while IFS= read -r subject; do
    /Users/apple/Documents/lmd_data_root/apps/ComfyUI/venv/bin/python auto_workflow_runner.py run \
        --id txt2img_精美肖像_20260314_220000 \
        --prompt "$subject, 高清，精致，专业摄影，8K" \
        --steps 30 \
        --cfg 7
    sleep 2  # 任务间延迟
done < subjects.txt

# 6. 查看结果
ls -la ~/Downloads/comfyui_organized/txt2img/$(date +%Y-%m-%d)/
```

---

祝你使用愉快！🎨✨
