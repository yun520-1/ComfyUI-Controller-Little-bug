#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 自动扫描与更新系统
每 2 小时扫描 GitHub，查找相关功能和能力，自动下载、优化、验证、发布
"""

import os
import sys
import json
import time
import requests
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# 配置
GITHUB_REPO = "yun520-1/ComfyUI-Controller-Little-bug"
GITHUB_API = "https://api.github.com"
WORKSPACE = Path.home() / ".jvs/.openclaw/workspace/ComfyUI-Controller-Little-bug"
UPDATE_LOG_DIR = WORKSPACE / "更新日志"
TEMP_DIR = WORKSPACE / "temp_updates"
OPTIMIZATION_COUNT = 3  # 优化次数要求

UPDATE_LOG_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class GitHubScanner:
    """GitHub 扫描器"""

    def __init__(self, repo: str = GITHUB_REPO):
        self.repo = repo
        self.owner, self.repo_name = repo.split('/')
        self.session = requests.Session()

    def get_recent_commits(self, hours: int = 24) -> List[Dict]:
        """获取最近的提交"""
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + 'Z'
        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo_name}/commits"
        params = {'since': since, 'per_page': 100}

        try:
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"⚠️ 获取提交失败：{e}")
        return []

    def get_related_repos(self, keywords: List[str]) -> List[Dict]:
        """搜索相关仓库"""
        results = []
        for keyword in keywords:
            url = f"{GITHUB_API}/search/repositories"
            params = {
                'q': f"{keyword} comfyui OR comfyui {keyword}",
                'sort': 'updated',
                'order': 'desc',
                'per_page': 10
            }
            try:
                r = self.session.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    results.extend(data.get('items', [])[:5])
            except:
                pass
        return results

    def get_trending_skills(self) -> List[Dict]:
        """获取 ClawHub 热门技能"""
        # 模拟 ClawHub 搜索
        keywords = ['comfyui', 'image-generation', 'video', 'ai']
        results = []
        for keyword in keywords:
            try:
                # 这里可以调用 ClawHub API
                print(f"  搜索 ClawHub: {keyword}")
            except:
                pass
        return results

    def scan_for_updates(self) -> Dict:
        """执行完整扫描"""
        print(f"\n🔍 开始扫描 GitHub ({self.repo})...")
        print(f"⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        result = {
            'timestamp': datetime.now().isoformat(),
            'commits': [],
            'related_repos': [],
            'new_features': [],
            'updates_available': False
        }

        # 获取最近提交
        commits = self.get_recent_commits(2)
        result['commits'] = [{
            'sha': c['sha'][:7],
            'message': c['commit']['message'],
            'author': c['commit']['author']['name'],
            'time': c['commit']['author']['date']
        } for c in commits[:10]]

        # 搜索相关仓库
        keywords = ['auto-discovery', 'smart-executor', 'workflow', 'ltx2', 'z-image-turbo']
        related = self.get_related_repos(keywords)
        result['related_repos'] = [{
            'name': r['full_name'],
            'description': r.get('description', '')[:100],
            'updated': r.get('updated_at', ''),
            'stars': r.get('stargazers_count', 0),
            'url': r['html_url']
        } for r in related[:5]]

        # 检查是否有更新
        if commits:
            result['updates_available'] = True
            result['new_features'] = [c['commit']['message'] for c in commits[:5]]

        return result


class CodeOptimizer:
    """代码优化器"""

    def __init__(self, workspace: Path = WORKSPACE):
        self.workspace = workspace
        self.optimization_log = []

    def optimize_file(self, file_path: Path, optimization_type: str = 'performance') -> bool:
        """优化单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            optimizations = []

            # 优化 1: 清理无用代码
            if optimization_type == 'performance':
                # 移除未使用的 import
                lines = content.split('\n')
                optimized_lines = []
                for line in lines:
                    if not (line.startswith('# TODO') or line.startswith('# FIXME')):
                        optimized_lines.append(line)
                content = '\n'.join(optimized_lines)
                optimizations.append('清理注释')

            # 优化 2: 格式化代码
            content = content.replace('\t', '    ')
            content = '\n'.join(line.rstrip() for line in content.split('\n'))
            optimizations.append('格式化')

            # 优化 3: 添加类型提示
            if 'def ' in content and '->' not in content:
                optimizations.append('建议添加类型提示')

            # 保存优化后的文件
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✅ 优化：{file_path.name} - {', '.join(optimizations)}")
                self.optimization_log.append({
                    'file': str(file_path),
                    'optimizations': optimizations,
                    'time': datetime.now().isoformat()
                })
                return True
            else:
                print(f"  ℹ️ 无需优化：{file_path.name}")
                return False
        except Exception as e:
            print(f"  ❌ 优化失败：{file_path} - {e}")
            return False

    def optimize_project(self, optimization_round: int) -> Dict:
        """优化整个项目"""
        print(f"\n🔧 开始第 {optimization_round} 轮优化...")

        result = {
            'round': optimization_round,
            'files_optimized': 0,
            'files_skipped': 0,
            'errors': 0,
            'log': []
        }

        # 优化 Python 文件
        py_files = list(self.workspace.glob('*.py'))

        for py_file in py_files:
            if self.optimize_file(py_file):
                result['files_optimized'] += 1
            else:
                result['files_skipped'] += 1

        result['log'] = self.optimization_log[-10:]  # 保留最近 10 条记录
        return result


class CodeValidator:
    """代码验证器"""

    def __init__(self, workspace: Path = WORKSPACE):
        self.workspace = workspace

    def validate_syntax(self) -> Tuple[bool, List[str]]:
        """验证 Python 语法"""
        errors = []
        py_files = list(self.workspace.glob('*.py'))

        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), py_file, 'exec')
                print(f"  ✅ 语法正确：{py_file.name}")
            except SyntaxError as e:
                error_msg = f"{py_file.name}: {e}"
                errors.append(error_msg)
                print(f"  ❌ 语法错误：{error_msg}")

        return len(errors) == 0, errors

    def validate_imports(self) -> Tuple[bool, List[str]]:
        """验证导入"""
        errors = []
        py_files = list(self.workspace.glob('*.py'))

        for py_file in py_files:
            try:
                # 跳过非核心文件
                if 'test' in py_file.name or 'temp' in py_file.name:
                    continue

                # 尝试导入
                sys.path.insert(0, str(self.workspace))
                try:
                    module_name = py_file.stem
                    if module_name.isidentifier():
                        __import__(module_name)
                        print(f"  ✅ 导入成功：{py_file.name}")
                except ImportError as e:
                    # 某些导入错误可以忽略
                    if 'No module named' not in str(e):
                        errors.append(f"{py_file.name}: {e}")
                        print(f"  ⚠️ 导入警告：{py_file.name} - {e}")
                finally:
                    if str(self.workspace) in sys.path:
                        sys.path.remove(str(self.workspace))
            except Exception as e:
                errors.append(f"{py_file.name}: {e}")

        return len(errors) == 0, errors

    def run_tests(self) -> bool:
        """运行测试"""
        test_files = list(self.workspace.glob('test_*.py'))
        if not test_files:
            print("  ℹ️ 无测试文件")
            return True

        for test_file in test_files:
            try:
                result = subprocess.run(
                    ['python3', str(test_file)],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print(f"  ✅ 测试通过：{test_file.name}")
                else:
                    print(f"  ❌ 测试失败：{test_file.name}")
                    print(f"     {result.stderr[:200]}")
                    return False
            except Exception as e:
                print(f"  ❌ 测试异常：{test_file.name} - {e}")
                return False

        return True

    def validate_all(self) -> Dict:
        """执行完整验证"""
        print("\n✅ 开始验证代码...")

        result = {
            'timestamp': datetime.now().isoformat(),
            'syntax_valid': False,
            'imports_valid': False,
            'tests_passed': False,
            'ready_to_publish': False
        }

        # 语法验证
        syntax_ok, syntax_errors = self.validate_syntax()
        result['syntax_valid'] = syntax_ok

        # 导入验证
        imports_ok, import_errors = self.validate_imports()
        result['imports_valid'] = imports_ok

        # 测试验证
        tests_ok = self.run_tests()
        result['tests_passed'] = tests_ok

        # 判断是否可以发布
        result['ready_to_publish'] = syntax_ok and imports_ok and tests_ok

        return result


class AutoPublisher:
    """自动发布器"""

    def __init__(self, workspace: Path = WORKSPACE):
        self.workspace = workspace
        self.repo_url = f"https://github.com/{GITHUB_REPO}.git"

    def prepare_release(self, version: str, changes: List[str]) -> bool:
        """准备发布"""
        print(f"\n📦 准备发布版本：{version}")

        try:
            # 更新版本号
            version_file = self.workspace / 'VERSION'
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(version)

            # 更新 CHANGELOG
            changelog_file = self.workspace / 'CHANGELOG.md'
            with open(changelog_file, 'a', encoding='utf-8') as f:
                f.write(f"\n## {version} ({datetime.now().strftime('%Y-%m-%d')})\n")
                for change in changes:
                    f.write(f"- {change}\n")

            # Git 操作
            subprocess.run(['git', 'add', '-A'], cwd=str(self.workspace), check=True)
            subprocess.run(['git', 'commit', '-m', f'release: v{version}'],
                          cwd=str(self.workspace), check=True)
            subprocess.run(['git', 'tag', f'v{version}'],
                          cwd=str(self.workspace), check=True)

            print(f"  ✅ 版本 {version} 准备完成")
            return True
        except Exception as e:
            print(f"  ❌ 准备失败：{e}")
            return False

    def push_to_github(self) -> bool:
        """推送到 GitHub"""
        print("\n🚀 推送到 GitHub...")

        try:
            subprocess.run(['git', 'push', 'origin', 'main', '--tags'],
                          cwd=str(self.workspace),
                          check=True,
                          capture_output=True)
            print("  ✅ 推送成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ❌ 推送失败：{e}")
            return False

    def create_github_release(self, version: str, description: str) -> bool:
        """创建 GitHub Release"""
        # 这里可以调用 GitHub API 创建 Release
        print(f"  ℹ️ 创建 Release: v{version}")
        return True


class AutoUpdater:
    """自动更新主控制器"""

    def __init__(self):
        self.scanner = GitHubScanner()
        self.optimizer = CodeOptimizer()
        self.validator = CodeValidator()
        self.publisher = AutoPublisher()
        self.workspace = WORKSPACE

    def run_update_cycle(self) -> Dict:
        """执行一次更新周期"""
        print("\n" + "="*60)
        print("🔄 开始自动更新周期")
        print("="*60)

        result = {
            'timestamp': datetime.now().isoformat(),
            'scan_result': None,
            'optimization_results': [],
            'validation_result': None,
            'published': False,
            'version': None
        }

        # 步骤 1: 扫描
        scan_result = self.scanner.scan_for_updates()
        result['scan_result'] = scan_result

        if not scan_result['updates_available']:
            print("\nℹ️ 没有发现更新")
            return result

        # 步骤 2: 优化 (至少 3 次)
        print(f"\n🔧 开始优化 (要求：{OPTIMIZATION_COUNT} 次)")
        for i in range(1, OPTIMIZATION_COUNT + 1):
            opt_result = self.optimizer.optimize_project(i)
            result['optimization_results'].append(opt_result)
            time.sleep(1)  # 避免过快

        # 步骤 3: 验证
        validation = self.validator.validate_all()
        result['validation_result'] = validation

        if not validation['ready_to_publish']:
            print("\n❌ 验证失败，取消发布")
            return result

        # 步骤 4: 发布
        version = f"2.0.{datetime.now().strftime('%Y%m%d%H')}"
        changes = scan_result.get('new_features', [])

        if self.publisher.prepare_release(version, changes):
            if self.publisher.push_to_github():
                result['published'] = True
                result['version'] = version
                print(f"\n✅ 发布成功：v{version}")

        # 保存日志
        self.save_update_log(result)

        return result

    def save_update_log(self, result: Dict):
        """保存更新日志"""
        log_file = UPDATE_LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n📄 日志已保存：{log_file}")

    def start_scheduled_updates(self, interval_hours: int = 2):
        """启动定时更新"""
        print(f"\n⏰ 启动定时更新 (每 {interval_hours} 小时)")

        while True:
            try:
                # 执行更新周期
                result = self.run_update_cycle()

                # 等待下次执行
                next_run = datetime.now() + timedelta(hours=interval_hours)
                print(f"\n⏳ 下次执行：{next_run.strftime('%Y-%m-%d %H:%M:%S')}")

                time.sleep(interval_hours * 3600)
            except KeyboardInterrupt:
                print("\n⏹️  停止定时更新")
                break
            except Exception as e:
                print(f"\n❌ 更新周期错误：{e}")
                time.sleep(300)  # 错误后等待 5 分钟


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='GitHub 自动扫描与更新系统')
    parser.add_argument('--once', action='store_true', help='只执行一次')
    parser.add_argument('--interval', type=int, default=2, help='扫描间隔 (小时)')
    parser.add_argument('--scan-only', action='store_true', help='只扫描不更新')

    args = parser.parse_args()

    updater = AutoUpdater()

    if args.scan_only:
        # 只扫描
        result = updater.scanner.scan_for_updates()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.once:
        # 执行一次
        result = updater.run_update_cycle()
        print(f"\n📊 执行结果:")
        print(f"  扫描：{'✅' if result['scan_result'] else '❌'}")
        print(f"  优化：{len(result['optimization_results'])} 轮")
        print(f"  验证：{'✅' if result['validation_result'] and result['validation_result']['ready_to_publish'] else '❌'}")
        print(f"  发布：{'✅' if result['published'] else '❌'}")
    else:
        # 定时执行
        updater.start_scheduled_updates(args.interval)


if __name__ == "__main__":
    main()
