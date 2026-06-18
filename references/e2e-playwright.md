# Playwright E2E 契约

## 生成原则

- 选择器必须来自真实页面结构：优先使用 `browser_snapshot` 与 `templates/extract-selectors.js` 的结果。
- 语义 locator 可以使用，但必须被实际页面验证。
- 不使用 `waitForLoadState('networkidle')`。
- 等待具体元素可见、URL 状态稳定或业务 toast 出现。

## 文件结构

```text
测试用例/{sprint}/{sprint}_scripts/
├── playwright.config.ts
├── fixtures/login.fixture.ts
├── selectors/{模块名}.selectors.ts
└── {模块名}.spec.ts
```

## 修复边界

`bf-e2e-healer` 只能修复选择器和等待策略。
不得为了让测试通过而修改业务断言、预期值、操作步骤或业务分支。
断言失败应记录实际值与预期值差异，交由人工确认。
