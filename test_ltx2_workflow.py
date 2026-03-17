#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 LTX2 工作流并提交
"""

import json
import requests
import uuid

COMFYUI = "127.0.0.1:8189"
WORKFLOW_FILE = "/Users/apple/Documents/lmd_data_root/apps/ComfyUI/user/default/workflows/ltx2_t2v_gguf.json"

# 加载工作流
with open(WORKFLOW_FILE, 'r') as f:
    workflow = json.load(f)

print(f"工作流 ID: {workflow.get('id', 'N/A')}")
print(f"节点数：{workflow.get('last_node_id', 'N/A')}")
print(f"节点列表：{len(workflow.get('nodes', []))} 个")

# 转换为 API 格式
api_prompt = {}
for node in workflow.get("nodes", []):
    node_id = str(node["id"])
    node_type = node.get("type", "")

    # 提取 inputs
    inputs = {}
    widgets = node.get("widgets_values", [])

    if node_type == "CLIPTextEncode" and widgets:
        inputs["text"] = widgets[0]
    elif node_type == "EmptyLTXVLatentVideo" and len(widgets) >= 4:
        inputs["width"] = widgets[0]
        inputs["height"] = widgets[1]
        inputs["length"] = widgets[2]
        inputs["batch_size"] = widgets[3]
    elif node_type == "PrimitiveInt" and widgets:
        inputs["value"] = widgets[0]
    elif node_type == "PrimitiveFloat" and widgets:
        inputs["value"] = widgets[0]
    elif node_type == "VAELoaderKJ" and widgets:
        inputs["vae_name"] = widgets[0]
        inputs["device"] = widgets[1] if len(widgets) > 1 else "main_device"
        inputs["weight_dtype"] = widgets[2] if len(widgets) > 2 else "bf16"
    elif node_type == "UnetLoaderGGUF" and widgets:
        inputs["unet_name"] = widgets[0]
    elif node_type == "DualCLIPLoaderGGUF" and widgets:
        inputs["clip_name1"] = widgets[0]
        inputs["clip_name2"] = widgets[1] if len(widgets) > 1 else ""
        inputs["type"] = widgets[2] if len(widgets) > 2 else "ltxv"
    elif node_type == "KSamplerSelect" and widgets:
        inputs["sampler_name"] = widgets[0]
    elif node_type == "LTXVScheduler" and len(widgets) >= 6:
        inputs["steps"] = widgets[0]
        inputs["max_shift"] = widgets[1]
        inputs["base_shift"] = widgets[2]
        inputs["stretch"] = widgets[3]
        inputs["terminal"] = widgets[4]
    elif node_type == "CFGGuider" and widgets:
        inputs["cfg"] = widgets[0]
    elif node_type == "RandomNoise" and widgets:
        inputs["noise_seed"] = widgets[0]
    elif node_type == "LoraLoaderModelOnly" and len(widgets) >= 2:
        inputs["lora_name"] = widgets[0]
        inputs["strength_model"] = widgets[1]
    elif node_type == "SaveVideo" and widgets:
        inputs["filename_prefix"] = widgets[0]
        inputs["format"] = widgets[1] if len(widgets) > 1 else "mp4"
        inputs["codec"] = widgets[2] if len(widgets) > 2 else "auto"
    elif node_type == "CreateVideo" and widgets:
        inputs["fps"] = widgets[0]

    # 提取 inputs 从节点的输入连接
    for inp in node.get("inputs", []):
        link_id = inp.get("link")
        if link_id:
            # 找到对应的 link
            for link in workflow.get("links", []):
                if link[0] == link_id:
                    src_node_id = str(link[1])
                    src_output_index = link[2]
                    input_name = inp.get("name", "input")
                    # 简化处理，使用节点 ID
                    inputs[inp.get("name", f"input_{link_id}")] = [src_node_id, src_output_index]
                    break

    if inputs or node_type in ["CLIPTextEncode", "EmptyLTXVLatentVideo", "UnetLoaderGGUF", "VAELoaderKJ", "DualCLIPLoaderGGUF"]:
        api_prompt[node_id] = {
            "class_type": node_type,
            "inputs": inputs
        }

print(f"\nAPI 格式节点数：{len(api_prompt)}")
print("\n前 5 个节点:")
for i, (nid, ndata) in enumerate(list(api_prompt.items())[:5]):
    print(f"  {nid}: {ndata['class_type']} - inputs: {len(ndata.get('inputs', {}))}")

# 测试提交
print(f"\n🚀 提交测试...")
client_id = str(uuid.uuid4())

resp = requests.post(
    f"http://{COMFYUI}/prompt",
    json={"prompt": api_prompt, "client_id": client_id},
    timeout=10
)

print(f"状态码：{resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"✅ 提交成功！Prompt ID: {data.get('prompt_id')}")
else:
    print(f"❌ 提交失败")
    print(f"响应：{resp.text[:500]}")

    # 保存转换后的工作流用于调试
    with open('/tmp/api_prompt.json', 'w') as f:
        json.dump(api_prompt, f, indent=2)
    print(f"\n已保存转换后的工作流到：/tmp/api_prompt.json")
