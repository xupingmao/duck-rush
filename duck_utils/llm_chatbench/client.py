# -*- coding: utf-8 -*-
"""ollama 原生 chat 接口客户端 (仅用标准库 urllib)。

多轮评测必须发送完整 messages 历史, 所以用 /api/chat 而非 `ollama run`。
非流式返回, 便于统计每轮 token 数与耗时。
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .model import ChatReply, RunOptions
from .util import strip_thinking

DEFAULT_BASE_URL = 'http://localhost:11434'

# 推理模型: 思考过程会吃掉大量输出 token, 默认关闭 think 以保证横比的是可用回复
REASONING_HINTS = ('r1', 'qwq', 'thinking', 'reasoner')


def is_reasoning_model(model: str) -> bool:
    low = (model or '').lower()
    return any(h in low for h in REASONING_HINTS)


class OllamaChatClient:
    """调用 ollama /api/chat, 失败时返回带 error 的 ChatReply 而不抛异常。"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = 300, python_exe: str = ''):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.python_exe = python_exe or sys.executable

    def _post(self, path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            self.base_url + path, data=data,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def list_models(self) -> List[str]:
        """通过 /api/tags 列出本地已下载模型名。"""
        try:
            req = urllib.request.Request(self.base_url + '/api/tags')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return [str(m['name']) for m in data.get('models', []) if m.get('name')]
        except Exception:
            return []

    def chat(self, model: str, messages: List[Dict[str, str]],
             opts: RunOptions) -> ChatReply:
        options: Dict[str, Any] = {
            'temperature': opts.temperature,
            'seed': opts.seed,
            'num_ctx': opts.num_ctx,
            'num_predict': opts.max_tokens,
        }
        payload: Dict[str, Any] = {
            'model': model, 'messages': messages,
            'stream': False, 'options': options,
        }
        think = opts.think
        if think is None and is_reasoning_model(model):
            think = False
        if think is not None:
            payload['think'] = bool(think)
        if is_reasoning_model(model):
            # 实测 ollama 0.32.6: 对 deepseek-r1 传 think=false 仍会生成很长的
            # 思考段 (放在 message.thinking), 且这些 token 同样计入 num_predict。
            # 预算不足时正文还没开始就被截断, message.content 为空。给足预算。
            options['num_predict'] = max(opts.max_tokens, 8192)
        started = time.time()
        try:
            data = self._post('/api/chat', payload, opts.timeout)
        except urllib.error.HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')[:300]
            except Exception:
                pass
            return ChatReply('', elapsed_ms=int((time.time() - started) * 1000),
                             error='HTTP %s: %s' % (e.code, body))
        except Exception as e:
            return ChatReply('', elapsed_ms=int((time.time() - started) * 1000),
                             error='%s: %s' % (type(e).__name__, e))
        elapsed = int((time.time() - started) * 1000)
        msg = data.get('message') or {}
        raw = str(msg.get('content') or '')
        content = strip_thinking(raw)
        return ChatReply(
            content=content,
            prompt_tokens=int(data.get('prompt_eval_count') or 0),
            eval_tokens=int(data.get('eval_count') or 0),
            elapsed_ms=elapsed,
            error=None if content else 'empty reply (think-only or truncated)',
        )
