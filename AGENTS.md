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
- `duck_utils/` — 独立共享工具包（`fs_util`、`os_util`、`sqlite_util`），由 `install.py` 安装到本地，脚本通过 `import duck_utils` 使用
- `config/requirements.txt` — Python依赖（termcolor, fire, chardet, xlwt, xlrd）
- `install.py` — 构建/安装编排脚本（**无其他构建系统**）
- `lib/` — 第三方库（目前仅jquery-1.12.4）
- `data/` — 运行时生成，已gitignore

## 关键命令

| 命令 | 说明 |
|------|------|
| `python install.py` | 安装全部（pip install 依赖 → 安装 duck_utils 包 → 生成包装器 → 索引采集） |
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
- **跨平台**：使用 `duck_utils/os_util.py` 的 `is_windows/is_mac/is_linux` 判断平台
- **依赖按需引入**：部分脚本（如图片处理）可能需PIL/numpy等额外包，但 `requirements.txt` 未列出
- **`-h`/`--help` 必须支持**：每个工具/命令脚本（`.py`/`.sh`）都必须支持 `-h` 与 `--help`，
  打印用法说明后以退出码 `0` 结束，且**不得产生任何副作用**（不得执行 git 操作、文件写入、网络请求、
  删除分支、重置代码等）。`duck` 会在安装/列举命令时调用 `{cmd} -h` 获取简介，因此带副作用的脚本一旦
  被 `-h` 触发就会误执行——`git-pull-force.py` 曾因此被 `-h` 触发 `git reset --hard`。
  - Python：在 `if __name__ == "__main__":` 块**最开头**判断 `sys.argv[1] in ("-h", "--help")`，
    打印用法（优先用模块 docstring，其次自述）后 `sys.exit(0)`，再执行原有逻辑；
    切勿在模块顶层（import 之外）或 `__main__` 中无条件执行有副作用的操作。
  - Shell：在脚本开头（`#!` 之后）用 `case "$1" in -h|--help) echo "Usage: ..."; exit 0;; esac` 处理。
  - 例外：`editor/sublime-text/*` 等 Sublime Text 插件、纯 Python 2 第三方库（如 `html2text.py`）
    不在独立 CLI 环境运行，不受此约束。
- **Python版本**: >= 3.6
- **类型注解**: 默认加上类型注解；默认值为 `None` 的参数必须标注为
  `Optional[...]`（如 `fields: Optional[list] = None`、`result: Optional[dict] = None`）
- **mypy 类型检查**: **增量代码必须通过 mypy 检查**（按 mypy 1.x 默认规则，无配置文件）。
  提交/合并前，对本次改动的 `.py` 文件运行：
  `python -m mypy <改动文件1> <改动文件2> ...`，确保输出 `Success: no issues found`。
  新增或修改的函数/方法需补齐类型注解；动态设置的属性（如 `setattr(obj, "x", v)`）
  或 `importlib` 加载等无法静态推断处，用 `assert xxx is not None` 收窄类型而非 `# type: ignore`。
- **代码组织**: 避免过深的嵌套函数调用（如 `SortOp(JsonOnlyOp(FilterOp(...)))`），
  应拆成多行逐步构造，提升可读性
- **算子/流水线**: 数据处理类脚本可采用 Volcano 模型——`ScanOp` 产出
  `('json', obj)`/`('text', str)` 行，后续 `FilterOp`/`SplitOp`/`GroupByOp`/`SortOp`
  等依次消费上游 `source` 迭代器，最后组装输出