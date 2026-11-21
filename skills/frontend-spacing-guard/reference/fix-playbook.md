# 常见翻车模式与修复

按报告里的规则名查。每条给出：症状 → 病因 → 改前/改后。

---

## 1. 按钮组贴在一起（`flex-no-gap`）

**症状**：一排按钮边框互相挨着，看起来像一个分段控件。

**病因**：写了 `display:flex`，忘了 `gap`。

```css
/* 改前 */
.toolbar { display: flex; padding: 12px; }

/* 改后 */
.toolbar { display: flex; gap: 8px; padding: 12px; }
```

注意：如果子元素上已经有 `margin-right`，**先删掉 margin 再加 gap**，否则间距翻倍。

---

## 2. 卡片里的文字贴着边框（`content-flush`）

**症状**：文字顶在卡片左上角，像被裁掉一块。

```css
/* 改前 */
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; }

/* 改后 */
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px 24px; }
```

`padding` 一般为 `16px` 起，桌面端卡片 `20–24px` 更舒展。

---

## 3. 标题和正文糊成一片（`text-block-too-close`）

**症状**：标题和下面那段文字粘在一起，读者不知道标题管哪段。

**病因**：全局 reset 把 `margin: 0` 加到了所有元素上，之后再没补回来。

```css
/* 改前 */
* { margin: 0; }
h2, p { font-size: 14px; }

/* 改后：reset 保留，但正文区域把层级补回来 */
.prose h2 { margin: 32px 0 8px; }   /* 上方远、下方近 —— 标题靠近它管的内容 */
.prose p  { margin: 0 0 12px; }
.prose h3 { margin: 24px 0 6px; }
```

关键比值：**标题上方 : 标题下方 ≈ 4 : 1**。上下一样时标题谁也不属于。

---

## 4. 表单 label 贴着输入框（`text-block-too-close`）

```html
<!-- 改前：label 和 input 是相邻块，无间距 -->
<div><label>邮箱</label><input type="email"></div>

<!-- 改后：字段本身用 flex column + gap -->
<div class="field">
  <label for="mail">邮箱</label>
  <input id="mail" type="email">
</div>
```

```css
.field { display: flex; flex-direction: column; gap: 6px; }   /* label 与 input */
.form  { display: flex; flex-direction: column; gap: 16px; }  /* 字段之间 */
```

**label↔input 用 6，字段之间用 16** —— 这样"一组"的边界才看得出来。

---

## 5. 列表项挤成一坨（`text-block-too-close` 聚合报告）

**症状**：报告说"`ul` 内有 10 处文本间距过小"，指向父容器而不是某两个 `li`。

```css
/* 改前 */
.nav li { padding: 8px 12px; border-radius: 6px; }

/* 改后 */
.nav { display: flex; flex-direction: column; gap: 4px; }
.nav li { padding: 8px 12px; border-radius: 6px; }
```

导航项之间 4px 足够（有背景块分隔），普通内容列表用 `8–12px`。

---

## 6. 图标按钮又小又挤（`tap-target-small` + `tap-targets-too-close`）

**症状**：一排 18×18 的图标挤在一起，手机上根本点不中。

```css
/* 改前 */
.icon-btn { width: 18px; height: 18px; padding: 0; border: none; }

/* 改后：视觉尺寸可以小，点击区域必须够大 */
.icon-row { display: flex; gap: 8px; }
.icon-btn {
  width: 18px; height: 18px;        /* 图标本身 */
  padding: 7px;                      /* 撑到 32×32 的点击区 */
  min-width: 32px; min-height: 32px;
  box-sizing: content-box;
  border: none; background: transparent; border-radius: 6px;
}
```

---

## 7. 浮层压在文字上（`floater-covers-sibling`）

**症状**：绝对定位的提示/标签盖住了同容器的说明文字。

```css
/* 改前：浮层没有脱离兄弟的占位，直接压上去 */
.wrap { position: relative; }
.wrap .note { position: absolute; top: 0; left: 0; }

/* 改后 A：给浮层留出空间 */
.wrap { position: relative; padding-top: 28px; }
.wrap .note { position: absolute; top: 0; left: 0; }

/* 改后 B：其实不需要浮层，回到正常文档流 */
.wrap { display: flex; flex-direction: column; gap: 8px; }
.wrap .note { position: static; }
```

先判断这个浮层是不是**真的需要浮**。很多绝对定位是"懒得排版"的产物。

---

## 8. 行与行挤在一起（`line-height-tight`）

```css
/* 改前 */
.tight { line-height: 1; }

/* 改后 */
.tight { line-height: 1.65; }   /* 正文 */
h1, h2 { line-height: 1.25; }   /* 标题可以紧一点 */
```

正文 `1.5–1.7`，标题 `1.2–1.3`，代码块 `1.5`。

---

## 9. 文字贴着屏幕边（`edge-flush`）

```css
/* 改前：body 直接装文字，移动端两边零留白 */
body { margin: 0; }

/* 改后 */
.page { max-width: 720px; margin: 0 auto; padding: 32px 20px 48px; }
```

`max-width` 同时解决另一个问题：宽屏下正文一行太长（超过 75 字符就难读）。

---

## 10. 间距翻倍（报告全部通过，但页面看起来特别空）

**病因**：`gap` 和子元素 `margin` 同时生效。

```css
/* 改前：实际 24px */
.list { display: flex; flex-direction: column; gap: 12px; }
.list > * { margin-bottom: 12px; }

/* 改后：12px */
.list { display: flex; flex-direction: column; gap: 12px; }
.list > * { margin: 0; }
```

检测器**不会**报这个（间距大不是"紧挨"），但它是同一类问题的反面。看到"明明写了 12px 却显得很空"，先查这里。

---

## 11. 整页均匀，结构看不出来（检测器不报，但要改）

**症状**：所有间距都是 16px，技术上完全一致，读起来却没有分组。

```css
/* 改前 */
.section { margin-bottom: 16px; }
.section h2 { margin-bottom: 16px; }

/* 改后 */
.section { margin-bottom: 32px; }
.section h2 { margin-bottom: 8px; }
```

**组内 : 组间 ≈ 1 : 2.5~3**。这是审美问题，也是可用性问题 —— 读者靠空白切分信息。

---

## 改完必须重跑

```bash
node scripts/run-audit.js --url http://localhost:5173/ --min-severity warning
```

目标：`0 critical`。`warning` 允许有，但每一条都要能说出"为什么这样是对的"。

间距修复的典型回退：加了 `gap` 忘了删子元素的 `margin`（翻倍）、加了 `padding` 又加了 `margin`（翻倍）、改了一个容器影响了下游布局（错位）。**每次改完都跑，不要攒着一次改十处再跑** —— 出问题时无法定位是哪一处引入的。
