"""Widget contains procesor settings."""
# pyright: reportAny=false

from typing import ClassVar as _ClassVar
from typing import final as _final
from typing import override as _override
from PySide6.QtGui import QRegularExpressionValidator as _QRegularExpressionValidator
from PySide6.QtCore import QDir as _QDir
from PySide6.QtCore import Slot as _Slot
from PySide6.QtCore import QFile as _QFile
from PySide6.QtCore import QFileInfo as _QFileInfo
from PySide6.QtCore import QRegularExpression as _QRegularExpression
from PySide6.QtWidgets import QWidget as _QWidget
from PySide6.QtWidgets import QFileDialog as _QFileDialog
from PySide6.QtWidgets import QLineEdit as _QLineEdit
from PySide6.QtWidgets import QMessageBox as _QMessageBox
from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout
from PySide6.QtWidgets import QPushButton as _QPushButton
from autoxuexiplaywright.config import Config as _Config
from autoxuexiplaywright.config import BrowserType as _BrowserType
from autoxuexiplaywright.config import ChannelType as _ChannelType
from autoxuexiplaywright.config import ProxySettings as _ProxySettings
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.ui.qt.qlabelwithcheckbox import (
    QLabelWithCheckbox as _QLabelWithCheckbox,
)
from autoxuexiplaywright.ui.qt.qlabelwithlineedit import (
    QLabelWithLineEdit as _QLabelWithLineEdit,
)
from autoxuexiplaywright.ui.qt.qlabelwithcombobox import (
    QLabelWithCombobox as _QLabelWithCombobox,
)
from autoxuexiplaywright.ui.qt.qlabelwithpathsetter import (
    QLabelWithPathSetter as _QLabelWithPathSetter,
)
from autoxuexiplaywright.ui.qt.settingconfigcomplexitemcontainer import (
    SettingConfigComplexItemContainer as _SettingConfigComplexItemContainer,
)
from autoxuexiplaywright.processor.answer_sources.openai_compatible import (
    test_ai_answer_config_sync as _test_ai_answer_config,
)


def _isBrowserChannelSupported(i: _BrowserType) -> bool:
    return i == "chromium"


def _toNoneIfFalse[T](i: T) -> T | None:
    return i or None


@_final
class SettingConfigWidget(_QWidget):
    """Widget contains procesor settings."""

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

    @_override
    def __init__(self, parent: _QWidget | None = None):
        super().__init__(parent)
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

        self._aiAnswerModelSetter = _QLabelWithLineEdit(self)
        self._setUpAiAnswerModelSetter()
        self.layout().addWidget(self._aiAnswerModelSetter)

        self._aiAnswerTestButton = _QPushButton(self)
        self._setUpAiAnswerTestButton()
        self.layout().addWidget(self._aiAnswerTestButton)

        self._complexItemContainer = _SettingConfigComplexItemContainer(self)
        self._setUpComplexItemContainer()
        self.layout().addWidget(self._complexItemContainer)

        _ = self.objectNameChanged.connect(self._refreshObjectName)
        _ = self.setProperty("contaienr", True)

    @_Slot(str, result=None)
    def _refreshObjectName(self, objectName: str):
        self._browserSelector.setObjectName(objectName + "-browser-selector")
        self._channelSelector.setObjectName(objectName + "-channel-selector")
        self._debugChecker.setObjectName(objectName + "-debug-checker")
        self._guiChecker.setObjectName(objectName + "-gui-checker")
        self._autoStartChecker.setObjectName(objectName + "-auto-start-checker")
        self._executablePathSetter.setObjectName(objectName + "-executable-path-setter")
        self._aiAnswerChecker.setObjectName(objectName + "-ai-answer-checker")
        self._aiAnswerBaseUrlSetter.setObjectName(objectName + "-ai-answer-base-url")
        self._aiAnswerApiKeySetter.setObjectName(objectName + "-ai-answer-api-key")
        self._aiAnswerModelSetter.setObjectName(objectName + "-ai-answer-model")
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
        channelSupported = _isBrowserChannelSupported(item)
        self._channelSelector.selectorWidget().setEnabled(channelSupported)

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

    def _setUpExecutablePathSetter(self):
        self._executablePathSetter.titleWidget().setText(__("Browser Executable Path:"))
        self._executablePathSetter.browseButton().setText(__("Browse..."))
        _ = self._executablePathSetter.browseButton().clicked.connect(
            self._onExecutablePathSetterBrowseButtonClicked,
        )

    def _setUpAiAnswerChecker(self):
        self._aiAnswerChecker.labelWidget().setText(__("Enable AI answer:"))

    def _setUpAiAnswerBaseUrlSetter(self):
        self._aiAnswerBaseUrlSetter.titleWidget().setText(__("AI API Base URL:"))
        self._aiAnswerBaseUrlSetter.lineEditWidget().setToolTip(
            __("OpenAI compatible API base URL, for example https://api.openai.com or http://127.0.0.1:8000/v1."),
        )

    def _setUpAiAnswerApiKeySetter(self):
        self._aiAnswerApiKeySetter.titleWidget().setText(__("AI API Key:"))
        self._aiAnswerApiKeySetter.lineEditWidget().setEchoMode(
            _QLineEdit.EchoMode.PasswordEchoOnEdit,
        )

    def _setUpAiAnswerModelSetter(self):
        self._aiAnswerModelSetter.titleWidget().setText(__("AI Model:"))

    def _setUpAiAnswerTestButton(self):
        self._aiAnswerTestButton.setText(__("Test AI API"))
        _ = self._aiAnswerTestButton.clicked.connect(self._onAiAnswerTestButtonClicked)

    @_Slot(result=None)
    def _onAiAnswerTestButtonClicked(self):
        self._aiAnswerTestButton.setEnabled(False)
        self._aiAnswerTestButton.setText(__("Testing..."))
        success, message = _test_ai_answer_config(self.toConfig())
        self._aiAnswerTestButton.setEnabled(True)
        self._aiAnswerTestButton.setText(__("Test AI API"))
        if success:
            _QMessageBox.information(self, __("AI API test"), message)
        else:
            _QMessageBox.warning(self, __("AI API test"), message)

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
        skippedItemsSetter.textEditWidget().setToolTip(
            __("Put items to be skipped one by one here."),
        )

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
        """The widget to config gui mode."""
        return self._guiChecker

    def complexItemContainer(self) -> _SettingConfigComplexItemContainer:
        """The widget contains complex settings items."""
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

        executablePath = (
            "" if config.executable_path is None else config.executable_path
        )
        self._executablePathSetter.pathDisplayWidget().setText(executablePath)

        self._aiAnswerChecker.checkerWidget().setChecked(config.ai_answer_enabled)
        self._aiAnswerBaseUrlSetter.lineEditWidget().setText(
            config.ai_answer_base_url,
        )
        self._aiAnswerApiKeySetter.lineEditWidget().setText(config.ai_answer_api_key)
        self._aiAnswerModelSetter.lineEditWidget().setText(config.ai_answer_model)

        proxySetter = self._complexItemContainer.proxySetter()
        server = config.proxy.get("server", "") if config.proxy is not None else ""
        proxySetter.serverWidget().lineEditWidget().setText(server)
        bypass = config.proxy.get("bypass", "") if config.proxy is not None else ""
        bypass = bypass if bypass is not None else ""
        proxySetter.bypassWidget().lineEditWidget().setText(bypass)
        username = config.proxy.get("username", "") if config.proxy is not None else ""
        username = username if username is not None else ""
        proxySetter.usernameWidget().lineEditWidget().setText(username)
        password = config.proxy.get("password", "") if config.proxy is not None else ""
        password = password if password is not None else ""
        proxySetter.passwordWidget().lineEditWidget().setText(password)

        self._complexItemContainer.skippedItemsSetter().textEditWidget().setPlainText(
            "\n".join(config.skipped),
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

        skippedWidget = self._complexItemContainer.skippedItemsSetter().textEditWidget()
        skipped = skippedWidget.toPlainText().splitlines()

        aiAnswerEnabled = self._aiAnswerChecker.checkerWidget().isChecked()
        aiAnswerBaseUrl = self._aiAnswerBaseUrlSetter.lineEditWidget().text().strip()
        aiAnswerApiKey = self._aiAnswerApiKeySetter.lineEditWidget().text().strip()
        aiAnswerModel = self._aiAnswerModelSetter.lineEditWidget().text().strip()

        return _Config(
            browserId,
            browserChannel,
            debug,
            executablePath,
            gui,
            autoStart,
            proxy,
            skipped,
            aiAnswerEnabled,
            aiAnswerBaseUrl,
            aiAnswerApiKey,
            aiAnswerModel,
        )
