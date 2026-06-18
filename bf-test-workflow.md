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
- **bf-graph-agent**（V2 新增）：带 Bash 专属跑 `~/.claude/skills/scripts/build_index.py` 维护 SQLite 知识图谱，提供 5 个查询原语（coverage / impact / setup / flow / recall）+ apply-confirmation 写 manual 边。主对话把图谱相关 DB 操作全部交它执行；**AskUserQuestion 一律主对话发起**，子 agent 无法问用户

**两条铁律**：① 图谱构建/查询专属 **bf-graph-agent**（带 Bash）；生成类 agent 纯文本生成器，消费主对话注入的结果。② Bash 分工——bf-graph-agent 只管 DB 操作（build/query/apply-confirmation），文件操作（cp/diff/mkdir）留主对话。

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

## 功能点1：{功能名称} <!--FP_{模块缩写}_01-->

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
- **每个功能点标题必须带 FP 锚点**：格式 `## 功能点N：{名称} <!--FP_{模块缩写}_{两位序号}-->`，序号在模块内从 01 连续递增；`{模块缩写}` 必须与后续用例 ID 中的缩写一致（如 `下单` → `XD` → `FP_XD_01`、`SPD_TC_XD_001`）。锚点为 HTML 注释，对 V1 脚本与人类阅读无害
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

### G1. 骨架图谱闸门（V2 新增，所有模式收敛后执行）

**前提**：模式 A / B / C 中至少一个已完成所有功能点.md 的生成与合并（A1→A2→A3 / B1→B2 / C1），`需求文档/{sprint}/需求功能点/` 下所有模块的功能点.md 已就绪且每个标题都带 FP 锚点。

> ⚠️ **此闸门必须在所有功能点探索完成后才执行**——A2 的 UI 探索、A3 的合并去重、B/C 的探索都可能新增功能点；如果先建图谱再补功能点，新增的 FP 锚点与跨模块依赖会丢失，图谱不完整。

> ⚠️ **增量模式（sprintN）不走此闸门**：增量模式有自己的 Step1-Step6 流程，Step1 已包含 build，Step2 已是用户确认。G1 仅用于**全量模式（sprint0）首次建立项目骨架图谱**。

#### G1.1 全量模式 merge sprint0 → sprint_all（仅全量模式）

图谱只扫 `需求文档/sprint_all/`（单一真相源），而 A2/A3 与 B/C 的探索产物默认只写 sprint0（或 sprintN）。建图前必须先 merge：

```bash
# 全量模式：sprint0 全量覆盖回 sprint_all（功能点.md / cases.json）
cp -rf 需求文档/sprint0/需求功能点/* 需求文档/sprint_all/需求功能点/
```

> A1 文档解析阶段已双写 sprint0 + sprint_all，但 A2/A3 后续更新只写 sprint0。
> 此处 merge 是为了把 A2/A3 的合并结果同步到 sprint_all，确保单一真相源数据完整。
> 增量模式的 merge 在增量 Step5 处理，此步仅全量模式执行。

#### G1.2 建骨架图谱（主对话调度 bf-graph-agent）

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：build
项目根：{当前项目根}
mode：rebuild（首次或大改时 DROP 重建）
sprint_tag：sprint0
```

agent 执行：
```bash
python ~/.claude/skills/scripts/build_index.py \
  --project {项目根} --source sprint_all --rebuild --sprint-tag sprint0
```

> 注意：`--build` 与 `--rebuild` 互斥。骨架建图用 `--rebuild`（DROP 后重建）。
> 后续 upsert 增量更新用 `--build`（或不传，默认 upsert）。

产物（固定 `{项目根}/需求文档/sprint_all/索引/`）：
- `知识图谱.db` / `知识图谱.json`
- `覆盖率报告.md`（此时还无 covers 边，覆盖率为 0；FP 节点已就位）
- `流程依赖图.md`（Mermaid，fp 节点 + precedes/depends_on/step_in_flow 边）
- `待确认依赖.md`（启发式推断但需人工确认的依赖清单）

agent 把 db_path、流程依赖图节点/边统计、**unresolved_deps 条数与摘要**返回主对话。

#### G1.3 人工确认依赖（主对话发起 AskUserQuestion）

主对话拿到 G1.2 返回的「待确认依赖清单」后，**通过 AskUserQuestion 向用户逐条确认**（子 agent 无法问用户）：

```
图谱发现 N 条启发式依赖需要您确认：

1. 下单.FP_XD_01「选择商品」 precedes 下单.FP_XD_02「支付」
   推断理由：PRD「下单流程」章节有序步骤 1.选商品 → 2.支付
   ☑ 确认    ☐ 拒绝    ☐ 修改（请补充正确关系）

2. ...
```

用户对每条选择「确认 / 拒绝 / 修改」。所有条目处理完后，主对话把确认结果组装成 JSON，**调度 bf-graph-agent** `apply-confirmation`：

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：apply-confirmation
项目根：{当前项目根}
确认 JSON：
{
  "edges": [
    {"source":"FP_XD_01","target":"FP_XD_02","kind":"precedes","metadata":{"via_flow":"FLOW_下单流程","order":1}},
    {"source":"FP_XD_02","target":"FP_XD_01","kind":"depends_on","metadata":{"via_flow":"FLOW_下单流程"}}
  ]
}
```

agent 执行：
```bash
python ~/.claude/skills/scripts/build_index.py \
  --project {项目根} --source sprint_all \
  --apply-confirmation '{"edges":[...]}'
```

写入 `manual` 边 + 清空 unresolved_deps。

> 若 G1.2 返回的 unresolved_deps 为 0（图谱推断充分无歧义），跳过此步直接进 G1.4。

#### G1.4 暂停等继续

完成后**主对话暂停流程**，输出：

```
⏸️ 骨架图谱已就绪（{X} 个 FP / {Y} 条依赖 / {Z} 条 manual 边）。
请回复「继续」进入 P1（生成测试用例）。
```

用户回复后进入 P1。**这一步是 V2 关键质量闸门**——图谱中的跨模块依赖在此时被人工锚定，后续覆盖率/影响面/流程注入都依赖此锚定结果。

### P1. 生成测试用例（Agent 并行方案）

#### P1.1 准备工作（主对话执行）

1. 若存在 `测试用例/测试用例模板.xlsx`，参考其业务列名；最终 Excel 以 `references/contracts.md` 的 10 列契约为准。
2. **确定项目前缀**：使用 AskUserQuestion 询问用户。
3. 统计 `需求文档/{sprint}/需求功能点/` 下所有模块，为每个模块确定**模块缩写**。
4. 确认脚本存在：`~/.claude/skills/scripts/json_to_excel.py`。

#### P1.2 启动 bf-case-generator Agent（并行，V2 流程上下文注入）

V2 改造：启动 generator 前，**主对话先对每个模块的每个 fp 调度 bf-graph-agent** `query flow`，把返回的 JSON 作为「V2 流程上下文」拼进 generator prompt。

##### P1.2.0 准备流程上下文（V2 新增，主对话调度 bf-graph-agent）

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：query
子命令：query flow
项目根：{当前项目根}
fp 列表：FP_XD_01、FP_XD_02、FP_SJZH_01、...（P0 由 A1 锚点 / 当前模块扫描得出）
```

agent 执行（每个 fp 一次调用，或主对话循环）：
```bash
python ~/.claude/skills/scripts/build_index.py \
  --project {项目根} --source sprint_all --query flow --query-arg FP_XD_01
```

返回 `{fp, upstream, downstream, apis, rules, flow, existing_covers}` 索引层包，主对话把它原样拼进下方 generator prompt。

##### P1.2.1 启动 generator（含 V2 上下文）

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

【V2 流程上下文（图谱注入，必须遵守）】
FP_XD_01（选择商品）：
  上游：—（无）
  下游：FP_XD_02（支付）
  关联 API：API_ORDER_CREATE
  关联规则：RULE_XD_01（必选商品规格）
  所在流程：FLOW_下单流程（order=1）
  已有 covers：—（首次生成）
FP_XD_02（支付）：
  上游：FP_XD_01（选择商品）
  下游：—
  关联 API：API_ORDER_PAY
  关联规则：RULE_XD_02（金额>0）
  所在流程：FLOW_下单流程（order=2）
  已有 covers：—

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

#### P1.3.5 重建知识图谱（V2 新增，主对话调度 bf-graph-agent）

Excel 生成完成后，主对话**调度 bf-graph-agent** 跑 `build`，把本次 cases.json / 功能点.md / spec.ts 全量入图谱：

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：build
项目根：{当前项目根}
mode：upsert（首次）或 rebuild（数据格式大改）
sprint_tag：{sprintN 或 sprint0}
```

agent 执行：
```bash
python ~/.claude/skills/scripts/build_index.py \
  --project {项目根} --source sprint_all --sprint-tag {sprint_tag} --build
```

返回主对话所需信息：DB 路径、节点/边统计、`overall_coverage_rate`、（P2 起）待确认依赖清单。**单一真相源**：图谱只扫 `需求文档/sprint_all/`，产物固定落 `{项目根}/需求文档/sprint_all/索引/`。全量模式（sprint0）后主对话需把 sprint0 的 cases.json 与功能点.md 同步到 sprint_all（见 A1），再跑 build；增量模式 sprintN 完成后必须 merge 回 sprint_all 再 build。

#### P1.4 覆盖率检查（V2 改造：调度 bf-graph-agent）

主对话**调度 bf-graph-agent** 跑 `query coverage`，读取图谱产出的 `覆盖率报告.md` 替代 V1 文本模糊匹配：

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：query
项目根：{当前项目根}
子命令：query coverage
```

agent 执行：
```bash
python ~/.claude/skills/scripts/build_index.py \
  --project {项目根} --source sprint_all --query coverage
```

主对话拿到 `{modules:[...], overall:{...}}` 后判定：
- **整体覆盖率 ≥ 80%** → 进入 P2 审核
- **整体覆盖率 < 80%** → 把 `uncovered_fps`（未覆盖 FP 列表）作为「待补用例清单」，对每个未覆盖模块**追加启动 bf-case-generator**，prompt 明确告知「必须为以下 FP 各补 1-2 条用例：[FP_XXX_01 名称、FP_XXX_02 名称、...]」，所有补的用例 `covers` 字段必须填入对应 FP 锚点。补完后回到 P1.3 → P1.3.5 → P1.4 循环，直到达标。

### P2. 审核测试用例（主对话执行）

1. 对生成的 `testCase.xlsx` 进行自检：
   - **覆盖率数值不再重复计算**：直接读取 P1.4 由 bf-graph-agent 产出的 `覆盖率报告.md`（`{项目根}/需求文档/sprint_all/索引/覆盖率报告.md`），引用其中的整体覆盖率和未覆盖 FP 清单
   - 检查用例可执行性：步骤是否具体、预期结果是否可验证、前置条件是否可满足
   - 标记可能不可执行或冗余的用例（如 covers 为空、tests_api 与功能点无关联的孤儿用例）
2. 生成审核报告，保存在 `reports/测试用例审核报告.md`，内容包括：
   - 覆盖率数值（引用图谱报告）
   - 未覆盖的功能点列表及原因
   - 优化建议
3. 如果覆盖率低于 80%（P1.4 已循环过则不会再触发），主动请求用户确认是否补充用例

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
系统地址：http://your-test-system.example.com/
测试账号：your_test_account / your_admin_account
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

### C.3 同步脚本到汇总目录（主对话执行）

Stage C 的 healer 会修改 sprint 脚本目录下的 spec.ts 和 selectors.ts，需要同步到汇总目录。

全量模式（sprint0）：
```bash
# 同步脚本
cp -r 测试用例/sprint0/sprint0_scripts/* 测试用例/sprint_all/scripts/
# 同步含实际结果的测试用例 Excel
cp 测试用例/sprint0/sprint0_testCase.xlsx 测试用例/sprint_all/testCase.xlsx
```

增量模式（sprintN）：
```bash
# 仅同步 healer 修改过的模块
cp 测试用例/sprintN/sprintN_scripts/{修改模块}.spec.ts 测试用例/sprint_all/scripts/
cp 测试用例/sprintN/sprintN_scripts/selectors/{修改模块}.selectors.ts 测试用例/sprint_all/scripts/selectors/
# 同步含实际结果的测试用例 Excel
cp 测试用例/sprintN/sprintN_testCase.xlsx 测试用例/sprint_all/testCase.xlsx
```

同步完成后验证：
```bash
# 脚本一致性
diff -rq 测试用例/{sprint}/{sprint_scripts}/ 测试用例/sprint_all/scripts/
```

若 healer 修改了 shared 文件（login.fixture.ts、playwright.config.ts），也需要同步：
```bash
cp 测试用例/{sprint}/{sprint_scripts}/fixtures/login.fixture.ts 测试用例/sprint_all/scripts/fixtures/
cp 测试用例/{sprint}/{sprint_scripts}/playwright.config.ts 测试用例/sprint_all/scripts/
```

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

### 增量 Step 1：解析 PRD，识别变更模块 + 影响面（V2 改造）

1. 读取 `需求文档/sprintN/` 目录下的需求文档。
2. 解析文档内容，提取涉及的模块列表与变更的功能点 / 接口（记录变更 FP_/API_ 节点 ID 列表）。
3. 与 `需求文档/sprint_all/需求功能点/` 对比，区分：
   - **已有模块**（sprint_all 中已存在）→ 需要从 sprint_all 复制
   - **新增模块**（sprint_all 中没有）→ 无需复制，标记为全新
4. **V2 关键：跑影响面分析**。先**调度 bf-graph-agent** `build` 保证图谱最新（含上轮 sprintN 的功能点 merge）：
   ```
   subagent_type: bf-graph-agent
   Agent prompt：
   任务类型：build
   项目根：{当前项目根}
   mode：upsert
   sprint_tag：sprintN
   ```
   然后对**变更 FP/API 节点**调度 `query impact`（查下游受影响）+ 对**任一变更节点**调度 `query setup`（查上游数据准备）：
   ```
   subagent_type: bf-graph-agent
   Agent prompt：
   任务类型：query
   子命令1：query impact --query-arg FP_XD_02,API_ORDER_PAY --depth 2
   子命令2：query setup --query-arg FP_XD_02 --depth 3
   ```
   主对话把两份 JSON 拼成**两栏** `影响面报告_sprintN.md` 写入 `{项目根}/需求文档/sprint_all/索引/`：
   - **【受影响 / 可能 break】**：impact 命中节点 → 这些用例需要复核（断言可能失效）
   - **【回归前置 / 数据准备】**：setup 命中节点 → 这些用例当 setup 重跑（提供测试数据）

5. **V2 新增：处理新启发式依赖（1e 子步）**。检查 Step 4 build 返回的 `unresolved_deps` 条数：
   - **`unresolved_deps = 0`** → 跳过此步，直接进入 Step 2
   - **`unresolved_deps > 0`** → 主对话**通过 AskUserQuestion 逐条确认**（与 G1.3 同样的流程），用户对每条选择「确认 / 拒绝 / 修改」，确认后调度 bf-graph-agent `apply-confirmation` 写 manual 边 + 清 unresolved_deps。

   > 增量场景下 unresolved_deps 的常见来源：
   > - PRD 新流程章节产生新的 precedes/depends_on 启发式推断
   > - 新增模块的 FP 锚点序号与已有冲突（kind=`conflict`，由 extract_fp_md 检测，见 Step 4a）
   > - cases.json 的 tests_api 指向不存在的 api 节点（数据错误）
   >
   > 注意：`conflict` 类型通常意味着功能点.md 序号算错，需要回 Step 4a 修复 sprintN 的功能点.md 重新跑 4a→5a，而不是 apply-confirmation 写 manual 边。主对话应根据 kind 区分处理。

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

### 增量 Step 3：复制相关文件（V2 改造：基于影响面 cp 粒度细化）

V2 改造点：**不再整模块复制**，而是按 Step1 影响面报告的命中范围细化复制。

**已有模块**（按影响面范围复制，cp 粒度从模块目录细化到具体 spec.ts test 块 + cases.json 具体用例）：

```bash
# 功能点和用例：仍按模块复制（功能点.md / cases.json 需要完整快照给 generator）
cp -r 需求文档/sprint_all/需求功能点/{模块名}/ 需求文档/sprintN/需求功能点/{模块名}/

# 选择器映射：模块级复制（selectors 是页面级资源，全量带过去）
cp 测试用例/sprint_all/scripts/selectors/{模块名}.selectors.ts 测试用例/sprintN/sprintN_scripts/selectors/

# 测试脚本：模块级复制（spec.ts 文件作为基底，后续 generator 在范围内追加/修改 test() 块）
cp 测试用例/sprint_all/scripts/{模块名}.spec.ts 测试用例/sprintN/sprintN_scripts/
```

**仅复制影响面命中的模块**（不再复制未变更模块）：
- impact 命中模块（下游可能 break）→ 复制 spec.ts + cases.json（供 generator 在范围内复核修改）
- setup 命中模块（上游数据准备）→ 复制 spec.ts（供 generator 把这些用例当 fixture）
- 未命中模块 → 不复制，回归时跑 sprint_all 的原脚本即可

> V2 的精细化体现在 **bf-e2e-generator 的处理范围**（见 Step 4c），而非 cp 命令本身——cp 仍是模块级，但 generator 只在 impact/setup 命中的 test() 块上动作。

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
  4. **新增/修改的功能点标题必须带 FP 锚点（沿用全量 A1 模板规则）**：格式 `## 功能点N：{名称} <!--FP_{模块缩写}_{两位序号}-->`，新增功能点序号在模块内续接已有最大序号（如已有 FP_XD_02，新增即 FP_XD_03）

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

### 增量 Step 5：覆盖回 sprint_all（V2 改造：merge-as-you-go）

V2 关键改造：**功能点.md 与 cases.json 在子步骤就 merge 回 sprint_all + 立即重建图谱**，Step5 只剩脚本 merge 与最终 build。这样图谱在每个子步骤之后都是最新状态，可被下一步的 query 调用。

#### 5a. 功能点先 merge（4a 完成后立即执行）

```bash
# 4a 更新功能点.md 完成后，立即 merge 到 sprint_all
cp -r 需求文档/sprintN/需求功能点/{变更模块}/ 需求文档/sprint_all/需求功能点/{变更模块}/

# 立即调度 bf-graph-agent 重建图谱（功能点先入图谱，后续 cases.json 的 covers 才能连边）
# 主对话调度：
#   subagent_type: bf-graph-agent
#   Agent prompt：任务类型：build；项目根：{项目根}；sprint_tag：sprintN
#                  mode：<按下方规则选择>
```

**mode 选择规则（V2 修复问题 5）**：

| 变更类型 | mode | 原因 |
|---------|------|------|
| 仅**新增**模块 / 新增 FP 锚点 / 新增用例 | **`upsert`** | 增量叠加，GC 会清理孤儿；保留 manual 边与历史节点 |
| 涉及**修改**已有 FP 锚点 / 修改已有用例 | **`rebuild`** | 修改可能改了 ID（如 FP_XD_02 改名为 FP_XD_05），upsert 会残留旧节点；rebuild 更稳 |
| 涉及**删除**模块 / 删除 FP / 删除用例 | **`rebuild`** | upsert 不感知删除（即使有 GC 也可能漏处理复杂删除场景）；rebuild 最干净 |

> 经验法则：**有不确定时优先 `rebuild`**（sprint_all 体量通常不大，重建几秒完成）。
> `upsert` 仅在「明确只增不改不删」的简单场景使用，性能略好但容错低。

#### 5b. cases.json merge（4b 完成后）

```bash
# cases.json 是完整快照，直接覆盖
cp 需求文档/sprintN/需求功能点/{变更模块}/cases.json 需求文档/sprint_all/需求功能点/{变更模块}/cases.json
```

#### 5c. 脚本 merge（4c/healer 完成后）

```bash
# 测试脚本覆盖回 sprint_all
cp 测试用例/sprintN/sprintN_scripts/{变更模块}.spec.ts 测试用例/sprint_all/scripts/{变更模块}.spec.ts
cp 测试用例/sprintN/sprintN_scripts/selectors/{变更模块}.selectors.ts 测试用例/sprint_all/scripts/selectors/{变更模块}.selectors.ts
```

#### 5d. 最终重建图谱 + 重新生成 Excel

所有变更 merge 完成后，最后**调度 bf-graph-agent** `build` 把 cases.json 与 spec.ts 的最新 covers/implements 边刷入图谱：

```
subagent_type: bf-graph-agent
Agent prompt：
任务类型：build
项目根：{当前项目根}
mode：<同 5a 的 mode 选择规则>
sprint_tag：sprintN
```

**mode 选择规则（同 5a）**：仅新增 → `upsert`；涉及修改/删除 → `rebuild`；不确定优先 `rebuild`。

> 5a 与 5d 用同一个 mode。若 5a 用了 rebuild，5d 也用 rebuild（保持一致）。

然后重新生成 sprint_all 的 testCase.xlsx：
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
