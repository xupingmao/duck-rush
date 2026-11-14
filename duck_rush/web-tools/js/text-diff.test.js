const assert = require('assert');
const { computeTextDiff, normalizeLine } = require('./text-diff-core.js');

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

console.log('text-diff.test.js');

test('identical lines produce equal rows', () => {
    const rows = computeTextDiff(['a', 'b', 'c'], ['a', 'b', 'c'], {});
    assert.strictEqual(rows.length, 3);
    rows.forEach(r => assert.strictEqual(r.type, 'equal'));
});

test('insertion produces one added row', () => {
    const rows = computeTextDiff(['a', 'b'], ['a', 'x', 'b'], {});
    const added = rows.filter(r => r.type === 'added');
    const removed = rows.filter(r => r.type === 'removed');
    assert.strictEqual(added.length, 1);
    assert.strictEqual(removed.length, 0);
    assert.strictEqual(added[0].right, 'x');
});

test('deletion produces one removed row', () => {
    const rows = computeTextDiff(['a', 'x', 'b'], ['a', 'b'], {});
    const removed = rows.filter(r => r.type === 'removed');
    assert.strictEqual(removed.length, 1);
    assert.strictEqual(removed[0].left, 'x');
});

test('modification produces removed then added', () => {
    const rows = computeTextDiff(['a', 'old'], ['a', 'new'], {});
    const changed = rows.filter(r => r.type !== 'equal');
    assert.strictEqual(changed.length, 2);
    assert.strictEqual(changed[0].type, 'removed');
    assert.strictEqual(changed[0].left, 'old');
    assert.strictEqual(changed[1].type, 'added');
    assert.strictEqual(changed[1].right, 'new');
});

test('line numbers are assigned correctly', () => {
    const rows = computeTextDiff(['a', 'b', 'c'], ['a', 'c'], {});
    const removed = rows.find(r => r.type === 'removed');
    assert.strictEqual(removed.ln, 2);
    assert.strictEqual(removed.left, 'b');
    assert.strictEqual(rows[0].ln, 1);
    assert.strictEqual(rows[0].rn, 1);
});

test('ignoreWhitespace treats padded lines as equal', () => {
    const rows = computeTextDiff(['  hello  '], ['hello'], { ignoreWhitespace: true });
    assert.strictEqual(rows[0].type, 'equal');
});

test('ignoreCase treats different cases as equal', () => {
    const rows = computeTextDiff(['Hello'], ['hello'], { ignoreCase: true });
    assert.strictEqual(rows[0].type, 'equal');
});

test('normalizeLine respects options', () => {
    assert.strictEqual(normalizeLine('  Ab ', { ignoreWhitespace: true, ignoreCase: true }), 'ab');
    assert.strictEqual(normalizeLine('  Ab ', { ignoreWhitespace: true }), 'Ab');
    assert.strictEqual(normalizeLine('Ab', { ignoreCase: true }), 'ab');
});

test('empty inputs produce no rows', () => {
    const rows = computeTextDiff([], [], {});
    assert.strictEqual(rows.length, 0);
});

test('jsdiff handles multi-line blocks', () => {
    const left = ['function f() {', '  return 1;', '}', ''];
    const right = ['function f() {', '  return 2;', '}', ''];
    const rows = computeTextDiff(left, right, {});
    const changed = rows.filter(r => r.type !== 'equal');
    assert.strictEqual(changed.length, 2);
    assert.strictEqual(changed[0].left, '  return 1;');
    assert.strictEqual(changed[1].right, '  return 2;');
});

console.log('\n' + passed + ' tests passed');
