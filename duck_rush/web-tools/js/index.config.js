// 导航菜单配置
const menuConfig = [
    {
        id: 'home',
        name: '首页',
        url: 'web-tools-index.html',
        icon: '🏠'
    },
    {
        id: 'development',
        name: '开发工具',
        icon: '💻',
        children: [
            {
                id: 'tool-hub',
                name: '网址导航',
                url: 'pages/tool-hub.html',
                description: "集成了各种 Web 工具的综合管理界面，支持分类浏览和快速访问。"
            },
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
                name: 'JSON 格式化工具',
                url: 'pages/json.html',
                description: "用于格式化和验证 JSON 数据的工具，方便阅读和处理。"
            },
            {
                id: 'awesome-projects',
                name: 'awesome项目',
                url: 'pages/projects/awesome-projects.html',
                description: "用于awsome项目导航"
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
            },{
                id: 'investment-calculator',
                name: '投资计算器',
                url: 'pages/calculator/investment-calculator.html',
                description: "基于长期投资和储蓄的财务规划工具，帮助您预测未来财务状况。"
            },{
                id: 'calorie-calculator',
                name: '卡路里计算器',
                url: 'pages/calculator/calorie-calculator.html',
                description: "用于计算食物热量的工具，帮助您管理和控制饮食。"
            }
        ]
    },
    {
        id: 'web-tools',
        name: 'Web 工具',
        icon: '🌐',
        children: [
            {
                id: 'web-tool-panel',
                name: 'Web 工具面板',
                url: 'pages/web-tool-panel.html',
                description: "提供标签页管理功能的 Web 工具面板，方便在多个工具之间快速切换。"
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
