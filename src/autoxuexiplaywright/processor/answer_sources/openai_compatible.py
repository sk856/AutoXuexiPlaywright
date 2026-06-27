"""Get answer from OpenAI compatible chat completions API."""

import asyncio as _asyncio
import json as _json
from logging import getLogger as _get_logger
from urllib.error import HTTPError as _HTTPError
from urllib.error import URLError as _URLError
from urllib.request import Request as _Request
from urllib.request import urlopen as _urlopen
from collections.abc import AsyncIterator as _AsyncIterator
from semver import Version as _Version
from typing import final as _final
from typing import override as _override
from autoxuexiplaywright import APPAUTHOR as _APPAUTHOR
from autoxuexiplaywright import __version__ as _version
from autoxuexiplaywright.config import Config as _Config
from autoxuexiplaywright.sdk import AnswerSource as _AnswerSource
from autoxuexiplaywright.sdk import module_entrance as _module
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.processor.tasks.utils import clean_string as _clean_string


_logger = _get_logger(__name__)
_ANSWER_CONNECTOR = "#"
_DEFAULT_TIMEOUT_SECS = 30

_runtime_config = _Config()


def set_ai_answer_config(config: _Config):
    """Set config for AI answer source."""
    global _runtime_config  # noqa: PLW0603
    _runtime_config = config


def _chat_completions_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return base_url + "/chat/completions"
    return base_url + "/v1/chat/completions"


def _request_chat_completion(
    prompt: str,
    system_prompt: str,
    timeout: int = _DEFAULT_TIMEOUT_SECS,
) -> str:
    payload = {
        "model": _runtime_config.ai_answer_model.strip(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    request = _Request(
        _chat_completions_url(_runtime_config.ai_answer_base_url),
        data=_json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + _runtime_config.ai_answer_api_key.strip(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with _urlopen(request, timeout=timeout) as response:  # noqa: S310
        response_json = _json.loads(response.read().decode("utf-8"))
    content = response_json["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("AI response content is not string")
    return content


def _build_prompt(title: str) -> str:
    return "\n".join(
        [
            "请根据题目作答。",
            "只返回最终答案，不要解释。",
            f"题目：{title}",
            f"如果有多个答案，请使用 {_ANSWER_CONNECTOR} 连接。",
        ],
    )


def _parse_answers(content: str) -> list[str]:
    content = content.strip()
    for prefix in ("答案：", "答案:", "最终答案：", "最终答案:"):
        if content.startswith(prefix):
            content = content.removeprefix(prefix).strip()
    content = content.replace("\n", _ANSWER_CONNECTOR)
    separators = [_ANSWER_CONNECTOR, "；", ";", "，", ",", "、"]
    answers = [content]
    for separator in separators:
        if separator in content:
            answers = content.split(separator)
            break
    return [_clean_string(answer) for answer in answers if _clean_string(answer) != ""]


def test_ai_answer_config_sync(config: _Config) -> tuple[bool, str]:
    """Test whether current AI answer config can call chat completions."""
    set_ai_answer_config(config)
    if (
        config.ai_answer_base_url.strip() == ""
        or config.ai_answer_api_key.strip() == ""
        or config.ai_answer_model.strip() == ""
    ):
        return False, __("AI answer is not configured.")
    try:
        content = _request_chat_completion(
            "请只回复 OK 两个字母。",
            "你用于测试接口连通性。必须只输出 OK。",
            15,
        )
    except (_HTTPError, _URLError, KeyError, IndexError, TypeError, ValueError) as e:
        return False, __("AI API test failed: %(e)s") % {"e": e}
    if content.strip().upper().startswith("OK"):
        return True, __("AI API is available.")
    return True, __("AI API is available, response: %(response)s") % {
        "response": content.strip(),
    }


async def test_ai_answer_config(config: _Config) -> tuple[bool, str]:
    """Test whether current AI answer config can call chat completions."""
    return await _asyncio.to_thread(test_ai_answer_config_sync, config)


@_module(_Version.parse(_version))
@_final
class OpenAICompatibleAnswerSource(_AnswerSource):
    """Get answer from OpenAI compatible chat completions API."""

    @property
    @_override
    def name(self) -> str:
        return self.__class__.__name__

    @property
    @_override
    def author(self) -> str:
        return _APPAUTHOR

    @_override
    async def get_answer(self, title: str) -> _AsyncIterator[str]:
        if not _runtime_config.ai_answer_enabled:
            return
        if (
            _runtime_config.ai_answer_base_url.strip() == ""
            or _runtime_config.ai_answer_api_key.strip() == ""
            or _runtime_config.ai_answer_model.strip() == ""
        ):
            _logger.warning(__("AI answer is not configured."))
            return
        try:
            content = await _asyncio.to_thread(
                _request_chat_completion,
                _build_prompt(title),
                "你是一个答题助手。必须只输出答案本身，不要输出解释、编号、Markdown 或多余文字。",
            )
        except (_HTTPError, _URLError, KeyError, IndexError, TypeError, ValueError) as e:
            _logger.warning(__("AI answer failed because %(e)s"), {"e": e})
            return
        for answer in _parse_answers(content):
            yield answer
