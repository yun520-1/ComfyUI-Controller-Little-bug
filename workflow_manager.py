#!/usr/bin/env python3
# -*- utf-8 -*-
"""
ComfyUI 工作流管理器
功能：
- 工作流上传和保存
- 工作流库管理
- 自动替换提示词
- 批量工作流执行
- 工作流模板化
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import requests
import uuid


class WorkflowManager:
    """工作流管理器"""
    
    def __init__(self, workflows_dir: str = None):
        if workflows_dir is None:
            workflows_dir = Path(__file__).parent / "workflows"
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # 工作流分类目录
        self.categories = {
            "txt2img": "文生图",
            "img2img": "图生图",
            "video": "视频生成",
            "upscale": "高清放大",
            "controlnet": "ControlNet",
            "face": "人脸增强",
            "custom": "自定义"
        }
        
        # 为每个分类创建目录
        for cat in self.categories.keys():
            (self.workflows_dir / cat).mkdir(parents=True, exist_ok=True)
        
        self.workflow_registry = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """加载工作流注册表"""
        registry_file = self.workflows_dir / "registry.json"
        if registry_file.exists():
            with open(registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"workflows": []}
    
    def _save_registry(self):
        """保存工作流注册表"""
        registry_file = self.workflows_dir / "registry.json"
        with open(registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.workflow_registry, f, ensure_ascii=False, indent=2)
    
    def upload_workflow(self, workflow_path: str, name: str = None, 
                       category: str = "custom", description: str = "") -> Dict:
        """
        上传工作流文件
        
        Args:
            workflow_path: 工作流 JSON 文件路径
            name: 工作流名称（可选，默认使用文件名）
            category: 分类（txt2img/img2img/video/upscale/controlnet/face/custom）
            description: 描述信息
        
        Returns:
            工作流信息字典
        """
        workflow_path = Path(workflow_path)
        if not workflow_path.exists():
            return {"success": False, "error": f"文件不存在：{workflow_path}"}
        
        # 读取工作流
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"读取失败：{e}"}
        
        # 验证工作流格式
        if not self._validate_workflow(workflow_data):
            return {"success": False, "error": "无效的工作流格式"}
        
        # 生成名称
        if not name:
            name = workflow_path.stem
        
        # 生成唯一 ID
        workflow_id = f"{category}_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 保存文件
        dest_path = self.workflows_dir / category / f"{workflow_id}.json"
        shutil.copy2(workflow_path, dest_path)
        
        # 注册工作流
        workflow_info = {
            "id": workflow_id,
            "name": name,
            "category": category,
            "description": description,
            "file_path": str(dest_path),
            "created_at": datetime.now().isoformat(),
            "prompt_nodes": self._find_prompt_nodes(workflow_data),
            "model_nodes": self._find_model_nodes(workflow_data),
            "parameter_nodes": self._find_parameter_nodes(workflow_data)
        }
        
        self.workflow_registry["workflows"].append(workflow_info)
        self._save_registry()
        
        print(f"✅ 工作流已上传：{name}")
        print(f"   分类：{category}")
        print(f"   ID: {workflow_id}")
        print(f"   路径：{dest_path}")
        
        return {"success": True, "workflow": workflow_info}
    
    def _validate_workflow(self, workflow: Dict) -> bool:
        """验证工作流格式"""
        if not isinstance(workflow, dict):
            return False
        
        # 检查是否至少有一个节点
        if len(workflow) == 0:
            return False
        
        # 检查节点格式
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                return False
            if "class_type" not in node_data:
                return False
        
        return True
    
    def _find_prompt_nodes(self, workflow: Dict) -> List[Dict]:
        """查找提示词节点（CLIPTextEncode）"""
        prompt_nodes = []
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "CLIPTextEncode":
                inputs = node_data.get("inputs", {})
                if "text" in inputs:
                    prompt_nodes.append({
                        "node_id": node_id,
                        "type": "positive" if "negative" not in inputs.get("text", "").lower() else "negative",
                        "default_text": inputs.get("text", "")
                    })
        return prompt_nodes
    
    def _find_model_nodes(self, workflow: Dict) -> List[Dict]:
        """查找模型加载节点"""
        model_nodes = []
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            if "CheckpointLoader" in class_type or "LoadCheckpoints" in class_type:
                inputs = node_data.get("inputs", {})
                model_nodes.append({
                    "node_id": node_id,
                    "class_type": class_type,
                    "model_name": inputs.get("ckpt_name", "")
                })
        return model_nodes
    
    def _find_parameter_nodes(self, workflow: Dict) -> Dict:
        """查找可配置参数节点"""
        params = {}
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
            
            # KSampler 参数
            if "KSampler" in class_type:
                params["sampler"] = {
                    "node_id": node_id,
                    "steps": inputs.get("steps", 20),
                    "cfg": inputs.get("cfg", 7),
                    "sampler_name": inputs.get("sampler_name", "euler"),
                    "scheduler": inputs.get("scheduler", "normal")
                }
            
            # 分辨率参数
            if "EmptyLatentImage" in class_type:
                params["resolution"] = {
                    "node_id": node_id,
                    "width": inputs.get("width", 512),
                    "height": inputs.get("height", 512),
                    "batch_size": inputs.get("batch_size", 1)
                }
        
        return params
    
    def list_workflows(self, category: str = None) -> List[Dict]:
        """列出所有工作流"""
        workflows = self.workflow_registry["workflows"]
        if category:
            workflows = [w for w in workflows if w["category"] == category]
        return workflows
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        for workflow in self.workflow_registry["workflows"]:
            if workflow["id"] == workflow_id:
                return workflow
        return None
    
    def load_workflow(self, workflow_id: str) -> Optional[Dict]:
        """加载工作流数据"""
        workflow_info = self.get_workflow(workflow_id)
        if not workflow_info:
            return None
        
        workflow_path = Path(workflow_info["file_path"])
        if not workflow_path.exists():
            return None
        
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def replace_prompts(self, workflow: Dict, prompt: str, negative: str = "") -> Dict:
        """
        替换工作流中的提示词
        
        Args:
            workflow: 工作流数据
            prompt: 新的正向提示词
            negative: 新的负面提示词
        
        Returns:
            修改后的工作流
        """
        import copy
        workflow_copy = copy.deepcopy(workflow)
        
        for node_id, node_data in workflow_copy.items():
            if node_data.get("class_type") == "CLIPTextEncode":
                inputs = node_data.get("inputs", {})
                current_text = inputs.get("text", "")
                
                # 判断是正向还是负面提示词
                if "negative" in current_text.lower() or "nsfw" in current_text.lower():
                    if negative:
                        node_data["inputs"]["text"] = negative
                else:
                    node_data["inputs"]["text"] = prompt
        
        return workflow_copy
    
    def update_parameters(self, workflow: Dict, **kwargs) -> Dict:
        """
        更新工作流参数
        
        Args:
            workflow: 工作流数据
            **kwargs: 参数（steps, cfg, width, height, batch_size, seed 等）
        
        Returns:
            修改后的工作流
        """
        import copy
        workflow_copy = copy.deepcopy(workflow)
        
        for node_id, node_data in workflow_copy.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
            
            # 更新 KSampler 参数
            if "KSampler" in class_type:
                if "steps" in kwargs:
                    node_data["inputs"]["steps"] = kwargs["steps"]
                if "cfg" in kwargs:
                    node_data["inputs"]["cfg"] = kwargs["cfg"]
                if "seed" in kwargs:
                    node_data["inputs"]["seed"] = kwargs["seed"]
            
            # 更新分辨率参数
            if "EmptyLatentImage" in class_type:
                if "width" in kwargs:
                    node_data["inputs"]["width"] = kwargs["width"]
                if "height" in kwargs:
                    node_data["inputs"]["height"] = kwargs["height"]
                if "batch_size" in kwargs:
                    node_data["inputs"]["batch_size"] = kwargs["batch_size"]
        
        return workflow_copy
    
    def delete_workflow(self, workflow_id: str) -> Dict:
        """删除工作流"""
        workflow_info = self.get_workflow(workflow_id)
        if not workflow_info:
            return {"success": False, "error": "工作流不存在"}
        
        # 删除文件
        workflow_path = Path(workflow_info["file_path"])
        if workflow_path.exists():
            workflow_path.unlink()
        
        # 从注册表移除
        self.workflow_registry["workflows"] = [
            w for w in self.workflow_registry["workflows"] 
            if w["id"] != workflow_id
        ]
        self._save_registry()
        
        print(f"✅ 工作流已删除：{workflow_info['name']}")
        return {"success": True}
    
    def export_workflow(self, workflow_id: str, output_path: str) -> Dict:
        """导出工作流"""
        workflow_info = self.get_workflow(workflow_id)
        if not workflow_info:
            return {"success": False, "error": "工作流不存在"}
        
        workflow_path = Path(workflow_info["file_path"])
        if not workflow_path.exists():
            return {"success": False, "error": "工作流文件不存在"}
        
        shutil.copy2(workflow_path, output_path)
        return {"success": True, "path": output_path}
    
    def get_stats(self) -> Dict:
        """获取工作流统计"""
        workflows = self.workflow_registry["workflows"]
        stats = {
            "total": len(workflows),
            "by_category": {}
        }
        
        for cat in self.categories.keys():
            stats["by_category"][cat] = len([w for w in workflows if w["category"] == cat])
        
        return stats


# 命令行工具
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ComfyUI 工作流管理器")
    parser.add_argument("action", choices=["upload", "list", "show", "delete", "stats"],
                       help="操作类型")
    parser.add_argument("--file", "-f", help="工作流文件路径")
    parser.add_argument("--name", "-n", help="工作流名称")
    parser.add_argument("--category", "-c", default="custom",
                       choices=["txt2img", "img2img", "video", "upscale", "controlnet", "face", "custom"],
                       help="工作流分类")
    parser.add_argument("--description", "-d", default="", help="工作流描述")
    parser.add_argument("--id", help="工作流 ID")
    
    args = parser.parse_args()
    
    manager = WorkflowManager()
    
    if args.action == "upload":
        if not args.file:
            print("❌ 请指定工作流文件 (--file)")
            exit(1)
        result = manager.upload_workflow(
            args.file,
            name=args.name,
            category=args.category,
            description=args.description
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == "list":
        workflows = manager.list_workflows(category=args.category if args.category != "custom" else None)
        print(f"\n📋 工作流列表 (共 {len(workflows)} 个):\n")
        for w in workflows:
            print(f"  ID: {w['id']}")
            print(f"  名称：{w['name']}")
            print(f"  分类：{w['category']}")
            print(f"  描述：{w['description']}")
            print(f"  创建时间：{w['created_at']}")
            print()
    
    elif args.action == "show":
        if not args.id:
            print("❌ 请指定工作流 ID (--id)")
            exit(1)
        workflow = manager.get_workflow(args.id)
        if workflow:
            print(json.dumps(workflow, ensure_ascii=False, indent=2))
        else:
            print("❌ 工作流不存在")
    
    elif args.action == "delete":
        if not args.id:
            print("❌ 请指定工作流 ID (--id)")
            exit(1)
        result = manager.delete_workflow(args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == "stats":
        stats = manager.get_stats()
        print(f"\n📊 工作流统计:\n")
        print(f"  总数：{stats['total']}")
        print(f"  分类统计:")
        for cat, count in stats['by_category'].items():
            print(f"    {cat}: {count}")
