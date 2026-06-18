#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BF 测试知识图谱构建器（V2）

维护 {项目}/需求文档/sprint_all/索引/知识图谱.db，把功能点 / 用例 / 接口 / 脚本块 /
业务规则 / 端到端流程显式连成网，供主对话（bf-test-workflow）通过 bf-graph-agent 调用。

调用约定（固定，防漂移）：
    python build_index.py --project <项目根> --source sprint_all <子命令>

阶段实现进度：
    ✅ P1  环境层 / Schema 层 / 容错层 / extract(fp_md/cases_json/spec_ts) /
          coverage_report / dump_json / write_coverage_md / CLI(coverage)
    ✅ P2  extract_flow_prd / resolve_cross_module / impact_radius / setup_path /
          write_flow_graph_md / write_unresolved_md / CLI(impact/setup/apply-confirmation)
    ✅ P3  extract_api_md / resolve_api_data_flow / flow_context / semantic_recall /
          get_node_detail / CLI(flow/recall)
    注：recall 的 top-K 用 --depth 参数复用（语义同 LIMIT）。
"""

import sqlite3
import sys
import os
import re
import json
import glob
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# 环境层
# ---------------------------------------------------------------------------

def check_env():
    """返回 (has_sqlite3, has_fts5)。

    - import sqlite3 失败 → sys.exit（要求标准 CPython）
    - FTS5 用 :memory: 建虚表实测，失败 → has_fts5=False，后续 LIKE 兜底
    """
    try:
        import sqlite3  # noqa: F401
    except ImportError:
        sys.exit('[build_index] 致命错误：当前 Python 无 sqlite3 模块，请使用标准 CPython。')
    has_fts5 = False
    try:
        con = sqlite3.connect(':memory:')
        con.execute('CREATE VIRTUAL TABLE t USING fts5(x)')
        con.close()
        has_fts5 = True
    except sqlite3.OperationalError:
        pass
    return True, has_fts5


# ---------------------------------------------------------------------------
# Schema 层
# ---------------------------------------------------------------------------

def init_schema(con, has_fts5):
    """CREATE nodes/edges/flows/unresolved_deps；FTS5→nodes_fts+触发器，否则普通索引走 LIKE。

    边方向约定：source=依赖者 → target=被依赖者。
    边 kind：covers / tests_api / implements / has_rule / depends_on / precedes /
            consumes_data_from / step_in_flow / exposes（P3）/ setup_for（manual）。
    """
    cur = con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS nodes (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,           -- fp/case/api/script/rule/flow/page
        name TEXT NOT NULL,
        module TEXT,
        sprint TEXT,
        content TEXT,                  -- 全文（按需取详情，flow_context 用）
        source_path TEXT,              -- provenance 文件位置
        provenance TEXT,               -- from-fp-md / from-cases-json / from-spec / inferred-... / manual
        extra_json TEXT,               -- 杂项附加（covers/tests_api/...）
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS edges (
        source TEXT NOT NULL,          -- 依赖者（出边）
        target TEXT NOT NULL,          -- 被依赖者（入边）
        kind TEXT NOT NULL,            -- 边类型
        metadata_json TEXT,
        provenance TEXT,
        PRIMARY KEY (source, target, kind)
    );

    CREATE TABLE IF NOT EXISTS flows (
        id TEXT PRIMARY KEY,           -- FLOW_{流程名}
        name TEXT,
        source_path TEXT,
        provenance TEXT
    );

    CREATE TABLE IF NOT EXISTS unresolved_deps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        target TEXT,
        kind TEXT,
        reason TEXT,
        suggested_metadata TEXT,
        provenance TEXT,
        created_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
    CREATE INDEX IF NOT EXISTS idx_nodes_module ON nodes(module);
    CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
    CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
    CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind);
    ''')

    if has_fts5:
        cur.executescript('''
        CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
            id, name, content, module,
            content='nodes', content_rowid='rowid'
        );
        CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO nodes_fts(rowid, id, name, content, module)
            VALUES (new.rowid, new.id, new.name, new.content, new.module);
        END;
        CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, id, name, content, module)
            VALUES ('delete', old.rowid, old.id, old.name, old.content, old.module);
        END;
        CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, id, name, content, module)
            VALUES ('delete', old.rowid, old.id, old.name, old.content, old.module);
            INSERT INTO nodes_fts(rowid, id, name, content, module)
            VALUES (new.rowid, new.id, new.name, new.content, new.module);
        END;
        ''')

    # WAL 建库后立即开（防并发读阻塞）
    con.execute('PRAGMA journal_mode=WAL;')
    con.commit()


# ---------------------------------------------------------------------------
# 容错层（复用 json_to_excel.py 的 repair_json 思路）
# ---------------------------------------------------------------------------

def repair_json(filepath):
    """尝试修复常见的 JSON 问题（如字符串内未转义的双引号）。

    返回解析后的 Python 对象；失败返回 None 并打印警告。
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        m = re.match(r'^(\s*"[^"]+"\s*:\s*)"(.*)"(\s*,?\s*)$', line)
        if m:
            prefix, value, suffix = m.group(1), m.group(2), m.group(3)
            fixed_value = ''
            i = 0
            while i < len(value):
                if value[i] == '\\' and i + 1 < len(value) and value[i + 1] == '"':
                    fixed_value += '\\"'
                    i += 2
                elif value[i] == '"':
                    open_count = fixed_value.count('「') - fixed_value.count('」')
                    fixed_value += '「' if open_count % 2 == 0 else '」'
                    i += 1
                else:
                    fixed_value += value[i]
                    i += 1
            line = f'{prefix}"{fixed_value}"{suffix}'
        fixed_lines.append(line)
    fixed = '\n'.join(fixed_lines)
    try:
        data = json.loads(fixed)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)
        return data
    except json.JSONDecodeError as e:
        print(f'  警告: {filepath} 修复失败 ({e})，跳过')
        return None


def read_text_safe(filepath):
    """读文本，吞编码错误。"""
    for enc in ('utf-8', 'gbk', 'utf-8-sig'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ''


def upsert_node(con, node_id, node_type, name, module=None, sprint=None,
                content=None, source_path=None, provenance=None, extra=None):
    """INSERT OR REPLACE 幂等写节点。"""
    con.execute('''
        INSERT OR REPLACE INTO nodes
            (id, type, name, module, sprint, content, source_path, provenance, extra_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        node_id, node_type, name, module, sprint, content, source_path, provenance,
        json.dumps(extra, ensure_ascii=False) if extra else None,
        datetime.now().isoformat(timespec='seconds'),
    ))


def upsert_edge(con, source, target, kind, metadata=None, provenance=None):
    """INSERT OR REPLACE 幂等写边。edges PK(source,target,kind) 折叠重复。"""
    con.execute('''
        INSERT OR REPLACE INTO edges (source, target, kind, metadata_json, provenance)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        source, target, kind,
        json.dumps(metadata, ensure_ascii=False) if metadata else None,
        provenance,
    ))


# ---------------------------------------------------------------------------
# extract 层（P1：fp_md / cases_json / spec_ts）
# ---------------------------------------------------------------------------

FP_ANCHOR_RE = re.compile(r'## 功能点(\d+)：.*?<!--(FP_[A-Z]+_\d+)-->')
SPEC_TEST_RE = re.compile(r"test\(['\"]([^'\"]+?)['\"]")


def extract_fp_md(con, sprint_all_root, sprint_tag):
    """扫 **/功能点.md → fp 节点 + rule 节点 + has_rule 边。

    provenance=from-fp-md
    返回 (cnt_fp, cnt_rule, scanned_ids_set)
    同文件内 fp_id 重复时写入 unresolved_deps（kind=conflict）供主对话确认。
    """
    pattern = os.path.join(sprint_all_root, '**', '功能点.md')
    cnt_fp = cnt_rule = cnt_conflict = 0
    scanned = set()
    for md_path in glob.glob(pattern, recursive=True):
        rel_module = os.path.basename(os.path.dirname(md_path))
        text = read_text_safe(md_path)
        seen_fps_in_file = set()
        for m in FP_ANCHOR_RE.finditer(text):
            seq, fp_id = m.group(1), m.group(2)
            # 冲突检测：同文件内 fp_id 重复（序号算错的典型症状）
            if fp_id in seen_fps_in_file:
                con.execute('''INSERT INTO unresolved_deps
                    (source, target, kind, reason, suggested_metadata, provenance, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (fp_id, fp_id, 'conflict',
                     f'模块 {rel_module} 的 功能点.md 中 FP 锚点 {fp_id} 重复出现（序号可能算错，请检查标题序号与锚点序号是否匹配）',
                     json.dumps({'file': md_path, 'fp_id': fp_id}, ensure_ascii=False),
                     'from-fp-md',
                     datetime.now().isoformat(timespec='seconds')))
                cnt_conflict += 1
                continue  # 不再 upsert 重复节点，避免静默覆盖
            seen_fps_in_file.add(fp_id)
            # 提取该功能点段落直到下一个 ## 标题
            start = m.end()
            next_h = text.find('\n## ', start)
            section = text[start:next_h] if next_h != -1 else text[start:]
            # 简易取名称：标题里 ：后的文本
            title_line = m.group(0)
            fp_name = title_line.split('：', 1)[1].split('<!--')[0].strip() if '：' in title_line else fp_id
            upsert_node(con, fp_id, 'fp', fp_name, module=rel_module, sprint=sprint_tag,
                        content=section.strip(), source_path=md_path,
                        provenance='from-fp-md')
            scanned.add(fp_id)
            cnt_fp += 1
            # 业务规则提取：粗略匹配 - **业务规则**：xxx
            rule_m = re.search(r'\*\*业务规则\*\*[：:]\s*(.+?)(?=\n- \*\*|\Z)', section, re.S)
            if rule_m:
                rule_text = rule_m.group(1).strip().split('\n')[0][:200]
                rule_seq = fp_id.split('_')[-1]
                rule_id = f"RULE_{fp_id.split('_')[1]}_{rule_seq}"
                upsert_node(con, rule_id, 'rule', rule_text[:80], module=rel_module,
                            sprint=sprint_tag, content=rule_text, source_path=md_path,
                            provenance='from-fp-md')
                scanned.add(rule_id)
                upsert_edge(con, fp_id, rule_id, 'has_rule',
                            metadata={'rule_text': rule_text[:200]},
                            provenance='from-fp-md')
                cnt_rule += 1
    return cnt_fp, cnt_rule, scanned, cnt_conflict


def extract_cases_json(con, sprint_all_root, sprint_tag):
    """扫 需求文档/sprint_all/需求功能点/*/cases.json → case 节点 + covers/tests_api 边。

    provenance=from-cases-json
    返回 (cnt_case, cnt_covers, cnt_api, scanned_ids_set)
    """
    pattern = os.path.join(sprint_all_root, '需求功能点', '*', 'cases.json')
    cnt_case = cnt_covers = cnt_api = 0
    scanned = set()
    for jf in sorted(glob.glob(pattern)):
        rel_module = os.path.basename(os.path.dirname(jf))
        cases = repair_json(jf)
        if not cases:
            continue
        for case in cases:
            case_id = case.get('id')
            if not case_id:
                continue
            upsert_node(con, case_id, 'case', case.get('title', case_id),
                        module=case.get('module', rel_module), sprint=sprint_tag,
                        content=json.dumps({
                            'precondition': case.get('precondition', ''),
                            'test_data': case.get('test_data', ''),
                            'steps': case.get('steps', ''),
                            'expected': case.get('expected', ''),
                        }, ensure_ascii=False),
                        source_path=jf, provenance='from-cases-json',
                        extra={'covers': case.get('covers', []),
                               'tests_api': case.get('tests_api', [])})
            scanned.add(case_id)
            cnt_case += 1
            for fp_id in case.get('covers', []) or []:
                upsert_edge(con, case_id, fp_id, 'covers', provenance='from-cases-json')
                cnt_covers += 1
            for api_id in case.get('tests_api', []) or []:
                # 防孤儿：检查 api 节点是否已存在；若不存在先记 unresolved_deps（不建孤儿边）
                cur = con.cursor()
                cur.execute('SELECT 1 FROM nodes WHERE id = ? AND type = "api"', (api_id,))
                if cur.fetchone():
                    upsert_edge(con, case_id, api_id, 'tests_api', provenance='from-cases-json')
                    cnt_api += 1
                else:
                    con.execute('''INSERT INTO unresolved_deps
                        (source, target, kind, reason, suggested_metadata, provenance, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (case_id, api_id, 'tests_api',
                         f'cases.json 中声明的 tests_api="{api_id}" 在接口功能点.md 中找不到对应 api 节点',
                         None, 'from-cases-json',
                         datetime.now().isoformat(timespec='seconds')))
    return cnt_case, cnt_covers, cnt_api, scanned


def extract_spec_ts(con, sprint_all_root, sprint_tag):
    """扫 测试用例/sprint_all/scripts/**/*.spec.ts → script 节点 + implements 边。

    正则 test('ID - title') 抽 ID；provenance=from-spec
    返回 (cnt_script, scanned_ids_set)
    """
    pattern = os.path.join(sprint_all_root, '..', '..', '测试用例', 'sprint_all', 'scripts', '**', '*.spec.ts')
    cnt_script = 0
    scanned = set()
    for spec in glob.glob(pattern, recursive=True):
        rel_module = os.path.splitext(os.path.basename(spec))[0]
        text = read_text_safe(spec)
        for tm in SPEC_TEST_RE.finditer(text):
            title = tm.group(1).strip()
            # 期望格式：SPD_TC_XXX_NNN - 文字
            parts = title.split(' - ', 1)
            case_id = parts[0].strip() if parts else title
            script_id = f'SCRIPT_{rel_module}_{case_id}'
            upsert_node(con, script_id, 'script', title, module=rel_module,
                        sprint=sprint_tag, source_path=spec, provenance='from-spec')
            scanned.add(script_id)
            upsert_edge(con, script_id, case_id, 'implements', provenance='from-spec')
            cnt_script += 1
    return cnt_script, scanned


def extract_flow_prd(con, sprint_all_root, sprint_tag):
    """扫 sprint_all 根下 *.md（PRD/需求文档）抽端到端流程 → flow 节点 + step_in_flow 边。

    启发式：标题含「流程 / 时序 / 步骤 / 业务流程」章节，或有序列表（1. xxx → 2. xxx）。
    每个 step 通过模块名/功能名匹配回 fp 节点；匹配不到则只建 step 节点不连边。
    provenance=inferred-from-prd-flow
    """
    cnt_flow = cnt_step = 0
    # 排除 功能点.md（已由 extract_fp_md 处理）与 索引/ 目录下的产物（流程依赖图.md / 覆盖率报告.md 等）
    candidates = []
    index_dir = os.path.join(sprint_all_root, '索引') + os.sep
    for md in glob.glob(os.path.join(sprint_all_root, '*.md'), recursive=False):
        candidates.append(md)
    for md in glob.glob(os.path.join(sprint_all_root, '**', '*.md'), recursive=True):
        if os.path.basename(md) == '功能点.md':
            continue
        if md.startswith(index_dir) or os.path.normpath(os.path.dirname(md)) == os.path.normpath(index_dir.rstrip(os.sep)):
            continue
        candidates.append(md)
    seen_flows = set()
    scanned = set()
    for md_path in candidates:
        text = read_text_safe(md_path)
        # 1) 标题启发式：「流程 / 时序 / 步骤」段
        for m in re.finditer(r'(?m)^#{1,4}\s+(.*?(?:流程|时序|步骤|业务流程)[^#\n]*)$', text):
            flow_name = m.group(1).strip()
            flow_id = 'FLOW_' + re.sub(r'[^\w]', '_', flow_name)[:60]
            if flow_id in seen_flows:
                continue
            seen_flows.add(flow_id)
            section_start = m.end()
            next_h = text.find('\n#', section_start)
            section = text[section_start:next_h] if next_h != -1 else text[section_start:]
            con.execute('INSERT OR REPLACE INTO flows (id, name, source_path, provenance) VALUES (?, ?, ?, ?)',
                        (flow_id, flow_name, md_path, 'inferred-from-prd-flow'))
            upsert_node(con, flow_id, 'flow', flow_name, sprint=sprint_tag,
                        content=section.strip()[:2000], source_path=md_path,
                        provenance='inferred-from-prd-flow')
            scanned.add(flow_id)
            cnt_flow += 1
            # 解析有序列表 step：1. 选商品 → 2. 支付
            steps = []
            for sm in re.finditer(r'(?m)^\s*(\d+)[.、)]\s*(.+)$', section):
                steps.append((int(sm.group(1)), sm.group(2).strip()))
            # 模糊匹配 fp：step 文本含某 fp name 或 module 名
            cur = con.cursor()
            cur.execute('SELECT id, name, module FROM nodes WHERE type = "fp"')
            all_fps = cur.fetchall()
            for order, step_text in steps:
                # 用 step 文本反查 fp（包含 fp.name 子串）
                matched_fp = None
                for fp_id, fp_name, fp_module in all_fps:
                    if fp_name and (fp_name in step_text or (fp_module and fp_module in step_text)):
                        matched_fp = fp_id
                        break
                if matched_fp:
                    upsert_edge(con, flow_id, matched_fp, 'step_in_flow',
                                metadata={'order': order, 'step_text': step_text[:200]},
                                provenance='inferred-from-prd-flow')
                    cnt_step += 1
    return cnt_flow, cnt_step, scanned


# ---------------------------------------------------------------------------
# resolve 层（P2：跨模块依赖推断）
# ---------------------------------------------------------------------------

# 黑名单字段：明显不是业务数据流转（含 Markdown 表头噪音）
PARAM_BLACKLIST = {'page', 'size', 'pagesize', 'pageno', 'token', 'authorization',
                   'content-type', 'accept', 'user-agent',
                   '字段', 'field', 'column', '类型', 'type', '说明', 'desc',
                   'description', 'name', '备注'}


def resolve_cross_module(con):
    """跨模块依赖推断：

    ① 接口入参 ∩ 接口出参，字段非黑名单 → B consumes_data_from A，metadata.data_field
    ② PRD「流程/时序」章节抽「A → B」有序步骤 → A precedes B + B depends_on A，metadata.order
    ③ 无法确定的写入 unresolved_deps

    P2 阶段：仅② 已落地（接口入参出参匹配需 P3 extract_api_md 提供 api 节点）；
             ① 的逻辑已预埋但当前无 api 节点会自动跳过。
    provenance=inferred-from-prd-flow（②） / inferred-from-api-params（① 预留）
    """
    cur = con.cursor()
    cnt_dep = cnt_pre = cnt_unresolved = 0

    # ② flow step_in_flow 边按 order 转换成 fp 间 precedes / depends_on
    cur.execute('SELECT source FROM edges WHERE kind = "step_in_flow" GROUP BY source')
    flow_ids = [r[0] for r in cur.fetchall()]
    for flow_id in flow_ids:
        cur.execute('SELECT target, metadata_json FROM edges WHERE source = ? AND kind = "step_in_flow" '
                    'ORDER BY CAST(json_extract(metadata_json, "$.order") AS INTEGER)',
                    (flow_id,))
        rows = cur.fetchall()
        prev_fp = None
        for fp_id, meta_json in rows:
            if prev_fp and prev_fp != fp_id:
                upsert_edge(con, prev_fp, fp_id, 'precedes',
                            metadata={'via_flow': flow_id},
                            provenance='inferred-from-prd-flow')
                upsert_edge(con, fp_id, prev_fp, 'depends_on',
                            metadata={'via_flow': flow_id},
                            provenance='inferred-from-prd-flow')
                cnt_pre += 1
                cnt_dep += 1
            prev_fp = fp_id

    # ① 接口入参出参匹配（P3 才有 api 节点，这里防御性写好）
    cur.execute('SELECT id FROM nodes WHERE type = "api"')
    api_ids = [r[0] for r in cur.fetchall()]
    if len(api_ids) >= 2:
        # 简易实现：解析 extra_json 里的 input_fields / output_fields
        api_params = {}
        for api_id in api_ids:
            cur.execute('SELECT extra_json FROM nodes WHERE id = ?', (api_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                continue
            try:
                extra = json.loads(row[0])
                ins = {f.lower() for f in extra.get('input_fields', []) if f.lower() not in PARAM_BLACKLIST}
                outs = {f.lower() for f in extra.get('output_fields', []) if f.lower() not in PARAM_BLACKLIST}
                api_params[api_id] = (ins, outs)
            except json.JSONDecodeError:
                continue
        for b_id, (b_in, _) in api_params.items():
            for a_id, (_, a_out) in api_params.items():
                if a_id == b_id:
                    continue
                shared = b_in & a_out
                if shared:
                    upsert_edge(con, b_id, a_id, 'consumes_data_from',
                                metadata={'data_fields': sorted(shared)},
                                provenance='inferred-from-api-params')

    return {'depends_on_edges': cnt_dep, 'precedes_edges': cnt_pre, 'unresolved': cnt_unresolved}


# ---------------------------------------------------------------------------
# 查询层（P2：impact_radius / setup_path）
# ---------------------------------------------------------------------------

def impact_radius(con, node_ids, depth=2):
    """影响面：谁依赖 X，可能 break；BFS 到 depth 层。

    边方向区分（plan 字面 `A precedes B` 与 source=依赖者约定冲突，按方向查询）：
    - depends_on: source=依赖者→target=被依赖者。X 的下游 = 入边 source
    - consumes_data_from: source=消费者→target=数据源。X 的下游 = 入边 source
    - covers: source=case→target=fp。X(fp) 的下游 = 入边 source
    - precedes: source=前置→target=后置。X 的下游 = 出边 target（X 先于 Y，Y 是 X 下游）
    """
    visited = set()
    frontier = list(node_ids)
    affected = []
    cur = con.cursor()
    for d in range(depth):
        next_frontier = []
        for nid in frontier:
            if nid in visited:
                continue
            visited.add(nid)
            # 入边：depends_on / consumes_data_from / covers（X 是被依赖者）
            cur.execute('SELECT source, kind, metadata_json FROM edges WHERE target = ? '
                        'AND kind IN ("depends_on", "consumes_data_from", "covers")',
                        (nid,))
            for src, kind, meta in cur.fetchall():
                if src in visited:
                    continue
                affected.append({
                    'node_id': src,
                    'depth': d + 1,
                    'via_edge_kind': kind,
                    'via_target': nid,
                    'metadata': json.loads(meta) if meta else None,
                })
                next_frontier.append(src)
            # 出边：precedes（X 是前置，target 是后置=下游）
            cur.execute('SELECT target, kind, metadata_json FROM edges WHERE source = ? '
                        'AND kind = "precedes"',
                        (nid,))
            for tgt, kind, meta in cur.fetchall():
                if tgt in visited:
                    continue
                affected.append({
                    'node_id': tgt,
                    'depth': d + 1,
                    'via_edge_kind': kind,
                    'via_source': nid,
                    'metadata': json.loads(meta) if meta else None,
                })
                next_frontier.append(tgt)
        frontier = next_frontier
        if not frontier:
            break
    # 补 name / type / module + 同节点多次命中去重（保留最早 depth + 合并 via_edge_kind）
    by_node = {}
    for a in affected:
        nid = a['node_id']
        if nid not in by_node:
            by_node[nid] = a
            by_node[nid]['via_edge_kinds'] = [a['via_edge_kind']]
        else:
            existing = by_node[nid]
            if a['via_edge_kind'] not in existing['via_edge_kinds']:
                existing['via_edge_kinds'].append(a['via_edge_kind'])
            # 保留最小 depth
            if a['depth'] < existing['depth']:
                existing['depth'] = a['depth']
    affected_unique = list(by_node.values())
    for a in affected_unique:
        a.pop('via_edge_kind', None)
        cur.execute('SELECT name, type, module FROM nodes WHERE id = ?', (a['node_id'],))
        row = cur.fetchone()
        if row:
            a['name'], a['type'], a['module'] = row
    return {'anchor': node_ids, 'depth': depth, 'affected': affected_unique}


def setup_path(con, node_id, depth=3):
    """上游路径：跑 X 需准备谁的数据；BFS 到 depth 层。

    边方向区分：
    - depends_on: source=依赖者→target=被依赖者。X 的上游 = 出边 target（X 依赖谁）
    - consumes_data_from: source=消费者→target=数据源。X 的上游 = 出边 target
    - step_in_flow: source=flow→target=fp。X(fp) 的上游 = 出边 target（同 flow 的下一步）
    - precedes: source=前置→target=后置。X 的上游 = 入边 source（X 的前置）
    """
    visited = {node_id}
    frontier = [node_id]
    setup = []
    cur = con.cursor()
    for d in range(depth):
        next_frontier = []
        for nid in frontier:
            # 出边：depends_on / consumes_data_from / step_in_flow（X 依赖谁）
            cur.execute('SELECT target, kind, metadata_json FROM edges WHERE source = ? '
                        'AND kind IN ("depends_on", "consumes_data_from", "step_in_flow")',
                        (nid,))
            for tgt, kind, meta in cur.fetchall():
                if tgt in visited:
                    continue
                visited.add(tgt)
                cur.execute('SELECT name, type, module FROM nodes WHERE id = ?', (tgt,))
                row = cur.fetchone()
                setup.append({
                    'node_id': tgt,
                    'depth': d + 1,
                    'via_edge_kind': kind,
                    'via_source': nid,
                    'name': row[0] if row else None,
                    'type': row[1] if row else None,
                    'module': row[2] if row else None,
                    'metadata': json.loads(meta) if meta else None,
                })
                next_frontier.append(tgt)
            # 入边：precedes（X 是后置，source 是前置=上游）
            cur.execute('SELECT source, kind, metadata_json FROM edges WHERE target = ? '
                        'AND kind = "precedes"',
                        (nid,))
            for src, kind, meta in cur.fetchall():
                if src in visited:
                    continue
                visited.add(src)
                cur.execute('SELECT name, type, module FROM nodes WHERE id = ?', (src,))
                row = cur.fetchone()
                setup.append({
                    'node_id': src,
                    'depth': d + 1,
                    'via_edge_kind': kind,
                    'via_target': nid,
                    'name': row[0] if row else None,
                    'type': row[1] if row else None,
                    'module': row[2] if row else None,
                    'metadata': json.loads(meta) if meta else None,
                })
                next_frontier.append(src)
        frontier = next_frontier
        if not frontier:
            break
    return {'anchor': node_id, 'depth': depth, 'setup': setup}


# ---------------------------------------------------------------------------
# 查询层（P3：get_node_detail / flow_context / semantic_recall）
# ---------------------------------------------------------------------------

def get_node_detail(con, node_id):
    """单节点全字段，供 flow_context 渐进取详情。"""
    cur = con.cursor()
    cur.execute('SELECT id, type, name, module, sprint, content, source_path, provenance, extra_json '
                'FROM nodes WHERE id = ?', (node_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        'id': row[0], 'type': row[1], 'name': row[2], 'module': row[3],
        'sprint': row[4], 'content': row[5], 'source_path': row[6],
        'provenance': row[7],
        'extra': json.loads(row[8]) if row[8] else None,
    }


def flow_context(con, fp_id):
    """渐进式流程上下文包（省 token）：

    索引层（几十 token）：
    - 上游 fp（depends_on 出边 target）= X 依赖谁
    - 下游 fp（depends_on 入边 source / 谁依赖 X）= 谁依赖 X
    - 关联 api（exposes 边 source，指向 fp 的接口）
    - 关联 rule（has_rule 出边 target）
    - 同 flow 步骤（step_in_flow 边所在 flow 与 order）
    返回 ID + name 列表，主对话按需调 get_node_detail() 取全文。
    """
    cur = con.cursor()
    cur.execute('SELECT id, name, module FROM nodes WHERE id = ? AND type = "fp"', (fp_id,))
    fp_row = cur.fetchone()
    if not fp_row:
        return {'error': f'fp not found: {fp_id}'}
    fp = {'id': fp_row[0], 'name': fp_row[1], 'module': fp_row[2]}

    # 上游（出边 depends_on）：fp → 上游 fp
    cur.execute('SELECT target FROM edges WHERE source = ? AND kind = "depends_on"', (fp_id,))
    upstream_fps = []
    for (up_id,) in cur.fetchall():
        cur.execute('SELECT id, name, module FROM nodes WHERE id = ?', (up_id,))
        r = cur.fetchone()
        if r:
            upstream_fps.append({'id': r[0], 'name': r[1], 'module': r[2]})

    # 下游（入边 depends_on）：下游 fp → fp
    cur.execute('SELECT source FROM edges WHERE target = ? AND kind = "depends_on"', (fp_id,))
    downstream_fps = []
    for (down_id,) in cur.fetchall():
        cur.execute('SELECT id, name, module FROM nodes WHERE id = ?', (down_id,))
        r = cur.fetchone()
        if r:
            downstream_fps.append({'id': r[0], 'name': r[1], 'module': r[2]})

    # 关联 api（api → fp exposes）
    cur.execute('SELECT source, name FROM edges e JOIN nodes n ON e.source = n.id '
                'WHERE e.target = ? AND e.kind = "exposes" AND n.type = "api"', (fp_id,))
    apis = [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]

    # 关联 rule
    cur.execute('SELECT target, name FROM edges e JOIN nodes n ON e.target = n.id '
                'WHERE e.source = ? AND e.kind = "has_rule"', (fp_id,))
    rules = [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]

    # 同 flow 步骤
    cur.execute('SELECT source, json_extract(metadata_json, "$.order") AS ord, '
                'json_extract(metadata_json, "$.step_text") AS txt '
                'FROM edges WHERE target = ? AND kind = "step_in_flow" ORDER BY ord', (fp_id,))
    flows_in = []
    for flow_id, order, step_text in cur.fetchall():
        cur.execute('SELECT name FROM flows WHERE id = ?', (flow_id,))
        fr = cur.fetchone()
        flows_in.append({'flow_id': flow_id, 'flow_name': fr[0] if fr else None,
                         'order': order, 'step_text': step_text})

    # 已有 covers（同一 fp 已被哪些用例覆盖，供 case-generator 避免重复）
    cur.execute('SELECT source FROM edges WHERE target = ? AND kind = "covers"', (fp_id,))
    existing_covers = [r[0] for r in cur.fetchall()]

    return {
        'fp': fp,
        'upstream': upstream_fps,
        'downstream': downstream_fps,
        'apis': apis,
        'rules': rules,
        'flow': flows_in,
        'existing_covers': existing_covers,
    }


def semantic_recall(con, query, k=10, has_fts5=False):
    """语义召回：HAS_FTS5→nodes_fts MATCH；否则 name/content LIKE。

    返回 top-K 节点（按相关度排序，FTS5 用 bm25，LIKE 用命中字段数粗排）。

    注意：FTS5 默认 unicode61 tokenizer 把「支付订单」当一个 token，
    对中文短查询召回不准（漏召回子串场景）。因此查询含中文时强制 LIKE 兜底，
    FTS5 仅用于英文术语（如 order、playwright）召回。
    """
    cur = con.cursor()
    has_chinese = bool(re.search(r'[一-鿿]', query))
    if has_fts5 and not has_chinese and len(query) >= 2:
        try:
            cur.execute(
                'SELECT n.id, n.type, n.name, n.module, bm25(nodes_fts) AS score '
                'FROM nodes_fts f JOIN nodes n ON n.rowid = f.rowid '
                'WHERE nodes_fts MATCH ? ORDER BY score LIMIT ?', (query, k))
            rows = cur.fetchall()
            if rows:
                return {'query': query, 'matches': [
                    {'id': r[0], 'type': r[1], 'name': r[2], 'module': r[3], 'score': r[4]}
                    for r in rows
                ]}
        except sqlite3.OperationalError:
            pass  # FTS5 语法错误，降级
    # LIKE 兜底（中文查询或 FTS5 不可用 / 短查询时）
    like = f'%{query}%'
    cur.execute('SELECT id, type, name, module FROM nodes '
                'WHERE name LIKE ? OR content LIKE ? OR module LIKE ? LIMIT ?',
                (like, like, like, k))
    return {'query': query, 'matches': [
        {'id': r[0], 'type': r[1], 'name': r[2], 'module': r[3], 'score': None}
        for r in cur.fetchall()
    ]}


def resolve_api_data_flow(con):
    """P3：基于 extract_api_md 产出的 api 节点，补 consumes_data_from 边（与 P2 接口入参出参匹配同逻辑）。

    单独抽出方便在 build_index 主流程之外测试。P3 build 时由 resolve_cross_module 间接调用。
    """
    cur = con.cursor()
    cur.execute('SELECT id, extra_json FROM nodes WHERE type = "api"')
    api_params = {}
    for api_id, extra_json in cur.fetchall():
        if not extra_json:
            continue
        try:
            extra = json.loads(extra_json)
            ins = {f.lower() for f in extra.get('input_fields', []) if f.lower() not in PARAM_BLACKLIST}
            outs = {f.lower() for f in extra.get('output_fields', []) if f.lower() not in PARAM_BLACKLIST}
            api_params[api_id] = (ins, outs)
        except json.JSONDecodeError:
            continue
    cnt = 0
    for b_id, (b_in, _) in api_params.items():
        for a_id, (_, a_out) in api_params.items():
            if a_id == b_id:
                continue
            shared = b_in & a_out
            if shared:
                upsert_edge(con, b_id, a_id, 'consumes_data_from',
                            metadata={'data_fields': sorted(shared)},
                            provenance='inferred-from-api-params')
                cnt += 1
    return cnt


# ---------------------------------------------------------------------------
# 报告层（P2：write_flow_graph_md / write_unresolved_md）
# ---------------------------------------------------------------------------

def write_flow_graph_md(con, out_path):
    """Mermaid 流程依赖图：fp 节点 + precedes / depends_on / consumes_data_from 边。"""
    cur = con.cursor()
    cur.execute('SELECT id, name, module FROM nodes WHERE type = "fp"')
    fps = cur.fetchall()
    cur.execute('SELECT source, target, kind FROM edges WHERE kind IN '
                '("precedes", "depends_on", "consumes_data_from", "step_in_flow")')
    edges = cur.fetchall()
    lines = ['# 流程依赖图（Mermaid）', '',
             f'- 生成时间：{datetime.now().isoformat(timespec="seconds")}',
             f'- FP 节点数：{len(fps)}；跨模块边数：{len(edges)}', '',
             '```mermaid', 'graph LR']
    by_module = {}
    for fp_id, name, module in fps:
        by_module.setdefault(module or '未分组', []).append((fp_id, name))
    # 按 module 分组渲染 subgraph，避免大图凌乱
    for mod, items in sorted(by_module.items()):
        safe_mod = mod.replace('"', "'")
        lines.append(f'  subgraph "{safe_mod}"')
        for fp_id, name in items:
            safe = (name or fp_id).replace('"', "'")[:40]
            lines.append(f'    {fp_id}["{safe}<br/>{fp_id}"]')
        lines.append('  end')
    for src, tgt, kind in edges:
        style = {'precedes': '-->', 'depends_on': '-->|depends on|',
                 'consumes_data_from': '-->|data|', 'step_in_flow': '-->'}.get(kind, '-->')
        lines.append(f'  {src} {style} {tgt}')
    lines.append('```')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return len(fps), len(edges)


def write_unresolved_md(con, out_path):
    """待确认依赖清单：启发式推断但需人工确认的边。"""
    cur = con.cursor()
    cur.execute('SELECT source, target, kind, reason, suggested_metadata FROM unresolved_deps '
                'ORDER BY id')
    rows = cur.fetchall()
    lines = ['# 待确认依赖清单', '',
             f'- 生成时间：{datetime.now().isoformat(timespec="seconds")}',
             f'- 待确认数：{len(rows)}', '']
    if not rows:
        lines.append('> 当前没有待确认依赖。')
    else:
        lines.append('| # | 上游 | 下游 | 类型 | 推断理由 |')
        lines.append('|---|------|------|------|---------|')
        for i, (src, tgt, kind, reason, meta) in enumerate(rows, 1):
            lines.append(f'| {i} | {src} | {tgt} | {kind} | {reason or "—"} |')
        lines.append('')
        lines.append('> **使用方式**：主对话通过 AskUserQuestion 逐条确认 → 调度 bf-graph-agent '
                     '`apply-confirmation` 写 manual 边 + 重建。')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return len(rows)


def extract_api_md(con, sprint_all_root, sprint_tag):
    """扫 接口功能点.md → api 节点 + exposes 边（接口→其所属 fp 模块）。

    启发式：
    - 文件名/路径含「接口」字样
    - 节点 ID 推断为 API_{大写下划线名}（取 ## 标题或 URL 路径段）
    - 解析 input/output 字段（粗略：含「入参/请求参数」「出参/返回字段」段）
    provenance=from-api-md
    """
    cnt_api = cnt_exposes = 0
    scanned = set()
    candidates = []
    for md in glob.glob(os.path.join(sprint_all_root, '**', '接口*.md'), recursive=True):
        candidates.append(md)
    for md in glob.glob(os.path.join(sprint_all_root, '**', '*接口*.md'), recursive=True):
        if md not in candidates:
            candidates.append(md)
    for md_path in candidates:
        text = read_text_safe(md_path)
        rel_module = os.path.basename(os.path.dirname(md_path))
        # 每个 ## 二级标题视为一个接口
        for m in re.finditer(r'(?m)^##\s+(.+)$', text):
            title = m.group(1).strip()
            # 抽 URL 路径段作 API ID：行内含 /api/... 取末段大写下划线
            # section 必须包含标题行（URL 可能在标题里，如「## POST /api/order/create」）
            section_start = m.end()
            next_h = text.find('\n## ', section_start)
            section_tail = text[section_start:next_h] if next_h != -1 else text[section_start:]
            section = m.group(0) + '\n' + section_tail
            url_m = re.search(r'/api/([\w/\-]+)', section)
            if url_m:
                api_id = 'API_' + re.sub(r'[^\w]', '_', url_m.group(1).split('/')[-1]).upper()
            else:
                api_id = 'API_' + re.sub(r'[^\w]', '_', title)[:60].upper()
            # 字段抽取：Markdown 表格抽首列，过滤表头与分隔线
            def _extract_fields(text_block):
                rows = re.findall(r'(?m)^\|\s*([^|\n]+?)\s*\|', text_block)
                out = []
                for r in rows:
                    r = r.strip()
                    if not r or set(r) <= {'-'} or r.lower() in ('字段', 'field', 'column'):
                        continue
                    out.append(r)
                return out
            input_fields = []
            output_fields = []
            if '出参' in section:
                parts = re.split(r'出参', section, maxsplit=1)
                input_fields = _extract_fields(parts[0])
                output_fields = _extract_fields(parts[1])
            else:
                input_fields = _extract_fields(section)
            upsert_node(con, api_id, 'api', title, module=rel_module, sprint=sprint_tag,
                        content=section.strip()[:2000], source_path=md_path,
                        provenance='from-api-md',
                        extra={'input_fields': input_fields[:30],
                               'output_fields': output_fields[:30],
                               'url': url_m.group(0) if url_m else None})
            scanned.add(api_id)
            cnt_api += 1
            # exposes：api → 该模块 fp（模糊：fp module 与 api module 相同）
            cur = con.cursor()
            cur.execute('SELECT id FROM nodes WHERE type = "fp" AND module = ?', (rel_module,))
            for (fp_id,) in cur.fetchall():
                upsert_edge(con, api_id, fp_id, 'exposes',
                            provenance='from-api-md')
                cnt_exposes += 1
    return cnt_api, cnt_exposes, scanned


def extract_all(con, sprint_all_root, sprint_tag):
    """extract 阶段总入口（P1 + P2 flow + P3 api）。

    顺序：fp/api/rule 先入图（被依赖的基础），cases/spec 后入图（消费方）。
    这样 cases.json 的 tests_api 检查 api 节点是否已存在才不会误判。
    返回 dict 多一个 '_scanned_ids'（本次扫到的所有节点 id 集合），供 GC 使用。
    """
    fp, rule, s_fp, cnt_conflict = extract_fp_md(con, sprint_all_root, sprint_tag)
    api_node, exposes, s_api = extract_api_md(con, sprint_all_root, sprint_tag)
    flow, step_in_flow, s_flow = extract_flow_prd(con, sprint_all_root, sprint_tag)
    case, covers, api_tests, s_case = extract_cases_json(con, sprint_all_root, sprint_tag)
    script, s_script = extract_spec_ts(con, sprint_all_root, sprint_tag)
    scanned = s_fp | s_api | s_flow | s_case | s_script
    return {
        'fp_nodes': fp,
        'rule_nodes': rule,
        'case_nodes': case,
        'covers_edges': covers,
        'tests_api_edges': api_tests,
        'script_nodes': script,
        'flow_nodes': flow,
        'step_in_flow_edges': step_in_flow,
        'api_nodes': api_node,
        'exposes_edges': exposes,
        'fp_conflicts': cnt_conflict,
        '_scanned_ids': scanned,
    }


def gc_stale_nodes(con, scanned_ids):
    """GC：清理本次未扫到的非 manual 节点 + 孤儿边（仅 upsert 模式调用）。

    - 删除 type ∈ {fp,case,script,rule,flow,api} 且 id 不在 scanned_ids 的节点
    - 保留：apply-confirmation 写入的 manual 边两端节点（即使本次未扫到，可能是历史 manual 节点）
    - 清理：孤儿边（source 或 target 不在 nodes 表）
    - 返回清理的节点数（dict）

    场景：sprintN 删了某条 case 后，sprint_all cases.json 也没了这条 case。
    若不做 GC，旧 case 节点 + covers/tests_api/implements 边会残留在图谱中，导致覆盖率虚高。
    """
    cur = con.cursor()
    # manual 边涉及的所有 node_id（即使是本次未扫到的也保留）
    cur.execute("SELECT DISTINCT source FROM edges WHERE provenance='manual'")
    manual_sources = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT DISTINCT target FROM edges WHERE provenance='manual'")
    manual_targets = {r[0] for r in cur.fetchall()}
    preserve = manual_sources | manual_targets

    # 候选删除：可重新生成的 type 中不在 scanned_ids 的节点
    regen_types = ('fp', 'case', 'script', 'rule', 'flow', 'api')
    placeholders = ','.join('?' * len(regen_types))
    cur.execute(f"SELECT id, type FROM nodes WHERE type IN ({placeholders})", regen_types)
    stale_by_type = {}
    stale_ids = []
    for nid, ntype in cur.fetchall():
        if nid in scanned_ids or nid in preserve:
            continue
        stale_ids.append(nid)
        stale_by_type.setdefault(ntype, 0)
        stale_by_type[ntype] += 1

    if stale_ids:
        # 先删关联边（含指向 stale 节点的边）
        edge_placeholders = ','.join('?' * len(stale_ids))
        cur.execute(f"DELETE FROM edges WHERE source IN ({edge_placeholders}) OR target IN ({edge_placeholders})",
                    tuple(stale_ids) + tuple(stale_ids))
        # 再删节点
        cur.execute(f"DELETE FROM nodes WHERE id IN ({edge_placeholders})", tuple(stale_ids))

    # 清理孤儿边（两端节点都不存在；防御性，应已被上面覆盖）
    cur.execute("""DELETE FROM edges WHERE
                   source NOT IN (SELECT id FROM nodes) OR
                   target NOT IN (SELECT id FROM nodes)""")

    con.commit()
    return {'stale_nodes': len(stale_ids), 'by_type': stale_by_type}


# ---------------------------------------------------------------------------
# 查询层（P1：coverage_report）
# ---------------------------------------------------------------------------

def coverage_report(con, module=None):
    """覆盖率报告：每个模块的「已覆盖 FP / 总 FP」与未覆盖 FP 列表。

    覆盖定义：存在 case 节点经 covers 边指向该 fp。
    返回结构供主对话读取并决定是否补用例：
        {
          "modules": [
            {"module": "下单", "total": 2, "covered": 2, "uncovered_fps": [], "rate": 1.0},
            ...
          ],
          "overall": {"total": N, "covered": K, "rate": r}
        }
    """
    cur = con.cursor()
    where = 'WHERE type = ?' + (' AND module = ?' if module else '')
    params = ['fp'] + ([module] if module else [])
    cur.execute(f'SELECT id, module, name FROM nodes {where}', params)
    rows = cur.fetchall()

    by_module = {}
    for fp_id, mod, name in rows:
        by_module.setdefault(mod, []).append((fp_id, name))

    modules_out = []
    total_all = covered_all = 0
    for mod, fps in sorted(by_module.items()):
        total = len(fps)
        uncovered = []
        covered = 0
        for fp_id, name in fps:
            cur.execute('SELECT 1 FROM edges WHERE source LIKE ? AND target = ? AND kind = ? LIMIT 1',
                        ('%_TC_%', fp_id, 'covers'))
            if cur.fetchone():
                covered += 1
            else:
                uncovered.append({'id': fp_id, 'name': name})
        rate = covered / total if total else 0.0
        modules_out.append({
            'module': mod, 'total': total, 'covered': covered,
            'uncovered_fps': uncovered, 'rate': round(rate, 4),
        })
        total_all += total
        covered_all += covered
    return {
        'modules': modules_out,
        'overall': {
            'total': total_all, 'covered': covered_all,
            'rate': round(covered_all / total_all, 4) if total_all else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# 报告层（P1：dump_json / write_coverage_md）
# ---------------------------------------------------------------------------

def dump_json(con, out_path):
    """全库 dump 到 JSON，便于人工查看。"""
    cur = con.cursor()
    nodes = [dict(zip([d[0] for d in cur.description], r))
             for r in cur.execute('SELECT * FROM nodes ORDER BY type, id')]
    edges = [dict(zip([d[0] for d in cur.description], r))
             for r in cur.execute('SELECT * FROM edges ORDER BY kind, source')]
    payload = {'nodes': nodes, 'edges': edges,
               'generated_at': datetime.now().isoformat(timespec='seconds')}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(nodes), len(edges)


def write_coverage_md(con, out_path):
    """覆盖率报告 Markdown：每模块覆盖率 + 未覆盖 FP 清单。"""
    rep = coverage_report(con)
    lines = ['# 覆盖率报告']
    lines.append('')
    lines.append(f'- 生成时间：{datetime.now().isoformat(timespec="seconds")}')
    lines.append(f'- 整体覆盖率：**{rep["overall"]["covered"]}/{rep["overall"]["total"]} '
                 f'= {rep["overall"]["rate"]*100:.1f}%**')
    lines.append('')
    lines.append('## 各模块覆盖率')
    lines.append('')
    lines.append('| 模块 | 已覆盖 / 总 | 覆盖率 | 未覆盖功能点 |')
    lines.append('|------|-----------|-------|------------|')
    for m in rep['modules']:
        unc = '、'.join(f'{x["id"]}({x["name"]})' for x in m['uncovered_fps']) or '—'
        lines.append(f'| {m["module"]} | {m["covered"]}/{m["total"]} | '
                     f'{m["rate"]*100:.1f}% | {unc} |')
    lines.append('')
    overall_rate = rep['overall']['rate']
    if overall_rate < 0.8:
        lines.append(f'> ⚠️ 整体覆盖率 {overall_rate*100:.1f}% 低于 80% 阈值，主对话应把未覆盖 FP 注入补用例 agent。')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return rep['overall']['rate']


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_db_path(project_root):
    """图谱产物固定路径：{project}/需求文档/sprint_all/索引/知识图谱.db"""
    return os.path.join(project_root, '需求文档', 'sprint_all', '索引', '知识图谱.db')


def cmd_build(args, has_fts5):
    project_root = os.path.abspath(args.project)
    sprint_all_root = os.path.join(project_root, '需求文档', 'sprint_all')
    if not os.path.isdir(sprint_all_root):
        sys.exit(f'[build_index] 找不到 {sprint_all_root}，请先在项目中创建该目录。')
    db_path = get_db_path(project_root)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = sqlite3.connect(db_path)
    try:
        init_schema(con, has_fts5)
        if args.rebuild:
            con.executescript('DELETE FROM nodes; DELETE FROM edges; DELETE FROM flows; DELETE FROM unresolved_deps;')
            con.commit()
            stats = extract_all(con, sprint_all_root, args.sprint_tag)
            stats['resolve'] = resolve_cross_module(con)
        else:
            # upsert 模式：两阶段 GC
            # 阶段 1 pre-clean：清所有非 manual 节点 + 孤儿边（等同「保留 manual 的 rebuild」）
            #   目的：让 extract_* 看到干净状态，避免模糊匹配命中 stale 节点
            #   （如 extract_flow_prd 的 step→fp 匹配会查 nodes 表）
            pre_clean = gc_stale_nodes(con, set())
            # 阶段 2 extract + resolve：基于干净状态重建
            stats = extract_all(con, sprint_all_root, args.sprint_tag)
            stats['resolve'] = resolve_cross_module(con)
            # 阶段 3 post-clean：兜底清理本次 extract 产生的孤儿边
            #   场景：spec.ts 有 test 块但 cases.json 删了对应 case（implements 边变孤儿）
            #   stale_nodes 应该为 0（pre-clean 已清旧，extract 只建新），但孤儿边可能 >0
            post_clean = gc_stale_nodes(con, stats['_scanned_ids'])
            stats['gc'] = {'pre_clean': pre_clean, 'post_clean': post_clean}
        con.commit()
        n_nodes, n_edges = dump_json(con, os.path.join(os.path.dirname(db_path), '知识图谱.json'))
        rate = write_coverage_md(con, os.path.join(os.path.dirname(db_path), '覆盖率报告.md'))
        # P2 报告产物
        fp_n, edge_n = write_flow_graph_md(con, os.path.join(os.path.dirname(db_path), '流程依赖图.md'))
        unresolved_n = write_unresolved_md(con, os.path.join(os.path.dirname(db_path), '待确认依赖.md'))
        # 提取 fp_conflicts + _scanned_ids 不进 stats 顶层（_scanned_ids 是 internal）
        result = {
            'status': 'ok',
            'db_path': db_path,
            'stats': {k: v for k, v in stats.items() if not k.startswith('_')},
            'total_nodes': n_nodes,
            'total_edges': n_edges,
            'overall_coverage_rate': rate,
            'flow_graph': {'fp_nodes': fp_n, 'edges': edge_n},
            'unresolved_deps': unresolved_n,
            'has_fts5': has_fts5,
            'mode': 'rebuild' if args.rebuild else 'upsert',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        con.close()


def cmd_query(args, has_fts5):
    project_root = os.path.abspath(args.project)
    db_path = get_db_path(project_root)
    if not os.path.exists(db_path):
        sys.exit(f'[build_index] DB 不存在：{db_path}，请先执行 build。')
    con = sqlite3.connect(db_path)
    try:
        if args.query == 'coverage':
            rep = coverage_report(con, module=args.query_arg)
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        elif args.query == 'impact':
            # --query-arg: 逗号分隔的 node_id 列表；--depth 可选
            if not args.query_arg:
                sys.exit('[build_index] --query impact 需要 --query-arg <node_id,node_id,...>')
            ids = [x.strip() for x in args.query_arg.split(',') if x.strip()]
            depth = int(args.depth or 2)
            print(json.dumps(impact_radius(con, ids, depth), ensure_ascii=False, indent=2))
        elif args.query == 'setup':
            if not args.query_arg:
                sys.exit('[build_index] --query setup 需要 --query-arg <node_id>')
            depth = int(args.depth or 3)
            print(json.dumps(setup_path(con, args.query_arg, depth), ensure_ascii=False, indent=2))
        elif args.query == 'flow':
            if not args.query_arg:
                sys.exit('[build_index] --query flow 需要 --query-arg <fp_id>')
            print(json.dumps(flow_context(con, args.query_arg), ensure_ascii=False, indent=2))
        elif args.query == 'recall':
            if not args.query_arg:
                sys.exit('[build_index] --query recall 需要 --query-arg <自然语言查询>')
            k = int(args.depth or 10)
            print(json.dumps(semantic_recall(con, args.query_arg, k=k, has_fts5=has_fts5),
                             ensure_ascii=False, indent=2))
        else:
            sys.exit(f'[build_index] 子命令 --query {args.query} 尚未实现 '
                     f'（coverage / impact / setup / flow / recall 均已可用）。')
    finally:
        con.close()


def cmd_apply_confirmation(args, has_fts5):
    """读主对话转达的用户确认 JSON，写 manual 边 + 触发重建。

    输入 JSON 格式：
      {"edges":[{"source":"FP_XD_01","target":"FP_XD_02","kind":"precedes","metadata":{...}}]}
    """
    project_root = os.path.abspath(args.project)
    db_path = get_db_path(project_root)
    if not os.path.exists(db_path):
        sys.exit(f'[build_index] DB 不存在：{db_path}，请先执行 build。')
    try:
        payload = json.loads(args.apply_confirmation)
    except json.JSONDecodeError as e:
        sys.exit(f'[build_index] --apply-confirmation 不是合法 JSON：{e}')
    con = sqlite3.connect(db_path)
    inserted = 0
    try:
        for e in payload.get('edges', []):
            src = e.get('source')
            tgt = e.get('target')
            kind = e.get('kind')
            if not (src and tgt and kind):
                continue
            upsert_edge(con, src, tgt, kind,
                        metadata=e.get('metadata'),
                        provenance='manual')
            inserted += 1
        # 用户确认后这些条目视为已 resolve，从 unresolved_deps 清掉对应项
        con.executescript('DELETE FROM unresolved_deps;')
        con.commit()
        n_nodes, n_edges = dump_json(con, os.path.join(os.path.dirname(db_path), '知识图谱.json'))
        print(json.dumps({
            'status': 'ok',
            'manual_edges_inserted': inserted,
            'total_nodes': n_nodes,
            'total_edges': n_edges,
        }, ensure_ascii=False, indent=2))
    finally:
        con.close()


def main():
    has_sqlite3, has_fts5 = check_env()
    parser = argparse.ArgumentParser(description='BF 测试知识图谱构建器（V2）')
    parser.add_argument('--project', required=True,
                        help='项目根路径（DB 固定 {project}/需求文档/sprint_all/索引/知识图谱.db）')
    parser.add_argument('--source', default='sprint_all',
                        help='单一真相源，锁死 sprint_all（其他值会报错）')
    sub = parser.add_mutually_exclusive_group(required=True)
    sub.add_argument('--build', action='store_true', help='建图 / 增量更新')
    sub.add_argument('--rebuild', action='store_true', help='DROP 后重建（清空所有节点/边）')
    sub.add_argument('--query', metavar='{coverage|impact|setup|flow|recall}',
                      help='查询子命令（均可用）：coverage→模块；impact→逗号 IDs + --depth；'
                           'setup→单 ID + --depth；flow→单 fp_id；recall→自然语言 + --depth(=top-K)')
    sub.add_argument('--apply-confirmation', metavar='JSON',
                      help='读主对话转达的用户确认 JSON 写 manual 边 + 清 unresolved_deps')
    parser.add_argument('--query-arg', default=None,
                        help='查询参数（coverage→模块名；impact→逗号分隔 node_id；setup/flow→单 node_id）')
    parser.add_argument('--depth', default=None, type=int,
                        help='BFS 深度（impact 默认 2，setup 默认 3）')
    parser.add_argument('--sprint-tag', default=None, help='给节点打 sprint 字段（如 sprint1）')
    parser.add_argument('--out-md', default=None, help='（预留）报告 Markdown 路径')
    args = parser.parse_args()

    # 锁死单一真相源
    if args.source != 'sprint_all':
        sys.exit(f'[build_index] --source 必须为 sprint_all（防重复扫多 sprint），收到：{args.source}')

    if args.build or args.rebuild:
        cmd_build(args, has_fts5)
    elif args.query:
        cmd_query(args, has_fts5)
    elif args.apply_confirmation:
        cmd_apply_confirmation(args, has_fts5)


if __name__ == '__main__':
    main()
