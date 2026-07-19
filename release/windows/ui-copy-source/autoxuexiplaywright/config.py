from typing import Literal
from json import load, dump
from playwright._impl._api_structures import ProxySettings

ChannelType = Literal["msedge", "msedge-beta", "msedge-dev",
                      "chrome", "chrome-beta", "chrome-dev",
                      "chromium", "chromium-beta", "chromium-dev"] | None
BrowserType = Literal["firefox", "chromium", "webkit"]


class Config:
    def __init__(self) -> None:
        self.lang = "zh-cn"
        self.async_mode = False
        self.browser_id: BrowserType = "firefox"
        self.browser_channel: ChannelType = None
        self.debug = False
        self.executable_path: str | None = None
        self.gui = True
        self.auto_start = False
        self.proxy: ProxySettings | None = None
        self.skipped: list[str] = []
        self.get_video = False
        self.read_history_retention_days = 7
        self.ai_answer_enabled = False
        self.ai_answer_base_url = ""
        self.ai_answer_api_key = ""
        self.ai_answer_model = "gpt-4o-mini"
        self.captcha_local_enabled = False
        self.captcha_local_url = ""
        self.captcha_local_token = ""
        self.captcha_local_timeout_secs = 10.0

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Config) and (self.__dict__ == __o.__dict__)


_configs: dict[str, Config] = {}
_runtime_config_path: str | None = None


def set_runtime_config(config: Config, path: str | None = None):
    """Set config as runtime config

    Args:
        config (Config): The config to be set
        path (str | None): The source file of the runtime config.
    """
    global _runtime_config_path
    _configs["_"] = config
    _runtime_config_path = path


def get_runtime_config_path() -> str | None:
    """Return the file currently backing the runtime config."""
    return _runtime_config_path


def get_runtime_config() -> Config:
    """Get the runtime config set

    Returns:
        Config: The runtime config
    """
    return _configs["_"] if "_" in _configs.keys() else Config()


def deserialize_config(path: str) -> Config:
    """Deserialize config to config instance

    **Note**: `path="_"` means runtime config

    Args:
        path (str): The path to config

    Returns:
        Config: The config instance
    """
    if path not in _configs.keys():
        with open(path, "r", encoding="utf-8") as reader:
            config_json = load(reader)
        if path != "_":
            _configs[path] = _deserialize_config_from_json(config_json)
    return _configs[path]


def serialize_config(config: Config, path: str, indent: int = 4, sort_keys: bool = True):
    """Serialize config instance to path

    **Note**: `path="_"` will be skipped because it is runtime config

    Args:
        config (Config): The config instance
        path (str): The path to config
        indent (int, optional): The number of json indent. Defaults to 4.
        sort_keys (bool, optional): If sort json keys. Defaults to True.
    """
    if path == "_":
        return
    with open(path, "w", encoding="utf-8") as writer:
        dump(_serialize_config_to_json(config), writer,
             indent=indent, sort_keys=sort_keys)


def _deserialize_config_from_json(json: dict[str, bool | str | ProxySettings | None]) -> Config:
    """Create a config instance and apply json to it

    Args:
        json (dict[str, bool  |  str  |  ProxySettings  |  None]): The json dict

    Returns:
        Config: The config instance
    """
    config = Config()
    for key, value in json.items():
        if hasattr(config, key):
            match key:
                case "lang":
                    if isinstance(value, str):
                        config.lang = value
                case "async_mode":
                    if isinstance(value, bool):
                        config.async_mode = value
                case "browser_id":
                    if isinstance(value, str):
                        match value:
                            case "firefox" | "chromium" | "webkit":
                                config.browser_id = value
                            case _:
                                pass
                case "browser_channel":
                    if isinstance(value, str):
                        match value:
                            case \
                                "msedge" | "msedge-beta" | "msedge-dev" | \
                                "chromium" | "chromium-beta" | "chromium-dev" | \
                                    "chrome" | "chrome-beta" | "chrome-dev":
                                config.browser_channel = value
                            case _:
                                pass
                case "debug":
                    if isinstance(value, bool):
                        config.debug = value
                case "executable_path":
                    if isinstance(value, str):
                        config.executable_path = value
                case "gui":
                    if isinstance(value, bool):
                        config.gui = value
                case "auto_start":
                    if isinstance(value, bool):
                        config.auto_start = value
                case "proxy":
                    if isinstance(value, dict):
                        config.proxy = value
                case "skipped":
                    if isinstance(value, list):
                        config.skipped = value
                case "get_video":
                    if isinstance(value, bool):
                        config.get_video = value
                case "read_history_retention_days":
                    if isinstance(value, int) and value in (3, 7, 15, 30):
                        config.read_history_retention_days = value
                case "ai_answer_enabled":
                    if isinstance(value, bool):
                        config.ai_answer_enabled = value
                case "ai_answer_base_url":
                    if isinstance(value, str):
                        config.ai_answer_base_url = value
                case "ai_answer_api_key":
                    if isinstance(value, str):
                        config.ai_answer_api_key = value
                case "ai_answer_model":
                    if isinstance(value, str):
                        config.ai_answer_model = value
                case "captcha_local_enabled":
                    if isinstance(value, bool):
                        config.captcha_local_enabled = value
                case "captcha_local_url":
                    if isinstance(value, str):
                        config.captcha_local_url = value
                case "captcha_local_token":
                    if isinstance(value, str):
                        config.captcha_local_token = value
                case "captcha_local_timeout_secs":
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        config.captcha_local_timeout_secs = max(1.0, min(float(value), 120.0))
                case _:
                    pass

    return config


def _serialize_config_to_json(config: Config) -> dict[str, bool | str | ProxySettings | None]:
    """Convert a config instance to json dict

    Args:
        config (Config): The config instance

    Returns:
        dict[str, bool | str | ProxySettings | None]: The json dict
    """
    return config.__dict__
