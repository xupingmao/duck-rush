// 导航菜单配置
const menuConfig = [
    {
        id: 'home',
        name: '首页',
        url: 'web-tools-index.html',
        icon: '🏠'
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
            {
                id: 'web-tool-panel',
                name: '工具面板',
                url: 'pages/nav/web-tool-panel.html',
                description: "提供标签页管理功能的 Web 工具面板，方便在多个工具之间快速切换。",
                target: "_blank"
            },
            {
                id: 'awesome-projects',
                name: 'awesome项目',
                url: 'pages/projects/awesome-projects.html',
                description: "用于awsome项目导航"
            },
            {
                id: 'awesometop',
                name: 'Awesome Top',
                url: 'https://awesometop.cn/',
                target: "_blank",
                description: " Awesome Top 中文社区，精选了 GitHub 上优秀的开源项目，致力于帮助开发者了解当前热门项目和趋势，当访问GitHub受限时，为您提供第二通道。 "
            }
        ]
    },
    {
        id: 'development',
        name: '开发工具',
        icon: '💻',
        children: [
            {
                id: 'install-user-scripts',
                name: '安装油猴脚本',
                url: 'pages/install-user-scripts.html',
                description: "帮助您安装和管理用户脚本，提升浏览器功能。"
            },
            {
                id: 'localstorage-manager',
                name: '本地存储管理',
                url: 'pages/localstorage-manager.html',
                description: "用于管理浏览器LocalStorage数据的工具，支持添加、编辑、删除、清空和导入/导出操作。"
            },
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
            {
                id: 'run-js',
                name: '运行JS脚本',
                url: 'pages/runscripts/runjs.html',
                description: "用于运行自定义 JavaScript 脚本的工具，方便扩展浏览器功能。"
            },
            {
                id: 'timestamp-tool',
                name: '时间戳工具',
                url: 'pages/timestamp.html',
                description: "用于转换和操作时间戳的工具，方便时间计算和显示。"
            },
            {
                id: 'examples',
                name: '组件示例',
                url: 'pages/examples/index.html',
                description: "包含常用脚本示例的工具，帮助您快速上手。",
                tabs: [
                    {
                        id: 'examples-index',
                        name: '介绍',
                        url: 'pages/examples/index.html',
                        description: "包含常用脚本示例的工具，帮助您快速上手。"
                    },
                    {
                        id: 'example-tabs',
                        name: 'tab组件',
                        url: 'pages/examples/tabs.html',
                        description: "包含常用脚本示例的工具，帮助您快速上手。"
                    }
                ]
            }
        ]
    },
    {
        id: 'finance',
        name: '计算器',
        icon: '⌨️',
        children: [
            {
                id: "math-calculator",
                name: "数学计算器",
                url: "pages/calculator/math-calculator.html",
                description: "用于进行基本数学计算的工具，支持加、减、乘、除等操作。"
            }, {
                id: 'investment-calculator',
                name: '投资计算器',
                tabs: [
                    {
                        id: 'investment-calculator',
                        name: '投资计算器',
                        url: 'pages/calculator/investment-calculator.html',
                        description: "基于长期投资和储蓄的财务规划工具，帮助您预测未来财务状况。"
                    },
                    {
                        id: 'portfolio-calculator',
                        name: '组合计算器',
                        url: 'pages/calculator/portfolio-calculator.html',
                        description: "基于组合资产和利率的财务规划工具，帮助您预测未来财务状况。"
                    }
                ]
            }, {
                id: 'calorie-calculator',
                name: '卡路里计算器',
                url: 'pages/calculator/calorie-calculator.html',
                description: "用于计算食物热量的工具，帮助您管理和控制饮食。"
            }
        ]
    },
    {
        id: "design-tools",
        name: "设计工具",
        icon: "🎨",
        children: [
            {
                id: "emoji",
                name: "Emoji 选择器",
                url: "pages/emoji.html",
                description: "用于选择和复制 Emoji 字符的工具，方便在设计中使用。"
            }
        ]
    }
];
