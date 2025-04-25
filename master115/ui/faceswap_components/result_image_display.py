import os
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush, QResizeEvent, QMouseEvent

from qt_base_app.models import Logger
from qt_base_app.theme import ThemeManager

class ResultImageDisplay(QWidget):
    """
    Widget to display a single face swap result image within the review popup,
    including overlays for numbering and approval status.
    """

    def __init__(self, image_path: Path, index: int, parent=None):
        """
        Initialize the display widget.

        Args:
            image_path (Path): Path to the result image file.
            index (int): The 1-based index for the digit overlay.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.logger = Logger.instance()
        self.theme = ThemeManager.instance()
        self.caller = "ResultImageDisplay"

        self.image_path = image_path
        self.index = index # Store 0-based index
        self.is_approved = False # Initial state

        self._original_pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None

        # Set size policy to expanding vertically, preferred horizontally
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._setup_ui()
        self._load_image()

    def _setup_ui(self):
        """Minimal UI setup, painting handled by paintEvent."""
        # We will use paintEvent for drawing image and overlays
        # self.setMinimumSize(100, 150) # No longer needed, height controlled by ReviewPopupDialog

    def _load_image(self):
        """Load the original image pixmap."""
        try:
            if self.image_path.is_file():
                pixmap = QPixmap(str(self.image_path))
                if not pixmap.isNull():
                    self._original_pixmap = pixmap
                else:
                    self.logger.error(self.caller, f"Failed to load QPixmap from {self.image_path}")
                    self._original_pixmap = None # Ensure it's reset
            else:
                self.logger.warn(self.caller, f"Image file not found: {self.image_path}")
                self._original_pixmap = None

            # Initial update after loading (or failing to load)
            self.updateGeometry() # Ensure layout knows initial size hint
            self.update()         # Trigger initial paint
        except Exception as e:
            self.logger.error(self.caller, f"Error loading image {self.image_path}: {e}", exc_info=True)
            self._original_pixmap = None

    def resizeEvent(self, event: QResizeEvent):
        """Handle widget resize event to rescale the pixmap and set fixed width."""
        super().resizeEvent(event)
        if self._original_pixmap:
            # Scale pixmap to fit the new widget height, keeping aspect ratio
            self._scaled_pixmap = self._original_pixmap.scaledToHeight(
                self.height(),
                Qt.TransformationMode.SmoothTransformation
            )
            # Set fixed width based on the scaled image width
            self.setFixedWidth(self._scaled_pixmap.width())
        else:
            self._scaled_pixmap = None
            # Use minimum width if no pixmap
            self.setFixedWidth(self.minimumSize().width())

        self.update() # Trigger repaint

    def paintEvent(self, event):
        """Paint the scaled image and overlays."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get widget dimensions
        widget_rect = self.rect()

        if self._scaled_pixmap:
            # Draw pixmap at top-left corner (0,0) of this widget
            # The widget's size is now controlled by resizeEvent to match the pixmap
            painter.drawPixmap(0, 0, self._scaled_pixmap)

            # --- Draw Overlays ---
            overlay_margin = 5 # Pixels from corner
            digit_diameter = 24

            # 1. Digit Overlay (Top-Left)
            digit_rect = QRectF(
                overlay_margin,
                overlay_margin,
                digit_diameter,
                digit_diameter
            )
            # Change digit background based on approval state
            digit_bg_color = QColor(30, 160, 30, 160) if self.is_approved else QColor(0, 0, 0, 128)
            painter.setBrush(QBrush(digit_bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(digit_rect)

            painter.setPen(QPen(Qt.GlobalColor.white))
            # Adjust font size based on diameter
            font = QFont("Arial", int(digit_diameter * 0.6))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(digit_rect, Qt.AlignmentFlag.AlignCenter, str(self.index + 1)) # index is 0-based

        else:
            # Draw placeholder text if image failed to load
            secondary_text_color = self.theme.get_color('text', 'secondary')
            fallback_color = Qt.GlobalColor.gray # Fallback if theme color is None
            pen_color = QColor(secondary_text_color) if secondary_text_color else fallback_color
            painter.setPen(QPen(pen_color))
            font = QFont("Arial", 12)
            painter.setFont(font)
            error_text = "Load Failed" if self.image_path.exists() else "Not Found"
            if self._original_pixmap is None and self.image_path.exists() and self.image_path.is_file():
                error_text = "Error" # Generic error if file exists but load failed
            painter.drawText(widget_rect, Qt.AlignmentFlag.AlignCenter, error_text)

    def sizeHint(self) -> QSize:
        """Provide a size hint based on the scaled pixmap."""
        if self._scaled_pixmap:
            return self._scaled_pixmap.size()
        elif self._original_pixmap:
            # Provide hint based on original aspect ratio scaled to minimum height
            min_height = self.minimumSize().height()
            aspect_ratio = self._original_pixmap.width() / self._original_pixmap.height() if self._original_pixmap.height() > 0 else 1
            return QSize(int(min_height * aspect_ratio), min_height)
        else:
            # Return a default minimum size if no image is loaded
            return QSize(100, 150)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks to toggle approval status."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.logger.debug(self.caller, f"Mouse click detected on image: {self.image_path.name}")
            self.toggle_approval()
        else:
            super().mousePressEvent(event) # Pass other button clicks to base class

    def toggle_approval(self):
        """Toggles the approval state and triggers a repaint."""
        self.is_approved = not self.is_approved
        self.logger.debug(self.caller, f"Approval state for {self.image_path.name} toggled to: {self.is_approved}")
        self.update() # Redraw to show/hide checkmark

    def get_approval_state(self) -> bool:
        """Returns the current approval state."""
        return self.is_approved

    def get_image_path(self) -> Path:
        """Returns the path of the image being displayed."""
        return self.image_path

    # TODO: Add method to report approval state
    # TODO: Override paintEvent for overlays OR manage layered QLabel widgets 