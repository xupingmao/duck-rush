// DOM 元素
const navMenu = document.getElementById('navMenu');
const pageTitle = document.getElementById('pageTitle');
const contentFrame = document.getElementById('contentFrame');
const openNewWindowBtn = document.getElementById('openNewWindowBtn');
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const sidebar = document.querySelector('.sidebar');
const pageTabs = document.querySelector('.page-tabs');

// 当前选中的菜单项和tab
let currentMenuItem = null;
let currentTabIndex = 0;

// 初始化函数
function init() {
    // 生成导航菜单
    generateNavMenu(true);

    // 添加导航事件监听器
    addNavEventListeners();

    // 加载默认页面
    loadInitPage();

    // 添加新Tab页打开功能
    if (openNewWindowBtn) {
        openNewWindowBtn.addEventListener('click', function () {
            const currentUrl = contentFrame.src;
            if (currentUrl) {
                window.open(currentUrl, '_blank');
            }
        });
    }

    // 添加切换侧边栏功能
    if (toggleSidebarBtn && sidebar) {
        toggleSidebarBtn.addEventListener('click', handleNavToggleClick);
    }

    // 添加窗口大小变化事件监听器
    window.addEventListener('resize', handleResizeEvent);
}

/**
 * 处理窗口大小变化事件
 * @param {Event} e - 窗口大小变化事件对象
 */
function handleResizeEvent(e) {
        // 重新生成导航菜单，确保在宽度变化时使用正确的菜单样式
        generateNavMenu(true);
        // 重新添加导航事件监听器
        addNavEventListeners();
}

// 处理导航切换点击事件
function handleNavToggleClick(e) {
    sidebar.classList.toggle('collapsed');
    // 重新生成导航菜单
    generateNavMenu();
    // 重新添加导航事件监听器
    addNavEventListeners();
}

// 生成展开状态的导航菜单
function generateExpandedNavMenu() {
    navMenu.innerHTML = '';

    menuConfig.forEach(item => {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.id = item.id;

        const a = document.createElement('a');
        a.id = `nav-${item.id}`;
        a.href = '#';
        a.dataset.url = item.url;
        a.dataset.title = item.name;
        if (item.children && item.children.length > 0) {
            a.innerHTML = `<span class="menu-content"><span>${item.icon}</span> ${item.name}</span> <span class="toggle-icon">▶</span>`;
        } else {
            a.innerHTML = `<span class="menu-content"><span>${item.icon}</span> ${item.name}</span>`;
        }

        li.appendChild(a);

        // 如果有子菜单
        if (item.children && item.children.length > 0) {
            const subMenu = document.createElement('ul');
            subMenu.className = 'sub-menu';

            item.children.forEach(child => {
                const childLi = document.createElement('li');
                childLi.className = 'nav-item';
                childLi.id = child.id;

                const childA = document.createElement('a');
                childA.href = '#';
                childA.dataset.url = child.url;
                childA.dataset.title = child.name;
                childA.textContent = child.name;

                // 添加点击事件
                childA.addEventListener('click', function (e) {
                    e.preventDefault();
                    const url = this.dataset.url;
                    const title = this.dataset.title;
                    loadPage(url, title, child);
                    updateActiveNavItem(this);
                });

                childLi.appendChild(childA);
                subMenu.appendChild(childLi);
            });

            li.appendChild(subMenu);

            // 添加展开/折叠功能
            a.addEventListener('click', function (e) {
                e.preventDefault();
                expandNavItems(a);
            });
        } else {
            // 没有子菜单的菜单项，直接加载页面
            a.addEventListener('click', function (e) {
                e.preventDefault();
                const url = this.dataset.url;
                const title = this.dataset.title;
                loadPage(url, title, item);
                updateActiveNavItem(this);
            });
        }

        navMenu.appendChild(li);
    });
}

// 展开/折叠导航项
function expandNavItems(target) {
    const subMenu = target.nextElementSibling;
    const toggleIcon = target.querySelector('.toggle-icon');
    if (subMenu) {
        subMenu.classList.toggle('open');
        if (toggleIcon) {
            if (subMenu.classList.contains('open')) {
                toggleIcon.style.transform = 'rotate(90deg)';
            } else {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        }
    }
}

// 生成折叠状态的导航菜单
function generateCollapsedNavMenu() {
    navMenu.innerHTML = '';

    menuConfig.forEach(item => {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.id = item.id;

        const a = document.createElement('a');
        a.href = '#';
        a.dataset.url = item.url;
        a.dataset.title = item.name;
        // 只显示图标，不显示文字
        a.innerHTML = `<span class="menu-content"><span>${item.icon}</span></span>`;

        li.appendChild(a);

        // 如果有子菜单
        if (item.children && item.children.length > 0) {
            // 添加展开/折叠功能
            a.addEventListener('click', function (e) {
                sidebar.classList.toggle('collapsed');
                // 重新生成导航菜单
                generateNavMenu();
                // 重新添加导航事件监听器
                addNavEventListeners();
                // 模拟点击导航项，展开子菜单
                const navItem = document.querySelector(`#nav-${item.id}`);
                navItem.click();
            });
        } else {
            // 没有子菜单的菜单项，直接加载页面
            a.addEventListener('click', function (e) {
                e.preventDefault();
                const url = this.dataset.url;
                const title = this.dataset.title;
                loadPage(url, title);
                updateActiveNavItem(this);
            });
        }

        navMenu.appendChild(li);
    });
}

/**
 * 生成导航菜单
 * @param {boolean} isInitOrResize - 是否是初始化调用或窗口大小变化调用
 */
function generateNavMenu(isInitOrResize) {
    if (isInitOrResize) {
        // 检查是否是移动端
        const isMobile = window.innerWidth <= 768;
    
        if (isMobile) {
            sidebar.classList.add('collapsed');
        }
    }
    
    if (sidebar && sidebar.classList.contains('collapsed')) {
        generateCollapsedNavMenu();
    } else {
        generateExpandedNavMenu();
    }
}

// 添加导航事件监听器
function addNavEventListeners() {
    // 事件监听器已在生成导航菜单时添加
}

// 加载默认页面
function loadInitPage() {
    // 获取当前URL参数
    const params = new URLSearchParams(window.location.search);
    const currentUrl = params.get('page');

    if (currentUrl) {
        // 找到对应的导航项并激活
        let found = false;
        
        // 查找顶级菜单项
        for (const item of menuConfig) {
            if (item.url === currentUrl) {
                loadPage(currentUrl, item.name, item);
                const navItem = document.querySelector(`#nav-${item.id}`);
                if (navItem) {
                    updateActiveNavItem(navItem);
                }
                found = true;
                break;
            }
            
            // 查找子菜单项
            if (item.children) {
                for (const child of item.children) {
                    if (child.url === currentUrl) {
                        loadPage(currentUrl, child.name, child);
                        const navItem = document.querySelector(`#${child.id} a`);
                        if (navItem) {
                            updateActiveNavItem(navItem);
                        }
                        found = true;
                        break;
                    }
                    
                    // 查找tab项
                    if (child.tabs) {
                        for (const tab of child.tabs) {
                            if (tab.url === currentUrl) {
                                loadPage(currentUrl, tab.name, child);
                                const navItem = document.querySelector(`#${child.id} a`);
                                if (navItem) {
                                    updateActiveNavItem(navItem);
                                }
                                found = true;
                                break;
                            }
                        }
                    }
                }
                if (found) break;
            }
        }
        
        if (!found) {
            // 如果没有找到对应的导航项，加载默认页面
            loadPage(menuConfig[0].url, menuConfig[0].name, menuConfig[0]);
        }
    } else {
        // 如果没有指定页面，加载默认页面
        loadPage(menuConfig[0].url, menuConfig[0].name, menuConfig[0]);
    }
}

// 加载页面
function loadPage(url, title, menuItem = null) {
    // 保存当前菜单项
    currentMenuItem = menuItem;
    currentTabIndex = 0;

    // 检查菜单项是否有tabs配置
    if (menuItem && menuItem.tabs && menuItem.tabs.length > 0) {
        pageTabs.classList.remove('hide');
        title = "";
        // 如果菜单项没有配置url，使用第一个tab的url
        if (!url && menuItem.tabs[0]) {
            url = menuItem.tabs[0].url;
        }
        // 更新页面tabs
        updatePageTabs(menuItem);
    } else {
        // 清空tabs
        if (pageTabs) {
            pageTabs.innerHTML = '';
        }
        pageTabs.classList.add('hide');
    }

    // 更新页面标题
    pageTitle.textContent = title;

    // 加载 iframe
    contentFrame.src = url;

    // 更新浏览器历史记录
    history.pushState({ url, title, menuItemId: menuItem?.id, tabIndex: currentTabIndex }, title, `?page=${encodeURIComponent(url)}`);
}

// 更新页面Tabs
function updatePageTabs(menuItem) {
    if (!pageTabs || !menuItem || !menuItem.tabs || menuItem.tabs.length === 0) {
        if (pageTabs) {
            pageTabs.innerHTML = '';
        }
        return;
    }

    // 清空现有tabs
    pageTabs.innerHTML = '';

    // 生成新的tabs
    menuItem.tabs.forEach((tab, index) => {
        const tabElement = document.createElement('div');
        tabElement.className = `page-tab ${index === currentTabIndex ? 'active' : ''}`;
        tabElement.textContent = tab.name;
        tabElement.dataset.index = index;
        tabElement.dataset.url = tab.url;
        tabElement.dataset.title = tab.name;

        // 添加点击事件
        tabElement.addEventListener('click', function() {
            const index = parseInt(this.dataset.index);
            const url = this.dataset.url;
            const title = this.dataset.title;
            
            // 更新当前tab索引
            currentTabIndex = index;
            
            // 更新tab激活状态
            document.querySelectorAll('.page-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // 加载页面
            contentFrame.src = url;
            // tab组件已经有样式, 不需要展示标题
            pageTitle.textContent = "";
            
            // 更新浏览器历史记录
            history.pushState({ 
                url, 
                title, 
                menuItemId: menuItem.id, 
                tabIndex: currentTabIndex 
            }, title, `?page=${encodeURIComponent(url)}`);
        });

        pageTabs.appendChild(tabElement);
    });
}

// 更新激活的导航项
function updateActiveNavItem(activeItem) {
    // 移除所有激活状态
    document.querySelectorAll('.nav-item a').forEach(item => {
        item.classList.remove('active');
    });

    // 添加激活状态
    activeItem.classList.add('active');

    // 如果是子菜单项，展开其父菜单
    const subMenu = activeItem.closest('.sub-menu');
    if (subMenu) {
        subMenu.classList.add('open');
    }
}

// 处理浏览器历史记录导航
window.addEventListener('popstate', function (e) {
    if (e.state) {
        loadPage(e.state.url, e.state.title);

        // 找到对应的导航项并激活
        document.querySelectorAll('.nav-item a').forEach(item => {
            if (item.dataset.url === e.state.url) {
                updateActiveNavItem(item);
            }
        });
    }
});

// 初始化
window.addEventListener('DOMContentLoaded', init);