import { Locator, Page } from '@playwright/test';

export class {模块名}Page {
  readonly page: Page;

  // 导航
  readonly menuLink: Locator;

  // 页面元素
  readonly xxxButton: Locator;
  readonly xxxInput: Locator;
  readonly xxxTable: Locator;

  constructor(page: Page) {
    this.page = page;
    // 选择器来自 browser_evaluate 提取的真实 DOM 属性
    // 格式：#id / [data-testid="xxx"] / .arco-xxx / tag
    this.menuLink = page.locator('{selector}');
    this.xxxButton = page.locator('{selector}');
    this.xxxInput = page.locator('{selector}');
    this.xxxTable = page.locator('{selector}');
  }

  async goto() {
    await this.menuLink.click();
    // 等待页面核心内容加载，按实际页面替换为具体元素
    await this.xxxTable.waitFor();
  }
}
