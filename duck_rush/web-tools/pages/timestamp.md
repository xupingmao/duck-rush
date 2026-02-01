# 时间戳转换器 - Claude AI 提示词

## 项目概述
基于HTML5、CSS3和JavaScript的单页面应用，使用layui 2.13.3作为UI框架，提供时间戳与日期时间的双向转换功能。

## 核心功能
1. **时区设置**：支持13个常用时区，自动检测本地时区，动态切换实时更新
2. **时间戳转时间**：支持秒级/毫秒级时间戳，自动识别类型，多种输出格式
3. **时间转时间戳**：集成layui时间选择器，支持手动输入多种格式
4. **批量转换**：支持批量输入，逐项显示结果，错误项高亮

## 技术栈
- HTML5、CSS3、JavaScript (ES6+)
- layui 2.13.3（时间选择器）
- 原生DOM API、Navigator Clipboard API

## 核心函数
- `getLocalTimezone()` - 获取本地时区
- `applyTimezoneOffset(date, timezone)` - 应用时区偏移
- `removeTimezoneOffset(date, timezone)` - 移除时区偏移
- `formatDateTime(date, format)` - 格式化日期时间
- `parseDateTime(dateTimeStr)` - 解析日期时间（支持多种格式）
- `convertTimestampToTime()` - 时间戳转时间
- `convertTimeToTimestamp()` - 时间转时间戳
- `batchConvert()` - 批量转换
- `copyToClipboard(text)` - 复制到剪贴板
- `showToast(message, type)` - 显示提示信息

## 关键配置
- layui路径：`../lib/layui/2.13.3/layui.js`
- 时区范围：UTC-08:00 到 UTC+11:00
- 时间戳类型阈值：1e11（自动识别秒级/毫秒级）
- 响应式断点：768px

## 支持的日期时间格式
- YYYY-MM-DD HH:mm:ss
- YYYY/MM/DD HH:mm:ss
- YYYY-MM-DDTHH:mm:ss
- YYYY-MM-DD
- YYYY/MM/DD

## 页面加载流程
1. 初始化时区（自动检测本地时区）
2. 获取当前时间戳并填充
3. 获取当前日期时间并填充

## 时区处理逻辑
- 时间戳转时间：将UTC时间戳转换为目标时区时间
- 时间转时间戳：将目标时区时间转换为UTC时间戳
- 时区切换：所有转换结果实时更新

## 错误处理
- 空值检查
- 数值验证
- 日期格式验证
- 使用showToast()显示错误信息
- 批量转换错误项高亮显示

## 安全考虑
- 使用escapeHtml()转义输出内容
- 使用textContent代替innerHTML
- 严格验证输入格式

## 开发规范
- 使用ES6+语法
- 函数和变量使用小驼峰命名
- CSS类名使用中划线分隔
- 添加必要的注释

## 测试要点
- 时间戳转时间（秒级、毫秒级、自动识别）
- 时间转时间戳（多种格式）
- 批量转换（大量数据）
- 时区切换（所有时区）
- 复制功能
- 错误处理
- 响应式布局
