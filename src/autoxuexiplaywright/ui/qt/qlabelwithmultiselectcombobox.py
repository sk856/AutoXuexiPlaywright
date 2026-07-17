"""Widget containing a label and a multi-select combo box."""

from typing import override as _override
from PySide6.QtCore import Slot as _Slot
from PySide6.QtWidgets import QLabel as _QLabel
from PySide6.QtWidgets import QWidget as _QWidget
from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout
from autoxuexiplaywright.ui.qt.multiselectcombobox import (
    MultiSelectComboBox as _MultiSelectComboBox,
)


class QLabelWithMultiSelectComboBox(_QWidget):
    """Widget containing a title label and a checkable combo box."""

    @_override
    def __init__(self, parent: _QWidget | None = None):
        super().__init__(parent)
        self.setLayout(_QVBoxLayout(self))
        self._titleWidget = _QLabel(self)
        self._comboBox = _MultiSelectComboBox(self)
        self.layout().addWidget(self._titleWidget)
        self.layout().addWidget(self._comboBox)
        _ = self.objectNameChanged.connect(self._refreshObjectName)
        _ = self.setProperty("container", True)

    @_Slot(str, result=None)
    def _refreshObjectName(self, objectName: str):
        self._titleWidget.setObjectName(objectName + "-title")
        self._comboBox.setObjectName(objectName + "-combo-box")

    def titleWidget(self) -> _QLabel:
        """The title label."""
        return self._titleWidget

    def comboBox(self) -> _MultiSelectComboBox:
        """The multi-select combo box."""
        return self._comboBox
