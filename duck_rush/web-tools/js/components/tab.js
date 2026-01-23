/**
 * Tab组件
 * 支持通过HTML结构和JavaScript API两种方式创建和管理tab
 * 支持动画效果、事件监听、自定义样式等功能
 */
class Tab {
    /**
     * 构造函数
     * @param {string|HTMLElement} container - tab容器元素或选择器
     * @param {Object} options - 配置选项
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        if (!this.container) {
            throw new Error('Tab container not found');
        }

        // 默认配置
        this.options = {
            activeClass: 'active',
            tabClass: 'tab-item',
            contentClass: 'tab-content',
            animate: true,
            defaultIndex: 0,
            ...options
        };

        // 初始化
        this.tabs = [];
        this.contents = [];
        this.activeIndex = -1;
        this.events = new Map();

        this.init();
    }

    /**
     * 初始化tab组件
     */
    init() {
        // 从HTML结构中解析tab
        this.parseFromHTML();

        // 绑定事件
        this.bindEvents();

        // 设置默认激活项
        if (this.tabs.length > 0 && this.options.defaultIndex >= 0) {
            this.activate(this.options.defaultIndex);
        }
    }

    /**
     * 从HTML结构中解析tab
     */
    parseFromHTML() {
        // 查找所有tab项
        const tabElements = this.container.querySelectorAll(`.${this.options.tabClass}`);
        const contentElements = this.container.querySelectorAll(`.${this.options.contentClass}`);

        tabElements.forEach((tab, index) => {
            this.tabs.push(tab);
            if (contentElements[index]) {
                this.contents.push(contentElements[index]);
                // 隐藏所有内容
                this.hideContent(contentElements[index]);
            }
        });
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        this.tabs.forEach((tab, index) => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.activate(index);
            });
        });
    }

    /**
     * 激活指定索引的tab
     * @param {number} index - tab索引
     */
    activate(index) {
        if (index < 0 || index >= this.tabs.length || index === this.activeIndex) {
            return;
        }

        // 取消之前激活的tab
        if (this.activeIndex >= 0) {
            this.deactivate(this.activeIndex);
        }

        // 激活新的tab
        const tab = this.tabs[index];
        const content = this.contents[index];

        tab.classList.add(this.options.activeClass);
        this.activeIndex = index;

        // 显示内容
        if (content) {
            this.showContent(content);
        }

        // 触发事件
        this.trigger('change', {
            index,
            tab,
            content
        });
    }

    /**
     * 取消激活指定索引的tab
     * @param {number} index - tab索引
     */
    deactivate(index) {
        const tab = this.tabs[index];
        const content = this.contents[index];

        if (tab) {
            tab.classList.remove(this.options.activeClass);
        }

        if (content) {
            this.hideContent(content);
        }
    }

    /**
     * 显示内容
     * @param {HTMLElement} content - 内容元素
     */
    showContent(content) {
        if (this.options.animate) {
            content.style.display = 'block';
            content.style.opacity = '0';
            content.style.transition = 'opacity 0.3s ease';
            
            setTimeout(() => {
                content.style.opacity = '1';
            }, 10);
        } else {
            content.style.display = 'block';
        }
    }

    /**
     * 隐藏内容
     * @param {HTMLElement} content - 内容元素
     */
    hideContent(content) {
        if (this.options.animate) {
            content.style.opacity = '0';
            content.style.transition = 'opacity 0.3s ease';
            
            setTimeout(() => {
                content.style.display = 'none';
            }, 300);
        } else {
            content.style.display = 'none';
        }
    }

    /**
     * 添加tab
     * @param {string} title - tab标题
     * @param {string|HTMLElement} content - tab内容
     * @param {number} index - 添加位置，默认添加到末尾
     * @returns {number} - 新添加的tab索引
     */
    addTab(title, content, index = -1) {
        if (index < 0 || index > this.tabs.length) {
            index = this.tabs.length;
        }

        // 创建tab元素
        const tab = document.createElement('div');
        tab.className = this.options.tabClass;
        tab.textContent = title;

        // 创建内容元素
        const contentElement = document.createElement('div');
        contentElement.className = this.options.contentClass;
        
        if (typeof content === 'string') {
            contentElement.innerHTML = content;
        } else if (content instanceof HTMLElement) {
            contentElement.appendChild(content);
        }

        // 插入到指定位置
        if (index === this.tabs.length) {
            // 添加到末尾
            this.container.appendChild(tab);
            this.container.appendChild(contentElement);
        } else {
            // 插入到指定位置
            const referenceTab = this.tabs[index];
            referenceTab.parentNode.insertBefore(tab, referenceTab);
            
            const referenceContent = this.contents[index];
            referenceContent.parentNode.insertBefore(contentElement, referenceContent);
        }

        // 更新数组
        this.tabs.splice(index, 0, tab);
        this.contents.splice(index, 0, contentElement);

        // 绑定事件
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            this.activate(index);
        });

        // 隐藏新内容
        this.hideContent(contentElement);

        // 触发事件
        this.trigger('add', {
            index,
            tab,
            content: contentElement
        });

        return index;
    }

    /**
     * 删除tab
     * @param {number} index - 要删除的tab索引
     */
    removeTab(index) {
        if (index < 0 || index >= this.tabs.length) {
            return;
        }

        const tab = this.tabs[index];
        const content = this.contents[index];

        // 如果删除的是激活的tab，激活前一个或第一个tab
        if (index === this.activeIndex) {
            this.deactivate(index);
            if (this.tabs.length > 1) {
                const newActiveIndex = index > 0 ? index - 1 : 0;
                this.activate(newActiveIndex);
            } else {
                this.activeIndex = -1;
            }
        } else if (index < this.activeIndex) {
            // 如果删除的tab在激活tab之前，更新激活索引
            this.activeIndex--;
        }

        // 移除元素
        if (tab && tab.parentNode) {
            tab.parentNode.removeChild(tab);
        }
        if (content && content.parentNode) {
            content.parentNode.removeChild(content);
        }

        // 更新数组
        this.tabs.splice(index, 1);
        this.contents.splice(index, 1);

        // 触发事件
        this.trigger('remove', {
            index,
            tab,
            content
        });
    }

    /**
     * 获取当前激活的tab索引
     * @returns {number} - 当前激活的tab索引
     */
    getActiveIndex() {
        return this.activeIndex;
    }

    /**
     * 设置当前激活的tab索引
     * @param {number} index - 要激活的tab索引
     */
    setActiveIndex(index) {
        this.activate(index);
    }

    /**
     * 获取tab数量
     * @returns {number} - tab数量
     */
    getTabCount() {
        return this.tabs.length;
    }

    /**
     * 获取指定索引的tab元素
     * @param {number} index - tab索引
     * @returns {HTMLElement|null} - tab元素
     */
    getTab(index) {
        return this.tabs[index] || null;
    }

    /**
     * 获取指定索引的内容元素
     * @param {number} index - tab索引
     * @returns {HTMLElement|null} - 内容元素
     */
    getContent(index) {
        return this.contents[index] || null;
    }

    /**
     * 清空所有tab
     */
    clear() {
        // 移除所有元素
        this.tabs.forEach(tab => {
            if (tab.parentNode) {
                tab.parentNode.removeChild(tab);
            }
        });

        this.contents.forEach(content => {
            if (content.parentNode) {
                content.parentNode.removeChild(content);
            }
        });

        // 重置状态
        this.tabs = [];
        this.contents = [];
        this.activeIndex = -1;

        // 触发事件
        this.trigger('clear');
    }

    /**
     * 事件监听
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    on(event, callback) {
        if (!this.events.has(event)) {
            this.events.set(event, []);
        }
        this.events.get(event).push(callback);
    }

    /**
     * 移除事件监听
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数，不指定则移除所有该事件的监听器
     */
    off(event, callback) {
        if (!this.events.has(event)) {
            return;
        }

        if (callback) {
            const callbacks = this.events.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        } else {
            this.events.delete(event);
        }
    }

    /**
     * 触发事件
     * @param {string} event - 事件名称
     * @param {Object} data - 事件数据
     */
    trigger(event, data = {}) {
        if (!this.events.has(event)) {
            return;
        }

        const callbacks = this.events.get(event);
        callbacks.forEach(callback => {
            callback.call(this, {
                type: event,
                target: this,
                ...data
            });
        });
    }

    /**
     * 销毁组件
     */
    destroy() {
        // 移除事件监听
        this.events.clear();

        // 移除元素事件
        this.tabs.forEach(tab => {
            // 移除所有事件监听器
            const clone = tab.cloneNode(true);
            tab.parentNode.replaceChild(clone, tab);
        });

        // 清空引用
        this.tabs = [];
        this.contents = [];
        this.container = null;
        this.events = null;
    }
}

/**
 * 静态方法：创建tab实例
 * @param {string|HTMLElement} container - tab容器元素或选择器
 * @param {Object} options - 配置选项
 * @returns {Tab} - tab实例
 */
Tab.create = function(container, options = {}) {
    return new Tab(container, options);
};

/**
 * 静态方法：初始化所有带有data-tab属性的元素
 */
Tab.initAll = function() {
    const containers = document.querySelectorAll('[data-tab]');
    const instances = [];

    containers.forEach(container => {
        const options = JSON.parse(container.dataset.tabOptions || '{}');
        const instance = new Tab(container, options);
        instances.push(instance);
        
        // 存储实例到容器元素
        container._tabInstance = instance;
    });

    return instances;
};

// 导出组件
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Tab;
} else if (typeof window !== 'undefined') {
    window.Tab = Tab;
}

// 自动初始化
if (typeof window !== 'undefined' && document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Tab.initAll);
} else if (typeof window !== 'undefined' && document.readyState === 'interactive') {
    Tab.initAll();
}
