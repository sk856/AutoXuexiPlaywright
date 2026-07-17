"""Get answer from OpenAI compatible chat completions API."""

# ruff: noqa: RUF001

import json as _json
import asyncio as _asyncio
from re import split as _re_split
from re import escape as _re_escape
from semver import Version as _Version
from typing import final as _final
from typing import override as _override
from logging import getLogger as _get_logger
from urllib.error import URLError as _URLError
from urllib.error import HTTPError as _HTTPError
from urllib.request import Request as _Request
from urllib.request import urlopen as _urlopen
from collections.abc import AsyncIterator as _AsyncIterator
from autoxuexiplaywright import APPAUTHOR as _APPAUTHOR
from autoxuexiplaywright import __version__ as _version
from autoxuexiplaywright.sdk import AnswerSource as _AnswerSource
from autoxuexiplaywright.sdk import module_entrance as _module
from autoxuexiplaywright.config import Config as _Config
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.processor.tasks.utils import clean_string as _clean_string


_logger = _get_logger(__name__)
_ANSWER_CONNECTOR = "#"
_DEFAULT_TIMEOUT_SECS = 30
_ERROR_BODY_LIMIT = 500

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


def _models_url(base_url: str) -> str:
    """Build the OpenAI-compatible model-list endpoint."""
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/models"):
        return base_url
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    if base_url.endswith("/v1"):
        return base_url + "/models"
    return base_url + "/v1/models"


def _request_models(config: _Config, timeout: int = _DEFAULT_TIMEOUT_SECS) -> list[str]:
    request = _Request(  # noqa: S310
        _models_url(config.ai_answer_base_url),
        headers={
            "Authorization": "Bearer " + config.ai_answer_api_key.strip(),
            "Accept": "application/json",
        },
        method="GET",
    )
    with _urlopen(request, timeout=timeout) as response:  # noqa: S310
        response_json = _json.loads(response.read().decode("utf-8"))
    data = response_json.get("data", [])
    if not isinstance(data, list):
        raise ValueError("AI models response data is not a list")
    models = sorted(
        {
            item["id"].strip()
            for item in data
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"].strip()
        },
    )
    if not models:
        raise ValueError("AI models response contains no model ids")
    return models


def fetch_ai_models_sync(config: _Config) -> tuple[bool, list[str], str]:
    """Fetch model ids from an OpenAI-compatible ``/models`` endpoint."""
    if config.ai_answer_base_url.strip() == "":
        return False, [], __("AI API base URL is empty.")
    if config.ai_answer_api_key.strip() == "":
        return False, [], __("AI API key is empty.")
    try:
        models = _request_models(config, 15)
    except Exception as e:
        return (
            False,
            [],
            __("Failed to fetch AI models: %(e)s")
            % {
                "e": _format_ai_error(e),
            },
        )
    return True, models, __("Fetched %(count)d AI models.") % {"count": len(models)}


async def fetch_ai_models(config: _Config) -> tuple[bool, list[str], str]:
    """Fetch model ids without blocking the asyncio event loop."""
    return await _asyncio.to_thread(fetch_ai_models_sync, config)


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
    request = _Request(  # noqa: S310
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


def _format_ai_error(error: Exception) -> str:
    if isinstance(error, _HTTPError):
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        body = body.strip()
        if len(body) > _ERROR_BODY_LIMIT:
            body = body[:_ERROR_BODY_LIMIT] + "..."
        return "HTTP %(code)s %(reason)s%(body)s" % {
            "code": error.code,
            "reason": error.reason,
            "body": ("; response: " + body) if body != "" else "",
        }
    if isinstance(error, _URLError):
        return "Network error: %(reason)s" % {"reason": error.reason}
    return "%(type)s: %(message)s" % {
        "type": error.__class__.__name__,
        "message": error,
    }


def _build_prompt(
    title: str,
    *,
    blank: bool = False,
    choices: list[str] | None = None,
) -> str:
    question_type = "填空题" if blank else "选择题"
    prompt_parts = [
        "请根据题目作答。",
        "只返回最终答案，不要解释。",
        f"题型：{question_type}",
        f"题目：{title}",
    ]
    if choices is not None and len(choices) > 0:
        prompt_parts.append(
            "可用选项："
            + _ANSWER_CONNECTOR.join(
                f"{chr(ord('A') + position)}. {choice}"
                for position, choice in enumerate(choices)
            ),
        )
    if blank:
        prompt_parts.append(f"如果有多个填空答案，请使用 {_ANSWER_CONNECTOR} 连接。")
    else:
        prompt_parts.append(
            "选择题必须优先返回选项文字本身；"
            "如果只能判断选项序号，也可以返回 A/B/C/D。"
            f"多选题请使用 {_ANSWER_CONNECTOR} 连接。",
        )
    return "\n".join(prompt_parts)


def _parse_answers(content: str, *, blank: bool = False) -> list[str]:
    content = content.strip()
    for prefix in ("答案：", "答案:", "最终答案：", "最终答案:"):
        if content.startswith(prefix):
            content = content.removeprefix(prefix).strip()
    content = content.replace("\n", _ANSWER_CONNECTOR)
    separators = [_ANSWER_CONNECTOR, "；", ";"]
    if not blank:
        separators.extend(["，", ",", "、"])
    answers = _re_split(
        "|".join(_re_escape(separator) for separator in separators),
        content,
    )
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
    except Exception as e:
        return False, __("AI API test failed: %(e)s") % {
            "e": _format_ai_error(e),
        }
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
    async def get_answer(
        self,
        title: str,
        *,
        blank: bool = False,
        choices: list[str] | None = None,
    ) -> _AsyncIterator[str]:
        if not _runtime_config.ai_answer_enabled:
            _logger.warning(__("AI answer is disabled, skipping AI."))
            return
        if (
            _runtime_config.ai_answer_base_url.strip() == ""
            or _runtime_config.ai_answer_api_key.strip() == ""
            or _runtime_config.ai_answer_model.strip() == ""
        ):
            _logger.warning(__("AI answer is not configured."))
            return
        try:
            _logger.info(
                __("Trying AI answer with model %(model)s and base URL %(base_url)s"),
                {
                    "model": _runtime_config.ai_answer_model.strip(),
                    "base_url": _runtime_config.ai_answer_base_url.strip(),
                },
            )
            content = await _asyncio.to_thread(
                _request_chat_completion,
                _build_prompt(title, blank=blank, choices=choices),
                "你是一个答题助手。必须只输出答案本身，"
                "不要输出解释、编号、Markdown 或多余文字。",
            )
        except Exception as e:
            _logger.warning(
                __("AI answer failed because %(e)s"),
                {"e": _format_ai_error(e)},
            )
            return
        parsed_answers = _parse_answers(content, blank=blank)
        if len(parsed_answers) == 0:
            _logger.warning(
                __("AI returned content but no answer could be parsed: %(content)s"),
                {"content": content.strip()},
            )
        for answer in parsed_answers:
            yield answer
