#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动验证测试脚本
在发布前运行，确保所有功能正常
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(__file__).parent

def test_import(module_name: str) -> bool:
    """测试模块导入"""
    try:
        sys.path.insert(0, str(WORKSPACE))
        __import__(module_name)
        print(f"✅ 导入测试：{module_name}")
        return True
    except Exception as e:
        print(f"❌ 导入失败：{module_name} - {e}")
        return False

def test_syntax(file_path: Path) -> bool:
    """测试语法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            compile(f.read(), file_path, 'exec')
        print(f"✅ 语法测试：{file_path.name}")
        return True
    except Exception as e:
        print(f"❌ 语法错误：{file_path.name} - {e}")
        return False

def test_execution(script: str) -> bool:
    """测试执行"""
    try:
        result = subprocess.run(
            ['python3', '-c', script],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"✅ 执行测试：{script[:50]}...")
            return True
        else:
            print(f"❌ 执行失败：{result.stderr[:100]}")
            return False
    except Exception as e:
        print(f"❌ 执行异常：{e}")
        return False

def main():
    """主测试"""
    print("="*60)
    print("🧪 自动验证测试")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print()

    results = {
        'syntax': [],
        'import': [],
        'execution': []
    }

    # 1. 语法测试
    print("📋 语法测试...")
    py_files = list(WORKSPACE.glob('*.py'))
    for py_file in py_files[:10]:  # 测试前 10 个文件
        ok = test_syntax(py_file)
        results['syntax'].append((py_file.name, ok))

    print()

    # 2. 导入测试
    print("📋 导入测试...")
    core_modules = [
        'comfyui_auto_discovery',
        'comfyui_smart_executor',
        'comfyui_monitor',
        'comfyui_smart_controller_fixed',
        'github_auto_updater'
    ]
    for module in core_modules:
        ok = test_import(module)
        results['import'].append((module, ok))

    print()

    # 3. 执行测试
    print("📋 执行测试...")
    tests = [
        "from comfyui_auto_discovery import ComfyUIDiscovery; d=ComfyUIDiscovery(); print('OK')",
        "from comfyui_monitor import ComfyUIMonitor; m=ComfyUIMonitor(); print('OK')",
    ]
    for test in tests:
        ok = test_execution(test)
        results['execution'].append((test[:40], ok))

    print()

    # 汇总结果
    print("="*60)
    print("📊 测试结果汇总")
    print("="*60)

    total = 0
    passed = 0

    for category, tests in results.items():
        cat_total = len(tests)
        cat_passed = sum(1 for _, ok in tests if ok)
        total += cat_total
        passed += cat_passed

        status = "✅" if cat_passed == cat_total else "⚠️"
        print(f"{status} {category}: {cat_passed}/{cat_total}")

    print()
    overall = "✅" if passed == total else "❌"
    print(f"{overall} 总计：{passed}/{total} 通过")
    print("="*60)

    # 返回状态
    if passed == total:
        print("\n✅ 所有测试通过，可以发布")
        return 0
    else:
        print(f"\n❌ {total - passed} 个测试失败，请修复后再发布")
        return 1

if __name__ == "__main__":
    exit(main())
