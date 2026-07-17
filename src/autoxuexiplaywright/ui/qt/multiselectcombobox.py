"""A combo box that keeps multiple rows checked at the same time."""

from typing import override as _override
from PySide6.QtGui import QMouseEvent as _QMouseEvent
from PySide6.QtGui import QStandardItem as _QStandardItem
from PySide6.QtGui import QStandardItemModel as _QStandardItemModel
from PySide6.QtCore import Qt as _Qt
from PySide6.QtCore import QEvent as _QEvent
from PySide6.QtCore import Signal as _Signal
from PySide6.QtCore import QObject as _QObject
from PySide6.QtCore import QModelIndex as _QModelIndex
from PySide6.QtWidgets import QWidget as _QWidget
from PySide6.QtWidgets import QComboBox as _QComboBox


class MultiSelectComboBox(_QComboBox):
    """Checkable combo box with stable popup behavior for every row click."""

    selectionChanged = _Signal()

    def __init__(self, parent: _QWidget | None = None):
        """Initialize a read-only display with a checkable item model."""
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(_QComboBox.InsertPolicy.NoInsert)
        self.setDuplicatesEnabled(False)
        self.setModel(_QStandardItemModel(self))
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            lineEdit.setReadOnly(True)
            lineEdit.installEventFilter(self)
        self.view().viewport().installEventFilter(self)
        self._emptyText = ""
        self._refreshText()

    def setEmptyText(self, text: str):
        """Set the display text when no item is checked."""
        self._emptyText = text
        self._refreshText()

    def addCheckItem(self, text: str, data: object | None = None):
        """Append a checkable item."""
        item = _QStandardItem(text)
        item.setData(data, _Qt.ItemDataRole.UserRole)
        item.setFlags(
            item.flags()
            | _Qt.ItemFlag.ItemIsEnabled
            | _Qt.ItemFlag.ItemIsUserCheckable,
        )
        item.setCheckState(_Qt.CheckState.Unchecked)
        self._itemModel().appendRow(item)

    def selectedData(self) -> list[object]:
        """Return user data for checked items."""
        model = self._itemModel()
        return [
            model.item(row).data(_Qt.ItemDataRole.UserRole)
            for row in range(model.rowCount())
            if model.item(row).checkState() == _Qt.CheckState.Checked
        ]

    def setSelectedData(self, values: list[object] | set[object]):
        """Check items whose user data is contained in ``values``."""
        selected = set(values)
        model = self._itemModel()
        for row in range(model.rowCount()):
            item = model.item(row)
            item.setCheckState(
                _Qt.CheckState.Checked
                if item.data(_Qt.ItemDataRole.UserRole) in selected
                else _Qt.CheckState.Unchecked,
            )
        self._refreshText()

    def _itemModel(self) -> _QStandardItemModel:
        model = self.model()
        if not isinstance(model, _QStandardItemModel):
            raise TypeError("MultiSelectComboBox requires QStandardItemModel")
        return model

    def _refreshText(self):
        model = self._itemModel()
        labels = [
            model.item(row).text()
            for row in range(model.rowCount())
            if model.item(row).checkState() == _Qt.CheckState.Checked
        ]
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            lineEdit.setText("、".join(labels) if labels else self._emptyText)

    def _toggleIndex(self, index: _QModelIndex):
        item = self._itemModel().itemFromIndex(index)
        if item is None:
            return
        item.setCheckState(
            _Qt.CheckState.Unchecked
            if item.checkState() == _Qt.CheckState.Checked
            else _Qt.CheckState.Checked,
        )
        self._refreshText()
        self.selectionChanged.emit()

    @_override
    def eventFilter(self, watched: _QObject, event: _QEvent) -> bool:
        """Toggle the popup or the clicked row without closing the popup."""
        if watched is self.lineEdit() and event.type() == _QEvent.Type.MouseButtonPress:
            if self.view().isVisible():
                self.hidePopup()
            else:
                self.showPopup()
            return True
        if watched is self.view().viewport():
            if event.type() == _QEvent.Type.MouseButtonPress:
                return True
            if event.type() == _QEvent.Type.MouseButtonRelease and isinstance(
                event,
                _QMouseEvent,
            ):
                index = self.view().indexAt(event.position().toPoint())
                if index.isValid():
                    self._toggleIndex(index)
                return True
        return super().eventFilter(watched, event)
