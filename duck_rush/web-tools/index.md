# 工具中心

功能：工具中心，用于展示所有可用的工具。

# 布局

左右布局
- 左侧：二级导航栏
  - 一级菜单：包含图标和文字
  - 一级菜单可以展开二级菜单
  - 二级菜单可以是单个工具，也可以是Tabs+多个工具
  - 最底部是一个展开/收起图标，用于展开和收起左侧菜单
- 右侧：
    - 工具标题栏
        - 工具栏右侧展示按钮“新Tab页打开”
        - 如果是单个工具，展示工具名称
        - 如果是Tabs+多个工具，展示Tabs导航
    - 工具iframe页面
        - 展示工具的具体功能页面
        - 宽度100%，高度100%

# 功能实现

- 功能实现文件 `./index.html`
- 配置文件 `./js/index.config.js`
- JavaScript实现文件 `./js/index.js`

约束条件
- 不依赖任何外部库

# 示例

菜单数据示例

```javascript
const menuConfig = [
    {
        id: 'home',
        name: '首页',
        url: 'web-tools-index.html',
        icon: '🏠',
        comment: '一级菜单'
    },
    {
        id: 'nav-tools',
        name: '导航工具',
        icon: '🌐',
        children: [
            {
                id: 'tool-hub',
                name: '网址导航',
                url: 'pages/nav/tool-hub.html',
                description: "集成了各种 Web 工具的综合管理界面，支持分类浏览和快速访问。"
            },
        ],
        comment: '二级菜单'
    },
    {
        id: 'development',
        name: '开发工具',
        icon: '💻',
        comment: '二级菜单+Tabs导航',
        children: [
            {
                id: 'text-split',
                name: '文本转换工具',
                url: 'pages/text/text-convert.html',
                description: "用于将长文本转换为不同格式的工具，方便阅读和处理。"
            },
            {
                id: 'json-formatter',
                name: 'JSON工具',
                tabs: [
                    {
                        id: 'json-formatter',
                        name: '格式化',
                        url: 'pages/json.html',
                        description: "用于格式化 JSON 数据的工具，方便阅读和处理。"
                    },
                    {
                        id: 'json-extract',
                        name: '提取',
                        url: 'pages/json/json-extract.html',
                        description: "用于从 JSON 数据中提取指定字段的工具，方便数据处理。"
                    }
                ],
                description: "用于格式化和验证 JSON 数据的工具，方便阅读和处理。"
            },
        ]
    }
]
```