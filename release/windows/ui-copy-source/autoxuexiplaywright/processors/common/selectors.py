class Selectors:
    LOADING = "div.ant-spin-spinning"


class PointsSelectors:
    POINTS_CARDS = "div.my-points-card"
    POINTS_SPAN = "span.my-points-points"
    CARD_TITLE = POINTS_CARDS.replace("div.", "p.") + "-title"
    CARD_PROGRESS = POINTS_CARDS + "-progress-filled"
    CARD_ACTION = "button, a, [role=\"button\"]"


class TestSelectors:
    TEST_WEEKS = "div.ant-spin-container div.week"
    TEST_WEEK_TITLE = "div.week-title"
    TEST_BTN = "button.button"
    TEST_WEEK_STAT = "span.stat > div"
    TEST_NEXT_PAGE = "li.ant-pagination-next"
    TEST_ITEMS = "div.items > div.item"
    TEST_SPECIAL_POINTS = "span.points"
    TEST_SPECIAL_TITLE = "div.item-title"
    TEST_SPECIAL_TITLE_BEFORE = "span.before"
    TEST_SPECIAL_TITLE_AFTER = "span.after"
    TEST_SPECIAL_SOLUTION = "a.solution"
    TEST_ACTION_ROW = "div.action-row"
    TEST_NEXT_QUESTION_BTN = "button.next-btn"
    TEST_SUBMIT_BTN = "button.submit-btn"
    TEST_SOLUTION = "div.solution"
    TEST_RESULT = "div.practice-result"
    TEST_RESULT_MODAL = "div.ant-modal-wrap"
    TEST_ANALYSIS_ANSWER = "div.q-answer-analysis"
    TEST_VIDEO_PLAYER = "div#videoplayer"
    TEST_VIDEO_PLAY_BTN = "div.outter"
    # Legacy swiper plus the Aliyun captcha currently used by the exam page.
    TEST_CAPTCHA_SWIPER = (
        "div#swiper_valid, div#JS_aliyun-captcha-dialog, "
        "div#JS_aliyun-captcha-main"
    )
    TEST_CAPTCHA_TEXT = (
        "div.scale_text, #aliyunCaptcha-sliding-text, "
        ".aliyunCaptcha-sliding-text"
    )
    TEST_CAPTCHA_SLIDER = (
        "#aliyunCaptcha-sliding-slider, .aliyunCaptcha-sliding-slider, "
        "span.btn_slide, .btn_slide, [class*='slider-handle'], "
        "[class*='slide-btn'], [class*='slide_button']"
    )
    TEST_CAPTCHA_TARGET = (
        "#aliyunCaptcha-sliding-body, .aliyunCaptcha-sliding-body, "
        "div.scale_text, .scale_text, [class*='slider-track'], "
        "[class*='slide-track'], [class*='scale']"
    )
    QUESTION = "div.question"
    QUESTION_TITLE = "div.q-body > div"
    ANSWERS = "div.q-answers"
    BLANK = "div.q-body input, div.q-body textarea, input.blank, input.ant-input, input[type=\"text\"], input:not([type]), textarea, [contenteditable=\"true\"]"
    # Normal choices plus click-to-fill/order tokens.
    ANSWER_ITEM = "div.q-answer.choosable, div.fill-answer.fill-answer-hover"
    TIPS = "span.tips"
    POPOVER = "div.ant-popover-placement-bottom"
    ANSWER_FONT = "div.line-feed font[color=\"red\"]"


class ReadSelectors:
    NEWS_TITLE_SPAN = "section[data-data-id=\"zhaiyao-title\"] span.moreUrl"
    NEWS_LIST = "section[data-data-id=\"textListGrid\"] div.grid-cell"
    NEWS_TITLE_TEXT = "div.text-wrap>span.text"
    NEXT_PAGE = "div.btn:has-text(\">>\")"

    PAGE_PARAGRAPHS = "div.render-detail-content>p,div.videoSet-article-summary>p"

    VIDEO_ENTRANCE = "div[data-data-id=\"tv-station-header\"]>div.right>span.moreText"
    # Maybe a.single.text-ellipsis[data-locations]:has-text("学习电视台")
    VIDEO_LIBRARY = "div.more-wrap p.text"
    VIDEO_TEXT_WRAPPER = "div.textWrapper"
    VIDEO_LINK_ATTRIBUTE = "data-link-target"
    VIDEO_DETAIL_URL_MARKER = "/lgpage/detail/"
    VIDEO_PLAYER = "div.gr-video-player"
    VIDEO_SUBTITLE = "div.videoSet-article-sub-title"
    PLAY_BTN = "div.prism-play-btn"
    REPLAY_BTN = "span.replay-btn"


class LoginSelectors:
    LOGIN_QGLOGIN = "div#qglogin"
    LOGIN_IFRAME = "iframe"
    LOGIN_IMAGE = "div#app img"
    LOGIN_CHECK = "div.point-manage"
