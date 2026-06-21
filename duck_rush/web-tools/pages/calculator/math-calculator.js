if (typeof Decimal === 'undefined') {
    var path = require('path');
    var Decimal = require(path.resolve(__dirname, '../../lib/decimal-10.6.0.min.js'));
}

﻿// ── Decimal 配置 ─────────────────────────────
Decimal.config({
    precision: 50,
    rounding: Decimal.ROUND_HALF_UP,
    toExpPos: 100,
    toExpNeg: -100,
});

// ── 表达式解析器  —  递归下降 + Decimal 大数 ──
const MATH_FNS = ['sqrt','abs','sin','cos','tan','log','ln','round','floor','ceil','max','min'];

class Tokenizer {
    constructor(s) { this.s = s; this.i = 0; }
    _ws() { while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++; }
    peek() { this._ws(); return this.i < this.s.length ? this.s[this.i] : ''; }
    next() { this._ws(); return this.i < this.s.length ? this.s[this.i++] : ''; }

    _num() {
        let j = this.i, dot = false;
        while (j < this.s.length && /[0-9.]/.test(this.s[j])) {
            if (this.s[j] === '.') { if (dot) break; dot = true; }
            j++;
        }
        let v = this.s.slice(this.i, j); this.i = j;
        return { t: 'n', v };
    }

    tokenize() {
        let ts = [];
        while (this.i < this.s.length) {
            let c = this.next();
            if (c === '') break;
            if (/[0-9]/.test(c)) { this.i--; ts.push(this._num()); continue; }
            if (/[a-zA-Z]/.test(c)) {
                let j = this.i;
                while (j < this.s.length && /[a-zA-Z]/.test(this.s[j])) j++;
                ts.push({ t: 'i', v: this.s.slice(this.i - 1, j) }); this.i = j;
                continue;
            }
            if (c === '$') {
                let j = this.i;
                while (j < this.s.length && /[0-9]/.test(this.s[j])) j++;
                let idx = this.s.slice(this.i, j);
                if (!idx) throw new Error('变量引用缺少序号');
                ts.push({ t: 'v', v: idx }); this.i = j;
                continue;
            }
            if ('+-*/%^(),'.includes(c)) { ts.push({ t: 'o', v: c }); continue; }
            throw new Error('未知字符: ' + c);
        }
        ts.push({ t: 'o', v: '' });
        return ts;
    }
}

class Parser {
    constructor(ts, vars) { this.ts = ts; this.p = 0; this.vars = vars || []; }
    peek() { return this.ts[this.p]; }
    next() { return this.ts[this.p++]; }
    match(t, v) { let x = this.peek(); return x.t === t && (v === undefined || x.v === v); }

    parse() {
        let r = this.expr();
        if (this.peek().v !== '') throw new Error('语法错误: 无法解析的内容');
        return r;
    }

    expr() {
        let r = this.term();
        while (this.match('o', '+') || this.match('o', '-')) {
            let op = this.next().v, right = this.term();
            r = op === '+' ? r.plus(right) : r.minus(right);
        }
        return r;
    }

    term() {
        let r = this.unary();
        while (this.match('o', '*') || this.match('o', '/') || this.match('o', '%')) {
            let op = this.next().v, right = this.unary();
            r = op === '*' ? r.times(right) : op === '/' ? r.div(right) : r.mod(right);
        }
        return r;
    }

    unary() {
        if (this.match('o', '+') || this.match('o', '-')) {
            let op = this.next().v, r = this.unary();
            return op === '-' ? r.negated() : r;
        }
        return this.power();
    }

    power() {
        let r = this.primary();
        if (this.match('o', '^')) {
            this.next();
            r = r.pow(this.unary());
        }
        return r;
    }

    primary() {
        let x = this.peek();
        if (x.t === 'n') { this.next(); return new Decimal(x.v); }
        if (x.t === 'i') {
            this.next();
            let name = x.v.toLowerCase();
            if (name === 'pi') return Decimal.acos(-1);
            if (name === 'e') return Decimal.exp(1);
            if (MATH_FNS.includes(name)) return this._call(name);
            throw new Error('未知标识符: ' + x.v);
        }
        if (x.t === 'v') {
            this.next();
            let idx = parseInt(x.v) - 1;
            if (idx < 0 || idx >= this.vars.length) return new Decimal('NaN');
            return new Decimal(this.vars[idx].result);
        }
        if (this.match('o', '(')) {
            this.next(); let r = this.expr();
            if (!this.match('o', ')')) throw new Error('缺少右括号 )');
            this.next(); return r;
        }
        throw new Error('语法错误: 无法解析 ' + (x.v || x.t));
    }

    _call(name) {
        if (!this.match('o', '(')) throw new Error('函数 ' + name + ' 需要参数列表');
        this.next();
        let args = [];
        if (!this.match('o', ')')) {
            args.push(this.expr());
            while (this.match('o', ',')) { this.next(); args.push(this.expr()); }
        }
        if (!this.match('o', ')')) throw new Error('函数 ' + name + ' 缺少右括号');
        this.next();
        switch (name) {
            case 'sqrt': return args[0].sqrt();
            case 'abs':  return args[0].abs();
            case 'sin':  return new Decimal(Math.sin(args[0].toNumber()));
            case 'cos':  return new Decimal(Math.cos(args[0].toNumber()));
            case 'tan':  return new Decimal(Math.tan(args[0].toNumber()));
            case 'log':  return Decimal.log10(args[0]);
            case 'ln':   return args[0].ln();
            case 'round':return args[0].round();
            case 'floor':return args[0].floor();
            case 'ceil': return args[0].ceil();
            case 'max':  return Decimal.max(...args);
            case 'min':  return Decimal.min(...args);
        }
    }
}

function calcExpr(expr, history) {
    let ts = new Tokenizer(expr).tokenize();
    return new Parser(ts, history || []).parse();
}

// ── 计算器 UI ────────────────────────────────
if (typeof window !== 'undefined' && window.document) {
    let g_history = [];
    const MAX_HISTORY = 10;

    const elInput = document.getElementById('calculationInput');
    const elCalc  = document.getElementById('calculateBtn');
    const elResult= document.getElementById('resultDisplay');
    const elHist  = document.getElementById('historyList');
    const elVars  = document.getElementById('variablesList');
    const elBtns  = document.querySelectorAll('.symbol-btn');

    function init() {
        loadHistory();
        renderVars();
        renderHist();
        elCalc.addEventListener('click', calculate);
        elInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); calculate(); }
        });
        elBtns.forEach(function (btn) {
            btn.addEventListener('click', function () { insertSymbol(this.dataset.symbol); });
        });
    }

    function insertSymbol(sym) {
        let s = elInput.selectionStart, e = elInput.selectionEnd, v = elInput.value;
        elInput.value = v.slice(0, s) + sym + v.slice(e);
        elInput.focus();
        elInput.selectionStart = elInput.selectionEnd = s + sym.length;
    }

    function calculate() {
        let expr = elInput.value.trim();
        if (!expr) { alert('请输入计算公式'); return; }
        try {
            let r = calcExpr(expr, g_history);
            let str = r.toString();
            elResult.textContent = str;
            g_history.unshift({ expression: expr, result: str });
            if (g_history.length > MAX_HISTORY) g_history.pop();
            renderVars();
            renderHist();
            saveHistory();
        } catch (e) {
            elResult.textContent = '错误: ' + e.message;
        }
    }

    function renderVars() {
        elVars.innerHTML = '';
        for (let i = 0; i < MAX_HISTORY; i++) {
            let d = document.createElement('div');
            d.className = 'variable-item';
            d.innerHTML = i < g_history.length
                ? '<span class="variable-name">$' + (i + 1) + '</span>: <span class="variable-value">' + g_history[i].result + '</span>'
                : '<span class="variable-name">$' + (i + 1) + '</span>: <span class="variable-value">-</span>';
            elVars.appendChild(d);
        }
    }

    function renderHist() {
        elHist.innerHTML = '';
        g_history.forEach(function (item, i) {
            let li = document.createElement('li');
            li.className = 'history-item';
            li.innerHTML = '<span class="history-expression">$' + (i + 1) + ': ' + item.expression + '</span><span class="history-result">' + item.result + '</span>';
            elHist.appendChild(li);
        });
    }

    function saveHistory() {
        try { localStorage.setItem('mathCalculatorHistory', JSON.stringify(g_history)); }
        catch (e) { console.error('保存历史失败:', e); }
    }

    function loadHistory() {
        try {
            let saved = localStorage.getItem('mathCalculatorHistory');
            if (saved) { g_history = JSON.parse(saved); if (g_history.length > MAX_HISTORY) g_history = g_history.slice(0, MAX_HISTORY); }
        } catch (e) { console.error('加载历史失败:', e); g_history = []; }
    }

    init();
}

// ── 导出测试 ──────────────────────────────────
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { calcExpr, Tokenizer, Parser, Decimal };
}
