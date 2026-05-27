#!/bin/bash
# 将 BF 测试 Agent 安装到目标项目的 .claude/agents/ 目录
# 用法: bash install.sh <项目路径>
# 示例: bash ~/.claude/skills/agents/install.sh "D:/BF-项目演示"

AGENTS_SRC="$HOME/.claude/skills/agents"
AGENT_FILES=(
    "bf-case-generator.md"
    "bf-e2e-generator.md"
    "bf-e2e-healer.md"
    "bf-ui-explorer.md"
    "bf-e2e-validator.md"
)

if [ -z "$1" ]; then
    echo "用法: bash install.sh <项目路径>"
    echo "示例: bash ~/.claude/skills/agents/install.sh \"D:/BF-项目演示\""
    exit 1
fi

PROJECT_DIR="$1"
AGENTS_DIR="$PROJECT_DIR/.claude/agents"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "错误: 项目目录不存在: $PROJECT_DIR"
    exit 1
fi

mkdir -p "$AGENTS_DIR"

installed=0
skipped=0
for agent in "${AGENT_FILES[@]}"; do
    src="$AGENTS_SRC/$agent"
    dst="$AGENTS_DIR/$agent"

    if [ ! -f "$src" ]; then
        echo "跳过: 源文件不存在: $src"
        skipped=$((skipped + 1))
        continue
    fi

    cp "$src" "$dst"
    echo "安装: $agent"
    installed=$((installed + 1))
done

echo ""
echo "完成: 安装 $installed 个 Agent 到 $AGENTS_DIR"
if [ $skipped -gt 0 ]; then
    echo "跳过: $skipped 个（源文件不存在）"
fi
echo ""
echo "注意: 需要重启 Claude Code 会话才能发现新安装的 Agent"
