#!/usr/bin/env node
/**
 * 发布 ComfyUI 智能控制器技能到 ClawHub
 * 自动打包、版本管理、上传
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SKILL_NAME = 'comfyui-controller';
const SKILL_VERSION = '2.0.0';
const SKILL_DIR = path.join(__dirname);

console.log('🚀 发布 ComfyUI 智能控制器技能到 ClawHub');
console.log('=' .repeat(60));

// 1. 验证必要文件
console.log('\n📋 检查必要文件...');
const requiredFiles = [
    'comfyui_auto_discovery.py',
    'comfyui_smart_executor.py',
    'comfyui_monitor.py',
    'README-智能技能.md',
    'SKILL.md',
];

let allFilesExist = true;
for (const file of requiredFiles) {
    const filePath = path.join(SKILL_DIR, file);
    if (fs.existsSync(filePath)) {
        console.log(`  ✅ ${file}`);
    } else {
        console.log(`  ❌ ${file} (缺失)`);
        allFilesExist = false;
    }
}

if (!allFilesExist) {
    console.log('\n❌ 缺少必要文件，无法发布');
    process.exit(1);
}

// 2. 更新版本
console.log('\n📦 更新版本信息...');
const skillMdPath = path.join(SKILL_DIR, 'SKILL.md');
if (fs.existsSync(skillMdPath)) {
    let content = fs.readFileSync(skillMdPath, 'utf-8');
    // 更新版本信息
    if (content.includes('版本:')) {
        content = content.replace(/版本：[\d.]+/, `版本：${SKILL_VERSION}`);
    } else {
        content = `# ComfyUI Controller 技能\n\n版本：${SKILL_VERSION}\n\n` + content;
    }
    fs.writeFileSync(skillMdPath, content);
    console.log(`  ✅ 版本更新为 ${SKILL_VERSION}`);
}

// 3. 创建发布包
console.log('\n📦 创建发布包...');
const distDir = path.join(SKILL_DIR, 'dist');
if (!fs.existsSync(distDir)) {
    fs.mkdirSync(distDir);
}

const archiveName = `${SKILL_NAME}-v${SKILL_VERSION}.zip`;
const archivePath = path.join(distDir, archiveName);

try {
    // 使用 zip 命令打包
    const zipCommand = `cd "${SKILL_DIR}" && zip -r "${archivePath}" \
        comfyui_auto_discovery.py \
        comfyui_smart_executor.py \
        comfyui_monitor.py \
        comfyui_smart_controller_fixed.py \
        README-智能技能.md \
        SKILL.md \
        发现报告.md \
        -x "*.pyc" "*__pycache__*" "*.log"`;
    
    console.log(`  执行：${zipCommand}`);
    execSync(zipCommand, { stdio: 'inherit' });
    console.log(`  ✅ 发布包已创建：${archivePath}`);
} catch (error) {
    console.log('  ⚠️ zip 命令失败，尝试使用 tar');
    try {
        const tarArchive = path.join(distDir, `${SKILL_NAME}-v${SKILL_VERSION}.tar.gz`);
        execSync(`cd "${SKILL_DIR}" && tar -czf "${tarArchive}" *.py *.md`, { stdio: 'inherit' });
        console.log(`  ✅ 发布包已创建：${tarArchive}`);
    } catch (error2) {
        console.log('  ❌ 打包失败');
        process.exit(1);
    }
}

// 4. 发布到 ClawHub
console.log('\n🌐 发布到 ClawHub...');
console.log('  提示：请使用以下命令手动发布:');
console.log(`  clawhub publish "${SKILL_DIR}"`);
console.log(`  或访问 https://clawhub.ai/ 上传 ${archivePath}`);

// 5. 提交到 Git
console.log('\n📝 提交到 Git...');
try {
    execSync('git status', { stdio: 'pipe' });
    console.log('  ✅ Git 仓库已初始化');
    
    const commitMsg = `release: v${SKILL_VERSION} - ComfyUI 智能控制器`;
    execSync(`cd "${SKILL_DIR}" && git add -A && git commit -m "${commitMsg}"`, { stdio: 'inherit' });
    console.log('  ✅ Git 提交完成');
    
    console.log('\n  提示：推送到远程仓库');
    console.log('  git push origin main');
} catch (error) {
    console.log('  ⚠️ 不是 Git 仓库或提交失败');
}

// 6. 生成发布报告
console.log('\n📄 生成发布报告...');
const reportPath = path.join(SKILL_DIR, '发布报告.md');
const report = `# 📦 发布报告

**技能名称**: ${SKILL_NAME}
**版本**: ${SKILL_VERSION}
**时间**: ${new Date().toISOString()}

## ✅ 发布内容

- comfyui_auto_discovery.py - 自动发现系统
- comfyui_smart_executor.py - 智能执行器
- comfyui_monitor.py - 监控器
- comfyui_smart_controller_fixed.py - 控制器
- README-智能技能.md - 使用文档
- SKILL.md - 技能说明

## 📦 发布包

- 位置：${archivePath}
- 大小：${fs.statSync(archivePath).size} bytes

## 🚀 下一步

1. 上传到 ClawHub:
   \`\`\`bash
   clawhub publish "${SKILL_DIR}"
   \`\`\`

2. 推送到 GitHub:
   \`\`\`bash
   git push origin main
   \`\`\`

3. 通知用户更新:
   \`\`\`bash
   clawhub update ${SKILL_NAME}
   \`\`\`

## 📝 更新内容

### v${SKILL_VERSION}
- ✅ 新增自动发现系统
- ✅ 新增智能执行器
- ✅ 跨平台支持 (Windows/Mac/Linux)
- ✅ 自动查询官方文档
- ✅ 工作流自动分析
- ✅ 最佳配置推荐
`;

fs.writeFileSync(reportPath, report);
console.log(`  ✅ 发布报告已保存：${reportPath}`);

console.log('\n' + '='.repeat(60));
console.log('✅ 发布准备完成!');
console.log('\n下一步操作:');
console.log(`1. 上传到 ClawHub: clawhub publish "${SKILL_DIR}"`);
console.log('2. 推送到 GitHub: git push origin main');
console.log(`3. 查看报告: cat "${reportPath}"`);
console.log('=' .repeat(60));
