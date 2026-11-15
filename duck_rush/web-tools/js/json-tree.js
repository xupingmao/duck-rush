/**
 * json-tree.js — 把格式化后的 JSON 文本渲染成可展开 / 折叠的树
 *
 * 与 json.html 的分工：
 *   - buildBlocks(text) 把「格式化结果」拆成若干块：非 JSON 文本原样保留，
 *     JSON 片段解析成树节点（复用 JSONInt64 保证 int64 不丢精度）。
 *   - 折叠状态保存在节点模型上（node.collapsed），提供全部展开 / 全部折叠 /
 *     按层级折叠 / 折叠路径保存与恢复等纯逻辑 API，便于 Node 下单测。
 *   - renderBlocks(blocks, container) 负责 DOM 渲染与点击交互，采用事件委托，
 *     整棵树只有一个 click 监听器，大 JSON 也不会挂几千个回调。
 *
 * 暴露方式：
 *   浏览器：window.JSONTree = { ... }
 *   Node  ：module.exports = { ... }
 */
(function (global) {
    'use strict';

    // 浏览器中由 json-int64.js / json.js 注入全局；Node 下回退到 require
    var JSONInt64 = (global && global.JSONInt64)
        || (typeof require !== 'undefined' ? require('./json-int64.js') : null);
    var extractAllJSONFromText = (global && global.extractAllJSONFromText)
        || (typeof require !== 'undefined' ? require('./json.js') : null);

    /** 判断 JSON 值的展示类型（BigInt 与 number 同样按数字着色） */
    function kindOf(value) {
        if (value === null) return 'null';
        if (Array.isArray(value)) return 'array';
        var t = typeof value;
        if (t === 'object') return 'object';
        if (t === 'bigint') return 'number';
        return t; // string / number / boolean
    }

    function isContainer(node) {
        return node.kind === 'object' || node.kind === 'array';
    }

    /** 对象键的 JSONPath 片段：合法标识符用 .name，其余用 ["..."] */
    function pathForKey(key) {
        if (/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(String(key))) {
            return '.' + key;
        }
        return '[' + JSONInt64.stringify(String(key)) + ']';
    }

    /**
     * 构造节点。key 为 null 表示根节点；数组元素用数字下标。
     * path 形如 $.data.users[0].name，depth 从根节点的 0 开始。
     */
    function createNode(key, value, path, depth, hasComma) {
        var kind = kindOf(value);
        var node = {
            key: key,
            path: path,
            depth: depth,
            kind: kind,
            value: value,
            children: [],
            collapsed: false,
            comma: !!hasComma
        };

        if (kind === 'array') {
            for (var i = 0; i < value.length; i++) {
                node.children.push(createNode(
                    i, value[i], path + '[' + i + ']', depth + 1, i < value.length - 1
                ));
            }
        } else if (kind === 'object') {
            var keys = Object.keys(value);
            for (var k = 0; k < keys.length; k++) {
                var childKey = keys[k];
                node.children.push(createNode(
                    childKey, value[childKey], path + pathForKey(childKey),
                    depth + 1, k < keys.length - 1
                ));
            }
        }
        return node;
    }

    /** 合并相邻的文本块，避免渲染出一堆零碎的空行 */
    function pushText(blocks, text) {
        if (!text) return;
        var last = blocks[blocks.length - 1];
        if (last && last.type === 'text') {
            last.text += text;
        } else {
            blocks.push({ type: 'text', text: text });
        }
    }

    /**
     * 把格式化文本拆成 [{type:'text'}, {type:'json', node}] 块。
     * 解析失败的片段按纯文本保留，不会让整页渲染中断。
     */
    function buildBlocks(text) {
        var blocks = [];
        if (typeof text !== 'string' || text === '') return blocks;

        var matches = extractAllJSONFromText(text);
        var cursor = 0;
        matches.forEach(function (m) {
            if (m.start > cursor) pushText(blocks, text.slice(cursor, m.start));
            var parsed = null;
            var ok = true;
            try {
                parsed = JSONInt64.parse(m.json);
            } catch (e) {
                ok = false;
            }
            if (ok) {
                blocks.push({
                    type: 'json',
                    raw: m.json,
                    node: createNode(null, parsed, '$', 0, false)
                });
            } else {
                pushText(blocks, m.json);
            }
            cursor = m.end + 1;
        });
        if (cursor < text.length) pushText(blocks, text.slice(cursor));
        return blocks;
    }

    /** 深度优先遍历所有节点（含根） */
    function walkNodes(node, fn) {
        fn(node);
        node.children.forEach(function (child) { walkNodes(child, fn); });
    }

    function walkBlocks(blocks, fn) {
        blocks.forEach(function (block) {
            if (block.type === 'json') walkNodes(block.node, fn);
        });
    }

    /** 统计节点总数与可折叠的容器数量，用于状态栏提示 */
    function countNodes(blocks) {
        var total = 0;
        var containers = 0;
        walkBlocks(blocks, function (node) {
            total++;
            if (isContainer(node) && node.children.length > 0) containers++;
        });
        return { total: total, containers: containers };
    }

    function setAllCollapsed(blocks, collapsed) {
        walkBlocks(blocks, function (node) {
            if (isContainer(node)) node.collapsed = !!collapsed;
        });
    }

    /**
     * 展开到指定层数：visibleLevels=1 时只展开根节点（显示顶层键），
     * 更深的容器一律折叠。传 Infinity 等价于全部展开。
     */
    function collapseToDepth(blocks, visibleLevels) {
        var levels = Number(visibleLevels);
        if (levels === Infinity) {
            setAllCollapsed(blocks, false);
            return;
        }
        if (!isFinite(levels) || levels < 1) levels = 1;
        walkBlocks(blocks, function (node) {
            if (isContainer(node)) node.collapsed = node.depth >= levels;
        });
    }

    /** 折叠路径带块序号，多个 JSON 片段之间不会串状态 */
    function getCollapsedPaths(blocks) {
        var paths = [];
        blocks.forEach(function (block, index) {
            if (block.type !== 'json') return;
            walkNodes(block.node, function (node) {
                if (node.collapsed) paths.push(index + '|' + node.path);
            });
        });
        return paths;
    }

    function restoreCollapsedPaths(blocks, paths) {
        var wanted = {};
        (paths || []).forEach(function (p) { wanted[p] = true; });
        blocks.forEach(function (block, index) {
            if (block.type !== 'json') return;
            walkNodes(block.node, function (node) {
                node.collapsed = isContainer(node) && !!wanted[index + '|' + node.path];
            });
        });
    }

    /** 叶子节点的展示文本（字符串带引号与转义，BigInt 输出纯整数字面量） */
    function formatLeaf(value) {
        var out = JSONInt64.stringify(value);
        return out === undefined ? String(value) : out;
    }

    // ---------- 以下为 DOM 渲染部分，Node 单测不会调用 ----------

    function elem(doc, tag, className, text) {
        var el = doc.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined && text !== null) el.textContent = text;
        return el;
    }

    function renderLeaf(row, node, doc) {
        row.appendChild(elem(doc, 'span', 'json-value json-value-' + node.kind,
            formatLeaf(node.value)));
    }

    function renderContainer(wrap, row, node, doc, nodeMap) {
        var isArray = node.kind === 'array';
        var open = isArray ? '[' : '{';
        var close = isArray ? ']' : '}';
        var hasChildren = node.children.length > 0;

        row.appendChild(elem(doc, 'span', 'json-bracket', open));

        if (hasChildren) {
            // 折叠时行内补上闭合括号与数量提示；展开时这些信息隐藏，由结尾行显示
            var count = node.children.length;
            var label = isArray ? count + ' 项' : count + ' 个键';
            row.appendChild(elem(doc, 'span', 'json-summary', ' … ' + label + ' '));
            row.appendChild(elem(doc, 'span', 'json-inline-close', close));

            var children = elem(doc, 'div', 'json-children');
            node.children.forEach(function (child) {
                children.appendChild(renderNode(child, doc, nodeMap));
            });
            wrap.appendChild(children);

            var closeRow = elem(doc, 'div', 'json-row json-close-row');
            // 结尾行占位，使括号与开头的三角对齐
            closeRow.appendChild(elem(doc, 'span', 'json-toggle-space'));
            closeRow.appendChild(elem(doc, 'span', 'json-bracket', close));
            if (node.comma) closeRow.appendChild(elem(doc, 'span', 'json-comma', ','));
            wrap.appendChild(closeRow);
        } else {
            // 空对象 / 空数组不需要折叠，直接 {} 或 [] 一行显示完
            row.appendChild(elem(doc, 'span', 'json-bracket', close));
        }
    }

    function renderNode(node, doc, nodeMap) {
        var containerNode = isContainer(node);
        var foldable = containerNode && node.children.length > 0;
        var wrap = elem(doc, 'div', 'json-node');
        if (containerNode) wrap.classList.add('json-container');
        if (foldable && node.collapsed) wrap.classList.add('collapsed');
        if (node.key === null) wrap.classList.add('json-root');

        var id = String(nodeMap.next++);
        wrap.setAttribute('data-node-id', id);
        nodeMap.nodes[id] = node;

        var row = elem(doc, 'div', 'json-row');
        wrap.appendChild(row);

        if (foldable) {
            var toggle = elem(doc, 'button', 'json-toggle',
                node.collapsed ? '▸' : '▾');
            toggle.type = 'button';
            toggle.title = '折叠 / 展开节点';
            toggle.setAttribute('aria-expanded', node.collapsed ? 'false' : 'true');
            toggle.setAttribute('aria-label', toggle.title);
            row.appendChild(toggle);
        } else {
            row.appendChild(elem(doc, 'span', 'json-toggle-space'));
        }

        if (node.key !== null) {
            var keyClass = typeof node.key === 'number' ? 'json-index' : 'json-key';
            var keyText = typeof node.key === 'number'
                ? String(node.key)
                : JSONInt64.stringify(String(node.key));
            var keyEl = elem(doc, 'span', keyClass, keyText);
            keyEl.title = '点击复制路径：' + node.path;
            row.appendChild(keyEl);
            row.appendChild(elem(doc, 'span', 'json-punct', ': '));
        }

        if (containerNode) {
            renderContainer(wrap, row, node, doc, nodeMap);
        } else {
            renderLeaf(row, node, doc);
        }

        if (node.comma) {
            // 折叠时逗号紧跟行内闭合括号；展开时逗号属于结尾行，这里隐藏
            var comma = elem(doc, 'span', 'json-comma json-row-comma', ',');
            if (foldable) comma.classList.add('json-comma-inline');
            row.appendChild(comma);
        }
        return wrap;
    }

    /**
     * 渲染到容器。options:
     *   onChange(node)          折叠状态变化后的回调
     *   onKeyClick(node)        点击键名 / 下标时的回调
     *   emptyText               无内容时的占位提示
     */
    function renderBlocks(blocks, container, options) {
        var doc = container.ownerDocument;
        var opts = options || {};
        var nodeMap = { next: 0, nodes: {} };
        var frag = doc.createDocumentFragment();

        blocks.forEach(function (block) {
            if (block.type === 'text') {
                frag.appendChild(elem(doc, 'pre', 'json-text-block', block.text));
            } else {
                frag.appendChild(renderNode(block.node, doc, nodeMap));
            }
        });

        if (!blocks.length) {
            frag.appendChild(elem(doc, 'div', 'json-empty',
                opts.emptyText || '暂无内容'));
        }

        var scrollTop = container.scrollTop;
        container.innerHTML = '';
        container.appendChild(frag);
        container.scrollTop = scrollTop;

        // 事件委托：整棵树只挂一个 click
        container.onclick = function (event) {
            var target = event.target;
            if (!target || !target.closest) return;
            var keyEl = target.closest('.json-key, .json-index');
            var row = target.closest('.json-row');
            if (!row) return;
            var wrap = row.parentNode;
            if (!wrap || !wrap.classList.contains('json-node')) return;
            var node = nodeMap.nodes[wrap.getAttribute('data-node-id')];
            if (!node) return;

            // 键名点击优先（叶子节点也要能复制路径）
            if (keyEl && opts.onKeyClick) {
                opts.onKeyClick(node);
                return;
            }
            if (node.children.length === 0) return;

            // 点击三角、首行或结尾行 -> 切换折叠
            node.collapsed = !node.collapsed;
            wrap.classList.toggle('collapsed', node.collapsed);
            var btn = wrap.children[0].querySelector('.json-toggle');
            if (btn) {
                btn.textContent = node.collapsed ? '▸' : '▾';
                btn.setAttribute('aria-expanded', node.collapsed ? 'false' : 'true');
            }
            if (opts.onChange) opts.onChange(node);
        };
    }

    var api = {
        kindOf: kindOf,
        buildBlocks: buildBlocks,
        walkBlocks: walkBlocks,
        countNodes: countNodes,
        setAllCollapsed: setAllCollapsed,
        collapseToDepth: collapseToDepth,
        getCollapsedPaths: getCollapsedPaths,
        restoreCollapsedPaths: restoreCollapsedPaths,
        formatLeaf: formatLeaf,
        renderBlocks: renderBlocks
    };

    if (typeof global !== 'undefined') global.JSONTree = api;
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    return api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
