# BF 全流程测试工作流 (bf-test-workflow)

> v2.0.0 — V2 知识图谱增强版

一套基于 Claude Code 的企业级测试自动化 Skill 体系，覆盖从需求文档到 E2E 测试的完整生命周期。**V2 引入 SQLite 知识图谱**，把功能点 / 用例 / 接口 / 脚本块 / 业务规则 / 端到端流程显式连成网，让用例生成、覆盖率、回归影响面全部变成「流程感知 + 跨模块」。支持 **Sprint 双轨迭代模式**，借鉴 Git 分支思想管理测试资产。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **🔧 V2 知识图谱** | SQLite 维护功能点/用例/接口/脚本/规则/流程的关联网，5 个查询原语（coverage/impact/setup/flow/recall） |
| **🔧 V2 跨模块依赖** | PRD 流程解析 + 接口入参出参匹配，自动推断 depends_on/precedes/consumes_data_from 边 |
| **🔧 V2 影响面分析** | sprintN 变更自动算出下游受影响用例 + 上游数据准备用例，回归范围精准 |
| **🔧 V2 FP 锚点** | 功能点标题带 HTML 注释锚点 `<!--FP_{缩写}_{序号}-->`，用例 `covers` 字段显式关联 |
| **🔧 V2 G1 公共闸门** | 所有模式（A/B/C）探索完功能点后，建图谱 + 人工确认依赖再进 P1 |
| **🔧 V2 merge-as-you-go** | 增量 Step4 子步骤完成立即 merge + build，图谱随时可查 |
| **Sprint 双轨迭代** | sprint0 基线 + sprintN 增量，sprint_all 汇总版持续更新 |
| **三种输入模式** | 需求文档驱动 / UI 探索驱动 / 混合模式 |
| **智能调度** | 主 Skill 调度，**6 个专用 Agent**（V2 新增 bf-graph-agent） |
| **断言质量保障** | 19 种语义断言映射 + 禁止弱断言 + 自动校验修复 |
| **选择器提取** | 使用 extract-selectors.js 确定性提取，不依赖 AI 推断 |
| **完整闭环** | 功能点 -> 测试用例 -> E2E 脚本 -> 执行修复 -> 结果回写 |
| **灵活回归** | 全量回归 / 精准回归 / 单模块回归三种模式 |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    bf-test-workflow (主 Skill)                   │
│            调度层 / 入口 / Sprint 管理 / AskUserQuestion           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┬───────────────────┐
    ▼                   ▼                   ▼                   ▼
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  探索层  │     │   用例层     │     │   生成层     │     │   修复层     │
│bf-ui-   │     │bf-case-     │     │bf-e2e-      │     │bf-e2e-      │
│explorer │     │generator    │     │generator    │     │healer       │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                   │                   │                   │
    ▼                   ▼                   ▼                   ▼
 功能点.md          cases.json         *.spec.ts          修复后测试
    │                   │                   │                   │
    └──────────┬────────┴─────────┬─────────┴──────────┬────────┘
               ▼                  ▼                    ▼
        ┌──────────────────────────────────────────────────┐
        │      bf-graph-agent (V2 新增)                    │
        │   带 Bash 专属跑 build_index.py                  │
        │   ┌────────────────────────────────────────┐    │
        │   │  SQLite 知识图谱 (sprint_all/索引/)     │    │
        │   │  • 5 查询原语（coverage/impact/setup/  │    │
        │   │    flow/recall）                       │    │
        │   │  • apply-confirmation 写 manual 边     │    │
        │   │  • pre_clean + post_clean 两阶段 GC    │    │
        │   └────────────────────────────────────────┘    │
        └────────────────────┬─────────────────────────────┘
                             │
                             ▼
                      bf-e2e-validator
                      (断言校验，消费图谱 covers 字段)
```

### Agent 职责划分（V2 共 6 个）

| Agent | 职责 | 工具权限 | V2 变化 |
|-------|------|----------|--------|
| **bf-ui-explorer** | 浏览器探索系统，发现功能点（标题带 FP 锚点） | 浏览器 + 创建文件 | + 锚点规则 + 页面流转链 |
| **bf-case-generator** | 生成测试用例 JSON（含 covers/tests_api） | 纯文件读写 | + covers 必填 + 流程上下文规则 |
| **bf-e2e-generator** | 录制选择器 + 生成 E2E 脚本 | 浏览器 + 创建文件 | + 影响面范围（impact/setup 命中才改） |
| **bf-e2e-validator** | 校验断言与预期对齐 | 文件读写 + 编辑 | （不变；可选注入 covers 做断言对齐） |
| **bf-e2e-healer** | 执行测试 + 诊断修复 + 回写结果 | 编辑 + Bash + 浏览器诊断 | （不变） |
| **bf-graph-agent** ⭐ | V2 新增：跑 build_index.py 维护图谱 | Bash + Read/Write/Glob/Grep | 新增 |

### 两条铁律

1. **AskUserQuestion 一律主对话发起**：子 agent 无法问用户/暂停
2. **Bash 分工**：bf-graph-agent 只管 DB 操作（build/query/apply-confirmation），文件操作（cp/diff/mkdir）留主对话

---

## V2 知识图谱（核心增强）

V2 引入一个由 `scripts/build_index.py` 维护的轻量知识图谱（SQLite），把功能点 / 用例 / 接口 / 脚本块 / 业务规则 / 端到端流程显式连成网。

### 节点 ID 规则

| 节点类型 | 前缀 | ID 格式 | 来源 |
|---------|------|--------|------|
| 功能点 | `fp` | `FP_{模块缩写}_{两位序号}` | 功能点.md 标题锚点 |
| 测试用例 | `case` | `{前缀}_TC_{模块缩写}_{三位序号}` | cases.json `id` |
| 接口 | `api` | `API_{大写下划线名}` | 接口功能点.md |
| 脚本块 | `script` | `SCRIPT_{模块}_{用例ID}` | spec.ts `test('ID - title')` |
| 业务规则 | `rule` | `RULE_{模块缩写}_{两位序号}` | 功能点.md `业务规则` |
| 端到端流程 | `flow` | `FLOW_{流程名}` | PRD 流程章节 |
| 页面 | `page` | `PAGE_{大写下划线名}` | bf-ui-explorer 报告 |

### 边类型与方向

**铁律**：`source=依赖者→target=被依赖者`

| 边类型 | 含义 | source → target |
|-------|------|----------------|
| `covers` | 用例覆盖功能点 | case → fp |
| `tests_api` | 用例验证接口 | case → api |
| `implements` | 脚本块实现用例 | script → case |
| `has_rule` | 功能点有业务规则 | fp → rule |
| `exposes` | 接口暴露给功能点 | api → fp |
| `step_in_flow` | 流程的步骤 | flow → fp |
| `precedes` | A 先于 B | 前置 fp → 后置 fp |
| `depends_on` | B 依赖 A | 依赖者 → 被依赖者 |
| `consumes_data_from` | B 消费 A 的数据 | 消费者 → 数据源 |

### 5 个查询原语

| 子命令 | 用途 | 示例 |
|-------|------|------|
| `query coverage [module]` | 模块/整体覆盖率 | `--query coverage --query-arg 下单` |
| `query impact [node_ids] --depth N` | 影响面（下游） | `--query impact --query-arg FP_XD_01 --depth 2` |
| `query setup [node_id] --depth N` | 上游数据准备 | `--query setup --query-arg FP_XD_02 --depth 3` |
| `query flow [fp_id]` | 流程上下文包 | `--query flow --query-arg FP_XD_02` |
| `query recall [query] --depth K` | 语义召回（FTS5/LIKE） | `--query recall --query-arg 支付 --depth 10` |

### 图谱产物固定位置（单一真相源）

每项目一个本地 SQLite 库，与其他项目天然隔离：

```
{项目根}/需求文档/sprint_all/索引/
├── 知识图谱.db              # SQLite 数据库
├── 知识图谱.json            # 节点/边 dump
├── 覆盖率报告.md
├── 流程依赖图.md            # Mermaid
├── 待确认依赖.md            # 启发式推断需人工确认
└── 影响面报告_sprintN.md    # 增量回归时按 sprint 产出
```

### build_index.py 两阶段 GC（V2 最新）

upsert 模式下，build 会做两次 GC：

| 阶段 | 时机 | scanned_ids | 目的 |
|------|------|-------------|------|
| **pre_clean** | extract 之前 | 空 set | 清掉所有非 manual 节点，让 extract_* 看到干净状态（避免模糊匹配 stale 节点） |
| **post_clean** | extract 之后 | 本次 scanned | 兜底清理本次 extract 产生的孤儿边（如 spec.ts 有 test 但 cases.json 删了对应 case） |

rebuild 模式不需要 GC（已 DROP）。

### mode 选择规则（增量 Step5a/5d）

| 变更类型 | mode | 原因 |
|---------|------|------|
| 仅**新增**模块 / FP / 用例 | `upsert` | pre_clean 已能感知，保留 manual 边 |
| **修改**已有 FP 锚点 / 用例 ID | `rebuild` | ID 改名，rebuild 最稳 |
| **删除**模块 / FP / 用例 | `rebuild` | 复杂删除场景最稳 |
| 不确定 | `rebuild` | 体量小重建几秒 |

---

## Sprint 双轨迭代模式

新版 Skill 引入 Sprint 迭代机制，借鉴 Git 的分支-合并思想：

```
需求文档/sprint0/  ──>  sprint0/（基线快照）
                     ↘
需求文档/sprintN/  ──>  sprintN/（增量快照）──> 覆盖回 sprint_all/（汇总版）
```

### Git 类比

| Git 概念 | Skill 对应 |
|---------|-----------|
| main 分支 | sprint_all/（汇总版） |
| feature 分支 | sprintN/（增量版） |
| 基线提交 | sprint0/（初始稳定版本） |
| git merge | 增量 Step 5：覆盖回 sprint_all |
| git diff | 增量 Step 1：对比 sprint_all 识别变更模块 |
| CI 精准测试 | 只跑 sprintN 变更模块 |
| nightly 全量测试 | 跑 sprint_all 所有模块 |

### 调用方式

```
/bf-test-workflow              → 全量模式（处理 sprint0，输出到 sprint0/ 和 sprint_all/）
/bf-test-workflow sprintN      → 增量模式（处理 sprintN，变更覆盖回 sprint_all/）
```

### 增量流程（sprintN 专属）

1. **解析 PRD + 影响面分析**：识别变更模块，调度 bf-graph-agent `build` + `query impact/setup`，产 `影响面报告_sprintN.md`
2. **处理 unresolved_deps（1e 子步）**：检测新启发式依赖（含 conflict/tests_api/precedes），主对话 AskUserQuestion 分类处理
3. **用户确认模块列表**：展示检测到的模块，用户可补充或删除
4. **复制文件（按影响面）**：仅复制 impact/setup 命中模块（V2 改造：cp 粒度细化）
5. **增量处理**：
   - 4a 更新功能点.md（模式 A 主对话加 FP 锚点；模式 B/C 走 bf-ui-explorer）
   - 4b 生成完整快照 cases.json（调度 bf-case-generator）
   - 4c 更新 E2E 脚本（调度 bf-e2e-generator + validator，注入影响面范围）
6. **merge-as-you-go 覆盖回 sprint_all**：
   - 5a 功能点先 merge + build（让 covers 边能连）
   - 5b cases.json merge
   - 5c 脚本 merge
   - 5d 最终 build + 重新生成 testCase.xlsx
7. **流程衔接**：展示完成状态、回归命令、后续手动触发步骤

### G1 公共骨架图谱闸门（V2 新增，仅全量模式）

模式 A/B/C 收敛后、P1 之前，建立项目骨架图谱：

```
G1.1 merge sprint0 → sprint_all  （仅全量，保证单一真相源数据完整）
G1.2 调度 bf-graph-agent build --rebuild
G1.3 主对话 AskUserQuestion 逐条确认 unresolved_deps → apply-confirmation
G1.4 暂停输出统计 → 等用户「继续」→ 进入 P1
```

> 增量模式（sprintN）不走 G1，它有自己的 Step1-6 流程。

### 合并规则

| 场景 | 处理方式 |
|------|---------|
| 修改已有功能点 | 覆盖 sprint_all |
| 删除已有功能点 | 从 sprint_all 删除 |
| 新增功能点 | 追加到 sprint_all |
| 修改已有用例（同ID） | 覆盖 sprint_all |
| 新增用例（新ID） | 追加到 sprint_all |
| 新增模块 | 在 sprint_all 创建新目录 |

### 回归测试

```
# 全量回归（sprint_all 所有模块）
npx playwright test --config=测试用例/sprint_all/scripts/playwright.config.ts

# 精准回归（只跑 sprintN 变更模块）
npx playwright test --config=测试用例/sprintN/sprintN_scripts/playwright.config.ts

# 单模块回归
npx playwright test 测试用例/sprint_all/scripts/{模块名}.spec.ts
```

---

## 三种工作模式

### 模式 A：主需求文档辅 UI 探索

需求文档完整，以文档为主，UI 探索补充文档未提及的功能。

### 模式 B：主 UI 探索辅需求文档

需求文档不完整，以 UI 探索为主，文档补充业务细节。

### 模式 C：纯 UI 探索

无需求文档，完全依赖浏览器探索。

### 混合模式

用户指定某些模块不完整，不完整的模块按模式 B 处理，其他模块按模式 A 处理。

---

## 完整流程

### 阶段 1：功能点发现

**输入**：需求文档 或 运行中的 Web 应用

**输出**：`需求文档/{sprint}/需求功能点/{模块名}/功能点.md`

功能点文件结构：
```markdown
# {模块名} 功能点

## 功能点1：{功能名称}

- **描述**：{功能描述}
- **操作入口**：{如何到达该功能}
- **交互元素**：{表单字段、按钮、表格等}
- **业务规则**：{必填项、格式要求、校验规则}
- **优先级**：{高/中/低}
- **来源**：需求文档 / UI探索
```

### 阶段 2：测试用例生成

**输入**：功能点.md

**输出**：`需求文档/{sprint}/需求功能点/{模块名}/cases.json`

用例格式：
```json
{
  "id": "SPD_TC_SJZH_001",
  "module": "数据整合",
  "title": "正常登录并查看数据列表",
  "precondition": "1. 系统可访问；2. 测试账号有效",
  "test_data": "账号: {TEST_PHONE}, 密码: {TEST_PASSWORD}",
  "steps": "1. 用户输入用户名、密码点击登录。\n2. 点击「数据整合」菜单。\n3. 查看数据列表。",
  "expected": "1. 登录成功，跳转首页。\n2. 进入数据整合页面。\n3. 列表正确加载，显示数据。",
  "covers": ["FP_SJZH_01"],
  "tests_api": []
}
```

**V2 字段说明**：
- `covers`（必填）：该用例覆盖的功能点 FP 锚点列表，从 功能点.md 标题锚点读取
- `tests_api`：该用例验证的接口 ID 列表（如 `API_ORDER_CREATE`），无则 `[]`

**覆盖率检查**（V2 改造）：调度 bf-graph-agent `query coverage`，读 `覆盖率报告.md`，低于 80% 把未覆盖 FP 注入补用例 agent。

### 阶段 3：E2E 脚本生成

**输入**：cases.json

**输出**：
- `{脚本路径}/selectors/{模块名}.selectors.ts` — 选择器映射（Page Object）
- `{脚本路径}/{模块名}.spec.ts` — Playwright 测试脚本
- `{脚本路径}/fixtures/login.fixture.ts` — 共享登录 fixture
- `{脚本路径}/playwright.config.ts` — Playwright 配置

**生成流程**：
1. 录制核心链路（1-3 条用例），理解页面布局
2. 使用 extract-selectors.js 提取真实选择器（确定性逻辑，不依赖 AI）
3. 生成 selectors.ts（Page Object Model）
4. 批量生成 spec.ts（从 cases.json 文本生成）
5. 自动校验断言质量（bf-e2e-validator）

### 阶段 4：执行与修复

**输入**：spec.ts 文件

**输出**：
- 修复后的测试脚本
- testCase.xlsx 实际结果回写
- 执行报告摘要
- 失败用例截图（`测试截图/{模块名}-{用例ID}-failed.png`）

**修复策略**：
- 检测系统性失败（选择器层面）→ 批量修复 selectors.ts
- 检测个体性失败（断言/等待）→ 逐条修复 spec.ts
- 最多 3 轮修复，仍失败则标记失败并截图
- **严格规则**：不允许修改预期结果值，实际值不符应标记为 bug

---

## 选择器提取机制

使用 extract-selectors.js 确定性逻辑提取页面选择器，不依赖 AI 推断：

```
选择器优先级：
1. #id                    → page.locator('#xxx')
2. [data-testid="xxx"]    → page.getByTestId('xxx')
3. .arco-xxx class        → page.locator('.arco-xxx')
4. tag + text             → page.locator('button').filter({ hasText: 'xxx' })
```

---

## 断言质量保障

### 禁止的弱断言

```typescript
// ❌ 禁止
expect(something).toBeTruthy()
expect(count).toBeGreaterThanOrEqual(0)
expect(text).not.toBe('')

// ✅ 必须
expect(text).toContainText('具体值')
expect(count).toBe(5)
expect(button).toBeVisible()
```

### 自动校验流程

bf-e2e-validator 逐条比对 cases.json 的 expected 和 spec.ts 的 expect()：
- 弱断言 → 自动修复为强断言
- 缺失断言 → 补充断言
- 断言不匹配 → 修正断言
- 校验报告 → `reports/validation/{模块名}-validation.md`

---

## 环境要求

### Skills 存放位置

```
Windows:  C:\Users\{用户名}\.claude\skills\
macOS:    ~/.claude/skills/
Linux:    ~/.claude/skills/
```

### 安装方式

```bash
# 克隆仓库后，运行全局安装脚本
bash install.sh

# 安装 Python 依赖
pip install -r requirements.txt
```

安装完成后重启 Claude Code 会话，在被测项目中执行 `/init-bf` 初始化。

### 环境依赖

| 依赖 | 说明 | 安装方式 |
|------|------|---------|
| **Claude Code CLI** | Skill 运行基础 | 参见 [Claude Code 文档](https://docs.anthropic.com/en/docs/claude-code) |
| **Node.js** | Playwright 运行时 | [nodejs.org](https://nodejs.org/) |
| **Playwright** | 浏览器自动化 | `npm install -g @anthropic-ai/mcp-server-playwright` 并在 Claude Code MCP 配置中注册 |
| **Chromium** | Playwright 浏览器引擎 | `npx playwright install chromium` |
| **Python 3** | 文档解析、Excel 处理 | 系统自带或 [python.org](https://python.org/) |
| **Python 包** | python-docx、openpyxl、pypdf | `pip install -r requirements.txt` |

### 完整路径结构

```
仓库目录（发布前）:
├── install.sh                   # 全局安装脚本
├── requirements.txt             # Python 依赖
├── bf-test-workflow.md          # 主 Skill（调度层入口）
├── init-bf.md                   # 项目初始化 Skill
├── agents/                      # Agent 定义文件
│   ├── bf-ui-explorer.md
│   ├── bf-case-generator.md
│   ├── bf-e2e-generator.md
│   ├── bf-e2e-validator.md
│   ├── bf-e2e-healer.md
│   ├── bf-graph-agent.md        # ⭐ V2 新增：图谱子 agent
│   └── install.sh               # 项目级 Agent 安装脚本
├── templates/                   # 模板文件
│   ├── claude-md.md             # 含 V2 关联图谱约定
│   ├── page-object.ts
│   ├── login-fixture.ts
│   ├── assertion-mapping.md
│   ├── write-results.py
│   ├── extract-selectors.js
│   └── sub-agent-prompt.md
└── scripts/
    ├── json_to_excel.py         # V2：10 列输出（加 covers/tests_api）
    └── build_index.py           # ⭐ V2 新增：知识图谱构建器（含 5 查询 + GC + 冲突检测）

安装后 ~/.claude/skills/:
├── bf-test-workflow.md
├── init-bf.md
├── agents/                      # Agent 定义 + 项目级安装脚本
├── templates/                   # 模板文件
└── scripts/                     # 工具脚本（含 build_index.py）
```

### V2 项目级图谱产物位置

```
项目根目录/
└── 需求文档/sprint_all/索引/     # ⭐ 唯一图谱位置（单一真相源）
    ├── 知识图谱.db              # SQLite
    ├── 知识图谱.json
    ├── 覆盖率报告.md
    ├── 流程依赖图.md            # Mermaid
    ├── 待确认依赖.md
    └── 影响面报告_sprintN.md    # 增量时按 sprint 产出
```

---

## 项目初始化

### 前置条件

| 项目 | 说明 | 示例 |
|------|------|------|
| **项目前缀** | 2-4 位大写字母 | SPD、NJ、BF |
| **系统地址** | 被测系统 URL | http://your-test-system.example.com/ |
| **测试账号** | 登录用户名 | 13800138000 |
| **测试密码** | 对应密码 | your_password_here |

### 初始化方式

```bash
# 自动探测（推荐）
/init-bf

# 手动指定参数
/init-bf SPD http://your-test-system.example.com/login 13800138000 your_password_here

# 混合方式
/init-bf SPD
```

### 初始化内容

1. 生成项目 CLAUDE.md
2. 创建 Sprint 目录结构（sprint0/、sprint_all/）
3. 安装 **6 个 Agent** 到 .claude/agents/（V2 含 bf-graph-agent）
4. **V2 第七步：一次性环境自检**——检测 Python 版本、sqlite3 + FTS5 可用性、docx/openpyxl/pypdf 库，结果写入 CLAUDE.md（`v2_fts5=ok/fallback_like`、`v2_sqlite3=ok`）

### 推荐的项目目录结构

```
项目根目录/
├── CLAUDE.md
├── 需求文档/
│   ├── sprint0/                     # 基线版本需求文档
│   ├── sprint1/                     # Sprint1 增量需求文档
│   └── sprint_all/                  # 汇总版本
│       └── 需求功能点/
│           ├── 模块A/
│           │   ├── 功能点.md
│           │   └── cases.json
│           └── 模块B/
├── 测试用例/
│   ├── 测试用例模板.xlsx
│   ├── sprint0/
│   │   ├── sprint0_testCase.xlsx
│   │   └── sprint0_scripts/
│   ├── sprint_all/
│   │   ├── testCase.xlsx
│   │   └── scripts/
│   └── sprintN/
│       ├── sprintN_testCase.xlsx
│       └── sprintN_scripts/
├── 测试截图/
├── reports/
└── config/
```

---

## 命令速查

| 命令 | 说明 |
|------|------|
| `/init-bf` | 初始化项目配置 + Sprint 目录结构 + **6 个 Agent 安装** + **V2 第七步环境自检** |
| `/bf-test-workflow` | 全量模式（处理 sprint0） |
| `/bf-test-workflow sprint1` | 增量模式（处理 sprint1） |
| 后接 "开始UI测试" | 进入 E2E 脚本生成 |
| 后接 "开始接口测试" | 进入接口测试用例生成 |
| 后接 "开始执行测试" | 运行 E2E 测试并自动修复 |
| 后接模块名 | 只执行指定模块 |

### V2 图谱命令（由 bf-graph-agent 执行）

```bash
# 建图（首次或大改用 --rebuild；增量更新用 --build）
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --rebuild --sprint-tag sprint0

# 5 个查询原语
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --query coverage
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --query impact --query-arg FP_XD_01 --depth 2
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --query setup --query-arg FP_XD_02 --depth 3
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --query flow --query-arg FP_XD_02
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all --query recall --query-arg 支付 --depth 10

# apply-confirmation 写 manual 边（A1.6 闸门 / 1e 子步）
python ~/.claude/skills/scripts/build_index.py \
    --project {项目根} --source sprint_all \
    --apply-confirmation '{"edges":[{"source":"FP_XD_01","target":"FP_XD_02","kind":"precedes"}]}'
```

---

## 注意事项

1. **首次使用前**：必须先执行 `/init-bf` 初始化项目配置（V2 含第七步环境自检，FTS5 不可用时自动降级 LIKE）
2. **Agent 安装后**：需重启 Claude Code 会话才能发现新 Agent
3. **Sprint 目录**：每个 sprint 文件夹是独立完整快照，可独立运行回归
4. **增量模式**：功能点.md 写增量（只含变更），cases.json 写完整快照（含所有用例）
5. **合并回写**：增量完成后必须覆盖回 sprint_all，保持汇总版最新
6. **JSON 格式**：菜单名、按钮名使用「」包裹，禁止使用双引号
7. **选择器优先级**：id > data-testid > arco- class > tag+text
8. **断言失败不改脚本**：断言失败时记录实际值和预期值差异，标记为失败
9. **回归不消耗 token**：修复完成后可直接运行 npx playwright test
10. **V2 单一真相源**：图谱只在 `需求文档/sprint_all/索引/` 创建与查询，不在 sprint0/sprintN 创建
11. **V2 FP 锚点必填**：功能点.md 每个标题必须带 `<!--FP_{缩写}_{NN}-->`，否则图谱解析不到
12. **V2 covers 必填**：cases.json 每条用例 `covers` 字段必须填 FP 锚点，否则不计入覆盖率
13. **V2 mode 选择**：仅新增 → upsert；修改/删除 → rebuild；不确定优先 rebuild
14. **V2 manual 边保护**：apply-confirmation 写的 manual 边两端节点不会被 GC 清
15. **V2 AskUserQuestion 主对话**：所有用户确认一律主对话发起（G1.3 / Step1 1e / Step2 模块列表）

---

## 常见问题

### Q: 全量模式和增量模式有什么区别？

A: 全量模式（`/bf-test-workflow`）处理 sprint0 基线，同时输出到 sprint0/ 和 sprint_all/。增量模式（`/bf-test-workflow sprintN`）只处理 sprintN 的变更模块，完成后覆盖回 sprint_all/。

### Q: sprint_all 和 sprintN 的关系是什么？

A: sprint_all 类似 Git 的 main 分支，是所有模块的汇总版。sprintN 类似 feature 分支，是某次迭代的增量快照。增量处理完成后，变更会合并回 sprint_all。

### Q: 覆盖率低于 80% 怎么办？

A: 系统会自动启动 bf-case-generator 补充用例，直至达到 80% 覆盖率。

### Q: E2E 修复超过 3 轮怎么办？

A: 失败用例会被截图保存到 `测试截图/{模块名}-{用例ID}-failed.png`，并在报告中标注失败原因，交由测试人员判断。

### Q: 回归测试还需要消耗 token 吗？

A: 不需要。修复完成后可直接运行 npx playwright test，支持三种回归模式：全量回归（sprint_all）、精准回归（sprintN）、单模块回归。

### Q: 如何查看断言校验报告？

A: 查看 `reports/validation/{模块名}-validation.md`，包含问题清单和修复状态。

### Q: V2 知识图谱有什么用？

A: 把功能点/用例/接口/脚本/规则/流程连成网，提供 5 个查询：
- `coverage`：精确算覆盖率（替代 V1 文本模糊匹配）
- `impact`：sprintN 变更算下游受影响用例（精准回归）
- `setup`：算上游数据准备用例（fixture 复用）
- `flow`：流程上下文注入 case-generator（补下游边界用例）
- `recall`：FTS5/LIKE 语义召回（兜底隐性依赖）

### Q: 全量模式为什么新增 G1 闸门？

A: V1 模式 A 在 A1 文档解析后就建图，但 A2/A3 还会产生新功能点，图谱不完整。V2 把建图移到所有模式（A/B/C）探索完成后，先建骨架 + 人工确认依赖（G1.3 AskUserQuestion），再进 P1 生成用例。

### Q: FP 锚点冲突怎么办？

A: 同一 `功能点.md` 内出现重复 FP 锚点（如两个 `FP_XD_01`）时，build_index.py 会写入 `unresolved_deps`（kind=`conflict`），重复节点不入图。主对话在 G1.3 / Step1 1e 通过 AskUserQuestion 提示用户回 Step 4a 修功能点.md 序号。

### Q: upsert 模式删除用例会怎样？

A: V2 build_index.py 有两阶段 GC：
- **pre_clean**：清掉所有非 manual 节点（让 extract_* 看到干净状态）
- **post_clean**：兜底清理本次 extract 产生的孤儿边
- 删除的 case 节点 + covers 边 + 孤儿 implements 边都会被清，覆盖率正确反映当前状态

### Q: rebuild 和 upsert 怎么选？

A: 看 [mode 选择规则](#mode-选择规则增量-step5a5d) 表。简单记法：**仅新增 → upsert；涉及修改/删除 → rebuild；不确定优先 rebuild**（sprint_all 体量小，重建几秒）。
