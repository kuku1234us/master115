import os
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush, QResizeEvent, QMouseEvent, QPainterPath

from qt_base_app.models import Logger
from qt_base_app.theme import ThemeManager

# Imports for bottom overlay avatar
from ...models.people_manager import PeopleManager
from .avatar import make_round_pixmap

# Constants for overlay drawing
OVERLAY_AVATAR_SIZE = 32 # Match PersonBadge size
OVERLAY_PADDING = 4

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
        self._display_number = self.index + 1 # Store the initial display number

        self._original_pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._round_avatar_pixmap: QPixmap | None = None

        # Set size policy to expanding vertically, preferred horizontally
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._setup_ui()
        self._load_image()
        self._load_and_prepare_avatar()

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

    def _load_and_prepare_avatar(self):
        """Finds, loads, and prepares the round avatar pixmap once."""
        self._round_avatar_pixmap = None # Reset in case called multiple times

        full_filename = self.image_path.stem
        filename_parts = full_filename.split(" ")
        person_name = filename_parts[0] if len(filename_parts) > 0 else None
        face_stem = filename_parts[1] if len(filename_parts) > 1 else None

        if not person_name or not face_stem:
             self.logger.warn(self.caller, f"Could not parse person/face stem from filename: {full_filename}")
             return # Cannot proceed

        original_face_path_str = None
        try:
            # Find the path using PeopleManager
            original_face_path_str = PeopleManager.instance().find_face_image_path(person_name, face_stem)
        except Exception as find_err:
            self.logger.error(self.caller, f"Error finding original face path for {person_name}/{face_stem}: {find_err}")
            # Fall through, path is None

        if original_face_path_str:
            try:
                # Load the pixmap
                original_pixmap = QPixmap(original_face_path_str)
                if original_pixmap.isNull():
                     raise ValueError("Failed to load QPixmap from path")
                # Make it round and store it
                self._round_avatar_pixmap = make_round_pixmap(original_pixmap, OVERLAY_AVATAR_SIZE)
                self.logger.debug(self.caller, f"Successfully loaded and prepared avatar for {person_name}/{face_stem}")
            except Exception as e:
                self.logger.debug(self.caller, f"Could not load/process avatar for {person_name}/{face_stem} from {original_face_path_str}: {e}")
                self._round_avatar_pixmap = None # Ensure it's None on error
        else:
            # Path not found by PeopleManager
            self.logger.debug(self.caller, f"Original face path not found for {person_name}/{face_stem}")

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
            # Use minimum width if no pixmap - adjusted to use minimumSizeHint
            min_width = self.minimumSizeHint().width()
            self.setFixedWidth(min_width if min_width > 0 else 100) # Ensure positive width

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
            painter.drawText(digit_rect, Qt.AlignmentFlag.AlignCenter, str(self._display_number))

            # 2. Face Image Name Overlay (Bottom-Center)
            self._draw_bottom_overlay(painter, widget_rect)

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

    def _draw_bottom_overlay(self, painter: QPainter, widget_rect: QRectF):
        """Draws the bottom overlay with avatar and face stem."""
        # --- Simplified: Use pre-loaded avatar, only parse for text ---
        full_filename = self.image_path.stem
        filename_parts = full_filename.split(" ")
        # person_name = filename_parts[0] if len(filename_parts) > 0 else None # Not needed here anymore
        face_stem = filename_parts[1] if len(filename_parts) > 1 else full_filename # Fallback to full stem

        # Setup colors and font
        label_bg_color = QColor(0, 0, 0, 180)
        label_text_color = QColor(255, 255, 255, 255)
        placeholder_avatar_color = QColor("#555555")

        filename_font = QFont("Arial", 18)
        filename_font.setBold(True)
        painter.setFont(filename_font)
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(face_stem)
        text_height = font_metrics.height()

        # Calculate sizes
        avatar_width_with_padding = OVERLAY_AVATAR_SIZE + OVERLAY_PADDING
        total_content_width = avatar_width_with_padding + text_width
        total_overlay_width = total_content_width + 2 * OVERLAY_PADDING
        overlay_height = max(OVERLAY_AVATAR_SIZE, text_height) + 2 * OVERLAY_PADDING

        # Positioning
        scrollbar_clearance = 20
        bg_rect_x = (widget_rect.width() - total_overlay_width) / 2
        bg_rect_y = widget_rect.height() - 1.5*overlay_height - scrollbar_clearance
        bg_rect = QRectF(bg_rect_x, bg_rect_y, total_overlay_width, overlay_height)

        # Draw background
        painter.setBrush(QBrush(label_bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 3, 3)

        # --- Draw Avatar (from pre-loaded pixmap) --- #
        avatar_x = bg_rect.left() + OVERLAY_PADDING
        avatar_y = bg_rect.top() + (bg_rect.height() - OVERLAY_AVATAR_SIZE) / 2

        # <<< REMOVED PeopleManager lookup and subsequent loading logic >>>
        # original_face_path = None
        # if person_name: # Only try if we could parse person name
        #     try:
        #         original_face_path = PeopleManager.instance().find_face_image_path(person_name, face_stem)
        #     except Exception as find_err:
        #          self.logger.error(self.caller, f"Error finding original face path for {person_name}/{face_stem}: {find_err}")
        #          original_face_path = None # Ensure placeholder is drawn
        #
        # if original_face_path:
        #     try:
        #         original_pixmap = QPixmap(original_face_path)
        #         if original_pixmap.isNull(): raise ValueError("Failed to load pixmap")
        #         avatar_pixmap = make_round_pixmap(original_pixmap, OVERLAY_AVATAR_SIZE)
        #         painter.drawPixmap(int(avatar_x), int(avatar_y), avatar_pixmap)
        #     except Exception as e:
        #         self.logger.debug(self.caller, f"Could not load avatar for {person_name}/{face_stem}: {e}")
        #         original_face_path = None # Flag to draw placeholder
        #
        # if not original_face_path: # Draw placeholder if path not found or load failed
        #     # ... placeholder drawing logic ...

        # <<< ADDED: Directly use self._round_avatar_pixmap >>>
        if self._round_avatar_pixmap:
             painter.drawPixmap(int(avatar_x), int(avatar_y), self._round_avatar_pixmap)
        else: # Draw placeholder if pre-load failed or path not found
            painter.setBrush(placeholder_avatar_color)
            painter.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.addEllipse(QRectF(avatar_x, avatar_y, OVERLAY_AVATAR_SIZE, OVERLAY_AVATAR_SIZE))
            painter.drawPath(path)
            painter.setBrush(Qt.BrushStyle.NoBrush) # Reset brush

        # --- Draw Text --- #
        text_x = avatar_x + OVERLAY_AVATAR_SIZE + OVERLAY_PADDING
        text_y = bg_rect.top() + (bg_rect.height() - text_height) / 2 # Center vertically
        text_rect = QRectF(text_x, text_y, text_width, text_height)

        painter.setPen(QPen(label_text_color))
        painter.setFont(filename_font) # Ensure font is set for text
        # Align text left and center vertically within its calculated area
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, face_stem)

    def sizeHint(self) -> QSize:
        """Provide a size hint based on the scaled pixmap."""
        if self._scaled_pixmap:
            return self._scaled_pixmap.size()
        elif self._original_pixmap:
            # Use minimumSizeHint for consistent fallback sizing
            min_height = self.minimumSizeHint().height()
            min_height = max(min_height, 150) # Ensure a reasonable minimum
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

    def set_approval_state(self, approved: bool):
        """Explicitly sets the approval state and triggers a repaint if changed."""
        if self.is_approved != approved:
            self.is_approved = approved
            self.logger.debug(self.caller, f"Approval state for {self.image_path.name} set to: {self.is_approved}")
            self.update() # Redraw if state changed

    def get_approval_state(self) -> bool:
        """Returns the current approval state."""
        return self.is_approved

    def get_image_path(self) -> Path:
        """Returns the path of the image being displayed."""
        return self.image_path

    def set_display_number(self, number: int):
        """Updates the number displayed in the overlay."""
        if self._display_number != number:
            self.logger.debug(self.caller, f"Updating display number for {self.image_path.name} to {number}")
            self._display_number = number
            self.update() # Trigger repaint with the new number

    # TODO: Add method to report approval state
    # TODO: Override paintEvent for overlays OR manage layered QLabel widgets 