
"""
doc-files是一个终端文件管理工具, 主要功能如下
1. 计算文件的哈希值,判断是否是重复文件,如果不是重复文件,添加到文件库里面
2. 根据文件类型/关键字构建文件索引(html格式)

目录结构
```
根目录
├── inbox
|   ├─ 待整理照片.jpg
├── index
|   ├─ 文档.txt
|   ├─ 照片.txt
|   ├─ 旅行.txt
├── files
|   ├─ 00/文件_{hash}.md
```

使用方式
```
> python duck-files.py
欢迎使用duck-rush文件管理

> search 关键字1 关键字2
找到345条搜索结果,展示前20条
1. 文档.txt
2. 照片.txt
...

> update-index
更新文件索引中...
更新完成
更新索引文件为index.html

```
"""

