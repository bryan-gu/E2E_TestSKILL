// extract-selectors.js
// 通过 browser_evaluate 执行，一次提取页面所有可交互元素的选择器
// 返回: Array<{ text, selector, tag, role }>
//
// 选择器策略（确定性逻辑，不依赖 AI 推断）：
//   1. id → #id
//   2. data-testid → [data-testid="xxx"]
//   3. arco- 开头的 class → .arco-xxx（取第一个 arco- class）
//   4. 无上述属性 → tag + text 组合（仅作为最后手段）

() => {
  const interactable = [
    'button', 'input', 'select', 'textarea', 'a[href]',
    '[role="button"]', '[role="link"]', '[role="menuitem"]', '[role="tab"]',
    '[role="combobox"]', '[role="option"]', '[role="checkbox"]', '[role="radio"]',
    '[class*="arco-select"]', '[class*="arco-menu"]', '[class*="arco-table"]',
    '[class*="arco-btn"]', '[class*="arco-input"]', '[class*="arco-trigger"]',
    '.arco-table-th', '.arco-table-td'
  ].join(', ');

  const elements = document.querySelectorAll(interactable);
  const results = [];

  for (const el of elements) {
    const text = el.textContent?.trim().slice(0, 50) || '';
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || null;

    // 策略 1: id
    if (el.id) {
      results.push({ text, selector: `#${el.id}`, tag, role });
      continue;
    }

    // 策略 2: data-testid
    const testId = el.getAttribute('data-testid');
    if (testId) {
      results.push({ text, selector: `[data-testid="${testId}"]`, tag, role });
      continue;
    }

    // 策略 3: arco- class
    const arcoCls = Array.from(el.classList).find(c => c.startsWith('arco-'));
    if (arcoCls) {
      results.push({ text, selector: `.${arcoCls}`, tag, role });
      continue;
    }

    // 策略 4: tag（信息量低，仅作兜底）
    results.push({ text, selector: tag, tag, role });
  }

  return results;
}
