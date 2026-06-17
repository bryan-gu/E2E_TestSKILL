#!/bin/bash
# BF 测试 Skill 全局安装脚本
# 将主 Skill、Agent、模板、脚本安装到 ~/.claude/skills/
# 用法: bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$HOME/.claude/skills"

echo "=== BF 测试 Skill 安装 ==="
echo "源目录: $SCRIPT_DIR"
echo "目标目录: $SKILL_DIR"
echo ""

# 创建目录结构
mkdir -p "$SKILL_DIR/agents"
mkdir -p "$SKILL_DIR/templates"
mkdir -p "$SKILL_DIR/scripts"

# 1. 主 Skill 文件
echo "--- 安装主 Skill ---"
cp "$SCRIPT_DIR/bf-test-workflow.md" "$SKILL_DIR/"
echo "  bf-test-workflow.md"
cp "$SCRIPT_DIR/init-bf.md" "$SKILL_DIR/"
echo "  init-bf.md"
cp "$SCRIPT_DIR/requirements.txt" "$SKILL_DIR/"
echo "  requirements.txt"

# 2. Agent 定义文件（供 init-bf 后续复制到项目用）
echo "--- 安装 Agent 定义 ---"
for f in "$SCRIPT_DIR/agents/"*.md; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/agents/"
        echo "  agents/$(basename "$f")"
    fi
done
cp "$SCRIPT_DIR/agents/install.sh" "$SKILL_DIR/agents/"
echo "  agents/install.sh"

# 3. 模板文件
echo "--- 安装模板 ---"
for f in "$SCRIPT_DIR/templates/"*; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/templates/"
        echo "  templates/$(basename "$f")"
    fi
done

# 4. 脚本文件
echo "--- 安装脚本 ---"
for f in "$SCRIPT_DIR/scripts/"*; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/scripts/"
        echo "  scripts/$(basename "$f")"
    fi
done

echo ""
echo "=== 安装完成 ==="
echo ""
echo "V2 关键文件确认："
echo "  scripts/build_index.py   — V2 知识图谱构建器"
echo "  agents/bf-graph-agent.md — V2 图谱子 agent"
echo ""
echo "后续步骤:"
echo "  1. 安装 Python 依赖:  pip install -r $SCRIPT_DIR/requirements.txt"
echo "     （sqlite3 + FTS5 随 Python 内置，无需 pip）"
echo "  2. 重启 Claude Code 会话"
echo "  3. 在被测项目中执行 /init-bf 初始化项目（V2 含第七步环境自检）"
