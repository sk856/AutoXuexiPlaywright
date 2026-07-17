"""Editable combo box with a consistently visible, colored arrow."""

from typing import override as _override
from PySide6.QtGui import QColor as _QColor
from PySide6.QtGui import QPainter as _QPainter
from PySide6.QtGui import QPolygon as _QPolygon
from PySide6.QtGui import QPaintEvent as _QPaintEvent
from PySide6.QtCore import Qt as _Qt
from PySide6.QtCore import QPoint as _QPoint
from PySide6.QtWidgets import QWidget as _QWidget
from PySide6.QtWidgets import QComboBox as _QComboBox


class ColoredArrowComboBox(_QComboBox):
    """Editable combo box whose arrow remains visible under the application QSS."""

    _ARROW_COLOR = _QColor("#6a7bea")
    _DISABLED_ARROW_COLOR = _QColor("#9da8b8")

    def __init__(self, parent: _QWidget | None = None):
        """Initialize the editable selector and reserve room for its arrow."""
        super().__init__(parent)
        lineEdit = self.lineEdit()
        if lineEdit is not None:
            lineEdit.setTextMargins(0, 0, 28, 0)

    @_override
    def paintEvent(self, event: _QPaintEvent):
        """Draw the combo box and overlay a visible colored arrow."""
        super().paintEvent(event)
        painter = _QPainter(self)
        painter.setRenderHint(_QPainter.RenderHint.Antialiasing)
        painter.setPen(_Qt.PenStyle.NoPen)
        painter.setBrush(
            self._ARROW_COLOR if self.isEnabled() else self._DISABLED_ARROW_COLOR,
        )
        centerX = self.width() - 18
        centerY = self.height() // 2
        painter.drawPolygon(
            _QPolygon(
                [
                    _QPoint(centerX - 5, centerY - 2),
                    _QPoint(centerX + 5, centerY - 2),
                    _QPoint(centerX, centerY + 4),
                ],
            ),
        )
        painter.end()
