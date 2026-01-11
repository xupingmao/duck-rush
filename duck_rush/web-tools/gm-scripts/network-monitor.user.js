// ==UserScript==
// @name         网络监控
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  模仿浏览器开发者工具监控网络请求
// @author       xupingmao
// @match        *://*/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 网络请求数据
    let networkData = [];
    // 过滤后的网络请求数据
    let filteredData = [];
    // 采集开关状态
    let isCapturing = false;
    // 面板展开状态
    let isPanelExpanded = false;
    // 过滤关键字
    let filterKeyword = '';
    // 请求编号计数器
    let requestCounter = 0;
    // 原始fetch
    let originalFetch = window.fetch;

    // 加载持久化状态
    function loadPersistentState() {
        try {
            const savedState = localStorage.getItem('networkMonitorState');
            if (savedState) {
                const state = JSON.parse(savedState);
                isCapturing = state.isCapturing || false;
                isPanelExpanded = state.isPanelExpanded || false;
                console.log('加载持久化状态:', { isCapturing, isPanelExpanded });
            }
        } catch (e) {
            console.error('加载持久化状态失败:', e);
        }
    }

    // 保存持久化状态
    function savePersistentState() {
        try {
            const state = {
                isCapturing: isCapturing,
                isPanelExpanded: isPanelExpanded
            };
            localStorage.setItem('networkMonitorState', JSON.stringify(state));
            console.log('保存持久化状态:', { isCapturing, isPanelExpanded });
        } catch (e) {
            console.error('保存持久化状态失败:', e);
        }
    }

    // 加载持久化状态
    loadPersistentState();

    // 立即替换系统函数，确保在页面加载前生效
    replaceSystemFunctions();

    // 替换系统函数
    function replaceSystemFunctions() {
        // 保存原始方法
        const originalOpen = XMLHttpRequest.prototype.open;
        const originalSend = XMLHttpRequest.prototype.send;
        const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

        // 重写XMLHttpRequest.prototype.open方法
        XMLHttpRequest.prototype.open = function(method, url, ...args) {
            if (isCapturing) {
                const xhr = this;
                const startTime = Date.now();
                const requestData = {
                    method: method,
                    url: url,
                    startTime: startTime,
                    requestHeaders: {},
                    requestBody: null,
                    responseHeaders: {},
                    responseBody: null,
                    status: 0,
                    statusText: '',
                    endTime: 0,
                    duration: 0,
                    type: 'XHR' // 标记请求类型为XHR
                };

                // 监听请求头
                xhr.setRequestHeader = function(header, value) {
                    requestData.requestHeaders[header] = value;
                    return originalSetRequestHeader.apply(this, arguments);
                };

                // 监听请求发送
                xhr.send = function(body) {
                    console.log('XMLHttpRequest.send:', body, requestData);

                    try {
                        requestData.requestBody = body;
                        requestData.readyState = xhr.readyState;
                        addRequest(requestData);
                        const result = originalSend.apply(this, arguments);
                        console.log('XMLHttpRequest.send result:', result);
                        return result;
                    } catch (e) {
                        console.error('XMLHttpRequest.send error:', e);
                        throw e;
                    }
                };

                // 保存当前的requestData引用
                const currentRequestData = requestData;

                // 保存原始的事件处理方法
                let originalOnError = xhr.onerror;
                let originalOnReadyStateChange = xhr.onreadystatechange;

                // 定义onreadystatechange的getter和setter，确保后续设置也能被监控
                Object.defineProperty(xhr, 'onreadystatechange', {
                    get: function() {
                        return originalOnReadyStateChange;
                    },
                    set: function(callback) {
                        originalOnReadyStateChange = callback;
                        // 重新设置包装后的回调
                        const wrappedCallback = function() {
                            console.log('XMLHttpRequest.response:', this.response);
                            // 先调用原始的回调
                            if (typeof originalOnReadyStateChange === 'function') {
                                originalOnReadyStateChange.apply(this, arguments);
                            }

                            // 只在请求完成时更新
                            if (this.readyState === 4) {
                                // 通过url、method和startTime查找请求
                                const requestIndex = networkData.findIndex(req =>
                                    req.url === currentRequestData.url &&
                                    req.method === currentRequestData.method &&
                                    req.startTime === currentRequestData.startTime
                                );
                                if (requestIndex !== -1) {
                                    const requestToUpdate = networkData[requestIndex];
                                    // 更新请求信息
                                    requestToUpdate.readyState = this.readyState;
                                    requestToUpdate.status = this.status;
                                    requestToUpdate.statusText = this.statusText;
                                    requestToUpdate.responseHeaders = parseHeaders(this.getAllResponseHeaders());

                                    console.log('XMLHttpRequest.response:', this.response);

                                    // 根据responseType处理响应
                                    try {
                                        if (this.responseType === 'json' && this.response) {
                                            // 对于JSON响应，使用response属性并转换为字符串
                                            requestToUpdate.responseBody = JSON.stringify(this.response);
                                        } else if (this.responseType === 'text' || this.responseType === '' || this.responseType === 'document') {
                                            // 对于文本、空或文档响应，使用responseText
                                            requestToUpdate.responseBody = this.responseText || '';
                                        } else if (this.response) {
                                            // 对于其他类型的响应，尝试转换为字符串
                                            requestToUpdate.responseBody = String(this.response);
                                        } else {
                                            // 兜底处理
                                            requestToUpdate.responseBody = this.responseText || '';
                                        }
                                    } catch (e) {
                                        // 处理异常，确保监控不会影响原网页功能
                                        requestToUpdate.responseBody = this.responseText || '';
                                    }

                                    requestToUpdate.endTime = Date.now();
                                    requestToUpdate.duration = requestToUpdate.endTime - requestToUpdate.startTime;
                                    applyFilter();
                                }
                            }
                        };
                        // 调用原始的setter，确保浏览器开发者工具能正确显示
                        Object.getOwnPropertyDescriptor(Object.getPrototypeOf(xhr), 'onreadystatechange').set.call(xhr, wrappedCallback);
                    },
                    enumerable: true,
                    configurable: true
                });
            }
            const result = originalOpen.apply(this, arguments);
            console.log('XMLHttpRequest.open:', method, url, ...args);
            console.log('XMLHttpRequest.open result:', result);
            return result;
        };

        // 重写fetch
        window.fetch = function(url, options = {}) {
            if (isCapturing) {
                const startTime = Date.now();
                const requestData = {
                    method: options.method || 'GET',
                    url: url,
                    startTime: startTime,
                    requestHeaders: options.headers || {},
                    requestBody: options.body || null,
                    responseHeaders: {},
                    responseBody: null,
                    status: 0,
                    statusText: '',
                    endTime: 0,
                    duration: 0,
                    type: 'Fetch' // 标记请求类型为Fetch
                };

                return originalFetch(url, options)
                    .then(response => {
                        // 克隆响应以读取内容
                        const clonedResponse = response.clone();

                        requestData.status = response.status;
                        requestData.statusText = response.statusText;
                        requestData.responseHeaders = Object.fromEntries(response.headers.entries());

                        return clonedResponse.text()
                            .then(text => {
                                requestData.responseBody = text;
                                requestData.endTime = Date.now();
                                requestData.duration = requestData.endTime - requestData.startTime;
                                addRequest(requestData);
                                return response;
                            });
                    })
                    .catch(error => {
                        requestData.responseBody = error.message;
                        requestData.endTime = Date.now();
                        requestData.duration = requestData.endTime - requestData.startTime;
                        addRequest(requestData);
                        throw error;
                    });
            }
            return originalFetch(url, options);
        };
    }

    // 创建监控面板
    function createMonitorPanel() {
        // 主面板
        const panel = document.createElement('div');
        panel.id = 'network-monitor-panel';
        panel.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #2d2d2d;
            color: #e0e0e0;
            font-family: monospace;
            font-size: 12px;
            z-index: 9999;
            border-top: 1px solid #444;
            transition: height 0.3s ease;
        `;

        // 面板头部（始终显示）
        const panelHeader = document.createElement('div');
        panelHeader.id = 'network-monitor-header';
        panelHeader.style.cssText = `
            padding: 8px 12px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #333;
            border-bottom: 1px solid #444;
            position: relative;
        `;

        // 添加高度调整手柄（放在面板上方）
        const resizeHandle = document.createElement('div');
        resizeHandle.id = 'network-monitor-resize';
        resizeHandle.style.cssText = `
            position: absolute;
            top: -4px;
            left: 0;
            right: 0;
            height: 4px;
            background: #ccc;
            cursor: ns-resize;
            z-index: 10;
            border-radius: 2px 2px 0 0;
            box-shadow: 0 1px 3px rgba(255,100,0,0.3);
        `;
        panel.appendChild(resizeHandle);

        // 实现高度调整功能（优化版本）
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;
        let animationFrameId = null;
        let lastUpdateTime = 0;
        const THROTTLE_DELAY = 16; // 约60fps

        // 节流函数，限制函数执行频率
        function throttle(func, delay) {
            let lastCall = 0;
            return function(...args) {
                const now = Date.now();
                if (now - lastCall >= delay) {
                    lastCall = now;
                    return func.apply(this, args);
                }
            };
        }

        // 使用requestAnimationFrame优化的高度更新函数
        function updatePanelHeightOptimized(e) {
            if (!isResizing) return;

            // 计算新高度
            const deltaY = startY - e.clientY;
            const newHeight = Math.max(100, startHeight + deltaY);

            // 直接更新高度，使用requestAnimationFrame可能会导致延迟感
            // 对于拖拽操作，直接更新通常感觉更响应
            panel.style.height = `${newHeight}px`;

            // 确保内容区域显示
            if (isPanelExpanded) {
                const contentElement = document.getElementById('network-monitor-content');
                if (contentElement) {
                    contentElement.style.display = 'block';
                }
            }
        }

        // 节流处理的鼠标移动事件
        const throttledMouseMove = throttle(updatePanelHeightOptimized, THROTTLE_DELAY);

        resizeHandle.addEventListener('mousedown', function(e) {
            e.preventDefault(); // 防止默认行为
            isResizing = true;
            startY = e.clientY;
            startHeight = panel.offsetHeight;
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'ns-resize';
        });

        document.addEventListener('mousemove', function(e) {
            if (isResizing) {
                e.preventDefault(); // 防止默认行为
                // 使用节流处理的函数
                throttledMouseMove(e);
            }
        });

        document.addEventListener('mouseup', function() {
            if (isResizing) {
                isResizing = false;
                document.body.style.userSelect = '';
                document.body.style.cursor = '';
                // 取消可能的动画帧
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
            }
        });

        // 头部左侧（标题和展开/折叠按钮）
        const headerLeft = document.createElement('div');
        headerLeft.style.cssText = 'display: flex; align-items: center; gap: 12px;';

        // 头部标题
        const headerTitle = document.createElement('div');
        headerTitle.textContent = '网络监控';

        // 展开/折叠按钮
        const toggleButton = document.createElement('button');
        toggleButton.id = 'network-monitor-expand-btn';
        toggleButton.textContent = '展开';
        toggleButton.style.cssText = `
            padding: 2px 6px;
            border: none;
            border-radius: 3px;
            background: #555;
            color: #fff;
            cursor: pointer;
            font-size: 10px;
        `;

        // 控制按钮
        const controlButtons = document.createElement('div');
        controlButtons.style.cssText = 'display: flex; gap: 8px; align-items: center;';

        // 过滤输入框
        const filterInput = document.createElement('input');
        filterInput.id = 'network-monitor-filter';
        filterInput.type = 'text';
        filterInput.placeholder = '过滤请求...';
        filterInput.style.cssText = `
            padding: 4px 8px;
            border: 1px solid #555;
            border-radius: 3px;
            background: #444;
            color: #fff;
            font-size: 10px;
            width: 150px;
        `;

        // 采集开关
        const captureToggle = document.createElement('button');
        captureToggle.id = 'network-monitor-toggle';
        captureToggle.textContent = isCapturing ? '停止采集' : '开始采集';
        captureToggle.style.cssText = `
            padding: 4px 8px;
            border: none;
            border-radius: 3px;
            background: ${isCapturing ? '#d9534f' : '#666'};
            color: #fff;
            cursor: pointer;
            font-size: 10px;
        `;

        // 清空按钮
        const clearButton = document.createElement('button');
        clearButton.textContent = '清空';
        clearButton.style.cssText = `
            padding: 4px 8px;
            border: none;
            border-radius: 3px;
            background: #666;
            color: #fff;
            cursor: pointer;
            font-size: 10px;
        `;

        // 面板内容
        const panelContent = document.createElement('div');
        panelContent.id = 'network-monitor-content';
        panelContent.style.cssText = `
            padding: 12px;
            max-height: 400px;
            overflow-y: auto;
            display: none;
        `;

        // 请求列表
        const requestList = document.createElement('div');
        requestList.id = 'network-request-list';

        // 组装面板
        headerLeft.appendChild(headerTitle);
        headerLeft.appendChild(toggleButton);
        controlButtons.appendChild(filterInput);
        controlButtons.appendChild(captureToggle);
        controlButtons.appendChild(clearButton);
        panelHeader.appendChild(headerLeft);
        panelHeader.appendChild(controlButtons);

        panelContent.appendChild(requestList);

        panel.appendChild(panelHeader);
        panel.appendChild(panelContent);

        // 添加到页面
        document.body.appendChild(panel);

        // 绑定事件
        // 移除面板头部点击展开/折叠功能，避免影响拖拽
        // panelHeader.addEventListener('click', function(e) {
        //     if (!e.target.closest('button') && !e.target.closest('input')) {
        //         togglePanel();
        //     }
        // });
        toggleButton.addEventListener('click', togglePanel);
        captureToggle.addEventListener('click', toggleCapture);
        clearButton.addEventListener('click', clearData);
        filterInput.addEventListener('input', function(e) {
            filterKeyword = e.target.value;
            console.log('过滤关键字:', filterKeyword);
            applyFilter();
        });

        // 初始化面板高度
        updatePanelHeight();
    }

    // 切换面板展开状态
    function togglePanel() {
        isPanelExpanded = !isPanelExpanded;
        updatePanelHeight();
        // 保存持久化状态
        savePersistentState();
    }

    // 更新面板高度
    function updatePanelHeight() {
        const panel = document.getElementById('network-monitor-panel');
        const content = document.getElementById('network-monitor-content');
        const toggleButton = document.getElementById('network-monitor-expand-btn');

        if (isPanelExpanded) {
            panel.style.height = '400px';
            content.style.display = 'block';
            toggleButton.textContent = '折叠';
        } else {
            panel.style.height = 'auto';
            content.style.display = 'none';
            toggleButton.textContent = '展开';
        }
    }

    // 切换采集状态
    function toggleCapture() {
        isCapturing = !isCapturing;
        const toggle = document.getElementById('network-monitor-toggle');

        if (isCapturing) {
            toggle.textContent = '停止采集';
            toggle.style.background = '#d9534f';
        } else {
            toggle.textContent = '开始采集';
            toggle.style.background = '#666';
        }

        // 保存持久化状态
        savePersistentState();
    }

    // 解析响应头
    function parseHeaders(headersStr) {
        const headers = {};
        if (!headersStr) return headers;

        headersStr.split('\r\n').forEach(line => {
            const parts = line.split(': ');
            if (parts.length >= 2) {
                headers[parts[0]] = parts.slice(1).join(': ');
            }
        });
        return headers;
    }

    // 应用过滤
    function applyFilter() {
        console.log('应用过滤，关键字:', filterKeyword);
        if (!filterKeyword) {
            filteredData = [...networkData];
        } else {
            const keyword = filterKeyword.toLowerCase();
            filteredData = networkData.filter(request => {
                return (
                    request.url.toLowerCase().includes(keyword) ||
                    request.method.toLowerCase().includes(keyword) ||
                    (request.requestBody && typeof request.requestBody === 'string' && request.requestBody.toLowerCase().includes(keyword)) ||
                    (request.responseBody && typeof request.responseBody === 'string' && request.responseBody.toLowerCase().includes(keyword))
                );
            });
        }
        console.log('过滤后的数据量:', filteredData.length);
        renderRequestList();
    }

    // 添加请求数据
    function addRequest(requestData) {
        // 为请求分配编号
        requestCounter++;
        requestData.id = requestCounter;
        // 将请求数据添加到数组开头
        networkData.unshift(requestData);
        // 应用过滤
        applyFilter();
        // 确保面板已创建
        if (document.getElementById('network-request-list')) {
            renderRequestList();
        }
        // 返回添加的请求对象引用
        return requestData;
    }

    // 截断URL
    function truncateUrl(url) {
        if (url.length > 100) {
            return url.substring(0, 100) + '...';
        }
        return url;
    }

    // 根据状态码获取颜色
    function getStatusCodeColor(status) {
        if (status >= 200 && status < 300) return '#5cb85c';
        if (status >= 300 && status < 400) return '#f0ad4e';
        if (status >= 400) return '#d9534f';
        return '#999';
    }

    // 渲染请求列表
    function renderRequestList() {
        const listContainer = document.getElementById('network-request-list');
        
        // 如果容器不存在，直接返回
        if (!listContainer) {
            return;
        }

        // 保存当前展开的详情面板ID
        const expandedPanelIds = [];
        document.querySelectorAll('[id^="detail-panel-"]').forEach(panel => {
            if (panel.style.display === 'block') {
                expandedPanelIds.push(panel.id);
            }
        });

        listContainer.innerHTML = '';

        if (filteredData.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.textContent = filterKeyword ? '没有匹配的请求' : '暂无采集到的请求';
            emptyMessage.style.cssText = 'padding: 12px; color: #999; text-align: center;';
            listContainer.appendChild(emptyMessage);
            return;
        }

        filteredData.forEach(request => {
            const requestItemWrapper = document.createElement('div');
            requestItemWrapper.style.cssText = `
                margin-bottom: 4px;
                border-radius: 3px;
                overflow: hidden;
            `;

            const requestItem = document.createElement('div');
            requestItem.style.cssText = `
                padding: 8px 12px;
                border: 1px solid #444;
                cursor: pointer;
                transition: background 0.2s ease;
                display: grid;
                grid-template-columns: 50px 60px 80px 1fr 100px 80px 80px;
                gap: 10px;
                align-items: center;
                background: #333;
                border-radius: 3px;
            `;

            requestItem.addEventListener('mouseenter', function() {
                this.style.background = '#3a3a3a';
            });

            requestItem.addEventListener('mouseleave', function() {
                this.style.background = '#333';
            });

            // 编号
            const id = document.createElement('div');
            id.textContent = request.id;
            id.style.cssText = 'font-weight: bold; color: #999; text-align: center;';

            // 请求类型
            const type = document.createElement('div');
            type.textContent = request.type || 'Unknown';
            type.style.cssText = 'font-weight: bold; color: #66a3ff; text-align: center; font-size: 10px;';

            // 方法
            const method = document.createElement('div');
            method.textContent = request.method;
            method.style.cssText = 'font-weight: bold;';

            // URL
            const url = document.createElement('div');
            url.textContent = truncateUrl(request.url);
            url.style.cssText = 'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';

            // 状态码
            const status = document.createElement('div');
            status.textContent = request.status;
            status.style.cssText = `
                font-weight: bold;
                color: ${getStatusCodeColor(request.status)};
            `;

            // 耗时
            const duration = document.createElement('div');
            duration.textContent = `${request.duration}ms`;
            duration.style.cssText = 'color: #999;';

            // 请求时间
            const time = document.createElement('div');
            const timeStr = new Date(request.startTime).toLocaleTimeString();
            time.textContent = timeStr;
            time.style.cssText = 'color: #999; font-size: 10px;';

            requestItem.appendChild(id);
            requestItem.appendChild(type);
            requestItem.appendChild(method);
            requestItem.appendChild(url);
            requestItem.appendChild(status);
            requestItem.appendChild(duration);
            requestItem.appendChild(time);

            // 创建详情面板
            const detailPanel = document.createElement('div');
            detailPanel.id = `detail-panel-${request.id}`;
            detailPanel.style.cssText = `
                padding: 12px;
                border: 1px solid #444;
                border-top: none;
                border-radius: 0 0 3px 3px;
                background: #2d2d2d;
                display: none;
            `;

            // 详情头部
            const detailHeader = document.createElement('div');
            detailHeader.style.cssText = `
                margin-bottom: 12px;
                font-weight: bold;
            `;
            detailHeader.textContent = `${request.method} ${request.url}`;

            // 详情内容
            const detailContent = document.createElement('div');
            detailContent.style.cssText = `
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            `;

            // 请求详情
            const requestDetail = document.createElement('div');
            requestDetail.style.cssText = `
                background: #222;
                padding: 8px;
                border-radius: 3px;
                max-height: 200px;
                overflow-y: auto;
            `;

            const requestTitle = document.createElement('div');
            requestTitle.textContent = '请求';
            requestTitle.style.cssText = `
                margin-bottom: 8px;
                font-weight: bold;
                color: #999;
            `;

            const requestBody = document.createElement('pre');
            requestBody.style.cssText = `
                margin: 0;
                white-space: pre-wrap;
                word-break: break-all;
                color: #e0e0e0;
            `;

            // 响应详情
            const responseDetail = document.createElement('div');
            responseDetail.style.cssText = `
                background: #222;
                padding: 8px;
                border-radius: 3px;
                max-height: 200px;
                overflow-y: auto;
            `;

            const responseTitle = document.createElement('div');
            responseTitle.textContent = '响应';
            responseTitle.style.cssText = `
                margin-bottom: 8px;
                font-weight: bold;
                color: #999;
            `;

            const responseBody = document.createElement('pre');
            responseBody.style.cssText = `
                margin: 0;
                white-space: pre-wrap;
                word-break: break-all;
                color: #e0e0e0;
            `;

            // 更新请求详情
            const requestInfo = {
                url: request.url,
                method: request.method,
                headers: request.requestHeaders,
                body: request.requestBody,
                readyState: request.readyState
            };
            requestBody.textContent = JSON.stringify(requestInfo, null, 2);

            // 更新响应详情
            const responseInfo = {
                status: request.status,
                statusText: request.statusText,
                headers: request.responseHeaders,
                body: request.responseBody
            };
            responseBody.textContent = JSON.stringify(responseInfo, null, 2);

            // 组装详情面板
            requestDetail.appendChild(requestTitle);
            requestDetail.appendChild(requestBody);
            responseDetail.appendChild(responseTitle);
            responseDetail.appendChild(responseBody);
            detailContent.appendChild(requestDetail);
            detailContent.appendChild(responseDetail);
            detailPanel.appendChild(detailHeader);
            detailPanel.appendChild(detailContent);

            // 绑定点击事件
            requestItem.addEventListener('click', function() {
                const isVisible = detailPanel.style.display === 'block';
                if (isVisible) {
                    detailPanel.style.display = 'none';
                } else {
                    // 先隐藏所有其他详情面板
                    document.querySelectorAll('[id^="detail-panel-"]').forEach(panel => {
                        panel.style.display = 'none';
                    });
                    // 显示当前详情面板
                    detailPanel.style.display = 'block';
                }
            });

            requestItemWrapper.appendChild(requestItem);
            requestItemWrapper.appendChild(detailPanel);
            listContainer.appendChild(requestItemWrapper);
        });

        // 恢复之前展开的详情面板
        expandedPanelIds.forEach(panelId => {
            const panel = document.getElementById(panelId);
            if (panel) {
                panel.style.display = 'block';
            }
        });
    }

    // 清空数据
    function clearData() {
        networkData = [];
        filteredData = [];
        filterKeyword = '';
        if (document.getElementById('network-monitor-filter')) {
            document.getElementById('network-monitor-filter').value = '';
        }
        if (document.getElementById('network-request-list')) {
            renderRequestList();
        }
    }

    // 初始化
    function init() {
        createMonitorPanel();
        // 初始化过滤数据
        filteredData = [...networkData];
        applyFilter();
    }

    // 页面加载完成后初始化面板
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();