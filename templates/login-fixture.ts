import { test as base, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || '{系统地址}';
const USERNAME = process.env.TEST_USERNAME || '{测试账号}';
const PASSWORD = process.env.TEST_PASSWORD || '{测试密码}';

type AuthFixture = {
  page: import('@playwright/test').Page;
};

export const test = base.extend<AuthFixture>({
  page: async ({ page }, use) => {
    const loginUrl = new URL('/login', BASE_URL).toString();
    await page.goto(loginUrl);
    await page.getByPlaceholder(/用户名|账号|手机号|工号/).fill(USERNAME);
    await page.getByPlaceholder(/密码/).fill(PASSWORD);
    await page.getByRole('button', { name: /登录|登 录/ }).click();

    await Promise.race([
      page.waitForURL((url) => !url.pathname.toLowerCase().includes('login'), { timeout: 15000 }),
      page.getByRole('navigation').waitFor({ state: 'visible', timeout: 15000 }),
      page.locator('.arco-layout, [class*="layout"], [class*="menu"]').first().waitFor({ state: 'visible', timeout: 15000 }),
    ]);

    await use(page);
  },
});

export { expect };
