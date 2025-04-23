# ./master115/ui/faceswap_components/person_badge.py
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy # Changed to QHBoxLayout for main layout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect # Added QRect
from PyQt6.QtGui import QPixmap, QColor, QPainter, QBrush, QPen, QBitmap, QPainterPath # Added QPainterPath

# --- Helper Function --- #
def make_round_pixmap(src: QPixmap, size: int) -> QPixmap:
    """
    Return `src` scaled/cropped to a *smooth* circular pixmap of `size`×`size`.
    """
    # Scale first (SmoothTransformation keeps the photo crisp)
    # Note: Scaling is slightly different here than in the user's _load_avatar example
    # We assume the input `src` pixmap might not be square yet.
    # Let's crop to square first like in the existing _load_avatar logic
    src_size = min(src.width(), src.height())
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
# --------------------- #

class PersonBadge(QWidget): # Changed inheritance from QFrame to QWidget
    """A widget representing a person with an avatar and name, acting as a toggle button."""
    toggled = pyqtSignal(str, bool) # Emit person_name and is_selected state

    def __init__(self, person_name: str, first_image_path: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("personBadge")
        # Remove frame specific stuff
        # self.setFrameShape(QFrame.Shape.StyledPanel)
        # self.setFrameShadow(QFrame.Shadow.Raised)

        self.person_name = person_name
        self.first_image_path = first_image_path
        self.is_selected = False

        # Enable background styling for the widget itself
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._setup_ui()
        self._load_avatar() # Load avatar on init now
        self.update_visuals() # Set initial visual state

    def _setup_ui(self):
        """Set up the UI elements within the badge."""
        # Main layout is now Horizontal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 12, 4) # L, T, R, B padding
        layout.setSpacing(8)
        # layout.setAlignment(Qt.AlignmentFlag.AlignVCenter) # Align items vertically centered

        # Avatar Label
        self.avatar_label = QLabel()
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_size = 32 # Smaller avatar size like example
        self.avatar_label.setFixedSize(self.avatar_size, self.avatar_size)
        # Initial placeholder styling
        self.avatar_label.setStyleSheet(f"""
            QLabel {{
                background-color: #cccccc; /* Placeholder grey */
                border-radius: {self.avatar_size // 2}px; /* Make it circular */
                border: 1px solid #aaaaaa;
            }}
        """)

        # Name Label
        self.name_label = QLabel(self.person_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        # Adjust font size/weight if needed
        self.name_label.setStyleSheet("font-size: 10pt; background-color: transparent; border: none;")

        layout.addWidget(self.avatar_label)
        layout.addWidget(self.name_label)
        # layout.addStretch() # No stretch needed for this style

        self.setLayout(layout)

        # Size policy: Fixed height, expanding width (or fixed width? Let's try fixed first)
        # self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.avatar_size + 8) # Based on avatar size + vertical margins
        # Set a reasonable minimum width, actual width might depend on name length
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _load_avatar(self):
        """Loads, scales, and masks the avatar image using make_round_pixmap."""
        # Clear previous pixmap and styles potentially affected by it
        self.avatar_label.setPixmap(QPixmap())
        default_placeholder_style = f"background-color: #cccccc; border-radius: {self.avatar_size // 2}px; border: 1px solid #aaaaaa;"
        error_placeholder_style = f"background-color: #ffcccc; border-radius: {self.avatar_size // 2}px;"

        if not self.first_image_path:
            print(f"[WARN] No image path for {self.person_name}")
            self.avatar_label.setStyleSheet(default_placeholder_style)
            self.avatar_label.setText("")
            return

        pixmap = QPixmap(self.first_image_path)
        if pixmap.isNull():
            print(f"[WARN] Failed load image: {self.first_image_path}")
            self.avatar_label.setStyleSheet(error_placeholder_style)
            self.avatar_label.setText("?")
            return

        # --- Use the helper function --- #
        rounded_pixmap = make_round_pixmap(pixmap, self.avatar_size)
        # ------------------------------- #

        self.avatar_label.setPixmap(rounded_pixmap)
        # Clear background/border styles to show the pixmap
        self.avatar_label.setStyleSheet(f"border-radius: {self.avatar_size // 2}px; border: none; background: transparent;")
        self.avatar_label.setText("") # Clear error text if any

    def mousePressEvent(self, event):
        """Handle mouse clicks to toggle the selected state."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_selection()
        # Don't call super().mousePressEvent(event) for QWidget if we handle it fully

    def toggle_selection(self):
        """Toggle the selection state and update visuals."""
        self.is_selected = not self.is_selected
        self.update_visuals()
        self.toggled.emit(self.person_name, self.is_selected) # Emit signal

    def update_visuals(self):
        """Update the appearance based on the selected state."""
        border_radius = (self.avatar_size + 8) // 2
        if self.is_selected:
            self.setStyleSheet(f"""
                QWidget#personBadge {{
                    background-color: #192319; /* Dark green background */
                    border: 1px solid #388E3C; /* Keep existing border */
                    border-radius: {border_radius}px;
                }}
                QLabel {{
                    color: #E0E0E0; /* Light grey text (adjust if needed) */
                    background-color: transparent;
                    border: none;
                    font-size: 10pt;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget#personBadge {{
                    background-color: #424242; /* Dark grey background */
                    border: 1px solid #616161;
                    border-radius: {border_radius}px;
                }}
                QLabel {{
                    color: #E0E0E0; /* Light grey text */
                    background-color: transparent;
                    border: none;
                    font-size: 10pt;
                }}
            """)

        # Re-apply specific avatar styling AFTER main widget style is set
        if self.avatar_label.pixmap() and not self.avatar_label.pixmap().isNull():
             # If pixmap exists, ensure transparent background and no border
             self.avatar_label.setStyleSheet(f"border-radius: {self.avatar_size // 2}px; border: none; background: transparent;")
        else:
             # Re-apply placeholder/error style if no valid pixmap
             current_avatar_style = self.avatar_label.styleSheet() 
             # Check if it was previously set to error style
             if "ffcccc" in current_avatar_style: 
                  self.avatar_label.setStyleSheet(f"background-color: #ffcccc; border-radius: {self.avatar_size // 2}px;")
             else: # Apply default placeholder style
                  self.avatar_label.setStyleSheet(f"background-color: #cccccc; border-radius: {self.avatar_size // 2}px; border: 1px solid #aaaaaa;")

    # --- Getters/Setters --- #
    def set_selected(self, selected: bool):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update_visuals()

    def get_person_name(self) -> str:
        return self.person_name

    # Add methods to get/set image paths later if needed

