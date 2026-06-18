# BF 测试资产契约

## 目录契约

- 全量需求输入：`需求文档/sprint0/`
- 汇总真相源：`需求文档/sprint_all/`
- Sprint 功能点：`需求文档/{sprint}/需求功能点/{模块名}/功能点.md`
- 汇总功能点：`需求文档/sprint_all/需求功能点/{模块名}/功能点.md`
- Sprint 用例 Excel：`测试用例/{sprint}/{sprint}_testCase.xlsx`
- 汇总用例 Excel：`测试用例/sprint_all/testCase.xlsx`
- Sprint E2E 脚本：`测试用例/{sprint}/{sprint}_scripts/`
- 汇总 E2E 脚本：`测试用例/sprint_all/scripts/`
- 图谱产物：`需求文档/sprint_all/索引/`

## 功能点契约

每个功能点标题必须带 FP 锚点：

```markdown
## 功能点1：选择商品 <!--FP_XD_01-->
```

字段必须完整：描述、操作入口、交互元素、业务规则、优先级、来源。
文档未提及时写 `文档未提及`，不要留空。

## cases.json 契约

每条用例必须包含：

```json
{
  "id": "SPD_TC_XD_001",
  "module": "下单",
  "title": "选择商品后进入结算页",
  "precondition": "1. 已登录；2. 商品SKU=1001存在",
  "test_data": "商品SKU=1001",
  "steps": "1. 用户输入用户名、密码点击登录。
2. 进入下单页选择商品。",
  "expected": "1. 登录成功。
2. 跳转结算页并展示商品。",
  "covers": ["FP_XD_01"],
  "tests_api": []
}
```

规则：

- `id` 格式：`{项目前缀}_TC_{模块缩写}_{三位序号}`。
- `covers` 必须来自 `功能点.md` 标题中的 FP 锚点。
- 不涉及接口时 `tests_api` 写 `[]`。
- `steps` 和 `expected` 的编号数量必须一致。
- 文本中引用按钮、菜单、字段时使用 `「」`，避免破坏 JSON 字符串。

## Excel 契约

Excel 统一为 10 列：

| 测试用例ID | 模块 | 标题 | 前置条件 | 测试数据 | 测试步骤 | 预期结果 | 实际结果 | 覆盖功能点 | 关联接口 |
| ---------- | ---- | ---- | -------- | -------- | -------- | -------- | -------- | ---------- | -------- |

`json_to_excel.py` 会把 `covers` 写入“覆盖功能点”，把 `tests_api` 写入“关联接口”。
