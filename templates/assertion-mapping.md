# 预期结果断言映射表

生成 `expect()` 断言时，根据用例 `expected` 文本的语义匹配下方断言模式，再用对应模板生成代码。

模板中的 `{占位符}` 需根据录制阶段获取的实际页面结构替换：
- `{表格行选择器}` → selectors 中的表格行定位（如 `.arco-table-body .arco-table-tr`）
- `{单元格选择器}` → 表格单元格定位（如 `.arco-table-td`）
- `{列索引}` → 目标列在表格中的位置（从0开始）
- `{下拉框选择器}` → selectors 中的下拉框定位（如 `.arco-select`）
- `{选项选择器}` → 下拉选项定位（如 `.arco-select-option`）

## 断言映射表

| 预期结果语义 | 断言模式 | 模板 |
|---|---|---|
| "显示xxx"/"展示xxx" | 验证元素文本包含 | T1 |
| "弹出xxx窗口/弹窗" | 验证弹窗可见且有内容 | T2 |
| "提示xxx" | 验证 toast/notification 文本 | T3 |
| "跳转至xxx" | 验证 URL 匹配 | T4 |
| "数量为N"/"共N个"/"N个选项" | 验证元素数量 | T5 |
| "从xx到yy"/"范围xx~yy" | 验证首尾选项文本 | T6 |
| "默认值为xx"/"默认显示xx" | 验证元素初始文本 | T7 |
| "仅展示xx"/"不包含xx" | 遍历表格行验证每行指定列 | T8 |
| "恢复为xx"/"恢复默认" | 重置后验证多个元素文本 | T9 |
| "按xx倒序/排序" | 取前后两行对比 | T10 |
| "状态变为xx" | 操作前后对比状态文本 | T11 |
| "暂无数据"/"暂无消息" | 验证空状态提示 | T12 |
| "字段包含A、B、C" | 逐一验证表头文本 | T13 |
| "不可用"/"不可点击" | 验证元素禁用 | T14 |
| "日期格式yyyy-MM-dd" | 验证文本匹配日期正则 | T15 |
| "无报错"/"无错误" | 验证错误元素不可见 | T16 |
| "数据为0"/"显示为0" | 验证单元格文本为0 | T17 |
| "数值精度"/"保留小数" | 验证文本匹配小数正则 | T18 |
| "缓存结果保留" | 操作前后内容对比 | T19 |

---

## 模板代码

### T1：验证元素文本包含「xxx」

```typescript
await expect({元素locator}).toContainText('{期望文本}');
```

### T2：验证弹窗可见且有内容

```typescript
const dialog = page.locator('{弹窗选择器}');
await expect(dialog).toBeVisible();
const content = await dialog.textContent();
expect(content.length).toBeGreaterThan(0);
```

### T3：验证 toast/notification 文本

```typescript
const toast = page.locator('[class*="toast"], [class*="message"], [class*="notification"]');
await expect(toast).toContainText('{期望提示文本}');
```

### T4：验证 URL 匹配

```typescript
await expect(page).toHaveURL(/{路径关键词}/);
```

### T5：验证元素数量

```typescript
const items = page.locator('{选项选择器}');
await items.first().waitFor({ state: 'visible' });
const count = await items.count();
expect(count).toBe({期望数量});
```

### T6：验证首尾选项文本

```typescript
const options = page.locator('{选项选择器}');
await options.first().waitFor({ state: 'visible' });
await expect(options.first()).toContainText('{首个选项文本}');
await expect(options.last()).toContainText('{末尾选项文本}');
```

### T7：验证元素初始文本（默认值）

```typescript
await expect({下拉框选择器}).toContainText('{默认值文本}');
```

### T8：遍历表格行验证每行指定列

```typescript
const rows = page.locator('{表格行选择器}');
const rowCount = await rows.count();
expect(rowCount).toBeGreaterThan(0);
for (let i = 0; i < rowCount; i++) {
  const cells = rows.nth(i).locator('{单元格选择器}');
  const targetCell = cells.nth({列索引});
  await expect(targetCell).toContainText('{期望文本}');
  // 如需排除：
  // await expect(targetCell).not.toContainText('{排除文本}');
}
```

### T9：重置后验证多个元素恢复默认值

```typescript
await pageObj.click重置();
await expect({元素1}).toContainText('{默认值1}');
await expect({元素2}).toContainText('{默认值2}');
await expect({元素3}).toContainText('{默认值3}');
```

### T10：取前后两行对比排序

```typescript
const rows = page.locator('{表格行选择器}');
const firstCell = rows.first().locator('{单元格选择器}').nth({列索引});
const secondCell = rows.nth(1).locator('{单元格选择器}').nth({列索引});
const firstVal = await firstCell.textContent();
const secondVal = await secondCell.textContent();
// 降序：firstVal >= secondVal
expect(firstVal >= secondVal).toBeTruthy();
```

### T11：操作前后对比状态文本

```typescript
// 记录操作前状态
const beforeText = await {状态元素}.textContent();
// 执行操作
await {操作};
// 验证状态变化
await expect({状态元素}).toContainText('{期望新状态}');
```

### T12：验证空状态提示

```typescript
const emptyEl = page.locator('.arco-empty, [class*="empty"]');
await expect(emptyEl).toContainText('暂无');
```

### T13：逐一验证表头文本

```typescript
const headers = page.locator('{表头选择器}');
await expect(headers).toContainText('{表头1}');
await expect(headers).toContainText('{表头2}');
await expect(headers).toContainText('{表头3}');
```

### T14：验证元素禁用

```typescript
await expect({按钮locator}).toBeDisabled();
```

### T15：验证文本匹配日期正则

```typescript
await expect({文本元素}).toMatch(/\d{4}-\d{2}-\d{2}/);
```

### T16：验证错误元素不可见

```typescript
const errorMsg = page.locator('[class*="error"], [class*="fail"], [class*="alert"]');
await expect(errorMsg).not.toBeVisible({ timeout: 3000 });
```

### T17：验证单元格文本为0

```typescript
const cell = page.locator('{表格行选择器}').nth({行索引}).locator('{单元格选择器}').nth({列索引});
await expect(cell).toHaveText('0');
```

### T18：验证文本匹配小数正则

```typescript
await expect({文本元素}).toMatch(/\d+\.\d+/);
```

### T19：操作前后内容对比（缓存验证）

```typescript
const beforeContent = await {元素}.textContent();
// 关闭再打开
await {关闭操作};
await {打开操作};
const afterContent = await {元素}.textContent();
expect(afterContent).toContain(beforeContent);
```

---

## 禁止使用的弱断言

以下断言模式**禁止**作为最终验证手段：

```typescript
expect(typeof val).toBe('boolean')     // 不验证实际值
expect(text).toBeTruthy()              // 仅验证非空
expect(count).toBeGreaterThanOrEqual(0) // 永远通过
expect(count).toBeGreaterThanOrEqual(0).catch(() => {}) // 永远通过 + 忽略错误
// 仅验证点击操作不报错（无任何断言）
```

## 数据依赖性断言处理

当预期结果依赖于实际数据状态（如"已同步"/"同步失败"），使用**兼容性正则**而非硬编码文本：

```typescript
// 正确：兼容多种状态
expect(rowText).toMatch(/已同步|失败/);

// 错误：硬编码假设数据状态
expect(rowText).toContain('已同步');
```
