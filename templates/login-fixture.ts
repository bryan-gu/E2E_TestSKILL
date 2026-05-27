import { test as base, expect } from '@playwright/test';

// 从 CLAUDE.md 或环境变量获取配置
const BASE_URL = process.env.BASE_URL || '{系统地址}';
const USERNAME = process.env.TEST_USERNAME || '{测试账号}';
const PASSWORD = process.env.TEST_PASSWORD || '{测试密码}';

type AuthFixture = {
  page: import('@playwright/test').Page;
};

export const test = base.extend<AuthFixture>({
  page: async ({ page }, use) => {
    // 登录流程
    await page.goto('/login');
    await page.getByPlaceholder(/用户名|账号|手机号|工号/).fill(USERNAME);
    await page.getByPlaceholder(/密码/).fill(PASSWORD);
    await page.getByRole('button', { name: /登录|登 录/ }).click();
    // 等待登录完成：导航离开登录页或首页元素出现
    await Promise.race([
      page.waitForURL('**/!(login)**'),
      page.getByRole('navigation').waitFor(),
    ]);
    await use(page);
  },
});

export { expect };
