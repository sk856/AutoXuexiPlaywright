"""Tests for configuration."""

import pytest
from autoxuexiplaywright.config import Config


def test_config_default_ignore_https_errors():
    """Test that ignore_https_errors defaults to False."""
    config = Config()
    assert config.ignore_https_errors is False


def test_config_with_ignore_https_errors():
    """Test that ignore_https_errors can be set to True."""
    config = Config(ignore_https_errors=True)
    assert config.ignore_https_errors is True


def test_config_serialization():
    """Test that config can be serialized and deserialized with ignore_https_errors."""
    from pydantic import TypeAdapter
    
    config = Config(
        browser_id="firefox",
        ignore_https_errors=True,
        debug=True,
    )
    
    # Convert to dict
    config_dict = {
        "browser_id": config.browser_id,
        "browser_channel": config.browser_channel,
        "debug": config.debug,
        "executable_path": config.executable_path,
        "gui": config.gui,
        "ignore_https_errors": config.ignore_https_errors,
        "proxy": config.proxy,
        "skipped": config.skipped,
    }
    
    # Deserialize
    t = TypeAdapter(Config)
    restored_config = t.validate_python(config_dict)
    
    assert restored_config.ignore_https_errors is True
    assert restored_config.debug is True
    assert restored_config.browser_id == "firefox"
