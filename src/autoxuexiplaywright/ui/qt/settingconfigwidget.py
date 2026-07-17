"""Widget contains processor settings."""
# pyright: reportAny=false

from typing import ClassVar as _ClassVar
from typing import final as _final
from typing import override as _override
from PySide6.QtGui import QRegularExpressionValidator as _QRegularExpressionValidator
from PySide6.QtCore import QDir as _QDir
from PySide6.QtCore import Slot as _Slot
from PySide6.QtCore import QFile as _QFile
from PySide6.QtCore import Signal as _Signal
from PySide6.QtCore import QThread as _QThread
from PySide6.QtCore import QFileInfo as _QFileInfo
from PySide6.QtCore import QRegularExpression as _QRegularExpression
from PySide6.QtWidgets import QWidget as _QWidget
from PySide6.QtWidgets import QComboBox as _QComboBox
from PySide6.QtWidgets import QLineEdit as _QLineEdit
from PySide6.QtWidgets import QFileDialog as _QFileDialog
from PySide6.QtWidgets import QHBoxLayout as _QHBoxLayout
from PySide6.QtWidgets import QMessageBox as _QMessageBox
from PySide6.QtWidgets import QPushButton as _QPushButton
from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout
from autoxuexiplaywright.config import Config as _Config
from autoxuexiplaywright.config import BrowserType as _BrowserType
from autoxuexiplaywright.config import ChannelType as _ChannelType
from autoxuexiplaywright.config import ProxySettings as _ProxySettings
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.ui.qt.qlabelwithcheckbox import (
    QLabelWithCheckbox as _QLabelWithCheckbox,
)
from autoxuexiplaywright.ui.qt.qlabelwithcombobox import (
    QLabelWithCombobox as _QLabelWithCombobox,
)
from autoxuexiplaywright.ui.qt.qlabelwithlineedit import (
    QLabelWithLineEdit as _QLabelWithLineEdit,
)
from autoxuexiplaywright.ui.qt.coloredarrowcombobox import (
    ColoredArrowComboBox as _ColoredArrowComboBox,
)
from autoxuexiplaywright.ui.qt.qlabelwithpathsetter import (
    QLabelWithPathSetter as _QLabelWithPathSetter,
)
from autoxuexiplaywright.ui.qt.settingconfigcomplexitemcontainer import (
    SettingConfigComplexItemContainer as _SettingConfigComplexItemContainer,
)
from autoxuexiplaywright.processor.answer_sources.openai_compatible import (
    fetch_ai_models_sync as _fetch_ai_models,
)
from autoxuexiplaywright.processor.answer_sources.openai_compatible import (
    test_ai_answer_config_sync as _test_ai_answer_config,
)


def _isBrowserChannelSupported(i: _BrowserType) -> bool:
    return i == "chromium"


def _toNoneIfFalse[T](i: T) -> T | None:
    return i or None


@_final
class _AIModelFetchThread(_QThread):
    resultReady = _Signal(bool, list, str)

    def __init__(self, config: _Config, parent: _QWidget | None = None):
        super().__init__(parent)
        self._config = config

    @_override
    def run(self):
        success, models, message = _fetch_ai_models(self._config)
        self.resultReady.emit(success, models, message)


@_final
class _AIAnswerTestThread(_QThread):
    resultReady = _Signal(bool, str)

    def __init__(self, config: _Config, parent: _QWidget | None = None):
        super().__init__(parent)
        self._config = config

    @_override
    def run(self):
        success, message = _test_ai_answer_config(self._config)
        self.resultReady.emit(success, message)


@_final
class SettingConfigWidget(_QWidget):
    """Widget contains processor settings."""

    _VALID_BROWSER_NAME_MAPS: _ClassVar[dict[str, _BrowserType]] = {
        __("Firefox"): "firefox",
        __("Chromium"): "chromium",
        __("WebKit"): "webkit",
    }
    _VALID_CHANNEL_NAME_MAPS: _ClassVar[dict[str, _ChannelType]] = {
        __("Microsoft Edge"): "msedge",
        __("Microsoft Edge Beta"): "msedge-beta",
        __("Microsoft Edge Dev"): "msedge-dev",
        __("Google Chrome"): "chrome",
        __("Google Chrome Beta"): "chrome-beta",
        __("Google Chrome Dev"): "chrome-dev",
        __("Chromium"): "chromium",
        __("Chromium Beta"): "chromium-beta",
        __("Chromium Dev"): "chromium-dev",
    }
    _VALID_PROXY_SERVER_VALIDATOR = _QRegularExpressionValidator(
        _QRegularExpression(
            r"(https?|socks[45])://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]",
        ),
    )
    _READ_HISTORY_RETENTION_DAYS: _ClassVar[tuple[int, ...]] = (3, 7, 15, 30)
    _SKIPPED_TASK_GROUPS: _ClassVar[dict[str, tuple[str, tuple[str, ...]]]] = {
        "article": (__("Read articles"), ("我要选读文章",)),
        "video": (
            __("Watch videos"),
            ("视听学习", "视听学习时长", "我要视听学习"),
        ),
        "daily_test": (__("Daily test"), ("每日答题",)),
    }

    @_override
    def __init__(self, parent: _QWidget | None = None):  # noqa: PLR0915
        super().__init__(parent)
        self._aiModelFetchThread: _AIModelFetchThread | None = None
        self._aiAnswerTestThread: _AIAnswerTestThread | None = None
        self._unknownSkippedItems: list[str] = []
        self.setLayout(_QVBoxLayout(self))

        self._browserSelector = _QLabelWithCombobox(self)
        self._setUpBrowserSelector()
        self.layout().addWidget(self._browserSelector)

        self._channelSelector = _QLabelWithCombobox(self)
        self._setUpChannelSelector()
        self.layout().addWidget(self._channelSelector)

        self._debugChecker = _QLabelWithCheckbox(self)
        self._setUpDebugChecker()
        self.layout().addWidget(self._debugChecker)

        self._guiChecker = _QLabelWithCheckbox(self)
        self._setUpGuiChecker()
        self.layout().addWidget(self._guiChecker)

        self._autoStartChecker = _QLabelWithCheckbox(self)
        self._setUpAutoStartChecker()
        self.layout().addWidget(self._autoStartChecker)

        self._readHistoryRetentionSelector = _QLabelWithCombobox(self)
        self._setUpReadHistoryRetentionSelector()
        self.layout().addWidget(self._readHistoryRetentionSelector)

        self._executablePathSetter = _QLabelWithPathSetter(self)
        self._setUpExecutablePathSetter()
        self.layout().addWidget(self._executablePathSetter)

        self._aiAnswerChecker = _QLabelWithCheckbox(self)
        self._setUpAiAnswerChecker()
        self.layout().addWidget(self._aiAnswerChecker)

        self._aiAnswerBaseUrlSetter = _QLabelWithLineEdit(self)
        self._setUpAiAnswerBaseUrlSetter()
        self.layout().addWidget(self._aiAnswerBaseUrlSetter)

        self._aiAnswerApiKeySetter = _QLabelWithLineEdit(self)
        self._setUpAiAnswerApiKeySetter()
        self.layout().addWidget(self._aiAnswerApiKeySetter)

        self._aiAnswerModelSelector = _QLabelWithCombobox(self)
        self._setUpAiAnswerModelSelector()
        self.layout().addWidget(self._aiAnswerModelSelector)

        self._aiButtonLayout = _QHBoxLayout()
        self._aiButtonLayout.addStretch(1)
        self._aiAnswerFetchButton = _QPushButton(self)
        self._setUpAiAnswerFetchButton()
        self._aiButtonLayout.addWidget(self._aiAnswerFetchButton)
        self._aiAnswerTestButton = _QPushButton(self)
        self._setUpAiAnswerTestButton()
        self._aiButtonLayout.addWidget(self._aiAnswerTestButton)
        self.layout().addLayout(self._aiButtonLayout)

        self._complexItemContainer = _SettingConfigComplexItemContainer(self)
        self._setUpComplexItemContainer()
        self.layout().addWidget(self._complexItemContainer)

        _ = self.objectNameChanged.connect(self._refreshObjectName)
        _ = self.setProperty("container", True)

    @_Slot(str, result=None)
    def _refreshObjectName(self, objectName: str):
        self._browserSelector.setObjectName(objectName + "-browser-selector")
        self._channelSelector.setObjectName(objectName + "-channel-selector")
        self._debugChecker.setObjectName(objectName + "-debug-checker")
        self._guiChecker.setObjectName(objectName + "-gui-checker")
        self._autoStartChecker.setObjectName(objectName + "-auto-start-checker")
        self._readHistoryRetentionSelector.setObjectName(
            objectName + "-read-history-retention-selector",
        )
        self._executablePathSetter.setObjectName(objectName + "-executable-path-setter")
        self._aiAnswerChecker.setObjectName(objectName + "-ai-answer-checker")
        self._aiAnswerBaseUrlSetter.setObjectName(objectName + "-ai-answer-base-url")
        self._aiAnswerApiKeySetter.setObjectName(objectName + "-ai-answer-api-key")
        self._aiAnswerModelSelector.setObjectName(objectName + "-ai-answer-model")
        self._aiAnswerFetchButton.setObjectName(objectName + "-ai-answer-fetch-models")
        self._aiAnswerTestButton.setObjectName(objectName + "-ai-answer-test")
        self._complexItemContainer.setObjectName(objectName + "-complex-item-container")

    @_Slot(result=None)
    def _onExecutablePathSetterBrowseButtonClicked(self):
        fileName, _ = _QFileDialog.getOpenFileName(
            self._executablePathSetter,
            __("Browse File"),
            _QDir.currentPath(),
        )
        execPermission = _QFile.Permission.ExeGroup
        execPermission |= _QFile.Permission.ExeOther
        execPermission |= _QFile.Permission.ExeOwner
        execPermission |= _QFile.Permission.ExeUser
        if len(fileName) > 0 and execPermission in _QFile.permissions(fileName):
            pathDisplayWidget = self._executablePathSetter.pathDisplayWidget()
            pathDisplayWidget.setToolTip(fileName)
            pathDisplayWidget.setText(_QFileInfo(fileName).fileName())

    @_Slot(int, result=None)
    def _onBrowserSelectorChanged(self, index: int):
        item = self._browserSelector.selectorWidget().itemData(index)
        self._channelSelector.selectorWidget().setEnabled(
            _isBrowserChannelSupported(item),
        )

    def _setUpBrowserSelector(self):
        self._browserSelector.labelWidget().setText(__("Browser:"))
        self._browserSelector.setSelectorWidgetContents(**self._VALID_BROWSER_NAME_MAPS)
        _ = self._browserSelector.selectorWidget().currentIndexChanged.connect(
            self._onBrowserSelectorChanged,
        )

    def _setUpChannelSelector(self):
        self._channelSelector.labelWidget().setText(__("Browser Channel:"))
        self._channelSelector.setSelectorWidgetContents(**self._VALID_CHANNEL_NAME_MAPS)

    def _setUpDebugChecker(self):
        self._debugChecker.labelWidget().setText(__("Debug Mode:"))

    def _setUpGuiChecker(self):
        self._guiChecker.labelWidget().setText(__("GUI Mode:"))

    def _setUpAutoStartChecker(self):
        self._autoStartChecker.labelWidget().setText(__("Start automatically:"))

    def _setUpReadHistoryRetentionSelector(self):
        self._readHistoryRetentionSelector.labelWidget().setText(
            __("Read history retention:"),
        )
        contents = {
            __("%(days)d days") % {"days": days}: days
            for days in self._READ_HISTORY_RETENTION_DAYS
        }
        self._readHistoryRetentionSelector.setSelectorWidgetContents(**contents)

    def _setUpExecutablePathSetter(self):
        self._executablePathSetter.titleWidget().setText(
            __("Browser Executable Path:"),
        )
        self._executablePathSetter.browseButton().setText(__("Browse..."))
        _ = self._executablePathSetter.browseButton().clicked.connect(
            self._onExecutablePathSetterBrowseButtonClicked,
        )

    def _setUpAiAnswerChecker(self):
        self._aiAnswerChecker.labelWidget().setText(__("Enable AI answer:"))

    def _setUpAiAnswerBaseUrlSetter(self):
        self._aiAnswerBaseUrlSetter.titleWidget().setText(__("AI API Base URL:"))
        self._aiAnswerBaseUrlSetter.lineEditWidget().setToolTip(
            __(
                "OpenAI compatible API base URL, for example https://api.openai.com or http://127.0.0.1:8000/v1.",
            ),
        )

    def _setUpAiAnswerApiKeySetter(self):
        self._aiAnswerApiKeySetter.titleWidget().setText(__("AI API Key:"))
        self._aiAnswerApiKeySetter.lineEditWidget().setEchoMode(
            _QLineEdit.EchoMode.PasswordEchoOnEdit,
        )

    def _setUpAiAnswerModelSelector(self):
        generic = self._aiAnswerModelSelector.selectorWidget()
        modelSelector = _ColoredArrowComboBox(self._aiAnswerModelSelector)
        modelSelector.setSizePolicy(generic.sizePolicy())
        self._aiAnswerModelSelector.layout().replaceWidget(generic, modelSelector)
        generic.deleteLater()
        self._aiAnswerModelSelector._selectorWidget = modelSelector
        self._aiAnswerModelSelector.labelWidget().setText(__("AI Model:"))
        modelSelector.setEditable(True)
        modelSelector.setInsertPolicy(_QComboBox.InsertPolicy.NoInsert)
        modelSelector.setDuplicatesEnabled(False)
        modelSelector.setToolTip(__("Model id sent to the OpenAI-compatible API."))

    def _setUpAiAnswerFetchButton(self):
        self._aiAnswerFetchButton.setText(__("Fetch AI models"))
        self._aiAnswerFetchButton.setToolTip(
            __("Fetch available model ids from the configured /models endpoint."),
        )
        _ = self._aiAnswerFetchButton.clicked.connect(
            self._onAiAnswerFetchButtonClicked,
        )

    def _setUpAiAnswerTestButton(self):
        self._aiAnswerTestButton.setText(__("Test AI API"))
        _ = self._aiAnswerTestButton.clicked.connect(self._onAiAnswerTestButtonClicked)

    def _setUpComplexItemContainer(self):
        proxySetter = self._complexItemContainer.proxySetter()
        proxySetter.serverWidget().lineEditWidget().setValidator(
            self._VALID_PROXY_SERVER_VALIDATOR,
        )
        proxySetter.serverWidget().titleWidget().setText(__("Proxy Server:"))
        proxySetter.bypassWidget().titleWidget().setText(__("Proxy Bypass:"))
        proxySetter.usernameWidget().titleWidget().setText(__("Proxy Username:"))
        proxySetter.passwordWidget().titleWidget().setText(__("Proxy Password:"))

        skippedItemsSetter = self._complexItemContainer.skippedItemsSetter()
        skippedItemsSetter.titleWidget().setText(__("Skipped items:"))
        skippedItemsSetter.comboBox().setEmptyText(__("No skipped items"))
        skippedItemsSetter.comboBox().setToolTip(
            __("Select one or more task groups to skip."),
        )
        for groupId, (label, _) in self._SKIPPED_TASK_GROUPS.items():
            skippedItemsSetter.comboBox().addCheckItem(label, groupId)

    @_Slot(result=None)
    def _onAiAnswerFetchButtonClicked(self):
        if (
            self._aiModelFetchThread is not None
            and self._aiModelFetchThread.isRunning()
        ):
            return
        self._aiAnswerFetchButton.setEnabled(False)
        self._aiAnswerFetchButton.setText(__("Fetching..."))
        thread = _AIModelFetchThread(self.toConfig(), self)
        self._aiModelFetchThread = thread
        _ = thread.resultReady.connect(self._onAiAnswerModelsFetched)
        _ = thread.finished.connect(thread.deleteLater)
        _ = thread.finished.connect(lambda: self._clearAiModelFetchThread(thread))
        thread.start()

    def _clearAiModelFetchThread(self, thread: _AIModelFetchThread):
        if self._aiModelFetchThread is thread:
            self._aiModelFetchThread = None

    @_Slot(bool, list, str, result=None)
    def _onAiAnswerModelsFetched(self, success: bool, models: list, message: str):
        self._aiAnswerFetchButton.setEnabled(True)
        self._aiAnswerFetchButton.setText(__("Fetch AI models"))
        if success:
            modelSelector = self._aiAnswerModelSelector.selectorWidget()
            currentModel = modelSelector.currentText().strip()
            modelSelector.blockSignals(True)
            modelSelector.clear()
            for model in models:
                modelSelector.addItem(model, model)
            if currentModel and currentModel not in models:
                modelSelector.insertItem(0, currentModel, currentModel)
            modelSelector.setCurrentText(currentModel if currentModel else models[0])
            modelSelector.blockSignals(False)
            _QMessageBox.information(self, __("Fetch AI models"), message)
        else:
            _QMessageBox.warning(self, __("Fetch AI models"), message)

    @_Slot(result=None)
    def _onAiAnswerTestButtonClicked(self):
        if (
            self._aiAnswerTestThread is not None
            and self._aiAnswerTestThread.isRunning()
        ):
            return
        self._aiAnswerTestButton.setEnabled(False)
        self._aiAnswerTestButton.setText(__("Testing..."))
        thread = _AIAnswerTestThread(self.toConfig(), self)
        self._aiAnswerTestThread = thread
        _ = thread.resultReady.connect(self._onAiAnswerTestFinished)
        _ = thread.finished.connect(thread.deleteLater)
        _ = thread.finished.connect(lambda: self._clearAiAnswerTestThread(thread))
        thread.start()

    def _clearAiAnswerTestThread(self, thread: _AIAnswerTestThread):
        if self._aiAnswerTestThread is thread:
            self._aiAnswerTestThread = None

    @_Slot(bool, str, result=None)
    def _onAiAnswerTestFinished(self, success: bool, message: str):
        self._aiAnswerTestButton.setEnabled(True)
        self._aiAnswerTestButton.setText(__("Test AI API"))
        if success:
            _QMessageBox.information(self, __("AI API test"), message)
        else:
            _QMessageBox.warning(self, __("AI API test"), message)

    def browserSelector(self) -> _QLabelWithCombobox:
        """The widget to config browser."""
        return self._browserSelector

    def channelSelector(self) -> _QLabelWithCombobox:
        """The widget to config browser channel."""
        return self._channelSelector

    def debugChecker(self) -> _QLabelWithCheckbox:
        """The widget to config debug mode."""
        return self._debugChecker

    def guiChecker(self) -> _QLabelWithCheckbox:
        """The widget to config GUI mode."""
        return self._guiChecker

    def complexItemContainer(self) -> _SettingConfigComplexItemContainer:
        """The widget containing complex settings items."""
        return self._complexItemContainer

    def applyProcessorConfig(self, config: _Config):
        """Apply processor config and update widget."""
        browserSelector = self._browserSelector.selectorWidget()
        index = browserSelector.findData(config.browser_id)
        browserSelector.setCurrentIndex(max(index, 0))

        channelSelector = self._channelSelector.selectorWidget()
        index = channelSelector.findData(config.browser_channel)
        channelSelector.setCurrentIndex(max(index, 0))
        channelSelector.setEnabled(_isBrowserChannelSupported(config.browser_id))

        self._debugChecker.checkerWidget().setChecked(config.debug)
        self._guiChecker.checkerWidget().setChecked(config.gui)
        self._autoStartChecker.checkerWidget().setChecked(config.auto_start)

        readHistoryRetentionSelector = (
            self._readHistoryRetentionSelector.selectorWidget()
        )
        index = readHistoryRetentionSelector.findData(
            config.read_history_retention_days,
        )
        if index < 0:
            index = readHistoryRetentionSelector.findData(7)
        readHistoryRetentionSelector.setCurrentIndex(max(index, 0))

        executablePath = (
            "" if config.executable_path is None else config.executable_path
        )
        self._executablePathSetter.pathDisplayWidget().setText(executablePath)

        self._aiAnswerChecker.checkerWidget().setChecked(config.ai_answer_enabled)
        self._aiAnswerBaseUrlSetter.lineEditWidget().setText(config.ai_answer_base_url)
        self._aiAnswerApiKeySetter.lineEditWidget().setText(config.ai_answer_api_key)
        modelSelector = self._aiAnswerModelSelector.selectorWidget()
        modelSelector.setCurrentText(config.ai_answer_model)

        proxySetter = self._complexItemContainer.proxySetter()
        server = config.proxy.get("server", "") if config.proxy is not None else ""
        proxySetter.serverWidget().lineEditWidget().setText(server)
        bypass = config.proxy.get("bypass", "") if config.proxy is not None else ""
        proxySetter.bypassWidget().lineEditWidget().setText(bypass or "")
        username = config.proxy.get("username", "") if config.proxy is not None else ""
        proxySetter.usernameWidget().lineEditWidget().setText(username or "")
        password = config.proxy.get("password", "") if config.proxy is not None else ""
        proxySetter.passwordWidget().lineEditWidget().setText(password or "")

        configuredSkipped = {
            item for item in (config.skipped or []) if isinstance(item, str) and item
        }
        allKnownSkipped = {
            title
            for _, (_, titles) in self._SKIPPED_TASK_GROUPS.items()
            for title in titles
        }
        self._unknownSkippedItems = sorted(configuredSkipped - allKnownSkipped)
        selectedGroups = [
            groupId
            for groupId, (_, taskTitles) in self._SKIPPED_TASK_GROUPS.items()
            if any(title in configuredSkipped for title in taskTitles)
        ]
        self._complexItemContainer.skippedItemsSetter().comboBox().setSelectedData(
            selectedGroups,
        )

    def toConfig(self) -> _Config:
        """Extract values in widget and build processor config."""
        browserId = self._browserSelector.selectorWidget().currentData()
        if browserId not in self._VALID_BROWSER_NAME_MAPS.values():
            browserId = "firefox"

        browserChannel = self._channelSelector.selectorWidget().currentData()
        browserChannel = (
            None if not _isBrowserChannelSupported(browserId) else browserChannel
        )
        debug = self._debugChecker.checkerWidget().isChecked()
        gui = self._guiChecker.checkerWidget().isChecked()
        autoStart = self._autoStartChecker.checkerWidget().isChecked()
        readHistoryRetentionDays = (
            self._readHistoryRetentionSelector.selectorWidget().currentData()
        )
        if readHistoryRetentionDays not in self._READ_HISTORY_RETENTION_DAYS:
            readHistoryRetentionDays = 7

        executablePath = _toNoneIfFalse(
            self._executablePathSetter.pathDisplayWidget().text(),
        )

        proxySetter = self._complexItemContainer.proxySetter()
        proxy: _ProxySettings | None = {}
        server = _toNoneIfFalse(proxySetter.serverWidget().lineEditWidget().text())
        bypass = _toNoneIfFalse(proxySetter.bypassWidget().lineEditWidget().text())
        username = _toNoneIfFalse(proxySetter.usernameWidget().lineEditWidget().text())
        password = _toNoneIfFalse(proxySetter.passwordWidget().lineEditWidget().text())
        if server is not None:
            proxy["server"] = server
        if bypass is not None:
            proxy["bypass"] = bypass
        if username is not None:
            proxy["username"] = username
        if password is not None:
            proxy["password"] = password
        proxy = _toNoneIfFalse(proxy)

        selectedGroups = (
            self._complexItemContainer.skippedItemsSetter().comboBox().selectedData()
        )
        skipped: list[str] = list(self._unknownSkippedItems)
        for groupId in selectedGroups:
            group = self._SKIPPED_TASK_GROUPS.get(groupId)
            if group is not None:
                skipped.extend(group[1])

        aiAnswerEnabled = self._aiAnswerChecker.checkerWidget().isChecked()
        aiAnswerBaseUrl = self._aiAnswerBaseUrlSetter.lineEditWidget().text().strip()
        aiAnswerApiKey = self._aiAnswerApiKeySetter.lineEditWidget().text().strip()
        aiAnswerModel = (
            self._aiAnswerModelSelector.selectorWidget().currentText().strip()
        )

        return _Config(
            browserId,
            browserChannel,
            debug,
            executablePath,
            gui,
            autoStart,
            proxy,
            skipped,
            readHistoryRetentionDays,
            aiAnswerEnabled,
            aiAnswerBaseUrl,
            aiAnswerApiKey,
            aiAnswerModel,
        )
