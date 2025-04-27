from typing import Optional

from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QPainterPath, QFont # Added QPainterPath, QFont
from PyQt6.QtCore import Qt, QSize, QRect # Added QRect

from qt_base_app.models import Logger

# --- Helper Function (Moved from PersonBadge) --- #
def make_round_pixmap(src: QPixmap, size: int) -> QPixmap:
    """
    Return `src` scaled/cropped to a *smooth* circular pixmap of `size`x`size`.
    """
    if src.isNull():
        return QPixmap(size, size) # Return transparent pixmap if source is null

    # Crop to square first
    src_size = min(src.width(), src.height())
    if src_size <= 0: return QPixmap(size, size) # Handle invalid source size
    
    src_rect = QRect(
       (src.width() - src_size) // 2,
       (src.height() - src_size) // 2,
       src_size,
       src_size
    )
    cropped_src = src.copy(src_rect)
    
    scaled = cropped_src.scaled(
        size, size,
        Qt.AspectRatioMode.IgnoreAspectRatio, # Ignore aspect as it's square
        Qt.TransformationMode.SmoothTransformation
    )

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent) # Ensure transparent background

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)

    painter.drawPixmap(0, 0, scaled) # Draw the scaled image onto the clipped transparent pixmap
    painter.end()
    return result
# ---------------------------------------------- #

class Avatar(QLabel):
    """A QLabel specifically designed to display a round avatar image with placeholders."""
    def __init__(self, size: int = 32, image_path: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = "AvatarWidget"
        self._size = size
        self._image_path: Optional[str] = None

        self.setFixedSize(self._size, self._size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("AvatarWidget") # For potential specific styling
        
        # Initial state is placeholder
        self._show_placeholder()

        # Set image if provided initially
        if image_path:
            self.setImage(image_path)

    def _show_placeholder(self, error: bool = False, letter: Optional[str] = None):
        """Styles the widget as a placeholder circle."""
        bg_color = "#ffcccc" if error else "#cccccc" # Reddish for error, grey otherwise
        border_color = "#aa0000" if error else "#aaaaaa"
        self.setStyleSheet(f"""
            QLabel#AvatarWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {self._size // 2}px;
                color: #555555; /* Text color for letter */
            }}
        """)
        self.setPixmap(QPixmap()) # Clear existing pixmap
        if letter:
            # Set a letter if provided (e.g., first letter of name)
            font = QFont()
            font.setPointSize(int(self._size * 0.5))
            font.setBold(True)
            self.setFont(font)
            self.setText(letter.upper())
        else:
             self.setText("?" if error else "") # Show question mark on error, nothing otherwise

    def setImage(self, image_path: Optional[str]):
        """Loads an image, makes it round, and sets it as the pixmap."""
        self._image_path = image_path
        self.setText("") # Clear any placeholder text

        if not image_path:
            self.logger.debug(self.caller, "setImage called with no path, showing placeholder.")
            self._show_placeholder()
            return

        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self.logger.warn(self.caller, f"Failed to load image (isNull): {image_path}")
                # Extract first letter of filename stem as placeholder
                placeholder_letter = Path(image_path).stem[:1] if Path(image_path).stem else None
                self._show_placeholder(error=True, letter=placeholder_letter)
                return

            rounded_pixmap = make_round_pixmap(pixmap, self._size)
            self.setPixmap(rounded_pixmap)
            # Clear background/border styles to show the pixmap properly
            self.setStyleSheet(f"""
                QLabel#AvatarWidget {{
                    border-radius: {self._size // 2}px;
                    border: none;
                    background-color: transparent;
                }}
            """)
            self.logger.debug(self.caller, f"Successfully set avatar image: {image_path}")
        except Exception as e:
            self.logger.error(self.caller, f"Error processing image {image_path}: {e}", exc_info=True)
            placeholder_letter = Path(image_path).stem[:1] if image_path and Path(image_path).stem else None
            self._show_placeholder(error=True, letter=placeholder_letter) 