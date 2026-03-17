#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本 - 验证增强功能
"""

import sys
import json
from pathlib import Path

# 添加项目路径
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from local_resource_manager import LocalComfyUIManager
from comfyui_super_controller import ComfyUISuperController, ModelDownloader


def test_local_manager():
    """测试本地资源管理器"""
    print("\n" + "="*60)
    print("测试 1: 本地资源管理器")
    print("="*60)
    
    manager = LocalComfyUIManager()
    
    # 查找 ComfyUI
    print("\n1. 查找 ComfyUI 安装...")
    comfyui_path = manager.find_comfyui()
    if comfyui_path:
        print(f"   ✅ 找到：{comfyui_path}")
    else:
        print(f"   ⚠️  未找到（这是正常的，如果没安装）")
    
    # 检测系统配置
    print("\n2. 检测系统配置...")
    config = manager.detect_system_config()
    print(f"   ✅ 配置已检测")
    
    # 扫描模型（如果有 ComfyUI）
    if comfyui_path:
        print("\n3. 扫描本地模型...")
        models = manager.scan_models()
        if models:
            print(f"   ✅ 找到 {len(models)} 类模型")
            for model_type, info in models.items():
                print(f"      - {model_type}: {info['count']} 个")
        else:
            print(f"   ⚠️  没有找到模型")
    
    # 获取推荐
    print("\n4. 获取推荐配置...")
    recs = manager.get_recommendations()
    if recs['models']:
        print(f"   ✅ 推荐模型:")
        for model in recs['models']:
            print(f"      - {model}")
    
    return True


def test_model_downloader():
    """测试模型下载器"""
    print("\n" + "="*60)
    print("测试 2: 模型下载器")
    print("="*60)
    
    manager = LocalComfyUIManager()
    manager.find_comfyui()
    
    if not manager.comfyui_path:
        print("⚠️  未找到 ComfyUI，跳过下载器测试")
        return True
    
    downloader = ModelDownloader(manager.comfyui_path)
    
    # 测试推荐模型
    print("\n1. 测试系统配置推荐...")
    config = manager.detect_system_config()
    recommended = downloader.get_recommended_model(config)
    print(f"   ✅ 推荐模型：{recommended}")
    
    # 测试检查模型是否存在
    print("\n2. 测试检查本地模型...")
    test_model = "v1-5-pruned-emaonly.ckpt"
    exists = downloader.check_model_exists(test_model)
    if exists:
        print(f"   ✅ 模型已存在：{exists}")
    else:
        print(f"   ⚠️  模型不存在：{test_model}")
    
    return True


def test_super_controller():
    """测试超级控制器"""
    print("\n" + "="*60)
    print("测试 3: 超级控制器")
    print("="*60)
    
    controller = ComfyUISuperController("127.0.0.1:8188")
    
    # 初始化
    print("\n1. 初始化控制器...")
    init_result = controller.initialize()
    print(f"   ComfyUI 路径：{init_result['comfyui_path']}")
    print(f"   连接状态：{'✅ 已连接' if init_result['connected'] else '❌ 未连接'}")
    
    # 测试模型查找
    if init_result['connected']:
        print("\n2. 测试模型查找...")
        model_info = controller.find_best_model()
        print(f"   来源：{model_info['source']}")
        print(f"   模型：{model_info['model']}")
        if model_info.get('needs_download'):
            print(f"   ⚠️  需要下载")
        else:
            print(f"   ✅ 本地可用")
    
    return True


def test_workflow_loading():
    """测试工作流加载"""
    print("\n" + "="*60)
    print("测试 4: 工作流加载")
    print("="*60)
    
    workflows_dir = project_dir / "workflows"
    registry_file = workflows_dir / "registry.json"
    
    if not registry_file.exists():
        print("⚠️  工作流注册表不存在")
        return True
    
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    workflows = registry.get('workflows', [])
    print(f"\n已注册工作流：{len(workflows)} 个")
    
    for wf in workflows[:5]:  # 只显示前 5 个
        print(f"   - {wf['name']} ({wf['category']})")
    
    return True


def main():
    print("\n" + "="*60)
    print("ComfyUI 超级控制器 - 功能测试")
    print("="*60)
    
    tests = [
        ("本地资源管理器", test_local_manager),
        ("模型下载器", test_model_downloader),
        ("超级控制器", test_super_controller),
        ("工作流加载", test_workflow_loading),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ 通过" if result else "❌ 失败"))
        except Exception as e:
            print(f"\n❌ 测试失败：{e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ 错误：{e}"))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for name, result in results:
        print(f"{name}: {result}")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())
