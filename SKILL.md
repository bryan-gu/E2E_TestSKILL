---
name: bf-test-workflow
description: BF project testing workflow for Claude Code. Use when generating or maintaining UI automation testing assets from requirements documents or UI exploration, including BF project initialization, sprint0 full test generation, sprintN incremental updates, test case Excel generation, Playwright E2E script generation, execution healing, and V2 knowledge graph coverage/impact/setup/flow queries.
---

# BF Test Workflow

Use this skill to run the BF testing workflow in Claude Code projects.

## Entry Points

- To initialize a project, read `init-bf.md` and execute `/init-bf` behavior.
- To generate full or incremental testing assets, read `bf-test-workflow.md` and follow its routing.
- For stable data contracts, read `references/contracts.md` before creating or validating `功能点.md`, `cases.json`, Excel, or E2E scripts.
- For graph operations, read `references/graph-v2.md` and delegate DB work to `bf-graph-agent`.
- For E2E generation and repair conventions, read `references/e2e-playwright.md`.

## Core Rules

- Keep project outputs inside the target project directory.
- Treat `需求文档/sprint_all/` as the single truth source for graph build/query.
- Require every feature point heading to include an FP anchor such as `<!--FP_XD_01-->`.
- Require every test case in `cases.json` to include `covers` and `tests_api` arrays.
- Use bundled scripts for deterministic work: `scripts/json_to_excel.py` and `scripts/build_index.py`.
