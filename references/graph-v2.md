# V2 知识图谱契约

图谱只读取 `需求文档/sprint_all/`，产物固定写入 `需求文档/sprint_all/索引/`。

## 执行入口

所有 DB 操作都委托 `bf-graph-agent` 调用：

```bash
python ~/.claude/skills/scripts/build_index.py --project {项目根} --source sprint_all --rebuild --sprint-tag sprint0
python ~/.claude/skills/scripts/build_index.py --project {项目根} --source sprint_all --build --sprint-tag sprintN
python ~/.claude/skills/scripts/build_index.py --project {项目根} --source sprint_all --query coverage
```

## 节点

| 类型 | 示例 | 来源 |
| ---- | ---- | ---- |
| fp | `FP_XD_01` | `功能点.md` 标题锚点 |
| case | `SPD_TC_XD_001` | `cases.json` |
| api | `API_ORDER_CREATE` | 接口功能点文档 |
| script | `SCRIPT_下单_SPD_TC_XD_001` | Playwright `test()` 块 |
| rule | `RULE_XD_01` | 功能点业务规则 |
| flow | `FLOW_下单流程` | PRD 流程章节 |

## 边方向

| kind | 方向 | 含义 |
| ---- | ---- | ---- |
| covers | case -> fp | 用例覆盖功能点 |
| tests_api | case -> api | 用例验证接口 |
| implements | script -> case | 脚本实现用例 |
| has_rule | fp -> rule | 功能点包含业务规则 |
| depends_on | dependent fp -> dependency fp | 后者是前者前置 |
| precedes | previous fp -> next fp | 流程顺序 |
| step_in_flow | flow -> fp | 流程包含功能点 |
| exposes | api -> fp | 接口支撑功能点 |
| consumes_data_from | consumer api -> producer api | 接口数据依赖 |

`precedes` 与 `depends_on` 方向不同，查询层已分别处理：

- impact 查“谁会被当前节点影响”。
- setup 查“执行当前节点前要准备什么”。
- flow 查单个 FP 的上下游、规则、接口、已有 covers。

## unresolved_deps 处理

- `kind=conflict`：通常是 FP 锚点重复或序号错误，回到功能点文件修复，不写 manual 边。
- `kind=tests_api`：通常是 `cases.json` 指向不存在的 API，修 cases 或接口文档，不写 manual 边。
- 流程/依赖推断类：主对话询问用户确认后，再调用 `apply-confirmation` 写 manual 边。
