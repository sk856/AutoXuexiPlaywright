"""Tests for filtering non-video cards from the video task."""

from autoxuexiplaywright.processor.tasks.video import VideoTask as _VideoTask


def test_video_detail_route_is_kept() -> None:
    """The supported detail route remains a valid video target."""
    target = "https://www.xuexi.cn/lgpage/detail/index.html?id=123"

    assert _VideoTask._is_video_detail_target(target)  # noqa: S101
    assert not _VideoTask._is_static_article_target(target)  # noqa: S101


def test_static_article_route_is_excluded_from_video_candidates() -> None:
    """Static article cards must not wait for a non-existent media player."""
    target = (
        "https://www.xuexi.cn/0809b8b6ab8a81a4f55ce9cbefa16eff/"
        "ae60b027cb83715fd0eeb7bb2527e88b.html?source=video#title"
    )

    assert not _VideoTask._is_video_detail_target(target)  # noqa: S101
    assert _VideoTask._is_static_article_target(target)  # noqa: S101
