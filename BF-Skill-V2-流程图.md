# BF-Skill V2 流程图（Mermaid 源码）

> 配套 `BF-Skill-V2-流程图.drawio`（V1 二进制版）。Mermaid 版可在 GitHub/IDE 直接渲染，便于版本管理与编辑。

## 1. 整体架构

```mermaid
graph TB
    User([用户])
    Main[bf-test-workflow.md<br/>主调度 + AskUserQuestion]

    subgraph Agents[6 个专用 Agent]
        direction LR
        UI[bf-ui-explorer<br/>浏览器探索 + FP 锚点]
        Case[bf-case-generator<br/>用例 JSON + covers/tests_api]
        E2E[bf-e2e-generator<br/>录制选择器 + 脚本<br/>注入影响面范围]
        Val[bf-e2e-validator<br/>断言校验]
        Heal[bf-e2e-healer<br/>执行 + 修复 + 回写]
        Graph[bf-graph-agent ⭐<br/>Bash 专属跑 build_index.py]
    end

    subgraph Knowledge[V2 知识图谱]
        DB[(SQLite<br/>知识图谱.db)]
        Reports[索引/<br/>覆盖率/流程图/待确认/影响面]
    end

    User -->|/bf-test-workflow<br/>/init-bf| Main
    Main --> UI
    Main --> Case
    Main --> E2E
    Main --> Val
    Main --> Heal
    Main -->|调度 build/query/<br/>apply-confirmation| Graph
    Graph --> DB
    Graph --> Reports
    DB -.->|查询结果注入| Case
    DB -.->|影响面注入| E2E
```

## 2. 全量模式工作流（sprint0）

```mermaid
flowchart TD
    Start([/bf-test-workflow 无参]) --> S0[Step 0 检测项目资源]
    S0 --> Mode{选择模式}

    Mode -->|文档完整| A1[A1 文档解析<br/>生成功能点.md<br/>带 FP 锚点]
    Mode -->|文档不完整| B1[B1 UI 探索<br/>bf-ui-explorer]
    Mode -->|无文档| C1[C1 UI 探索]

    A1 --> A2[A2 UI 补充<br/>bf-ui-explorer]
    A2 --> A3[A3 合并去重]
    B1 --> B2[B2 文档补充]
    B2 --> G1
    C1 --> G1
    A3 --> G1

    G1[G1 公共骨架图谱闸门 ⭐]
    G1 --> G11[G1.1 merge sprint0 → sprint_all]
    G11 --> G12[G1.2 调度 bf-graph-agent<br/>build --rebuild]
    G12 --> G13{unresolved_deps > 0?}
    G13 -->|是| G13a[G1.3 主对话 AskUserQuestion<br/>逐条确认 → apply-confirmation]
    G13 -->|否| G14
    G13a --> G14[G1.4 暂停等用户回复继续]

    G14 --> P1[P1 生成测试用例]
    P1 --> P120[P1.2.0 调度 query flow<br/>获取流程上下文]
    P120 --> P121[P1.2.1 启动 bf-case-generator<br/>注入 V2 流程上下文]
    P121 --> P13[P1.3 json_to_excel.py<br/>生成 10 列 Excel]
    P13 --> P135[P1.3.5 调度 build<br/>cases.json + spec.ts 入图]
    P135 --> P14[P1.4 调度 query coverage<br/>检查覆盖率]
    P14 -->|< 80%| P121
    P14 -->|≥ 80%| P2[P2 审核]

    P2 --> P3[P3 接口测试]
    P3 --> B0[B 阶段 UI 自动化生成]
    B0 --> C0[C 阶段 执行与修复]
    C0 --> D0[D 阶段 清理]

    D0 --> End([完成])
```

## 3. 增量模式工作流（sprintN）

```mermaid
flowchart TD
    Start([/bf-test-workflow sprintN]) --> S1[Step 1 解析 PRD<br/>识别变更模块]
    S1 --> S1b[Step 1b 调度 bf-graph-agent<br/>build upsert 保证图谱最新]
    S1b --> S1c[Step 1c 调度 query impact + setup]
    S1c --> S1d[Step 1d 产 影响面报告_sprintN.md<br/>两栏：受影响 / 数据准备]
    S1d --> S1e{Step 1e 检测<br/>unresolved_deps > 0?}
    S1e -->|是| S1e1[主对话 AskUserQuestion 分类处理<br/>conflict → 修功能点<br/>tests_api → 修 cases<br/>precedes 等 → apply-confirmation]
    S1e -->|否| S2
    S1e1 --> S2[Step 2 用户确认模块列表]

    S2 --> S3[Step 3 复制相关文件<br/>仅复制 impact/setup 命中模块]
    S3 --> S4[Step 4 增量处理]

    S4 --> S4a[4a 更新功能点.md<br/>模式 A：主对话加 FP 锚点<br/>模式 B/C：bf-ui-explorer]
    S4a --> S5a[5a 功能点 merge 回 sprint_all<br/>+ 调度 build upsert]

    S5a --> S4b[4b 生成完整快照 cases.json<br/>调度 bf-case-generator]
    S4b --> S5b[5b cases.json merge]

    S5b --> S4c[4c 更新 E2E 脚本<br/>调度 bf-e2e-generator<br/>注入影响面范围]
    S4c --> S5c[5c 脚本 merge]

    S5c --> S5d[5d 最终 build<br/>+ 重新生成 testCase.xlsx]
    S5d --> S6[Step 6 流程衔接提示]
    S6 --> End([完成])
```

## 4. 知识图谱节点类型与边

```mermaid
graph LR
    subgraph Nodes[7 类节点]
        FP[fp 功能点<br/>FP_XD_01]
        Case[case 用例<br/>SPD_TC_XD_001]
        API[api 接口<br/>API_ORDER_CREATE]
        Script[script 脚本块<br/>SCRIPT_下单_TC_001]
        Rule[rule 业务规则<br/>RULE_XD_01]
        Flow[flow 流程<br/>FLOW_下单流程]
        Page[page 页面<br/>PAGE_订单列表]
    end

    Case -->|covers| FP
    Case -->|tests_api| API
    Script -->|implements| Case
    FP -->|has_rule| Rule
    API -->|exposes| FP
    Flow -->|step_in_flow| FP
    FP -->|precedes| FP
    FP -->|depends_on| FP
    API -->|consumes_data_from| API
    Page -.->|precedes| Page
```

## 5. build_index.py 内部流程（含两阶段 GC）

```mermaid
flowchart TD
    Start([python build_index.py<br/>--project X --source sprint_all<br/>--build 或 --rebuild]) --> Env[check_env<br/>sqlite3 + FTS5 实测]
    Env --> Schema[init_schema<br/>建表 + WAL + FTS5 触发器]

    Schema --> Mode{rebuild?}
    Mode -->|是| Drop[DELETE 所有表数据]
    Mode -->|否| Pre[pre_clean GC<br/>scanned_ids = 空 set<br/>清所有非 manual 节点]

    Drop --> Extract
    Pre --> Extract

    Extract[extract_all] --> E1[extract_fp_md<br/>扫 功能点.md<br/>建 fp/rule 节点<br/>同文件冲突 → unresolved_deps]
    E1 --> E2[extract_api_md<br/>扫 接口*.md<br/>建 api 节点 + 字段]
    E2 --> E3[extract_flow_prd<br/>扫 PRD 流程章节<br/>建 flow + step_in_flow]
    E3 --> E4[extract_cases_json<br/>扫 cases.json<br/>建 case + covers/tests_api<br/>孤儿 tests_api → unresolved_deps]
    E4 --> E5[extract_spec_ts<br/>扫 spec.ts<br/>建 script + implements]

    E5 --> Resolve[resolve_cross_module<br/>step_in_flow → precedes + depends_on<br/>api 入参∩出参 → consumes_data_from]
    Resolve --> Post{rebuild?}
    Post -->|否| PostClean[post_clean GC<br/>scanned_ids = 本次扫到的<br/>兜底清孤儿]
    Post -->|是| Skip[跳过]
    PostClean --> Reports
    Skip --> Reports

    Reports[报告产物] --> R1[dump_json<br/>知识图谱.json]
    R1 --> R2[write_coverage_md<br/>覆盖率报告.md]
    R2 --> R3[write_flow_graph_md<br/>流程依赖图.md Mermaid]
    R3 --> R4[write_unresolved_md<br/>待确认依赖.md]
    R4 --> End([输出 JSON 统计])
```

## 6. 影响面查询语义（impact / setup）

```mermaid
graph LR
    subgraph Edge Direction[边方向约定]
        direction LR
        note["source=依赖者 → target=被依赖者"]
    end

    subgraph Impact[query impact FP_XD_01 找下游]
        I1[FP_XD_01 变更]
        I2[谁依赖 FP_XD_01?]
        I3[读入边 target=FP_XD_01<br/>covers: case 节点<br/>depends_on: 下游 fp]
        I4[读出边 source=FP_XD_01<br/>precedes: 后置 fp]
        I1 --> I2 --> I3 --> I4
    end

    subgraph Setup[query setup FP_XD_02 找上游]
        S1[跑 FP_XD_02 需准备谁的数据?]
        S2[读出边 source=FP_XD_02<br/>depends_on: 上游 fp<br/>consumes_data_from: 数据源 api]
        S3[读入边 target=FP_XD_02<br/>precedes: 前置 fp]
        S1 --> S2 --> S3
    end
```

## 7. agent 工具权限矩阵

```mermaid
graph TB
    subgraph 主对话 bf-test-workflow
        M1[Bash 仅文件操作<br/>cp/diff/mkdir]
        M2[AskUserQuestion 全部在此]
        M3[调度 agent]
    end

    subgraph bf-graph-agent V2 新增
        G1[Bash<br/>跑 build_index.py]
        G2[Read Write Glob Grep<br/>仅调试脚本时]
    end

    subgraph 生成类 agent
        C1[bf-case-generator<br/>Read Write Glob Grep<br/>无 Bash]
        E1[bf-e2e-generator<br/>Read Write Glob Grep<br/>+ Playwright MCP]
        V1[bf-e2e-validator<br/>Read Edit MultiEdit Write Glob Grep]
    end

    subgraph 修复类 agent
        H1[bf-e2e-healer<br/>Read Edit Write Glob Grep Bash<br/>+ Playwright MCP]
    end

    subgraph 探索类 agent
        U1[bf-ui-explorer<br/>Read Write Glob Grep<br/>+ Playwright MCP]
    end

    M3 --> G1
    M3 --> C1
    M3 --> E1
    M3 --> V1
    M3 --> H1
    M3 --> U1
```

## 8. AskUserQuestion 出现时机

```mermaid
timeline
    title AskUserQuestion 触发点（主对话发起）
    section 智能入口
        Step 0 : 文档完整性询问<br/>(模式 A/B/C 选择)
    section G1 闸门 (仅全量)
        G1.3 : unresolved_deps 逐条确认<br/>(写 manual 边)
        G1.4 : 暂停等用户继续
    section P1 生成用例
        P1.1 : 确定项目前缀
        P1.4 : 覆盖率 < 80% 时<br/>请求补用例
    section 增量模式
        Step 1e : unresolved_deps 分类处理
        Step 2 : 模块列表确认
    section 接口测试
        P3 : 触发条件确认
    section UI 测试
        B/C 阶段 : 触发条件确认
```
