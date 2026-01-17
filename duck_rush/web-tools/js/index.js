// DOM 元素
const navMenu = document.getElementById('navMenu');
const pageTitle = document.getElementById('pageTitle');
const contentFrame = document.getElementById('contentFrame');
const openNewWindowBtn = document.getElementById('openNewWindowBtn');

// 初始化函数
function init() {
    // 生成导航菜单
    generateNavMenu();
    
    // 添加导航事件监听器
    addNavEventListeners();
    
    // 加载默认页面
    loadCurrentPage();
    
    // 添加新Tab页打开功能
    if (openNewWindowBtn) {
        openNewWindowBtn.addEventListener('click', function() {
            const currentUrl = contentFrame.src;
            if (currentUrl) {
                window.open(currentUrl, '_blank');
            }
        });
    }
}

// 生成导航菜单
function generateNavMenu() {
    navMenu.innerHTML = '';
    
    menuConfig.forEach(item => {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.id = item.id;
        
        const a = document.createElement('a');
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
                
                childLi.appendChild(childA);
                subMenu.appendChild(childLi);
            });
            
            li.appendChild(subMenu);
            
            // 添加展开/折叠功能
            a.addEventListener('click', function(e) {
                e.preventDefault();
                const subMenu = this.nextElementSibling;
                const toggleIcon = this.querySelector('.toggle-icon');
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
            });
        } else {
            // 没有子菜单的菜单项，直接加载页面
            a.addEventListener('click', function(e) {
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

// 添加导航事件监听器
function addNavEventListeners() {
    // 为所有子菜单项添加点击事件
    const subMenuItems = document.querySelectorAll('.sub-menu .nav-item a');
    subMenuItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.dataset.url;
            const title = this.dataset.title;
            loadPage(url, title);
            updateActiveNavItem(this);
        });
    });
}

function loadCurrentPage() {
    // 获取当前URL参数
    const params = new URLSearchParams(window.location.search);
    const currentUrl = params.get('page');
    
    if (currentUrl) {
        // 找到对应的导航项并激活
        document.querySelectorAll('.nav-item a').forEach(item => {
            if (item.dataset.url === currentUrl) {
                updateActiveNavItem(item);
                loadPage(currentUrl, item.dataset.title);
            }
        });
    } else {
        // 如果没有指定页面，加载默认页面
        loadPage(menuConfig[0].url, menuConfig[0].name);
    }
}

// 加载页面
function loadPage(url, title) {
    // 更新页面标题
    pageTitle.textContent = title;
    
    // 加载 iframe
    contentFrame.src = url;
    
    // 更新浏览器历史记录
    history.pushState({ url, title }, title, `?page=${encodeURIComponent(url)}`);
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
window.addEventListener('popstate', function(e) {
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