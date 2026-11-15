/**
 * json-tree.js 单元测试（仅依赖 Node 标准库）
 * 运行: node duck_rush/web-tools/js/json-tree.test.js
 */
const assert = require('assert');
const JSONTree = require('./json-tree.js');

let passed = 0;
function test(name, fn) {
    try {
        fn();
        passed++;
        console.log('  ok  - ' + name);
    } catch (e) {
        console.error('  FAIL- ' + name);
        console.error('       ' + e.message);
        process.exitCode = 1;
    }
}

function rootOf(text) {
    const blocks = JSONTree.buildBlocks(text);
    assert.strictEqual(blocks.length, 1);
    assert.strictEqual(blocks[0].type, 'json');
    return blocks[0].node;
}

function child(root, key) {
    const found = root.children.filter(c => String(c.key) === String(key));
    assert.strictEqual(found.length, 1, 'child ' + key + ' not found');
    return found[0];
}

console.log('json-tree.test.js');

test('empty / non-string input yields no blocks', () => {
    assert.deepStrictEqual(JSONTree.buildBlocks(''), []);
    assert.deepStrictEqual(JSONTree.buildBlocks(null), []);
});

test('plain text without JSON stays a text block', () => {
    const blocks = JSONTree.buildBlocks('错误: 未找到 JSON 内容');
    assert.deepStrictEqual(blocks, [{ type: 'text', text: '错误: 未找到 JSON 内容' }]);
});

test('single JSON builds one block with root path', () => {
    const blocks = JSONTree.buildBlocks('{"a":1}');
    assert.strictEqual(blocks.length, 1);
    assert.strictEqual(blocks[0].type, 'json');
    assert.strictEqual(blocks[0].node.path, '$');
    assert.strictEqual(blocks[0].node.key, null);
    assert.strictEqual(blocks[0].node.kind, 'object');
});

test('mixed text keeps non-JSON parts in order', () => {
    const blocks = JSONTree.buildBlocks('日志开始\n{"a":1}\n日志结束');
    assert.deepStrictEqual(blocks.map(b => b.type), ['text', 'json', 'text']);
    assert.strictEqual(blocks[0].text, '日志开始\n');
    assert.strictEqual(blocks[2].text, '\n日志结束');
});

test('multiple JSON fragments become separate blocks', () => {
    const blocks = JSONTree.buildBlocks('{"a":1}\n\n[2,3]');
    const jsonBlocks = blocks.filter(b => b.type === 'json');
    assert.strictEqual(jsonBlocks.length, 2);
    assert.strictEqual(jsonBlocks[0].node.kind, 'object');
    assert.strictEqual(jsonBlocks[1].node.kind, 'array');
});

test('extract results with "JSON 1:" prefix render as text + tree', () => {
    const blocks = JSONTree.buildBlocks('JSON 1:\n{\n  "a": 1\n}');
    assert.deepStrictEqual(blocks.map(b => b.type), ['text', 'json']);
    assert.strictEqual(blocks[0].text, 'JSON 1:\n');
});

test('braces inside strings do not break extraction', () => {
    const root = rootOf('{"s": "a}b{c", "n": 2}');
    assert.strictEqual(child(root, 's').value, 'a}b{c');
    assert.strictEqual(child(root, 'n').value, 2);
});

test('invalid JSON fragment is preserved as text', () => {
    const blocks = JSONTree.buildBlocks('前缀 {"a": 1,} 后缀');
    assert.deepStrictEqual(blocks.map(b => b.type), ['text']);
    assert.ok(blocks[0].text.includes('{"a": 1,}'));
});

test('node kinds and leaf formatting', () => {
    const root = rootOf('{"s":"hi","n":1.5,"t":true,"f":false,"z":null}');
    assert.strictEqual(child(root, 's').kind, 'string');
    assert.strictEqual(child(root, 'n').kind, 'number');
    assert.strictEqual(child(root, 't').kind, 'boolean');
    assert.strictEqual(child(root, 'z').kind, 'null');
    assert.strictEqual(JSONTree.formatLeaf('a\nb'), '"a\\nb"');
    assert.strictEqual(JSONTree.formatLeaf(null), 'null');
    assert.strictEqual(JSONTree.formatLeaf(true), 'true');
});

test('int64 values keep precision and format as bare integer', () => {
    const big = '9223372036854775807';
    const root = rootOf('{"id":' + big + '}');
    const node = child(root, 'id');
    assert.strictEqual(node.kind, 'number');
    assert.strictEqual(typeof node.value, 'bigint');
    assert.strictEqual(JSONTree.formatLeaf(node.value), big);
});

test('array indices, keys with special chars and comma flags', () => {
    const root = rootOf('{"a-b":1,"list":[10,{"x":2}]}');
    assert.strictEqual(child(root, 'a-b').path, '$["a-b"]');
    const list = child(root, 'list');
    assert.strictEqual(list.path, '$.list');
    assert.strictEqual(list.children.length, 2);
    assert.strictEqual(list.children[0].path, '$.list[0]');
    assert.strictEqual(list.children[0].key, 0);
    assert.strictEqual(list.children[0].comma, true);
    assert.strictEqual(list.children[1].comma, false);
    assert.strictEqual(list.children[1].children[0].path, '$.list[1].x');
    assert.strictEqual(child(root, 'a-b').comma, true);
    assert.strictEqual(list.comma, false);
});

test('empty containers are not foldable', () => {
    const root = rootOf('{"a":{},"b":[]}');
    assert.strictEqual(child(root, 'a').children.length, 0);
    assert.strictEqual(child(root, 'b').children.length, 0);
});

test('countNodes counts all nodes and foldable containers', () => {
    const blocks = JSONTree.buildBlocks('{"a":{},"b":[1,2]}');
    assert.deepStrictEqual(JSONTree.countNodes(blocks), { total: 5, containers: 2 });
});

test('setAllCollapsed toggles every container', () => {
    const blocks = JSONTree.buildBlocks('{"a":{"b":{"c":1}}}');
    JSONTree.setAllCollapsed(blocks, true);
    JSONTree.walkBlocks(blocks, n => {
        if (n.children.length) assert.strictEqual(n.collapsed, true);
    });
    JSONTree.setAllCollapsed(blocks, false);
    JSONTree.walkBlocks(blocks, n => assert.strictEqual(n.collapsed, false));
});

test('collapseToDepth folds nodes at or beyond the visible level', () => {
    const blocks = JSONTree.buildBlocks('{"a":{"b":{"c":1}}}');
    const root = blocks[0].node;
    JSONTree.collapseToDepth(blocks, 2);
    assert.strictEqual(root.collapsed, false);
    assert.strictEqual(child(root, 'a').collapsed, false);
    assert.strictEqual(child(child(root, 'a'), 'b').collapsed, true);
    JSONTree.collapseToDepth(blocks, 1);
    assert.strictEqual(root.collapsed, false);
    assert.strictEqual(child(root, 'a').collapsed, true);
    JSONTree.collapseToDepth(blocks, Infinity);
    JSONTree.walkBlocks(blocks, n => assert.strictEqual(n.collapsed, false));
});

test('collapsed paths can be saved and restored per fragment', () => {
    const blocks = JSONTree.buildBlocks('{"a":{"b":1}}\n{"a":{"b":2}}');
    const first = blocks.filter(b => b.type === 'json')[0].node;
    child(first, 'a').collapsed = true;
    const saved = JSONTree.getCollapsedPaths(blocks);
    assert.deepStrictEqual(saved, ['0|$.a']);

    const fresh = JSONTree.buildBlocks('{"a":{"b":1}}\n{"a":{"b":2}}');
    JSONTree.restoreCollapsedPaths(fresh, saved);
    const jsonBlocks = fresh.filter(b => b.type === 'json');
    assert.strictEqual(child(jsonBlocks[0].node, 'a').collapsed, true);
    assert.strictEqual(child(jsonBlocks[1].node, 'a').collapsed, false);
});

test('restoreCollapsedPaths tolerates missing paths', () => {
    const blocks = JSONTree.buildBlocks('{"a":1}');
    JSONTree.restoreCollapsedPaths(blocks, null);
    JSONTree.walkBlocks(blocks, n => assert.strictEqual(n.collapsed, false));
});

console.log('\npassed ' + passed + ' cases');
