import { test, expect } from '../fixtures/login.fixture';
import { {模块名}Page } from '../selectors/{模块名}.selectors';

test.describe('{模块名}', () => {
  let {模块名Var}: {模块名}Page;

  test.beforeEach(async ({ page }) => {
    {模块名Var} = new {模块名}Page(page);
    await {模块名Var}.goto();
  });

  test('{用例标题}', async ({ page }) => {
    // 测试步骤
    // 预期结果断言（参考 templates/assertion-mapping.md）
  });
});
