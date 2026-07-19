from queue import Queue
from typing import TypeVar
from os.path import isfile
from PySide6.QtGui import (
    QAction, QMouseEvent, QPixmap, QIcon, QRegularExpressionValidator,
    QStandardItem, QStandardItemModel, QPainter, QPolygon, QColor,
)
from PySide6.QtCore import (
    QFile, QPoint, QPointF, QSettings, QThread, QTimer, Qt, QRegularExpression,
    QDir, Signal, QEvent,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QVBoxLayout, QInputDialog, QLabel, QMessageBox, QSystemTrayIcon,
    QLineEdit, QPlainTextEdit, QPushButton, QHBoxLayout, QWidget, QComboBox,
    QFileDialog, QGridLayout, QScrollArea, QSizePolicy, QFrame, QSpacerItem,
    QListWidget, QStackedWidget, QMenu
)
# Relative imports
from .objects import SubProcess
from ..defines import APPNAME
from ..languages import get_language_string
from ..storage import get_config_path, get_resources_path
from ..config import get_runtime_config, get_runtime_config_path, serialize_config
from ..processors.common import (
    ANSWER_CONNECTOR, is_processing_paused, request_processing_pause,
    reset_processing_pause, resume_processing,
)
from ..processors.common.answer.ai import fetch_ai_models, test_ai_answer_config
from ..processors.common.answer.utils import split_text, is_valid_answer

_SettingsValueType = TypeVar("_SettingsValueType", int, str, float, bool)
_QObjectType = TypeVar("_QObjectType")

_ICON_FILE_NAME = "icon.png"
_QSS_FILE_NAME = "ui.qss"
# Keep the dashboard surface opaque so underlying windows never bleed through.
_OPACITY = 1.0
_UI_CONFIG_PATH = get_config_path(APPNAME+".ini")
_UI_WIDTH = 960
_UI_HEIGHT = 640
_UI_MIN_WIDTH = 560
_UI_MIN_HEIGHT = 420
_START_BTN_SIZE = 5
_SETTINGS_BTN_SIZE = 2
_NOTIFY_SECS = 5
_SPLIT_TITLE_SIZE = 35
_LAYOUT_MARGIN = 16
_LAYOUT_SPACING = 12
_TITLE_BAR_SPACING = 8
_CONTROL_BTN_SIZE = 28
_VALID_BROWSERS = ["chromium", "firefox", "webkit"]
_VALID_CHANNELS = {
    "msedge": "Microsoft Edge", "msedge-beta": "Microsoft Edge Beta", "msedge-dev": "Microsoft Edge Dev",
    "chrome": "Google Chrome", "chrome-beta": "Google Chrome Beta", "chrome-dev": "Google Chrome Dev",
    "chromium": "Chromium", "chromium-beta": "Chromium Beta", "chromium-dev": "Chromium Dev"}
_PROXY_PRETTY_NAMES = {
    "server": ("ui-config-window-proxy-address", "ui-config-window-proxy-address-tooltip"),
    "username": ("ui-config-window-proxy-username", "ui-config-window-proxy-username-tooltip"),
    "password": ("ui-config-window-proxy-password", "ui-config-window-proxy-password-tooltip"),
    "bypass": ("ui-config-window-proxy-bypass", "ui-config-window-proxy-bypass-tooltip")
}
_AI_ANSWER_PRETTY_NAMES = {
    "base_url": ("ui-config-window-ai-answer-base-url", "ui-config-window-ai-answer-base-url-tooltip"),
    "api_key": ("ui-config-window-ai-answer-api-key", "ui-config-window-ai-answer-api-key-tooltip"),
    "model": ("ui-config-window-ai-answer-model", "ui-config-window-ai-answer-model-tooltip")
}
_LOCAL_CAPTCHA_PRETTY_NAMES = {
    "url": ("ui-config-window-local-captcha-url", "ui-config-window-local-captcha-url-tooltip"),
    "token": ("ui-config-window-local-captcha-token", "ui-config-window-local-captcha-token-tooltip"),
    "timeout": ("ui-config-window-local-captcha-timeout", "ui-config-window-local-captcha-timeout-tooltip"),
}
_READ_HISTORY_RETENTION_DAYS = [3, 7, 15, 30]
_SKIPPED_TASK_GROUPS = {
    "article": (
        "ui-config-window-skipped-article",
        ("我要选读文章",),
    ),
    "video": (
        "ui-config-window-skipped-video",
        ("视听学习", "视听学习时长", "我要视听学习"),
    ),
    "test": (
        "ui-config-window-skipped-test",
        ("每日答题", "趣味答题", "每周答题", "专项答题"),
    ),
}
_PROXY_REGEX = r"(https?|socks[45])://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]"


class _QObjectIDs():
    MAIN = "main"
    TITLE = "title"
    TRAY = "tray"
    CLOSE = "close"
    MINIMIZE = "minimize"
    ONTOP = "ontop"
    LOG_PANEL = "logpanel"
    LOG_PANEL_SCROLL = "logpanelscroll"
    START = "start"
    SETTINGS = "config"
    QR_LABEL = "qrlabel"
    SCORE = "score"
    STATUS = "status"
    SETTINGS_WINDOW = "config_main"
    SETTINGS_WINDOW_TITLE = "config_title"
    SETTINGS_WINDOW_BROWSER_SELECTOR = "browser"
    SETTINGS_WINDOW_CHANNEL_SELECTOR = "channel"
    SETTINGS_WINDOW_EXECUTABLE_INPUT = "browser_executable"
    SETTINGS_WINDOW_SKIPPED_ITEMS = "skipped_items"
    SETTINGS_WINDOW_ASYNC_CHECK = "async"
    SETTINGS_WINDOW_DEBUG_CHECK = "debug"
    SETTINGS_WINDOW_GUI_CHECK = "gui"
    SETTINGS_WINDOW_AUTO_START_CHECK = "auto_start"
    SETTINGS_WINDOW_LANG = "lang"
    SETTINGS_WINDOW_GET_VIDEO = "get_video"
    SETTINGS_WINDOW_READ_HISTORY_RETENTION = "read_history_retention"
    SETTINGS_WINDOW_AI_ANSWER_CHECK = "ai_answer"
    SETTINGS_WINDOW_AI_ANSWER_TEST = "ai_answer_test"
    SETTINGS_WINDOW_AI_ANSWER_FETCH_MODELS = "ai_answer_fetch_models"
    SETTINGS_WINDOW_AI_ANSWER = {
        "base_url": "ai_answer_base_url",
        "api_key": "ai_answer_api_key",
        "model": "ai_answer_model"
    }
    SETTINGS_WINDOW_LOCAL_CAPTCHA_CHECK = "captcha_local_enabled"
    SETTINGS_WINDOW_LOCAL_CAPTCHA = {
        "url": "captcha_local_url",
        "token": "captcha_local_token",
        "timeout": "captcha_local_timeout",
    }
    SETTINGS_WINDOW_PROXY = {
        "server": "proxy_addr",
        "username": "proxy_username",
        "password": "proxy_password",
        "bypass": "proxy_bypass"
    }


class _QWidgetExtended(QWidget):
    def findChildWithProperType(self, type: type[_QObjectType], name: str = "", options: Qt.FindChildOption = Qt.FindChildOption.FindChildrenRecursively) -> _QObjectType | None:
        """Find Child QObject with proper type

        This is for making static type checker happy

        Args:
            type (type[_QObjectType]): The type of target QObject
            name (str, optional): The object name of target QObject. Defaults to "".
            options (Qt.FindChildOption, optional): Find option. Defaults to Qt.FindChildOption.FindChildrenRecursively.

        Returns:
            _QObjectType | None: The target QObject, or None if not found
        """
        # PySide treats an explicitly supplied empty object name as "match
        # only unnamed objects". Omit the name argument when callers want the
        # first child by type; otherwise type-only lookups silently return None.
        result = (
            self.findChild(type)
            if name == ""
            else self.findChild(type, name, options)
        )
        if isinstance(result, type):
            return result


class _QSettingsExtended(QSettings):
    def getValueWithProperType(self, key: str, default: _SettingsValueType) -> _SettingsValueType:
        """Get value with proper type

        This is for making static type checker happy

        Args:
            key (str): The key of the value
            default (_SettingsValueType): The default value if not found

        Returns:
            _SettingsValueType: The value or the default value
        """
        value = self.value(key, default, type(default))
        if isinstance(value, type(default)):
            return value
        return default


class QFramelessWidget(_QWidgetExtended):
    def __init__(self, parent: QWidget | None = None, f: Qt.WindowType = Qt.WindowType.FramelessWindowHint) -> None:
        super().__init__(parent, f)

    def mousePressEvent(self, event: QMouseEvent):
        # Only top-level windows have a windowHandle; form-row widgets
        # also inherit this class and must not call startSystemMove.
        if (
            self.isWindow()
            and not self.isMaximized()
            and not self.isFullScreen()
            and event.button() == Qt.MouseButton.LeftButton
        ):
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        return super().mousePressEvent(event)


class _ColoredArrowComboBox(QComboBox):
    """Editable combo box with an explicitly painted, visible arrow."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._arrowColor = QColor("#6a7bea")
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            # Keep editable text clear of the painted arrow.
            lineEdit.setTextMargins(0, 0, 28, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._arrowColor if self.isEnabled() else QColor("#9da8b8")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        centerX = self.width() - 18
        centerY = self.height() // 2
        painter.drawPolygon(QPolygon([
            QPoint(centerX - 5, centerY - 2),
            QPoint(centerX + 5, centerY - 2),
            QPoint(centerX, centerY + 4),
        ]))
        painter.end()


class _QComboBoxWithLabel(QFramelessWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        self.label = QLabel(self)
        self.label.setObjectName("self-label")
        self.label.setMinimumWidth(110)
        self.comboBox = QComboBox(self)
        self.comboBox.setObjectName("self-combobox")
        self.comboBox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.label, 0)
        layout.addWidget(self.comboBox, 1)
        self.setLayout(layout)
        self.setStyleSheet(parent.styleSheet())


class _QMultiSelectComboBox(QComboBox):
    selectionChanged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._emptyText = ""
        self._keepPopupOpen = False
        self._popupToggleSerial = 0
        self._popupOpening = False
        self._suppressNextPopup = False
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            lineEdit.setReadOnly(True)
            lineEdit.setCursor(Qt.CursorShape.PointingHandCursor)
            lineEdit.installEventFilter(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setModel(QStandardItemModel(self))
        self.view().pressed.connect(self._onItemPressed)  # type: ignore
        self.view().viewport().installEventFilter(self)
        self._pressedRow: int | None = None
        # Editable combo boxes send clicks on the frame to the combo itself,
        # while clicks on the displayed text go to the child line edit. Filter
        # both objects so one deferred-toggle path handles either click target.
        self.installEventFilter(self)
        self.setCurrentIndex(-1)

    def eventFilter(self, watched, event):
        lineEdit = self.lineEdit()
        eventType = event.type()
        if watched is self.view().viewport() and eventType in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
        ) and event.button() == Qt.MouseButton.LeftButton:
            index = self.view().indexAt(event.position().toPoint())
            if eventType == QEvent.Type.MouseButtonPress:
                self._pressedRow = index.row() if index.isValid() else None
                return True
            pressedRow = self._pressedRow
            self._pressedRow = None
            if index.isValid() and pressedRow == index.row():
                self._onItemPressed(index)
            return True
        if (
            watched in (self, lineEdit)
            and eventType in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            )
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Opening the popup on mouse press lets the matching release event
            # reach the newly created popup and close it immediately on some
            # Windows/Qt combinations. Consume the press and open only after
            # the release event has completely finished.
            if eventType == QEvent.Type.MouseButtonPress:
                return True
            self._togglePopup()
            return True
        return super().eventFilter(watched, event)

    def _togglePopup(self):
        """Toggle the popup once, without a stale deferred open reopening it."""
        self._popupToggleSerial += 1
        serial = self._popupToggleSerial
        if self.view().isVisible() or self._popupOpening:
            self._popupOpening = False
            self._keepPopupOpen = False
            # If the native QComboBox handler also receives this click, stop
            # it from immediately showing the popup again during this event.
            self._suppressNextPopup = True
            super().hidePopup()
            self._updateDisplayText()
            QTimer.singleShot(0, self._clearPopupSuppression)
            QTimer.singleShot(0, self._updateDisplayText)
            return

        self._popupOpening = True
        QTimer.singleShot(0, lambda: self._showPopup(serial))

    def _showPopup(self, serial: int):
        if serial != self._popupToggleSerial or not self._popupOpening:
            return
        self._popupOpening = False
        if not self.view().isVisible():
            super().showPopup()

    def _clearPopupSuppression(self):
        self._suppressNextPopup = False

    def showPopup(self):
        if self._suppressNextPopup:
            return
        super().showPopup()

    def setEmptyText(self, text: str):
        self._emptyText = text
        self._updateDisplayText()

    def addCheckItem(self, text: str, data: str):
        item = QStandardItem(text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(data, Qt.ItemDataRole.UserRole)
        model = self.model()
        if isinstance(model, QStandardItemModel):
            model.appendRow(item)
        self._updateDisplayText()

    def selectedData(self) -> list[str]:
        selected: list[str] = []
        model = self.model()
        if not isinstance(model, QStandardItemModel):
            return selected
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, str):
                    selected.append(data)
        return selected

    def setSelectedData(self, values: list[str]):
        selected = set(values)
        model = self.model()
        if not isinstance(model, QStandardItemModel):
            return
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.data(Qt.ItemDataRole.UserRole) in selected
                    else Qt.CheckState.Unchecked
                )
        self._updateDisplayText()

    def _onItemPressed(self, index):
        model = self.model()
        if not isinstance(model, QStandardItemModel):
            return
        item = model.itemFromIndex(index)
        if item is None:
            return
        item.setCheckState(
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._keepPopupOpen = True
        self._updateDisplayText()
        QTimer.singleShot(0, self._updateDisplayText)
        self.selectionChanged.emit()

    def _updateDisplayText(self):
        model = self.model()
        labels: list[str] = []
        if isinstance(model, QStandardItemModel):
            for row in range(model.rowCount()):
                item = model.item(row)
                if item is not None and item.checkState() == Qt.CheckState.Checked:
                    labels.append(item.text())
        # An editable QComboBox otherwise restores the text of its last
        # current index when the popup closes. This control uses check states
        # as its only source of truth, so keep the ordinary current index empty.
        if self.currentIndex() != -1:
            signalsBlocked = self.blockSignals(True)
            self.setCurrentIndex(-1)
            self.blockSignals(signalsBlocked)
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            lineEdit.setText("、".join(labels) if labels else self._emptyText)
            lineEdit.setCursorPosition(0)

    def hidePopup(self):
        if self._keepPopupOpen:
            self._keepPopupOpen = False
            QTimer.singleShot(0, self._updateDisplayText)
            return
        super().hidePopup()
        self._updateDisplayText()
        QTimer.singleShot(0, self._updateDisplayText)


class _AIModelFetchThread(QThread):
    modelsFetched = Signal(bool, list, str)

    def run(self):
        success, models, message = fetch_ai_models()
        self.modelsFetched.emit(success, models, message)


class _QMultiSelectComboBoxWithLabel(QFramelessWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        self.label = QLabel(self)
        self.label.setObjectName("self-label")
        self.label.setMinimumWidth(110)
        self.comboBox = _QMultiSelectComboBox(self)
        self.comboBox.setObjectName("self-combobox")
        self.comboBox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.label, 0)
        layout.addWidget(self.comboBox, 1)
        self.setLayout(layout)
        self.setStyleSheet(parent.styleSheet())


class _QLineEditWithLabelOnly(QFramelessWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        self.label = QLabel(self)
        self.label.setObjectName("self-label")
        self.label.setMinimumWidth(110)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setObjectName("self-lineedit")
        self.lineEdit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.label, 0)
        layout.addWidget(self.lineEdit, 1)
        self.setLayout(layout)
        self.setStyleSheet(parent.styleSheet())


class _QLineEditWithBrowseButton(_QLineEditWithLabelOnly):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.browseBtn = QPushButton(self)
        self.browseBtn.setObjectName("self-browsebtn")
        self.browseBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layout().addWidget(self.browseBtn)
        self.setStyleSheet(parent.styleSheet())


class _QLineEditWithLabelMultiple(QFramelessWidget):
    def __init__(self, parent: QWidget, keys: list[str], split: int = 0):
        super().__init__(parent)
        self._lineEditsWithLabel: dict[str, _QLineEditWithLabelOnly] = {}
        layout = QGridLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        x = 0
        y = 0
        for key in keys:
            currentLineEditWithLabel = _QLineEditWithLabelOnly(self)
            self._lineEditsWithLabel[key] = currentLineEditWithLabel
            currentLineEditWithLabel.lineEdit.setObjectName(key)
            currentLineEditWithLabel.label.setObjectName(key)
            if split > 0 and x > split-1:
                y = y+1
                x = x-split
            layout.addWidget(currentLineEditWithLabel, y, x)
            x = x+1
        self.setLayout(layout)
        self.setStyleSheet(parent.styleSheet())

    def findLabelByKey(self, key: str) -> QLabel | None:
        lineEditWithLabel = self._lineEditsWithLabel.get(key)
        if lineEditWithLabel != None:
            return lineEditWithLabel.label

    def findLineEditByKey(self, key: str) -> QLineEdit | None:
        lineEditWithLabel = self._lineEditsWithLabel.get(key)
        if lineEditWithLabel != None:
            return lineEditWithLabel.lineEdit


class _SettingsSection(QFrame):
    def __init__(self, parent: QWidget, title: str, description: str = ""):
        super().__init__(parent)
        self.setObjectName("settings_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        titleLabel = QLabel(title, self)
        titleLabel.setObjectName("settings_section_title")
        layout.addWidget(titleLabel)
        if description:
            descriptionLabel = QLabel(description, self)
            descriptionLabel.setObjectName("settings_section_description")
            descriptionLabel.setWordWrap(True)
            layout.addWidget(descriptionLabel)
        self.contentLayout = QVBoxLayout()
        self.contentLayout.setContentsMargins(0, 4, 0, 0)
        self.contentLayout.setSpacing(8)
        layout.addLayout(self.contentLayout)


class _SettingsPage(QScrollArea):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("settings_page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(self)
        content.setObjectName("settings_page_content")
        self.contentLayout = QVBoxLayout(content)
        self.contentLayout.setContentsMargins(8, 2, 12, 8)
        self.contentLayout.setSpacing(12)
        self.contentLayout.addStretch(1)
        self.setWidget(content)

    def addSection(self, section: _SettingsSection):
        self.contentLayout.insertWidget(self.contentLayout.count() - 1, section)


class SettingsWindow(QFramelessWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent, parent.windowFlags() | Qt.WindowType.Dialog)
        self.setObjectName(_QObjectIDs.SETTINGS_WINDOW)
        self.setMinimumSize(760, 560)
        self.resize(940, 680)
        config = get_runtime_config()
        self._aiModelFetchThread: _AIModelFetchThread | None = None

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("settings_header")
        headerLayout = QHBoxLayout(header)
        headerLayout.setContentsMargins(24, 18, 18, 16)
        headerLayout.setSpacing(12)
        headingLayout = QVBoxLayout()
        headingLayout.setSpacing(2)
        title = QLabel(get_language_string("ui-config-window-title"), header)
        title.setObjectName(_QObjectIDs.SETTINGS_WINDOW_TITLE)
        subtitle = QLabel(get_language_string("ui-settings-subtitle"), header)
        subtitle.setObjectName("settings_subtitle")
        headingLayout.addWidget(title)
        headingLayout.addWidget(subtitle)
        headerLayout.addLayout(headingLayout, 1)
        closeBtn = QPushButton("×", header)
        closeBtn.setObjectName("dialog_close")
        closeBtn.setFixedSize(32, 32)
        closeBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        closeBtn.setToolTip(get_language_string("ui-close-btn-tooltip"))
        closeBtn.clicked.connect(self.close)  # type: ignore
        headerLayout.addWidget(closeBtn, 0, Qt.AlignmentFlag.AlignTop)
        mainLayout.addWidget(header)

        body = QWidget(self)
        body.setObjectName("settings_body")
        bodyLayout = QHBoxLayout(body)
        bodyLayout.setContentsMargins(16, 14, 16, 14)
        bodyLayout.setSpacing(16)

        navigation = QListWidget(body)
        navigation.setObjectName("settings_navigation")
        navigation.setFixedWidth(164)
        navigation.setSpacing(4)
        navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for label in (
            "ui-settings-nav-general",
            "ui-settings-nav-browser",
            "ui-settings-nav-ai",
            "ui-settings-nav-captcha",
            "ui-settings-nav-network",
        ):
            navigation.addItem(get_language_string(label))
        bodyLayout.addWidget(navigation, 0)

        stack = QStackedWidget(body)
        stack.setObjectName("settings_stack")
        bodyLayout.addWidget(stack, 1)
        mainLayout.addWidget(body, 1)

        generalPage = _SettingsPage(stack)
        browserPage = _SettingsPage(stack)
        aiPage = _SettingsPage(stack)
        captchaPage = _SettingsPage(stack)
        networkPage = _SettingsPage(stack)
        for page in (generalPage, browserPage, aiPage, captchaPage, networkPage):
            stack.addWidget(page)

        # General / task behavior
        runSection = _SettingsSection(
            generalPage,
            get_language_string("ui-settings-section-run"),
            get_language_string("ui-settings-section-run-description"),
        )
        switchGrid = QGridLayout()
        switchGrid.setHorizontalSpacing(18)
        switchGrid.setVerticalSpacing(10)
        switches = (
            (_QObjectIDs.SETTINGS_WINDOW_AUTO_START_CHECK,
             "ui-config-window-auto-start", "ui-config-window-auto-start-tooltip",
             config.auto_start, self._onAutoStartChanged),
            (_QObjectIDs.SETTINGS_WINDOW_GUI_CHECK,
             "ui-config-window-gui", "ui-config-window-gui-tooltip",
             config.gui, self._onGUIModeChanged),
            (_QObjectIDs.SETTINGS_WINDOW_ASYNC_CHECK,
             "ui-config-window-async", "ui-config-window-async-tooltip",
             config.async_mode, self._onAsyncModeChanged),
            (_QObjectIDs.SETTINGS_WINDOW_DEBUG_CHECK,
             "ui-config-window-debug", "ui-config-window-debug-tooltip",
             config.debug, self._onDebugModeChanged),
            (_QObjectIDs.SETTINGS_WINDOW_GET_VIDEO,
             "ui-config-window-get-video", "ui-config-window-get-video-tooltip",
             config.get_video, self._onGetVideoChanged),
        )
        for index, (objectName, labelKey, tooltipKey, checked, callback) in enumerate(switches):
            checkbox = QCheckBox(get_language_string(labelKey), runSection)
            checkbox.setObjectName(objectName)
            checkbox.setToolTip(get_language_string(tooltipKey))
            checkbox.setChecked(checked)
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            checkbox.stateChanged.connect(callback)  # type: ignore
            switchGrid.addWidget(checkbox, index // 2, index % 2)
        runSection.contentLayout.addLayout(switchGrid)
        generalPage.addSection(runSection)

        contentSection = _SettingsSection(
            generalPage,
            get_language_string("ui-settings-section-content"),
            get_language_string("ui-settings-section-content-description"),
        )
        langSetting = _QComboBoxWithLabel(contentSection)
        langSetting.setObjectName(_QObjectIDs.SETTINGS_WINDOW_LANG)
        langSetting.label.setText(get_language_string("ui-config-window-lang-title"))
        langSetting.comboBox.setToolTip(get_language_string(
            "ui-config-window-lang-selector-tooltip"))
        langSetting.comboBox.setObjectName(_QObjectIDs.SETTINGS_WINDOW_LANG)
        langIDs = self._getLangIDs()
        for languageID in langIDs:
            langSetting.comboBox.addItem(languageID, languageID)
        if config.lang in langIDs:
            langSetting.comboBox.setCurrentIndex(langIDs.index(config.lang))
        langSetting.comboBox.currentIndexChanged.connect(  # type: ignore
            self._onLanguageSettingIndexChanged)
        contentSection.contentLayout.addWidget(langSetting)

        readHistoryRetention = _QComboBoxWithLabel(contentSection)
        readHistoryRetention.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_READ_HISTORY_RETENTION)
        readHistoryRetention.label.setText(get_language_string(
            "ui-config-window-read-history-retention-title"))
        readHistoryRetention.comboBox.setToolTip(get_language_string(
            "ui-config-window-read-history-retention-tooltip"))
        readHistoryRetention.comboBox.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_READ_HISTORY_RETENTION)
        for days in _READ_HISTORY_RETENTION_DAYS:
            readHistoryRetention.comboBox.addItem(get_language_string(
                "ui-config-window-read-history-retention-days") % days, days)
        readHistoryRetention.comboBox.setCurrentIndex(
            _READ_HISTORY_RETENTION_DAYS.index(config.read_history_retention_days)
            if config.read_history_retention_days in _READ_HISTORY_RETENTION_DAYS else 1)
        readHistoryRetention.comboBox.currentIndexChanged.connect(  # type: ignore
            self._onReadHistoryRetentionChanged)
        contentSection.contentLayout.addWidget(readHistoryRetention)

        skippedItemsWidget = _QMultiSelectComboBoxWithLabel(contentSection)
        skippedItemsWidget.setObjectName(_QObjectIDs.SETTINGS_WINDOW_SKIPPED_ITEMS)
        skippedItemsWidget.label.setText(get_language_string(
            "ui-config-window-skipped-items-label"))
        skippedItemsWidget.comboBox.setToolTip(get_language_string(
            "ui-config-window-skipped-items-tooltip"))
        skippedItemsWidget.comboBox.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_SKIPPED_ITEMS)
        skippedItemsWidget.comboBox.setEmptyText(get_language_string(
            "ui-config-window-skipped-items-empty"))
        for groupID, (labelKey, _) in _SKIPPED_TASK_GROUPS.items():
            skippedItemsWidget.comboBox.addCheckItem(
                get_language_string(labelKey), groupID)
        configuredSkipped = {
            item for item in (config.skipped or [])
            if isinstance(item, str) and item
        }
        selectedGroups = [
            groupID
            for groupID, (_, taskTitles) in _SKIPPED_TASK_GROUPS.items()
            if any(title in configuredSkipped for title in taskTitles)
        ]
        skippedItemsWidget.comboBox.setSelectedData(selectedGroups)
        skippedItemsWidget.comboBox.selectionChanged.connect(
            self._onSkippedItemsEditFinished)
        contentSection.contentLayout.addWidget(skippedItemsWidget)
        generalPage.addSection(contentSection)

        # Browser page
        browserSection = _SettingsSection(
            browserPage,
            get_language_string("ui-settings-section-browser"),
            get_language_string("ui-settings-section-browser-description"),
        )
        selectorLayout = QHBoxLayout()
        selectorLayout.setSpacing(12)
        browserSelector = _QComboBoxWithLabel(browserSection)
        browserSelector.setObjectName(_QObjectIDs.SETTINGS_WINDOW_BROWSER_SELECTOR)
        browserSelector.label.setText(get_language_string(
            "ui-config-window-browser-title"))
        browserSelector.comboBox.setToolTip(get_language_string(
            "ui-config-window-browser-selector-tooltip"))
        browserSelector.comboBox.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_BROWSER_SELECTOR)
        for browserID in _VALID_BROWSERS:
            browserSelector.comboBox.addItem(browserID.title(), browserID)
        browserSelector.comboBox.setCurrentIndex(_VALID_BROWSERS.index(config.browser_id))
        browserSelector.comboBox.currentIndexChanged.connect(  # type: ignore
            self._onBrowserSelectorIndexChanged)
        selectorLayout.addWidget(browserSelector, 1)

        channelSelector = _QComboBoxWithLabel(browserSection)
        channelSelector.setObjectName(_QObjectIDs.SETTINGS_WINDOW_CHANNEL_SELECTOR)
        channelSelector.label.setText(get_language_string(
            "ui-config-window-channel-title"))
        channelSelector.comboBox.setToolTip(get_language_string(
            "ui-config-window-channel-selector-tooltip"))
        channelSelector.comboBox.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_CHANNEL_SELECTOR)
        for channelID, channelName in _VALID_CHANNELS.items():
            channelSelector.comboBox.addItem(channelName, channelID)
        if config.browser_channel is not None:
            channelSelector.comboBox.setCurrentIndex(
                list(_VALID_CHANNELS.keys()).index(config.browser_channel))
        channelSelector.setEnabled(
            (not bool(browserSelector.comboBox.currentIndex()))
            or config.browser_channel is not None)
        channelSelector.comboBox.currentIndexChanged.connect(  # type: ignore
            self._onChannelSelectorIndexChanged)
        selectorLayout.addWidget(channelSelector, 1)
        browserSection.contentLayout.addLayout(selectorLayout)

        executableSettingWidget = _QLineEditWithBrowseButton(browserSection)
        executableSettingWidget.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_EXECUTABLE_INPUT)
        executableSettingWidget.label.setText(get_language_string(
            "ui-config-window-executable-label"))
        executableSettingWidget.lineEdit.setToolTip(get_language_string(
            "ui-config-window-executable-tooltip"))
        executableSettingWidget.lineEdit.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_EXECUTABLE_INPUT)
        if config.executable_path is not None:
            executableSettingWidget.lineEdit.setText(config.executable_path)
        executableSettingWidget.lineEdit.editingFinished.connect(  # type: ignore
            self._onBrowserExecutableEditFinished)
        executableSettingWidget.browseBtn.setText(get_language_string(
            "ui-config-window-executable-browse-text"))
        executableSettingWidget.browseBtn.setToolTip(get_language_string(
            "ui-config-window-executable-browse-tooltip"))
        executableSettingWidget.browseBtn.clicked.connect(  # type: ignore
            self._onBrowserExecutableBrowseButtonClicked)
        browserSection.contentLayout.addWidget(executableSettingWidget)
        browserPage.addSection(browserSection)

        browserHintSection = _SettingsSection(
            browserPage,
            get_language_string("ui-settings-section-browser-hint"),
            get_language_string("ui-settings-section-browser-hint-description"),
        )
        browserPage.addSection(browserHintSection)

        # AI page
        aiSection = _SettingsSection(
            aiPage,
            get_language_string("ui-settings-section-ai"),
            get_language_string("ui-settings-section-ai-description"),
        )
        aiAnswer = QCheckBox(get_language_string(
            "ui-config-window-ai-answer"), aiSection)
        aiAnswer.setToolTip(get_language_string(
            "ui-config-window-ai-answer-tooltip"))
        aiAnswer.setObjectName(_QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_CHECK)
        aiAnswer.setChecked(config.ai_answer_enabled)
        aiAnswer.setCursor(Qt.CursorShape.PointingHandCursor)
        aiAnswer.stateChanged.connect(self._onAIAnswerChanged)  # type: ignore
        aiSection.contentLayout.addWidget(aiAnswer)

        aiAnswerSetting = _QLineEditWithLabelMultiple(
            aiSection, ["base_url", "api_key"], 1)
        for key in ("base_url", "api_key"):
            label = aiAnswerSetting.findLabelByKey(key)
            if label is not None:
                label.setText(get_language_string(_AI_ANSWER_PRETTY_NAMES[key][0]))
            lineEdit = aiAnswerSetting.findLineEditByKey(key)
            if lineEdit is not None:
                lineEdit.setToolTip(get_language_string(
                    _AI_ANSWER_PRETTY_NAMES[key][1]))
                lineEdit.setObjectName(_QObjectIDs.SETTINGS_WINDOW_AI_ANSWER[key])
                lineEdit.editingFinished.connect(  # type: ignore
                    self._onAIAnswerSettingEditFinished)
        aiBaseUrlLineEdit = aiAnswerSetting.findLineEditByKey("base_url")
        if aiBaseUrlLineEdit is not None:
            aiBaseUrlLineEdit.setText(config.ai_answer_base_url)
        aiApiKeyLineEdit = aiAnswerSetting.findLineEditByKey("api_key")
        if aiApiKeyLineEdit is not None:
            aiApiKeyLineEdit.setText(config.ai_answer_api_key)
            aiApiKeyLineEdit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        aiSection.contentLayout.addWidget(aiAnswerSetting)

        aiModelSetting = _QComboBoxWithLabel(aiSection)
        # Replace the generic combo with the AI model combo that paints its
        # arrow explicitly; the generic QSS hides the platform arrow.
        genericModelCombo = aiModelSetting.comboBox
        modelCombo = _ColoredArrowComboBox(aiModelSetting)
        modelCombo.setObjectName(_QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["model"])
        modelCombo.setSizePolicy(genericModelCombo.sizePolicy())
        aiModelSetting.layout().replaceWidget(genericModelCombo, modelCombo)
        genericModelCombo.deleteLater()
        aiModelSetting.comboBox = modelCombo
        aiModelSetting.setObjectName(_QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["model"])
        aiModelSetting.label.setText(get_language_string(
            _AI_ANSWER_PRETTY_NAMES["model"][0]))
        aiModelSetting.comboBox.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["model"])
        aiModelSetting.comboBox.setToolTip(get_language_string(
            _AI_ANSWER_PRETTY_NAMES["model"][1]))
        aiModelSetting.comboBox.setEditable(True)
        aiModelSetting.comboBox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        aiModelSetting.comboBox.setDuplicatesEnabled(False)
        aiModelSetting.comboBox.setCurrentText(config.ai_answer_model)
        aiModelSetting.comboBox.currentTextChanged.connect(  # type: ignore
            lambda _text: self._onAIAnswerSettingEditFinished())
        if aiModelSetting.comboBox.lineEdit() is not None:
            aiModelSetting.comboBox.lineEdit().editingFinished.connect(  # type: ignore
                self._onAIAnswerSettingEditFinished)
        aiSection.contentLayout.addWidget(aiModelSetting)

        aiButtonLayout = QHBoxLayout()
        aiButtonLayout.addStretch(1)
        aiFetchModelsBtn = QPushButton(get_language_string(
            "ui-config-window-ai-answer-fetch-models"), aiSection)
        aiFetchModelsBtn.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_FETCH_MODELS)
        aiFetchModelsBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        aiFetchModelsBtn.setToolTip(get_language_string(
            "ui-config-window-ai-answer-fetch-models-tooltip"))
        aiFetchModelsBtn.clicked.connect(  # type: ignore
            self._onFetchAIModelsButtonClicked)
        aiButtonLayout.addWidget(aiFetchModelsBtn)
        aiAnswerTestBtn = QPushButton(get_language_string(
            "ui-config-window-ai-answer-test"), aiSection)
        aiAnswerTestBtn.setObjectName(_QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_TEST)
        aiAnswerTestBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        aiAnswerTestBtn.setToolTip(get_language_string(
            "ui-config-window-ai-answer-test-tooltip"))
        aiAnswerTestBtn.clicked.connect(  # type: ignore
            self._onAIAnswerTestButtonClicked)
        aiButtonLayout.addWidget(aiAnswerTestBtn)
        aiSection.contentLayout.addLayout(aiButtonLayout)
        aiPage.addSection(aiSection)

        # Captcha page
        captchaSection = _SettingsSection(
            captchaPage,
            get_language_string("ui-settings-section-captcha"),
            get_language_string("ui-settings-section-captcha-description"),
        )
        localCaptchaEnabled = QCheckBox(get_language_string(
            "ui-config-window-local-captcha"), captchaSection)
        localCaptchaEnabled.setToolTip(get_language_string(
            "ui-config-window-local-captcha-tooltip"))
        localCaptchaEnabled.setObjectName(
            _QObjectIDs.SETTINGS_WINDOW_LOCAL_CAPTCHA_CHECK)
        localCaptchaEnabled.setChecked(config.captcha_local_enabled)
        localCaptchaEnabled.setCursor(Qt.CursorShape.PointingHandCursor)
        localCaptchaEnabled.stateChanged.connect(  # type: ignore
            self._onLocalCaptchaChanged)
        captchaSection.contentLayout.addWidget(localCaptchaEnabled)

        localCaptchaSetting = _QLineEditWithLabelMultiple(
            captchaSection, list(_LOCAL_CAPTCHA_PRETTY_NAMES.keys()), 1)
        for key in _LOCAL_CAPTCHA_PRETTY_NAMES:
            label = localCaptchaSetting.findLabelByKey(key)
            if label is not None:
                label.setText(get_language_string(
                    _LOCAL_CAPTCHA_PRETTY_NAMES[key][0]))
            lineEdit = localCaptchaSetting.findLineEditByKey(key)
            if lineEdit is not None:
                lineEdit.setToolTip(get_language_string(
                    _LOCAL_CAPTCHA_PRETTY_NAMES[key][1]))
                lineEdit.setObjectName(
                    _QObjectIDs.SETTINGS_WINDOW_LOCAL_CAPTCHA[key])
                lineEdit.editingFinished.connect(  # type: ignore
                    self._onLocalCaptchaSettingEditFinished)
        localCaptchaUrl = localCaptchaSetting.findLineEditByKey("url")
        if localCaptchaUrl is not None:
            localCaptchaUrl.setText(config.captcha_local_url)
        localCaptchaToken = localCaptchaSetting.findLineEditByKey("token")
        if localCaptchaToken is not None:
            localCaptchaToken.setText(config.captcha_local_token)
            localCaptchaToken.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        localCaptchaTimeout = localCaptchaSetting.findLineEditByKey("timeout")
        if localCaptchaTimeout is not None:
            localCaptchaTimeout.setText(str(config.captcha_local_timeout_secs))
        captchaSection.contentLayout.addWidget(localCaptchaSetting)
        captchaPage.addSection(captchaSection)

        # Network page
        proxySection = _SettingsSection(
            networkPage,
            get_language_string("ui-settings-section-network"),
            get_language_string("ui-settings-section-network-description"),
        )
        proxySetting = _QLineEditWithLabelMultiple(
            proxySection, list(_PROXY_PRETTY_NAMES.keys()), 1)
        for key in _PROXY_PRETTY_NAMES:
            label = proxySetting.findLabelByKey(key)
            if label is not None:
                label.setText(get_language_string(_PROXY_PRETTY_NAMES[key][0]))
            lineEdit = proxySetting.findLineEditByKey(key)
            if lineEdit is not None:
                lineEdit.setToolTip(get_language_string(
                    _PROXY_PRETTY_NAMES[key][1]))
                lineEdit.setObjectName(_QObjectIDs.SETTINGS_WINDOW_PROXY[key])
                lineEdit.editingFinished.connect(  # type: ignore
                    self._onProxySettingEditFinished)
                if config.proxy is not None:
                    value = config.proxy.get(key)
                    if isinstance(value, str):
                        lineEdit.setText(value)
        serverLineEdit = proxySetting.findLineEditByKey("server")
        if serverLineEdit is not None:
            serverLineEdit.setValidator(
                QRegularExpressionValidator(QRegularExpression(_PROXY_REGEX)))
        passwordLineEdit = proxySetting.findLineEditByKey("password")
        if passwordLineEdit is not None:
            passwordLineEdit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        proxySection.contentLayout.addWidget(proxySetting)
        networkPage.addSection(proxySection)

        navigation.currentRowChanged.connect(stack.setCurrentIndex)  # type: ignore
        navigation.setCurrentRow(0)

        footer = QFrame(self)
        footer.setObjectName("settings_footer")
        footerLayout = QHBoxLayout(footer)
        footerLayout.setContentsMargins(20, 12, 20, 16)
        footerLayout.setSpacing(10)
        footerHint = QLabel(get_language_string("ui-settings-footer-hint"), footer)
        footerHint.setObjectName("settings_footer_hint")
        footerLayout.addWidget(footerHint, 1)
        cancelBtn = QPushButton(get_language_string(
            "ui-config-window-cancel"), footer)
        cancelBtn.setObjectName("config_cancel")
        cancelBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancelBtn.setToolTip(get_language_string(
            "ui-config-window-cancel-tooltip"))
        cancelBtn.clicked.connect(self._onCancelButtonClicked)  # type: ignore
        footerLayout.addWidget(cancelBtn)
        saveBtn = QPushButton(get_language_string(
            "ui-config-window-save"), footer)
        saveBtn.setObjectName("config_save")
        saveBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        saveBtn.setToolTip(get_language_string(
            "ui-config-window-save-tooltip"))
        saveBtn.clicked.connect(self._onSaveButtonClicked)  # type: ignore
        footerLayout.addWidget(saveBtn)
        mainLayout.addWidget(footer)

        self.setStyleSheet(parent.styleSheet())

    def _getLangIDs(self) -> list[str]:
        langSuffix = ".json"
        langDir = QDir(get_resources_path("lang"))
        langDir.setNameFilters(["*"+langSuffix])
        return [langFile.replace(langSuffix, "")
                for langFile in langDir.entryList()]

    def _onBrowserSelectorIndexChanged(self, index: int):
        browserSelector = self.findChildWithProperType(
            _QComboBoxWithLabel, _QObjectIDs.SETTINGS_WINDOW_BROWSER_SELECTOR)
        if browserSelector != None:
            config = get_runtime_config()
            config.browser_id = browserSelector.comboBox.currentData()
        channelSelector = self.findChildWithProperType(
            _QComboBoxWithLabel, _QObjectIDs.SETTINGS_WINDOW_CHANNEL_SELECTOR)
        if channelSelector != None:
            channelSelector.setEnabled(not bool(index))
            self._onChannelSelectorIndexChanged(index)

    def _onChannelSelectorIndexChanged(self, index: int):
        channelSelector = self.findChildWithProperType(
            _QComboBoxWithLabel, _QObjectIDs.SETTINGS_WINDOW_CHANNEL_SELECTOR)
        if channelSelector != None:
            config = get_runtime_config()
            if channelSelector.isEnabled():
                config.browser_channel = channelSelector.comboBox.currentData()
            else:
                config.browser_channel = None

    def _onBrowserExecutableEditFinished(self):
        executableSettingWidget = self.findChildWithProperType(
            _QLineEditWithBrowseButton,
            _QObjectIDs.SETTINGS_WINDOW_EXECUTABLE_INPUT)
        if executableSettingWidget is not None:
            config = get_runtime_config()
            path = executableSettingWidget.lineEdit.text().strip()
            executableSettingWidget.lineEdit.setText(path)
            config.executable_path = path if isfile(path) else None

    def _onBrowserExecutableBrowseButtonClicked(self):
        executableSettingWidget = self.findChildWithProperType(
            _QLineEditWithBrowseButton,
            _QObjectIDs.SETTINGS_WINDOW_EXECUTABLE_INPUT)
        if executableSettingWidget is None:
            return

        currentPath = executableSettingWidget.lineEdit.text().strip()
        result: str = QFileDialog.getOpenFileName(  # type: ignore
            self,
            get_language_string("ui-config-window-executable-browse-title"),
            currentPath,
            get_language_string("ui-config-window-executable-filter"),
        )[0]
        # Cancelling the dialog must preserve the existing setting.
        if result == "":
            return
        executableSettingWidget.lineEdit.setText(result)
        get_runtime_config().executable_path = result

    def _onSkippedItemsEditFinished(self):
        skippedItemsWidget = self.findChildWithProperType(
            _QMultiSelectComboBoxWithLabel,
            _QObjectIDs.SETTINGS_WINDOW_SKIPPED_ITEMS,
        )
        if skippedItemsWidget is None:
            return

        skipped: list[str] = []
        for groupID in skippedItemsWidget.comboBox.selectedData():
            group = _SKIPPED_TASK_GROUPS.get(groupID)
            if group is not None:
                skipped.extend(group[1])
        get_runtime_config().skipped = list(dict.fromkeys(skipped))

    def _onAsyncModeChanged(self, state: Qt.CheckState):
        get_runtime_config().async_mode = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onDebugModeChanged(self, state: Qt.CheckState):
        get_runtime_config().debug = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onGUIModeChanged(self, state: Qt.CheckState):
        get_runtime_config().gui = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onAutoStartChanged(self, state: Qt.CheckState):
        get_runtime_config().auto_start = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onGetVideoChanged(self, state: Qt.CheckState):
        get_runtime_config().get_video = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onReadHistoryRetentionChanged(self, index: int):
        readHistoryRetention = self.findChildWithProperType(
            _QComboBoxWithLabel, _QObjectIDs.SETTINGS_WINDOW_READ_HISTORY_RETENTION)
        if readHistoryRetention != None:
            days = readHistoryRetention.comboBox.itemData(index)
            if days in _READ_HISTORY_RETENTION_DAYS:
                get_runtime_config().read_history_retention_days = days

    def _onAIAnswerChanged(self, state: Qt.CheckState):
        get_runtime_config().ai_answer_enabled = Qt.CheckState(state) == Qt.CheckState.Checked

    def _onAIAnswerSettingEditFinished(self):
        config = get_runtime_config()
        baseUrlLineEdit = self.findChildWithProperType(
            QLineEdit, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["base_url"], Qt.FindChildOption.FindChildrenRecursively)
        if baseUrlLineEdit != None:
            config.ai_answer_base_url = baseUrlLineEdit.text().strip()
        apiKeyLineEdit = self.findChildWithProperType(
            QLineEdit, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["api_key"], Qt.FindChildOption.FindChildrenRecursively)
        if apiKeyLineEdit != None:
            config.ai_answer_api_key = apiKeyLineEdit.text().strip()
        modelComboBox = self.findChildWithProperType(
            QComboBox, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["model"],
            Qt.FindChildOption.FindChildrenRecursively)
        if modelComboBox is not None:
            config.ai_answer_model = modelComboBox.currentText().strip()

    def _onFetchAIModelsButtonClicked(self):
        self._onAIAnswerSettingEditFinished()
        if self._aiModelFetchThread is not None and self._aiModelFetchThread.isRunning():
            return
        fetchButton = self.findChildWithProperType(
            QPushButton, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_FETCH_MODELS)
        if fetchButton is not None:
            fetchButton.setEnabled(False)
            fetchButton.setText(get_language_string(
                "ui-config-window-ai-answer-fetch-models-loading"))
        thread = _AIModelFetchThread(self)
        self._aiModelFetchThread = thread
        thread.modelsFetched.connect(self._onAIModelsFetched)  # type: ignore
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(  # type: ignore
            lambda: self._clearAIModelFetchThread(thread))
        thread.start()

    def _clearAIModelFetchThread(self, thread: _AIModelFetchThread):
        if self._aiModelFetchThread is thread:
            self._aiModelFetchThread = None

    def _onAIModelsFetched(self, success: bool, models: list, message: str):
        fetchButton = self.findChildWithProperType(
            QPushButton, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_FETCH_MODELS)
        if fetchButton is not None:
            fetchButton.setEnabled(True)
            fetchButton.setText(get_language_string(
                "ui-config-window-ai-answer-fetch-models"))
        if success:
            modelComboBox = self.findChildWithProperType(
                QComboBox, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER["model"],
                Qt.FindChildOption.FindChildrenRecursively)
            if modelComboBox is not None:
                currentModel = modelComboBox.currentText().strip()
                modelComboBox.blockSignals(True)
                modelComboBox.clear()
                for model in models:
                    modelComboBox.addItem(model, model)
                if currentModel and currentModel not in models:
                    modelComboBox.insertItem(0, currentModel, currentModel)
                modelComboBox.setCurrentText(
                    currentModel if currentModel else models[0])
                modelComboBox.blockSignals(False)
                self._onAIAnswerSettingEditFinished()
            QMessageBox.information(
                self, get_language_string("ui-config-window-ai-answer-fetch-models-title"), message)
        else:
            QMessageBox.warning(
                self, get_language_string("ui-config-window-ai-answer-fetch-models-title"), message)

    def _onLocalCaptchaChanged(self, state: Qt.CheckState):
        get_runtime_config().captcha_local_enabled = (
            Qt.CheckState(state) == Qt.CheckState.Checked)

    def _onLocalCaptchaSettingEditFinished(self):
        config = get_runtime_config()
        urlLineEdit = self.findChildWithProperType(
            QLineEdit, _QObjectIDs.SETTINGS_WINDOW_LOCAL_CAPTCHA["url"],
            Qt.FindChildOption.FindChildrenRecursively)
        if urlLineEdit != None:
            config.captcha_local_url = urlLineEdit.text().strip()
        tokenLineEdit = self.findChildWithProperType(
            QLineEdit, _QObjectIDs.SETTINGS_WINDOW_LOCAL_CAPTCHA["token"],
            Qt.FindChildOption.FindChildrenRecursively)
        if tokenLineEdit != None:
            config.captcha_local_token = tokenLineEdit.text().strip()
        timeoutLineEdit = self.findChildWithProperType(
            QLineEdit, _QObjectIDs.SETTINGS_WINDOW_LOCAL_CAPTCHA["timeout"],
            Qt.FindChildOption.FindChildrenRecursively)
        if timeoutLineEdit != None:
            try:
                timeout = float(timeoutLineEdit.text().strip())
            except ValueError:
                timeout = 10.0
            config.captcha_local_timeout_secs = max(1.0, min(timeout, 120.0))
            timeoutLineEdit.setText(str(config.captcha_local_timeout_secs))

    def _onProxySettingEditFinished(self):
        proxy: dict[str, str] = {}
        for key, objectName in _QObjectIDs.SETTINGS_WINDOW_PROXY.items():
            lineEdit = self.findChildWithProperType(
                QLineEdit, objectName, Qt.FindChildOption.FindChildrenRecursively)
            if lineEdit is not None:
                value = lineEdit.text().strip()
                if value:
                    proxy[key] = value
        get_runtime_config().proxy = proxy or None  # type: ignore

    def _onAIAnswerTestButtonClicked(self):
        self._onAIAnswerSettingEditFinished()
        testButton = self.findChildWithProperType(
            QPushButton, _QObjectIDs.SETTINGS_WINDOW_AI_ANSWER_TEST)
        if testButton != None:
            testButton.setEnabled(False)
            testButton.setText(get_language_string(
                "ui-config-window-ai-answer-testing"))
        success, message = test_ai_answer_config()
        if testButton != None:
            testButton.setEnabled(True)
            testButton.setText(get_language_string(
                "ui-config-window-ai-answer-test"))
        if success:
            QMessageBox.information(
                self, get_language_string("ui-config-window-ai-answer-test-title"), message)
        else:
            QMessageBox.warning(
                self, get_language_string("ui-config-window-ai-answer-test-title"), message)

    def _onLanguageSettingIndexChanged(self, index: int):
        languageSetting = self.findChildWithProperType(
            _QComboBoxWithLabel, _QObjectIDs.SETTINGS_WINDOW_LANG)
        if languageSetting != None:
            get_runtime_config().lang = self._getLangIDs()[index]

    def _onSaveButtonClicked(self):
        # Flush fields that may still own keyboard focus before writing.
        self._onBrowserExecutableEditFinished()
        self._onSkippedItemsEditFinished()
        self._onAIAnswerSettingEditFinished()
        self._onLocalCaptchaSettingEditFinished()
        self._onProxySettingEditFinished()

        path = get_runtime_config_path() or get_config_path("config.json")
        try:
            serialize_config(get_runtime_config(), path)
        except OSError as error:
            QMessageBox.warning(
                self,
                get_language_string("ui-config-window-save-error-title"),
                get_language_string("ui-config-window-save-error") % error,
            )
            return

        footerHint = self.findChildWithProperType(
            QLabel, "settings_footer_hint")
        if footerHint is not None:
            defaultHint = get_language_string("ui-settings-footer-hint")
            footerHint.setText(
                get_language_string("ui-config-window-save-success") % path)
            QTimer.singleShot(3500, lambda: footerHint.setText(defaultHint))

    def _onCancelButtonClicked(self):
        self.close()


class MainWindow(QFramelessWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(get_resources_path(_ICON_FILE_NAME)))
        self.setWindowTitle(APPNAME)
        self.setWindowOpacity(_OPACITY)
        self.setObjectName(_QObjectIDs.MAIN)
        # The previous fixed 960x640 logical size can exceed a high-DPI
        # desktop's available geometry, leaving the right side of the
        # dashboard off-screen.  Fit the initial window to the active screen
        # while keeping a usable lower bound for the responsive layout.
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is None:
            target_width, target_height = _UI_WIDTH, _UI_HEIGHT
            min_width, min_height = _UI_MIN_WIDTH, _UI_MIN_HEIGHT
            x, y = 0, 0
        else:
            target_width = min(_UI_WIDTH, max(480, available.width() - 32))
            target_height = min(_UI_HEIGHT, max(360, available.height() - 32))
            min_width = min(_UI_MIN_WIDTH, target_width)
            min_height = min(_UI_MIN_HEIGHT, target_height)
            settings = _QSettingsExtended(
                _UI_CONFIG_PATH, QSettings.Format.IniFormat, self)
            saved_x = settings.getValueWithProperType("UI/x", available.x())
            saved_y = settings.getValueWithProperType("UI/y", available.y())
            x = min(max(saved_x, available.x()), available.x() + available.width() - target_width)
            y = min(max(saved_y, available.y()), available.y() + available.height() - target_height)

        self.setMinimumSize(min_width, min_height)
        self.resize(target_width, target_height)
        self.move(x, y)
        settings = _QSettingsExtended(
            _UI_CONFIG_PATH, QSettings.Format.IniFormat, self)
        if settings.getValueWithProperType("UI/ontop", False):
            self.setWindowFlags(self.windowFlags()
                                | Qt.WindowType.WindowStaysOnTopHint)

        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip(APPNAME)
        tray.setObjectName(_QObjectIDs.TRAY)
        tray.activated.connect(self._onTrayActivated)  # type: ignore

        # Keep tray actions on the main window so they share the same task
        # thread and configuration state as the visible buttons.
        trayMenu = QMenu(self)
        self._trayStartAction = QAction(get_language_string(
            "ui-tray-action-start"), trayMenu)
        self._trayStartAction.triggered.connect(self._onTrayStartClicked)
        trayMenu.addAction(self._trayStartAction)
        self._trayPauseAction = QAction(get_language_string(
            "ui-tray-action-pause"), trayMenu)
        self._trayPauseAction.triggered.connect(self._onTrayPauseClicked)
        trayMenu.addAction(self._trayPauseAction)
        trayMenu.addSeparator()
        self._traySettingsAction = QAction(get_language_string(
            "ui-tray-action-settings"), trayMenu)
        self._traySettingsAction.triggered.connect(self._onSettingsBtnClicked)
        trayMenu.addAction(self._traySettingsAction)
        trayMenu.addSeparator()
        self._trayExitAction = QAction(get_language_string(
            "ui-tray-action-exit"), trayMenu)
        self._trayExitAction.triggered.connect(self._onTrayExitClicked)
        trayMenu.addAction(self._trayExitAction)
        tray.setContextMenu(trayMenu)
        self._updateTrayActions()

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(20, 18, 20, 20)
        mainLayout.setSpacing(14)

        # Header / draggable title area
        header = QFrame(self)
        header.setObjectName("main_header")
        headerLayout = QHBoxLayout(header)
        headerLayout.setContentsMargins(2, 0, 0, 0)
        headerLayout.setSpacing(12)
        logo = QLabel(header)
        logo.setObjectName("app_logo")
        logo.setFixedSize(38, 38)
        logoPixmap = QPixmap(get_resources_path(_ICON_FILE_NAME)).scaled(
            34, 34,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo.setPixmap(logoPixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headerLayout.addWidget(logo)

        brandLayout = QVBoxLayout()
        brandLayout.setSpacing(0)
        title = QLabel(APPNAME, header)
        title.setObjectName(_QObjectIDs.TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        subtitle = QLabel(get_language_string("ui-main-subtitle"), header)
        subtitle.setObjectName("main_subtitle")
        brandLayout.addWidget(title)
        brandLayout.addWidget(subtitle)
        headerLayout.addLayout(brandLayout, 1)

        controlLayout = QHBoxLayout()
        controlLayout.setSpacing(7)
        onTopCheck = QCheckBox("", header)
        onTopCheck.setObjectName(_QObjectIDs.ONTOP)
        onTopCheck.setFixedSize(_CONTROL_BTN_SIZE, _CONTROL_BTN_SIZE)
        onTopCheck.setCursor(Qt.CursorShape.PointingHandCursor)
        onTopCheck.setToolTip(get_language_string("ui-ontop-checkbox-tooltip"))
        onTopCheck.setAccessibleName(
            get_language_string("ui-ontop-checkbox-tooltip"))
        onTopCheck.setChecked(settings.getValueWithProperType("UI/ontop", False))
        onTopCheck.stateChanged.connect(self._onOnTopStateChanged)  # type: ignore
        controlLayout.addWidget(onTopCheck)

        minimizeBtn = QPushButton("", header)
        minimizeBtn.setObjectName(_QObjectIDs.MINIMIZE)
        minimizeBtn.setFixedSize(_CONTROL_BTN_SIZE, _CONTROL_BTN_SIZE)
        minimizeBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        minimizeBtn.setToolTip(get_language_string("ui-minimize-btn-tooltip"))
        minimizeBtn.setAccessibleName(get_language_string("ui-minimize-btn-tooltip"))
        minimizeBtn.clicked.connect(self.showMinimized)  # type: ignore
        controlLayout.addWidget(minimizeBtn)

        closeBtn = QPushButton("", header)
        closeBtn.setObjectName(_QObjectIDs.CLOSE)
        closeBtn.setFixedSize(_CONTROL_BTN_SIZE, _CONTROL_BTN_SIZE)
        closeBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        closeBtn.setToolTip(get_language_string("ui-close-btn-tooltip"))
        closeBtn.setAccessibleName(get_language_string("ui-close-btn-tooltip"))
        closeBtn.clicked.connect(self.close)  # type: ignore
        controlLayout.addWidget(closeBtn)
        headerLayout.addLayout(controlLayout)
        mainLayout.addWidget(header)

        # Dashboard summary
        dashboardLayout = QHBoxLayout()
        dashboardLayout.setSpacing(12)
        statusCard = QFrame(self)
        statusCard.setObjectName("dashboard_card")
        statusCardLayout = QHBoxLayout(statusCard)
        statusCardLayout.setContentsMargins(18, 14, 18, 14)
        statusCardLayout.setSpacing(12)
        statusIcon = QLabel("●", statusCard)
        statusIcon.setObjectName("status_indicator")
        statusIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        statusCardLayout.addWidget(statusIcon)
        statusTextLayout = QVBoxLayout()
        statusTextLayout.setSpacing(2)
        statusCaption = QLabel(get_language_string("ui-main-status-caption"), statusCard)
        statusCaption.setObjectName("card_caption")
        status = QLabel(get_language_string("ui-main-status-ready"), statusCard)
        status.setObjectName(_QObjectIDs.STATUS)
        status.setWordWrap(True)
        statusTextLayout.addWidget(statusCaption)
        statusTextLayout.addWidget(status)
        statusCardLayout.addLayout(statusTextLayout, 1)
        dashboardLayout.addWidget(statusCard, 5)

        scoreCard = QFrame(self)
        scoreCard.setObjectName("score_card")
        scoreLayout = QVBoxLayout(scoreCard)
        scoreLayout.setContentsMargins(18, 12, 18, 12)
        scoreLayout.setSpacing(4)
        scoreCaption = QLabel(get_language_string("ui-main-score-caption"), scoreCard)
        scoreCaption.setObjectName("card_caption")
        score = QLabel(get_language_string("ui-score-text") % (0, 0), scoreCard)
        score.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        score.setObjectName(_QObjectIDs.SCORE)
        score.setMinimumWidth(120)
        scoreLayout.addWidget(scoreCaption)
        scoreLayout.addWidget(score)
        dashboardLayout.addWidget(scoreCard, 3)
        mainLayout.addLayout(dashboardLayout)

        # Log workspace
        logCard = QFrame(self)
        logCard.setObjectName("log_card")
        logCardLayout = QVBoxLayout(logCard)
        logCardLayout.setContentsMargins(0, 0, 0, 0)
        logCardLayout.setSpacing(0)
        logHeader = QFrame(logCard)
        logHeader.setObjectName("log_header")
        logHeaderLayout = QHBoxLayout(logHeader)
        logHeaderLayout.setContentsMargins(16, 10, 16, 10)
        logTitle = QLabel(get_language_string("ui-main-log-title"), logHeader)
        logTitle.setObjectName("log_title")
        logHeaderLayout.addWidget(logTitle)
        logHeaderLayout.addStretch(1)
        logHint = QLabel(get_language_string("ui-main-log-hint"), logHeader)
        logHint.setObjectName("log_hint")
        logHeaderLayout.addWidget(logHint)
        logCardLayout.addWidget(logHeader)

        logPanel = QPlainTextEdit(logCard)
        logPanel.setObjectName(_QObjectIDs.LOG_PANEL)
        logPanel.setToolTip(get_language_string("ui-logpanel-default-tooltip"))
        logPanel.setReadOnly(True)
        logPanel.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        logPanel.setMinimumHeight(140)
        logPanel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        logPanel.verticalScrollBar().setObjectName(_QObjectIDs.LOG_PANEL_SCROLL)
        logCardLayout.addWidget(logPanel, 1)
        mainLayout.addWidget(logCard, 1)

        # Primary actions
        actionLayout = QHBoxLayout()
        actionLayout.setSpacing(12)
        settingsBtn = QPushButton(get_language_string(
            "ui-settings-btn-tooltip"), self)
        settingsBtn.setToolTip(get_language_string("ui-settings-btn-tooltip"))
        settingsBtn.setObjectName(_QObjectIDs.SETTINGS)
        settingsBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        settingsBtn.setMinimumHeight(48)
        settingsBtn.clicked.connect(self._onSettingsBtnClicked)  # type: ignore
        actionLayout.addWidget(settingsBtn, _SETTINGS_BTN_SIZE)

        startBtn = QPushButton(get_language_string(
            "ui-start-btn-tooltip"), self)
        startBtn.setToolTip(get_language_string("ui-start-btn-tooltip"))
        startBtn.setObjectName(_QObjectIDs.START)
        startBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        startBtn.setMinimumHeight(48)
        startBtn.clicked.connect(self._onStartBtnClicked)  # type: ignore
        actionLayout.addWidget(startBtn, _START_BTN_SIZE)
        mainLayout.addLayout(actionLayout)

        # Worker thread
        qThread = QThread(self)
        self.subProcess = SubProcess()
        self.subProcess.moveToThread(qThread)
        self.subProcess.jobFinishedSignal.connect(self._onJobFinished)
        self.subProcess.updateLogSignal.connect(logPanel.appendPlainText)
        self.subProcess.updateStatusSignal.connect(self._onStatusUpdated)
        self.subProcess.pauseThreadSignal.connect(self._onManualInputRequired)
        self.subProcess.qrControlSignal.connect(self._onQRBytesRecived)
        self.subProcess.updateScoreSignal.connect(self._onScoreUpdated)
        qThread.started.connect(self.subProcess.start)  # type: ignore
        qThread.finished.connect(self._onQThreadFinished)  # type: ignore

        qssFile = QFile(get_resources_path(_QSS_FILE_NAME))
        qssFile.open(QFile.OpenModeFlag.ReadOnly)
        self.setStyleSheet(qssFile.readAll().data().decode())
        qssFile.close()
        if get_runtime_config().auto_start:
            QTimer.singleShot(0, self._onStartBtnClicked)

    def show(self):
        tray = self.findChildWithProperType(QSystemTrayIcon, _QObjectIDs.TRAY)
        if tray != None:
            tray.show()
        super().show()

    def close(self) -> bool:
        tray = self.findChildWithProperType(QSystemTrayIcon, _QObjectIDs.TRAY)
        if tray != None:
            tray.hide()
        return super().close()

    def showMinimized(self):
        tray = self.findChildWithProperType(QSystemTrayIcon, _QObjectIDs.TRAY)
        if tray != None:
            if tray.isSystemTrayAvailable():
                tray.show()
                self.hide()
                return
        super().showMinimized()

    def _onJobFinished(self, data: str):
        thread = self.findChildWithProperType(QThread)
        if thread != None:
            thread.quit()
        self._onStatusUpdated(data)
        tray = self.findChildWithProperType(QSystemTrayIcon, _QObjectIDs.TRAY)
        if tray != None:
            tray.showMessage(get_language_string("ui-tray-notification-title-info"),
                             data, QSystemTrayIcon.MessageIcon.Information, _NOTIFY_SECS*1000)

    def _onQThreadFinished(self):
        logPanel = self.findChildWithProperType(
            QPlainTextEdit, _QObjectIDs.LOG_PANEL)
        if logPanel != None:
            logPanel.setToolTip(get_language_string(
                "ui-logpanel-default-tooltip"))
        startBtn = self.findChildWithProperType(QPushButton, _QObjectIDs.START)
        if startBtn != None:
            startBtn.setEnabled(True)
            startBtn.setToolTip(get_language_string("ui-start-btn-tooltip"))
            startBtn.setText(get_language_string("ui-start-btn-tooltip"))
        reset_processing_pause()
        self._updateTrayActions()
        qrLabel = self.findChildWithProperType(QLabel, _QObjectIDs.QR_LABEL)
        if qrLabel != None:
            qrLabel.close()

    def _onManualInputRequired(self, data: tuple[str, Queue[list[str]]]):
        title = data[0]
        queue = data[1]
        dialogTitle = get_language_string(
            "ui-manual-input-required") % ANSWER_CONNECTOR
        parsedTitle = title.split("\n")
        questionTitle = "\n".join(split_text(
            parsedTitle[0], _SPLIT_TITLE_SIZE))
        questionTips = "\n".join(split_text(parsedTitle[1], _SPLIT_TITLE_SIZE))
        answersFromPage = "\n".join(split_text(
            parsedTitle[2], _SPLIT_TITLE_SIZE)) if len(parsedTitle) > 2 else ""
        fullText = "\n".join(
            [dialogTitle, questionTitle, questionTips, answersFromPage])
        answerText, requireResult = QInputDialog.getText(
            self, dialogTitle, fullText, QLineEdit.EchoMode.Normal, "", Qt.WindowType.FramelessWindowHint)
        if requireResult:
            answer = [answerTextPart.strip() for answerTextPart in answerText.strip().split(
                ANSWER_CONNECTOR) if is_valid_answer(answerTextPart.strip())]
        else:
            answer = []
        queue.put(answer)
        self.subProcess.wait.wakeAll()

    def _onQRBytesRecived(self, qr: bytes):
        existingQRLabel = self.findChildWithProperType(
            QLabel, _QObjectIDs.QR_LABEL)
        if isinstance(existingQRLabel, QLabel):
            existingQRLabel.close()
        pixmap = QPixmap()
        if pixmap.loadFromData(qr):
            qrLabel = QLabel(self)
            qrLabel.setObjectName(_QObjectIDs.QR_LABEL)
            qrLabel.setWindowTitle(get_language_string("core-info-scan-required"))
            qrLabel.setWindowModality(Qt.WindowModality.NonModal)
            qrLabel.setWindowFlag(Qt.WindowType.Window, True)
            qrLabel.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            qrLabel.setStyle(self.style())
            pixmap = pixmap.scaled(
                320, 320,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            qrLabel.setPixmap(pixmap)
            qrLabel.setStyleSheet(self.styleSheet())
            qrLabel.setContentsMargins(16, 16, 16, 16)
            qrLabel.adjustSize()
            qrLabel.move(self.x()+round((self.width()-qrLabel.width())/2),
                         self.y()+round((self.height()-qrLabel.height())/2))
            qrLabel.show()
            qrLabel.raise_()
            qrLabel.activateWindow()

    def _onScoreUpdated(self, score: list[int]):
        score = score[:2]
        if score != [-1, -1]:
            scoreLabel = self.findChildWithProperType(
                QLabel, _QObjectIDs.SCORE)
            if scoreLabel != None:
                scoreLabel.setText(
                    get_language_string("ui-score-text") % tuple(score))

    def _onOnTopStateChanged(self, state: Qt.CheckState):
        settings = self.findChildWithProperType(_QSettingsExtended)
        if settings != None:
            match Qt.CheckState(state):
                case Qt.CheckState.Checked:
                    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
                    settings.setValue("UI/ontop", True)
                    self.show()
                case Qt.CheckState.Unchecked:
                    self.setWindowFlag(
                        Qt.WindowType.WindowStaysOnTopHint, False)
                    settings.setValue("UI/ontop", False)
                    self.show()
                case _:
                    pass

    def _onStartBtnClicked(self):
        qThread = self.findChildWithProperType(QThread)
        if qThread == None:
            return
        if qThread.isRunning():
            # The tray Start action doubles as Resume while paused.
            if is_processing_paused():
                resume_processing()
                self._appendTrayStatus(get_language_string(
                    "ui-tray-status-resumed"))
                self._updateTrayActions()
            return
        reset_processing_pause()
        startBtn = self.findChildWithProperType(QPushButton, _QObjectIDs.START)
        if startBtn != None:
            startBtn.setEnabled(False)
            startBtn.setText(get_language_string(
                "ui-start-btn-processing-tooltip"))
            startBtn.setToolTip(get_language_string(
                "ui-start-btn-processing-tooltip"))
        qThread.start()
        self._updateTrayActions()

    def _onTrayStartClicked(self):
        self._onStartBtnClicked()

    def _onTrayPauseClicked(self):
        qThread = self.findChildWithProperType(QThread)
        if qThread == None or not qThread.isRunning():
            return
        request_processing_pause()
        self._appendTrayStatus(get_language_string(
            "ui-tray-status-paused"))
        self._updateTrayActions()

    def _appendTrayStatus(self, message: str):
        logPanel = self.findChildWithProperType(
            QPlainTextEdit, _QObjectIDs.LOG_PANEL)
        if logPanel != None:
            logPanel.appendPlainText(message)

    def _updateTrayActions(self):
        qThread = self.findChildWithProperType(QThread)
        running = qThread != None and qThread.isRunning()
        paused = running and is_processing_paused()
        if hasattr(self, "_trayStartAction"):
            self._trayStartAction.setText(get_language_string(
                "ui-tray-action-resume" if paused else "ui-tray-action-start"))
            self._trayStartAction.setEnabled(not running or paused)
        if hasattr(self, "_trayPauseAction"):
            self._trayPauseAction.setText(get_language_string(
                "ui-tray-action-pause"))
            self._trayPauseAction.setEnabled(running and not paused)

    def _onTrayExitClicked(self):
        resume_processing()
        tray = self.findChildWithProperType(QSystemTrayIcon, _QObjectIDs.TRAY)
        if tray != None:
            tray.hide()
        self.close()
        QApplication.quit()

    def _onSettingsBtnClicked(self):
        settingsWindow = self.findChildWithProperType(
            SettingsWindow, _QObjectIDs.SETTINGS_WINDOW)
        if settingsWindow == None:
            settingsWindow = SettingsWindow(self)
        settingsWindow.resize(max(820, round(self.width()*9/10)),
                              max(600, round(self.height()*9/10)))
        settingsWindow.move(self.x()+round((self.width()-settingsWindow.width())/2),
                            self.y()+round((self.height()-settingsWindow.height())/2))
        settingsWindow.show()
        settingsWindow.raise_()
        settingsWindow.activateWindow()

    def _onTrayActivated(self, reason: QSystemTrayIcon.ActivationReason):
        match QSystemTrayIcon.ActivationReason(reason):
            case QSystemTrayIcon.ActivationReason.Trigger:
                self.setHidden(not self.isHidden())
            case _:
                pass

    def _onStatusUpdated(self, status: str):
        statusLabel = self.findChildWithProperType(
            QLabel, _QObjectIDs.STATUS)
        if statusLabel is not None:
            statusLabel.setText(status or get_language_string(
                "ui-main-status-ready"))
        logPanel = self.findChildWithProperType(
            QPlainTextEdit, _QObjectIDs.LOG_PANEL)
        if logPanel is not None:
            logPanel.setToolTip(get_language_string(
                "ui-status-tooltip") % status)
