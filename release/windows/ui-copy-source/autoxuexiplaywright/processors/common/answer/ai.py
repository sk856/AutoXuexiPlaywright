from json import dumps, loads
from re import escape, split, sub
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...common import ANSWER_CONNECTOR
from ....config import get_runtime_config
from ....languages import get_language_string
from ....logger import debug, warning

_DEFAULT_TIMEOUT_SECS = 30
_ERROR_BODY_LIMIT = 500


def _chat_completions_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return base_url + "/chat/completions"
    return base_url + "/v1/chat/completions"


def _models_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/models"):
        return base_url
    if base_url.endswith("/chat/completions"):
        return base_url[:-len("/chat/completions")] + "/models"
    if base_url.endswith("/v1"):
        return base_url + "/models"
    return base_url + "/v1/models"


def _parse_model_ids(response_json) -> list[str]:
    """Extract model IDs from standard and common compatible responses."""
    if isinstance(response_json, dict):
        candidates = response_json.get("data", response_json.get("models", []))
    elif isinstance(response_json, list):
        candidates = response_json
    else:
        candidates = []

    model_ids: list[str] = []
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, str):
                model_id = candidate.strip()
            elif isinstance(candidate, dict):
                model_id = candidate.get("id", candidate.get("name", ""))
                model_id = model_id.strip() if isinstance(model_id, str) else ""
            else:
                model_id = ""
            if model_id and model_id not in model_ids:
                model_ids.append(model_id)
    return model_ids


def fetch_ai_models(timeout: int = 15) -> tuple[bool, list[str], str]:
    """Fetch model IDs from the configured OpenAI-compatible /models endpoint."""
    config = get_runtime_config()
    base_url = config.ai_answer_base_url.strip()
    if base_url == "":
        return False, [], get_language_string(
            "core-warning-ai-answer-base-url-not-configured")

    try:
        headers = {"Accept": "application/json"}
        api_key = config.ai_answer_api_key.strip()
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        request = Request(_models_url(base_url), headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            response_json = loads(response.read().decode("utf-8"))
        model_ids = _parse_model_ids(response_json)
        if not model_ids:
            return False, [], get_language_string(
                "core-warning-ai-answer-models-empty")
        return True, model_ids, get_language_string(
            "ui-config-window-ai-answer-fetch-models-success") % len(model_ids)
    except Exception as error:
        return False, [], get_language_string(
            "ui-config-window-ai-answer-fetch-models-failed") % _format_ai_error(error)


def _build_prompt(title: str, tips: list[str], blank: bool) -> str:
    question_type = "填空题" if blank else "选择题"
    prompt_parts = [
        "请根据题目作答。",
        "只返回最终答案，不要解释。",
        f"题型：{question_type}",
        f"题目：{title}",
    ]
    if len(tips) > 1:
        prompt_parts.append("\n".join(tips[1:]))
    if blank:
        prompt_parts.append(f"如果有多个填空答案，请使用 {ANSWER_CONNECTOR} 连接。")
    else:
        prompt_parts.append(
            f"选择题必须优先返回选项文字本身；如果只能判断选项序号，也可以返回 A/B/C/D。多选题请使用 {ANSWER_CONNECTOR} 连接。")
    return "\n".join(prompt_parts)


def _request_chat_completion(prompt: str, system_prompt: str, timeout: int = _DEFAULT_TIMEOUT_SECS) -> str:
    config = get_runtime_config()
    payload = {
        "model": config.ai_answer_model.strip(),
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0,
    }
    request = Request(
        _chat_completions_url(config.ai_answer_base_url),
        data=dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + config.ai_answer_api_key.strip(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        response_json = loads(response.read().decode("utf-8"))
    content = response_json["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("AI response content is not string")
    return content


def _format_ai_error(error: Exception) -> str:
    if isinstance(error, HTTPError):
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        body = body.strip()
        if len(body) > _ERROR_BODY_LIMIT:
            body = body[:_ERROR_BODY_LIMIT] + "..."
        return "HTTP %s %s%s" % (
            error.code,
            error.reason,
            ("，返回：" + body) if body != "" else "",
        )
    if isinstance(error, URLError):
        return "网络错误：%s" % error.reason
    return "%s：%s" % (error.__class__.__name__, error)


def _parse_answers(content: str, blank: bool = False) -> list[str]:
    content = content.strip()
    for prefix in ("答案：", "答案:", "最终答案：", "最终答案:"):
        if content.startswith(prefix):
            content = content.removeprefix(prefix).strip()
    content = content.replace("\n", ANSWER_CONNECTOR)
    separators = [ANSWER_CONNECTOR, "；", ";"]
    if not blank:
        separators.extend(["，", ",", "、"])
    answers = split("|".join(escape(separator)
                    for separator in separators), content)
    cleaned_answers = []
    for answer in answers:
        cleaned = answer.strip()
        if not blank:
            cleaned = cleaned.strip("()（）[]【】")
            cleaned = sub(r"^([A-Za-zＡ-Ｚａ-ｚ])\s*[.．、:：。]\s*$", r"\1", cleaned)
        if cleaned != "" and cleaned[0].isprintable():
            cleaned_answers.append(cleaned)
    return cleaned_answers


def get_answer_from_ai(title: str, tips: list[str], blank: bool) -> list[str]:
    config = get_runtime_config()
    if not config.ai_answer_enabled:
        warning(get_language_string("core-warning-ai-answer-disabled"))
        return []
    if config.ai_answer_base_url.strip() == "" or config.ai_answer_api_key.strip() == "" or config.ai_answer_model.strip() == "":
        warning(get_language_string("core-warning-ai-answer-not-configured"))
        return []

    try:
        warning(get_language_string("core-info-ai-answer-trying") %
                (config.ai_answer_model.strip(), config.ai_answer_base_url.strip()))
        content = _request_chat_completion(
            _build_prompt(title, tips, blank),
            "你是一个答题助手。必须只输出答案本身，不要输出解释、编号、Markdown 或多余文字。"
        )
        answers = _parse_answers(content, blank)
        debug(get_language_string("core-debug-ai-answer-list") % answers)
        if len(answers) == 0:
            warning(get_language_string("core-warning-ai-answer-empty") %
                    content.strip())
        return answers
    except Exception as e:
        warning(get_language_string("core-warning-ai-answer-failed") %
                _format_ai_error(e))
    return []


def test_ai_answer_config() -> tuple[bool, str]:
    config = get_runtime_config()
    if config.ai_answer_base_url.strip() == "" or config.ai_answer_api_key.strip() == "" or config.ai_answer_model.strip() == "":
        return False, get_language_string("core-warning-ai-answer-not-configured")
    try:
        content = _request_chat_completion(
            "请只回复 OK 两个字母。",
            "你用于测试接口连通性。必须只输出 OK。",
            timeout=15,
        )
        if content.strip().upper().startswith("OK"):
            return True, get_language_string("ui-config-window-ai-answer-test-success")
        return True, get_language_string("ui-config-window-ai-answer-test-success-with-response") % content.strip()
    except Exception as e:
        return False, get_language_string("ui-config-window-ai-answer-test-failed") % _format_ai_error(e)
