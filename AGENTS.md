# duck-rush (冲鸭) — 项目指南

## 快速开始

```bash
python install.py    # 安装全部工具（装依赖 → sdist install → 生成包装脚本 → 收集命令索引）
```

## 项目结构

- `duck_rush/` — 主源码包，约110+个独立CLI脚本，按领域分目录
- `duck_rush/duck.py` — CLI入口，按名称匹配并执行各脚本
- `duck_rush/web-tools/` — 独立Web工具中心（SPA），入口 `index.html`
- `duck_rush/gui-tools/floatbar/` — tkinter浮动工具栏
- `duck_rush/utils/` — 共享工具模块（`fs_util`、`os_util`、`sqlite_util`）
- `config/requirements.txt` — Python依赖（termcolor, fire, chardet, xlwt, xlrd）
- `install.py` — 构建/安装编排脚本（**无其他构建系统**）
- `lib/` — 第三方库（目前仅jquery-1.12.4）
- `data/` — 运行时生成，已gitignore

## 关键命令

| 命令 | 说明 |
|------|------|
| `python install.py` | 安装全部（pip install → setup.py sdist install → 生成包装器 → 索引采集） |
| `python duck_rush/duck.py list` | 列出所有已注册命令 |
| `python duck_rush/web-tools/duck-web-tools.py` | 启动Web工具（file:// 或 HTTP :8000） |

## 测试

- 多数脚本**无正式测试框架**，`tests/` 目录仅为用法示例
- `duck_rush/text/test_duck_json.py` 是 unittest 单元测试(仅依赖标准库),
  覆盖 duck-json 的算子与 CLI 行为; 运行: `python duck_rush/text/test_duck_json.py`
- FloatBar GUI 含3个手动测试脚本：`gui-tools/floatbar/test_*.py`
- 直接 `python <脚本>` 执行测试

## 开发注意事项

- **安装后入口**：每个 `.py` 脚本被包装为独立命令（Win: `%USERPROFILE%\duck_rush\*.bat`，Unix: `local/bin/*`）
- **gitignore** 已忽略 `local/`、`data/`、`gui-tools/`、`*.local.json`、构建产物
- **Git远程**：`github` → github.com/xupingmao/duck-rush，`origin` → gitee.com/xupingmao/duck-rush
- **跨平台**：使用 `duck_rush/utils/os_util.py` 的 `is_windows/is_mac/is_linux` 判断平台
- **依赖按需引入**：部分脚本（如图片处理）可能需PIL/numpy等额外包，但 `requirements.txt` 未列出
- **Python版本**: >= 3.6
- **类型注解**: 默认加上类型注解；默认值为 `None` 的参数必须标注为
  `Optional[...]`（如 `fields: Optional[list] = None`、`result: Optional[dict] = None`）
- **代码组织**: 避免过深的嵌套函数调用（如 `SortOp(JsonOnlyOp(FilterOp(...)))`），
  应拆成多行逐步构造，提升可读性
- **算子/流水线**: 数据处理类脚本可采用 Volcano 模型——`ScanOp` 产出
  `('json', obj)`/`('text', str)` 行，后续 `FilterOp`/`SplitOp`/`GroupByOp`/`SortOp`
  等依次消费上游 `source` 迭代器，最后组装输出