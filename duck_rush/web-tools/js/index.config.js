// 导航菜单配置
const menuConfig = [
    {
        id: 'home',
        name: '首页',
        url: 'web-tools-index.html',
        icon: '🏠'
    },
    {
        id: 'gm-scripts',
        name: '脚本管理',
        icon: '📄',
        children: [
            {
                id: 'install-gm-scripts',
                name: '安装油猴脚本',
                url: 'pages/install-gm-scripts.html'
            }
        ]
    },
    {
        id: 'development',
        name: '开发工具',
        icon: '💻',
        children: [
            {
                id: 'localstorage-manager',
                name: '本地存储管理',
                url: 'pages/localstorage-manager.html'
            },
            {
                id: 'tool-hub',
                name: '工具中心',
                url: 'pages/tool-hub.html'
            }
        ]
    },
    {
        id: 'finance',
        name: '财务工具',
        icon: '💰',
        children: [
            {
                id: 'investment-calculator',
                name: '投资计算器',
                url: 'pages/investment-calculator.html'
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
                url: 'pages/web-tool-panel.html'
            }
        ]
    }
];
