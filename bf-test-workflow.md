---
description: 从需求文档或UI探索到UI自动化测试的全流程，支持文档驱动、UI探索驱动和混合模式。支持全量模式（sprint0）和增量模式（sprintN）
---

# BF 全流程测试工作流

本 Skill 是调度层，重活交给专用 Agent 执行：
- **bf-ui-explorer**：浏览器探索系统，发现功能点（浏览器 + 创建文件）
- **bf-case-generator**：生成测试用例 JSON（仅文件读写）
- **bf-e2e-generator**：录制选择器 + 生成 E2E 脚本（浏览器 + 创建文件）
- **bf-e2e-validator**：校验断言质量，比对 expected 与 expect()（仅文件读写）
- **bf-e2e-healer**：执行测试 + 修复 + 回写结果（编辑 + Bash + 浏览器诊断）

请严格按以下阶段执行，根据用户当前提供的资源自动推进流程。

---

## 智能入口：参数解析 + 模式选择

### 参数说明

```
/bf-test-workflow              → 全量模式（处理 sprint0，输出到 sprint0/ 和 sprint_all/）
/bf-test-workflow sprintN      → 增量模式（处理 sprintN，变更覆盖回 sprint_all/）
```

- 无参数：全量模式，读取 `需求文档/sprint0/`，产出写入 `sprint0/` 和 `sprint_all/`
- sprintN 参数：增量模式，读取 `需求文档/sprintN/`，产出写入 `sprintN/`，完成后覆盖回 `sprint_all/`

### Step 0：检测项目资源

1. 从 CLAUDE.md 提取项目配置（系统地址、测试账号、脚本存放路径等）。若缺失提示用户先执行 `/init-bf`。
2. 解析参数，判断运行模式：
   - 无参数 → **全量模式**，扫描 `需求文档/sprint0/` 目录
   - `sprintN` → **增量模式**，扫描 `需求文档/sprintN/` 目录
3. 扫描对应目录，判断是否存在可解析的需求文档（`.docx`/`.pdf`/`.txt`/`.md`）。
4. 根据检测结果自动选择路径：

```
对应 sprint 目录有可解析文件？
├── 无 → 直接进入【模式 C：纯 UI 探索】，不询问
└── 有 → 询问用户（AskUserQuestion）：
         "当前项目需求文档是否完整？"
         ├── "完整"         → 【模式 A：主文档辅 UI】
         ├── "不完整"       → 【模式 B：主 UI 辅文档】
         └── "xxx模块不完整" → 【混合模式：按模块分别处理】
```

**混合模式说明**：用户指定某些模块不完整（如"数据整合和物料看板不完整"），则：
- 不完整的模块 → 按【模式 B：主 UI 辅文档】处理
- 其他模块 → 按【模式 A：主文档辅 UI】处理

### 路径约定

以下文档中用 `{sprint}` 代表当前 sprint 目录名（如 `sprint0`、`sprint1`），`{sprint_scripts}` 代表对应脚本目录：

| 模式 | 需求文档输入 | 功能点输出 | Excel 输出 | 脚本输出 |
|------|------------|-----------|-----------|---------|
| 全量 | `需求文档/sprint0/` | `需求文档/sprint0/需求功能点/` + `需求文档/sprint_all/需求功能点/` | `测试用例/sprint0/sprint0_testCase.xlsx` + `测试用例/sprint_all/testCase.xlsx` | `测试用例/sprint0/sprint0_scripts/` + `测试用例/sprint_all/scripts/` |
| 增量 | `需求文档/sprintN/` | `需求文档/sprintN/需求功能点/` | `测试用例/sprintN/sprintN_testCase.xlsx` | `测试用例/sprintN/sprintN_scripts/` |

---

## 模式 A：主需求文档辅 UI 探索

需求文档完整，以文档为主，UI 探索补充文档未提及的功能。

### A1. 文档解析（主）

1. 读取 `需求文档/{sprint}/` 目录下的所有文档。支持的文件类型及处理方式：
   - `.docx` / `.doc`：使用 `python-docx` 提取文本。
   - `.pdf`：使用 `pypdf` 或 `pdfplumber` 提取文本。
   - `.txt`：直接读取。
   - `.md`：直接读取。
   - `.xmind`：优先尝试 `xmindparser` 库解析为文本；若库不可用，提示用户转换为 `.md` 或 `.txt` 后再放入目录。
   - **图片**（`.png` / `.jpg` / `.bmp`）：调用 OCR 库（如 `pytesseract`）提取文字；若 OCR 不可用或提取失败，要求用户手动提供图片中的关键文本。
2. 将所有提取到的文本合并，按文件来源添加标记，形成 `scripts/temp/_combined_docs.txt` 临时文件。若 `scripts/temp/` 目录不存在则先创建。
3. 分析合并后的文档，识别出系统的所有功能模块。
4. 在 `需求文档/{sprint}/` 下创建 `需求功能点/` 文件夹，并为每个模块创建子文件夹。全量模式时同时在 `需求文档/sprint_all/` 下创建对应的 `需求功能点/` 目录。
5. 在每个模块子文件夹下生成 `功能点.md`，遵循以下模板：

```markdown
# {模块名} 功能点

## 功能点1：{功能名称}

- **描述**：{从需求文档提取的功能描述，用自己的话概括，不要照搬原文}
- **操作入口**：{文档中描述的功能入口路径，如"点击左侧菜单'{模块名}' → 点击'新增'按钮"；文档未提及则写"文档未提及"}
- **交互元素**：{文档中涉及的表单字段、按钮、表格等；文档未提及则写"文档未提及"}
- **业务规则**：{必填项、数据格式、校验规则等约束}
- **优先级**：{高/中/低，根据文档中的业务重要性判断}
- **来源**：需求文档（{原始文件名}）
```

约束：
- 每个字段都必须填写，不可省略；文档确实未提及的字段写"文档未提及"，不要留空或跳过
- 描述要具体可理解，不要照搬文档原文的模糊表述
- 业务规则要尽量提取具体的约束条件（字段长度、格式要求、必填/选填），不要只写"按文档要求"
6. 报告：生成了哪些模块、每个模块多少功能点。

### A2. UI 探索补充（辅）

启动 bf-ui-explorer Agent，补充文档可能遗漏的功能：

```
subagent_type: bf-ui-explorer
```

Agent prompt：
```
系统地址：{从 CLAUDE.md 提取}
测试账号：{从 CLAUDE.md 提取}
探索模式：全量
输出目录：需求文档/{sprint}/需求功能点/
已有功能点目录：需求文档/{sprint}/需求功能点/

请探索系统，跳过已有 功能点.md 的模块。
只发现文档未覆盖的新模块/新功能。
```

### A3. 合并去重（主对话执行）

1. 读取文档生成的 `需求文档/{sprint}/需求功能点/` 下的 `功能点.md`（主源）
2. 读取 UI 探索新生成的功能点文件（辅源）
3. 合并逻辑：
   - 主辅都有同一功能 → 保留主源描述，不重复
   - 只有主源有 → 直接保留
   - 只有辅源有（文档未提及的功能/隐藏功能） → 追加到对应模块的 `功能点.md`，标记 `来源: UI探索`
   - 辅源发现文档没有的整个新模块 → 在 `需求文档/{sprint}/需求功能点/` 下创建新模块文件夹，标记 `来源: UI探索`
4. 向用户展示合并结果，确认后继续。

---

## 模式 B：主 UI 探索辅需求文档

需求文档不完整，以 UI 探索为主，文档补充业务细节。

### B1. UI 探索（主）

启动 bf-ui-explorer Agent 进行全量探索：

```
subagent_type: bf-ui-explorer
```

Agent prompt：
```
系统地址：{从 CLAUDE.md 提取}
测试账号：{从 CLAUDE.md 提取}
探索模式：全量
输出目录：需求文档/{sprint}/需求功能点/
已有功能点目录：需求文档/{sprint}/需求功能点/（可能为空）

请全面探索系统的每个模块和页面，生成所有模块的功能点.md。
```

### B2. 文档补充（辅）

1. 读取 `需求文档/{sprint}/` 中已有的文档（可能只覆盖部分模块）。
2. 对比 UI 探索生成的 `功能点.md`：
   - 文档中有更详细的业务规则/优先级 → 补充到对应功能点的描述中
   - 文档中提到的功能在 UI 上找不到 → 保留，标记 `来源: 文档（页面未找到入口）`
3. 向用户展示补充结果，确认后继续。

---

## 模式 C：纯 UI 探索

无需求文档，完全依赖 UI 探索。

### C1. UI 探索

与 B1 相同，启动 bf-ui-explorer Agent 全量探索。无文档补充步骤。

---

## 公共流程：功能点 → 测试用例 → E2E

以下阶段在所有模式中完全一致，输入路径由当前 sprint 决定。

### P1. 生成测试用例（Agent 并行方案）

#### P1.1 准备工作（主对话执行）

1. 读取 `测试用例/测试用例模板.xlsx`，获取列定义与样式。
2. **确定项目前缀**：使用 AskUserQuestion 询问用户。
3. 统计 `需求文档/{sprint}/需求功能点/` 下所有模块，为每个模块确定**模块缩写**。
4. 确认脚本存在：`~/.claude/skills/scripts/json_to_excel.py`。

#### P1.2 启动 bf-case-generator Agent（并行）

将模块按每批 2-3 个分组，每批启动 1 个 Agent：

```
subagent_type: bf-case-generator
```

Agent prompt 示例：
```
项目前缀：SPD
模块列表及缩写：
- 数据整合 → SJZH
- 物料协同看板 → WLXT

请读取以下功能点文件并生成测试用例 JSON：
- 需求文档/{sprint}/需求功能点/数据整合/功能点.md
- 需求文档/{sprint}/需求功能点/物料协同看板/功能点.md

生成的 cases.json 与功能点.md 放在同一目录下。
```

##### P1.3 执行模板脚本（主对话执行）

所有 Agent 完成后，执行：

```bash
# 全量模式
python ~/.claude/skills/scripts/json_to_excel.py --sprint sprint0
# 同时生成 sprint_all 版本
python ~/.claude/skills/scripts/json_to_excel.py --input 需求文档/sprint_all/需求功能点 --output 测试用例/sprint_all/testCase.xlsx

# 增量模式
python ~/.claude/skills/scripts/json_to_excel.py --sprint sprintN
```

该脚本会扫描对应 sprint 目录下的 `需求功能点/*/cases.json`，按列定义写入 `testCase.xlsx`，每个模块一个 Sheet。

#### P1.4 覆盖率检查

若覆盖率不足 80%，对未覆盖模块追加启动 Agent 补充用例。

### P2. 审核测试用例（主对话执行）

1. 对生成的 `testCase.xlsx` 进行自检：
   - 计算功能点覆盖率：统计 `需求文档/{sprint}/需求功能点/*/功能点.md` 中所有功能点，检查是否全部有对应用例。
   - 检查用例可执行性：步骤是否具体、预期结果是否可验证、前置条件是否可满足。
   - 标记可能不可执行或冗余的用例。
2. 生成审核报告，保存在 `reports/测试用例审核报告.md`，内容包括：
   - 覆盖率数值（如 92%）
   - 未覆盖的功能点列表及原因
   - 优化建议
3. 如果覆盖率低于 80%，主动请求用户确认是否补充用例，并循环补充直至达标。

### P3. 接口测试（需用户触发）

当用户明确说"开始接口测试"或提供接口文档后执行：

1. 如果接口文档尚未在 `需求文档/{sprint}/` 中，请用户提供接口文档文件（支持 .docx/.pdf/.md/.txt 等，处理方式同 A1）。
2. 解析接口信息，识别所有 API 端点、方法、请求参数、响应字段及约束。
3. 在 `需求文档/{sprint}/需求功能点/接口测试/` 目录下生成 `接口功能点.md`。
4. 生成接口测试用例，覆盖：
   - 正向调用：正确参数返回 200 及预期数据。
   - 参数异常：必填缺失、类型错误、越界值等。
   - 业务边界：资源不存在、重复提交、状态限制等。
   - 鉴权与权限。
5. 将接口测试用例写入 `测试用例/{sprint}/{sprint}_testCase.xlsx`（全量模式为 `测试用例/sprint_all/testCase.xlsx`）的新 Sheet（名如"接口测试_xxx"），遵循相同的列格式。
6. 若需要，同时生成可执行的 Python + Requests/Pytest 脚本模板，保存至 `测试用例/scripts/api_test_template.py`。

---

## 阶段 B：UI 自动化 - 生成（需用户触发）

当用户说"开始UI测试"后执行。

### B.0 检查项目配置（主对话执行）

确认 CLAUDE.md 存在且包含：系统地址、测试账号密码、脚本存放路径。若缺失，提示用户先执行 `/init-bf`。

### B.1 启动 bf-e2e-generator Agent（可并行）

对每个模块（或用户指定的模块）启动 Agent。若模块数量多，可分批启动 Agent，每批 2-3 个并行。

```
subagent_type: bf-e2e-generator
```

Agent prompt 示例：
```
模块名称：数据整合
系统地址：{SYSTEM_URL}
测试账号：{TEST_PHONE} / {TEST_PASSWORD}
脚本存放路径：测试用例/{sprint}/{sprint_scripts}/
用例文件：需求文档/{sprint}/需求功能点/数据整合/cases.json
```

Agent 会自动完成：录制选择器 → 生成 selectors.ts → 生成 spec.ts → 生成 fixture 和 config。

### B.2 检查 Agent 输出

确认每个模块生成了完整的文件结构：
```
测试用例/{sprint}/{sprint_scripts}/
├── playwright.config.ts
├── fixtures/login.fixture.ts
├── selectors/{模块名}.selectors.ts
└── {模块名}.spec.ts
```

### B.3 校验断言质量（自动执行）

e2e-generator 完成后，自动启动 bf-e2e-validator 校验断言：

```
subagent_type: bf-e2e-validator
```

Agent prompt 示例：
```
模块名称：采购量统计
用例文件：需求文档/{sprint}/需求功能点/采购量统计/cases.json
测试脚本：测试用例/{sprint}/{sprint_scripts}/采购量统计.spec.ts
断言映射表：~/.claude/skills/templates/assertion-mapping.md
```

校验器会逐条比对 cases.json 的 expected 和 spec.ts 的 expect()，输出问题清单并自动修复弱断言。

---

## 阶段 C：UI 自动化 - 执行与修复（需用户触发）

参数: $ARGUMENTS （可选，模块名称；不传则执行全部）

### C.1 启动 bf-e2e-healer Agent

```
subagent_type: bf-e2e-healer
```

Agent prompt 示例：
```
模块名称：数据整合
脚本存放路径：测试用例/{sprint}/{sprint_scripts}/
playwright 配置路径：测试用例/{sprint}/{sprint_scripts}/playwright.config.ts
测试用例文件：测试用例/{sprint}/{sprint}_testCase.xlsx
回写脚本路径：~/.claude/skills/templates/write-results.py
```

Agent 会自动完成：执行测试 → 分析失败 → 修复（最多 3 轮）→ 回写结果 → 输出报告。

### C.2 收集报告

若启动了多个模块的 Agent，汇总所有报告：

```
整体测试摘要：
模块A：通过 xx / 失败 xx / 跳过 xx
模块B：通过 xx / 失败 xx / 跳过 xx
总计：通过 xx / 失败 xx / 跳过 xx

跳过用例汇总：
- {模块A} {用例ID}: {原因}
- {模块B} {用例ID}: {原因}
```

截图检查：
- 确认 `测试截图/` 目录存在
- 列出失败用例的截图文件：{模块名}-{用例ID}-failed.png
- 若失败用例无截图，提示 Agent 未遵守截图规则

提示用户后续回归可直接运行 `npx playwright test`，无需再消耗 token。

---

## 阶段 D：清理

工作流完成后，删除所有临时文件：

```bash
rm -rf scripts/temp/
```

确认目录已删除后，输出"临时文件已清理"。

---

## 增量模式专属流程（sprintN）

当用户执行 `/bf-test-workflow sprintN` 时，在进入公共流程之前，需要先执行以下步骤。

### 增量 Step 1：解析 PRD，识别变更模块

1. 读取 `需求文档/sprintN/` 目录下的需求文档。
2. 解析文档内容，提取涉及的模块列表。
3. 与 `需求文档/sprint_all/需求功能点/` 对比，区分：
   - **已有模块**（sprint_all 中已存在）→ 需要从 sprint_all 复制
   - **新增模块**（sprint_all 中没有）→ 无需复制，标记为全新

### 增量 Step 2：用户确认模块列表

通过 AskUserQuestion 展示检测到的模块：

```
sprintN PRD 涉及以下模块：
  已有模块（将从 sprint_all 复制）：
     - 数据整合
     - 采购量统计
  新增模块（无需复制，将全新生成）：
     - 新增模块X

是否还有其他需要变更的模块？
```

用户可以补充或删除模块，确认后继续。

### 增量 Step 3：复制相关文件

根据用户确认的模块列表，从 sprint_all 复制到 sprintN：

**已有模块**（需要复制）：
```bash
# 功能点和用例
cp -r 需求文档/sprint_all/需求功能点/{模块名}/ 需求文档/sprintN/需求功能点/{模块名}/

# 选择器映射
cp 测试用例/sprint_all/scripts/selectors/{模块名}.selectors.ts 测试用例/sprintN/sprintN_scripts/selectors/

# 测试脚本
cp 测试用例/sprint_all/scripts/{模块名}.spec.ts 测试用例/sprintN/sprintN_scripts/
```

**新增模块**（无需复制，后续全新生成）。

**共享文件**（始终复制）：
```bash
# 确保目录存在
mkdir -p 测试用例/sprintN/sprintN_scripts/fixtures
mkdir -p 测试用例/sprintN/sprintN_scripts/selectors

# 复制共享文件
cp 测试用例/sprint_all/scripts/fixtures/login.fixture.ts 测试用例/sprintN/sprintN_scripts/fixtures/
cp 测试用例/sprint_all/scripts/playwright.config.ts 测试用例/sprintN/sprintN_scripts/
```

### 增量 Step 4：增量处理

在 sprintN 目录上，对变更模块执行以下子步骤。处理完成后，sprintN 目录下的文件是该模块的最新完整版本。

#### 4a. 更新功能点.md

根据用户在 Step 2 确认的模式选择执行：

- **模式 A（主文档辅 UI）**：
  1. 主对话直接读取 sprintN 的 PRD 文档
  2. 与已复制的功能点.md 对比，识别新增/修改的功能点
  3. 更新 sprintN 中的功能点.md（只追加/修改变更部分）

- **模式 B/C（主 UI 探索）**：
  1. 启动 bf-ui-explorer Agent 探索变更模块
     ```
     subagent_type: bf-ui-explorer
     Agent prompt：
     系统地址：{从 CLAUDE.md 提取}
     测试账号：{从 CLAUDE.md 提取}
     探索模式：指定模块
     模块列表：{变更模块列表}
     输出目录：需求文档/sprintN/需求功能点/
     已有功能点目录：需求文档/sprintN/需求功能点/
     ```
  2. 将探索结果与已复制的功能点.md 合并

- **新增模块**：无论何种模式，新增模块都需要完整生成功能点.md（文档模式从 PRD 提取，UI 模式从浏览器探索）

#### 4b. 生成/更新 cases.json

启动 bf-case-generator Agent，为变更模块生成**完整快照**的 cases.json：

```
subagent_type: bf-case-generator
Agent prompt：
项目前缀：{从 CLAUDE.md 提取}
模块列表及缩写：
- {模块名} → {模块缩写}

请读取以下功能点文件并生成测试用例 JSON：
- 需求文档/sprintN/需求功能点/{模块名}/功能点.md

生成的 cases.json 与功能点.md 放在同一目录下。
```

**注意**：cases.json 是该模块在 sprintN 结束后的**完整快照**，包含所有用例（原有 + 新增 + 修改）。

#### 4c. 更新 E2E 脚本

根据模块类型分别处理：

**新增模块**（sprint_all 中不存在）：
1. 启动 bf-e2e-generator Agent 从零生成
   ```
   subagent_type: bf-e2e-generator
   Agent prompt：
   模块名称：{模块名}
   系统地址：{从 CLAUDE.md 提取}
   测试账号：{从 CLAUDE.md 提取}
   脚本存放路径：测试用例/sprintN/sprintN_scripts/
   用例文件：需求文档/sprintN/需求功能点/{模块名}/cases.json
   ```

**已有模块**（功能点有变更）：
1. 启动 bf-e2e-generator Agent 更新 spec.ts
   ```
   subagent_type: bf-e2e-generator
   Agent prompt：
   模块名称：{模块名}
   系统地址：{从 CLAUDE.md 提取}
   测试账号：{从 CLAUDE.md 提取}
   脚本存放路径：测试用例/sprintN/sprintN_scripts/
   用例文件：需求文档/sprintN/需求功能点/{模块名}/cases.json
   已有脚本：测试用例/sprintN/sprintN_scripts/{模块名}.spec.ts
   已有选择器：测试用例/sprintN/sprintN_scripts/selectors/{模块名}.selectors.ts
   
   请在已有脚本基础上，追加/修改变更用例的 test() 块，保留未变更的用例。
   ```

**所有变更模块**（新增 + 已有）：
1. 启动 bf-e2e-validator Agent 校验断言质量
   ```
   subagent_type: bf-e2e-validator
   Agent prompt：
   模块名称：{模块名}
   用例文件：需求文档/sprintN/需求功能点/{模块名}/cases.json
   测试脚本：测试用例/sprintN/sprintN_scripts/{模块名}.spec.ts
   断言映射表：~/.claude/skills/templates/assertion-mapping.md
   ```

### 增量 Step 5：覆盖回 sprint_all

将 sprintN 中变更过的模块覆盖回 sprint_all：

```bash
# 功能点和用例覆盖回 sprint_all
cp -r 需求文档/sprintN/需求功能点/{变更模块}/ 需求文档/sprint_all/需求功能点/{变更模块}/

# 测试脚本覆盖回 sprint_all
cp 测试用例/sprintN/sprintN_scripts/{变更模块}.spec.ts 测试用例/sprint_all/scripts/{变更模块}.spec.ts
cp 测试用例/sprintN/sprintN_scripts/selectors/{变更模块}.selectors.ts 测试用例/sprint_all/scripts/selectors/{变更模块}.selectors.ts
```

最后重新生成 sprint_all 的 testCase.xlsx：
```bash
python ~/.claude/skills/scripts/json_to_excel.py --input 需求文档/sprint_all/需求功能点 --output 测试用例/sprint_all/testCase.xlsx
```

### 增量 Step 6：流程衔接提示

Step 5 完成后，向用户展示以下提示：

```
增量处理完成！

已完成：
✅ 变更模块的功能点.md 已更新
✅ 变更模块的 cases.json 已生成（完整快照）
✅ 变更模块的 E2E 脚本已更新
✅ 变更已覆盖回 sprint_all
✅ sprint_all 的 testCase.xlsx 已重新生成

后续步骤（需手动触发）：
1. 执行「开始UI测试」→ 生成/更新 E2E 脚本（如 Step 4c 已完成可跳过）
2. 执行「开始执行测试」→ 运行 E2E 测试并自动修复
3. 查看测试报告 → reports/ 目录

回归测试命令：
- 精准回归（只跑 sprintN 变更模块）：npx playwright test --config=测试用例/sprintN/sprintN_scripts/playwright.config.ts
- 全量回归（跑 sprint_all 所有模块）：npx playwright test --config=测试用例/sprint_all/scripts/playwright.config.ts
```

### 合并规则总结

| 场景 | 处理方式 |
|------|---------|
| sprintN 修改了已有功能点 | 覆盖 sprint_all 中对应的功能点.md |
| sprintN 删除了已有功能点 | 从 sprint_all 中删除对应的功能点.md 和 cases.json |
| sprintN 新增了功能点 | 追加到 sprint_all 中对应模块的功能点.md |
| sprintN 修改了已有用例（同 ID） | 覆盖 sprint_all 中对应的用例 |
| sprintN 新增了用例（新 ID） | 追加到 sprint_all 中对应的 cases.json |
| sprintN 删除了已有用例 | 从 sprint_all 的 cases.json 中删除 |
| sprintN 修改了 E2E 脚本 | 覆盖 sprint_all 中对应的 spec.ts 和 selectors.ts |
| sprintN 新增了模块 | 在 sprint_all 中创建新的模块目录和脚本文件 |

---

## 回归测试策略

### 全量回归（跑 sprint_all 所有用例）

```bash
npx playwright test --config=测试用例/sprint_all/scripts/playwright.config.ts
```

### 精准回归（只跑当前 sprint 变更的模块）

```bash
npx playwright test --config=测试用例/sprintN/sprintN_scripts/playwright.config.ts
```

### 单模块回归

```bash
npx playwright test 测试用例/sprint_all/scripts/{模块名}.spec.ts
```

---

## 常用提示

- 需要用户额外提供内容时先暂停说明，不要假设。
- 所有文件放在当前项目目录内，使用相对路径。
- 每一步结束后明确报告进度。
- Agent 可以并行启动以加速执行，但注意 token 消耗。
- 混合模式中，按模块拆分后可并行处理不同模式的模块。
- 全量模式产出需同时写入 sprint0/ 和 sprint_all/，确保两份一致。
- 增量模式完成后必须覆盖回 sprint_all/，保持汇总版最新。
- 功能点.md 写增量（只含新增/修改的功能点），cases.json 写完整快照。
- 每个 sprint 文件夹是独立完整快照，可独立运行回归测试。

现在，请从 Step 0 开始执行：解析参数、检测项目资源并选择路径。
