"""Tests for video-card filtering and daily score limits."""

from autoxuexiplaywright.event import Score as _Score
from autoxuexiplaywright.processor import _has_reached_daily_score_limit
from autoxuexiplaywright.processor.tasks.video import VideoTask as _VideoTask


def test_daily_score_limit_stops_remaining_tasks() -> None:
    """A completed daily score must prevent processing more task cards."""
    assert _has_reached_daily_score_limit(_Score(30, 4494))  # noqa: S101
    assert _has_reached_daily_score_limit(_Score(31, 4494))  # noqa: S101
    assert not _has_reached_daily_score_limit(_Score(29, 4494))  # noqa: S101


def test_video_card_url_classification() -> None:
    """Only video detail routes are preferred over static article cards."""
    assert _VideoTask._is_video_detail_target(  # noqa: S101
        "https://www.xuexi.cn/lgpage/detail/index.html?id=123",
    )
    assert not _VideoTask._is_static_article_target(  # noqa: S101
        "https://www.xuexi.cn/lgpage/detail/index.html?id=123",
    )
    assert _VideoTask._is_static_article_target(  # noqa: S101
        "https://www.xuexi.cn/3271716c843e44c7e00e66e38ad6fcd5/"
        "e2c3733327a5a413f63fc980e92f4552.html",
    )
