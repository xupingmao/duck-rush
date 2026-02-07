# 日历工具

# 布局

左右布局，左侧展示日历，右侧展示当月/当日的详细信息

## 左侧布局
- 第一行：日历导航栏
   - 左侧展示当前的年份和月份，支持通过select组件切换年份和月份
   - 右侧展示按钮组，包括“上个月”，“本月”，“下个月“
- 第二行：日历表格
    - 展示当前月的日期
    - 标记当前日期
    - 如果当日有事件，展示事件的第一行内容，最多保留5个字符

## 右侧布局
- 第一行：更新事件表单
   - 日期：展示选中的日期，日期格式YYYY-MM-DD，不需要时间粒度
   - 事件描述：textarea输入框，默认3行，第一行是标题，其他是内容
   - “更新事件”按钮
- 第二行：展示Tabs
   - 展示“当月事件”,"JSON"两个个选项卡，默认选中“当月事件”
- 对于当月事件
   - 展示当月所有事件的列表
   - 每个事件包含日期和描述
      - 第一行：展示日期和删除按钮
      - 第二行：展示事件描述
- 对于JSON选项卡
   - 展示当月所有事件的JSON字符串
   - 支持格式化显示

# 功能实现

- 功能实现文件 `./calendar.html`
- 事件信息使用localstorage存储，key为`calendar-events:${year}-${month}`，value为json字符串
- 不要使用原生的alert/confirm/prompt弹窗功能，使用自定义的弹窗组件优化交互体验
- 配色方案：
   - 背景颜色：#f5f5f5
   - 文字颜色：#333
   - 按钮颜色：#4285f4
   - 星期背景颜色：#ccc
- 添加成功后的提示使用toast
- 删除动作使用confirm确认后执行
- HTML标题展示“Duck日历”
- 当月所有事件包含这个月从第一天到最后一天每天的事件，按照时间顺序排期
- 每天固定一个事件，可以在右侧进行更新
- 选中日期的时候，在右侧的更新事件表单中展示选中日期的事件信息
- 事件列表支持删除事件，点击删除按钮后，使用confirm确认删除

约束条件
- 不依赖任何外部库
- 使用ES6语法实现


## 读取事件代码

```javascript

/**
 * year 年份
 * month 月份，1-12
 * return 事件存储key
 */
function getMonthEventsKey(year, month) {
   const yearStr = year.toString();
   const monthStr = month.toString().padStart(2, '0');
   return `calendar-events:${yearStr}-${monthStr}`;
}

/**
 * year 年份
 * month 月份，1-12
 * return 事件数组
 */
function getMonthEvents(year, month) {
   const storageKey = getMonthEventsKey(year, month);
   const stored = localStorage.getItem(storageKey);
   
   if (!stored) {
         return [];
   }

   return JSON.parse(stored);
}
```
