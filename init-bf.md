---
description: 初始化BF项目的CLAUDE.md配置文件，自动探测项目信息（前缀、系统地址、测试账号），生成标准化的项目测试上下文配置
---

# 初始化 BF 项目

为当前项目生成 CLAUDE.md，基于通用 BF 项目模板填充项目特定信息。

参数: $ARGUMENTS （可选，格式：项目前缀/系统地址/测试账号/测试密码，用空格分隔。不传则自动探测或交互询问）

## 执行流程

### 第一步：收集项目信息

按优先级从高到低获取以下 4 项信息：

1. **项目前缀**（如 NJ、SPD）
2. **系统地址**（如 http://your-test-system.example.com/login）
3. **测试账号**（如 13800138000）
4. **测试密码**（如 your_password_here）

获取来源优先级：
- 命令参数（`/init-bf SPD http://your-test-system.example.com/login 13800138000 your_password_here`）
- 项目目录中的 `*测试环境信息*.txt` 文件
- 项目目录名称推断（`D:\BF-纳杰电气` → 前缀 NJ，`D:\BF-输配电` → 前缀 SPD）
- 交互询问用户

### 第二步：探测项目结构

扫描当前项目目录，识别已有的目录和文件：
- `需求文档/` 及其子目录（sprint0/、sprint1/、sprint_all/、需求功能点/）
- `测试用例/` 及其子目录（sprint0/、sprint1/、sprint_all/、含 `.xlsx` 文件）
- `测试截图/` 或类似目录
- `*测试环境信息*.txt`
- `*VPN*密码*.txt`
- 是否已存在 CLAUDE.md
- 是否已存在 sprint 目录结构

同时检查项目根目录是否存在散落的中间产物文件（`.xlsx`、`.txt`、`.py`、`.md`、`.pem` 等），若有则建议用户移入对应目录：
- `.xlsx` → 提示移入 `测试用例/` 或 `testdata/`
- `.txt`（非配置文件）→ 提示移入 `testdata/` 或 `config/`
- `.pem` → 提示移入 `config/`
- 其他中间 `.md` / `.py` → 提示归档或删除

### 第三步：生成 CLAUDE.md

1. 读取模板文件 `~/.claude/skills/templates/claude-md.md`。
2. 用第一步和第二步收集的信息替换模板中的占位符：
   - `{前缀}` → 项目前缀
   - `{系统地址}` → 目标系统地址
   - `{账号}` → 测试账号
   - `{密码}` → 测试密码
   - `{根据实际探测结果生成目录树}` → 根据第二步探测结果生成实际目录树
3. 根据实际目录结构调整模板中的路径（如 `需求文档/` 不存在但有 `docs/`，则替换）。

### 第四步：写入 CLAUDE.md

将生成的 CLAUDE.md 写入当前项目根目录。

如果已有 CLAUDE.md，提示用户确认是否覆盖，或合并新增的 E2E 部分。

### 第五步：创建 Sprint 目录结构

检查项目是否已建立 sprint 目录结构。如果尚未建立，询问用户是否创建标准目录：

```
需求文档/
├── sprint0/                 # 基线版本（初始稳定版本需求文档放这里）
└── sprint_all/              # 汇总版本（持续更新的汇总版）

测试用例/
├── 测试用例模板.xlsx
├── sprint0/
│   └── sprint0_scripts/
├── sprint_all/
│   └── scripts/
```

如果用户选择创建，使用 `mkdir -p` 建立目录结构：
```bash
mkdir -p 需求文档/sprint0 需求文档/sprint_all
mkdir -p 测试用例/sprint0/sprint0_scripts 测试用例/sprint_all/scripts
```

如果项目已有 sprint 目录，跳过此步骤。

### 第六步：安装 Agent

将 BF 测试 Agent 安装到项目的 `.claude/agents/` 目录：

```bash
bash ~/.claude/skills/agents/install.sh "{项目根目录路径}"
```

安装完成后确认输出：
```
安装: bf-case-generator.md
安装: bf-e2e-generator.md
安装: bf-e2e-validator.md
安装: bf-e2e-healer.md
完成: 安装 4 个 Agent
```

若项目 `.claude/agents/` 目录下已有同名 Agent 文件，直接覆盖（更新到最新版本）。

## 注意事项

- 目录结构必须根据项目实际探测结果生成，不可使用固定路径
- 测试环境信息文件可能包含多个账号，优先使用第一条
- 项目前缀若无法自动推断，必须询问用户，不可留空
- Agent 安装后需**重启 Claude Code 会话**才能发现新 Agent
