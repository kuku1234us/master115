# ./master115/ui/faceswap_components/person_badge.py
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy # Changed to QHBoxLayout for main layout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect # Added QRect
from PyQt6.QtGui import QPixmap, QColor, QPainter, QBrush, QPen, QBitmap, QPainterPath, QFont # Added QPainterPath and QFont
from typing import Optional

# Import the new Avatar component
from .avatar import Avatar

# Need manager to check if running
from ...models.faceswap_manager import FaceSwapManager

# --- Helper Classes --- #
class ProgressOverlay(QWidget):
    """A widget that displays a progress counter on top of everything."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText(None)  # No text initially
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Let mouse events pass through
        self.hide()  # Initially hidden
        
    def setText(self, text: Optional[str]):
        """Set the text to display, or hide the overlay if None."""
        self._text = text
        if text is None:
            self.hide()
        else:
            self.show()
            self.raise_()  # Ensure this widget is on top
            self.update()
            
    def paintEvent(self, event):
        """Draw the overlay with text."""
        if not self._text:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fully opaque black background with white text
        overlay_color = QColor(0, 0, 0, 255)  # Black, fully opaque
        text_color = QColor(240, 240, 240, 255)  # White/light grey text
        
        # Calculate text dimensions 
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        text_metrics = painter.fontMetrics()
        text_rect = text_metrics.boundingRect(self._text)
        
        # Size the overlay box
        box_height = text_rect.height() + 4  # Padding
        box_width = text_rect.width() + 8  # Padding
        
        # Position centered in the widget
        box_x = (self.width() - box_width) / 2
        box_y = (self.height() - box_height) / 2
        
        overlay_rect = QRect(int(box_x), int(box_y), int(box_width), int(box_height))
        
        # Draw background box
        painter.setBrush(QBrush(overlay_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(overlay_rect, 3, 3)  # Rounded corners
        
        # Draw text
        painter.setPen(QPen(text_color))
        painter.drawText(overlay_rect, Qt.AlignmentFlag.AlignCenter, self._text)

# --- Remove Helper Function --- #
# def make_round_pixmap(src: QPixmap, size: int) -> QPixmap:
#    ...
# ---------------------------- #

class PersonBadge(QWidget): # Changed inheritance from QFrame to QWidget
    """A widget representing a person with an avatar and name, acting as a toggle button."""
    toggled = pyqtSignal(str, bool) # Emit person_name and is_selected state
    context_menu_requested = pyqtSignal(str) # Emit person_name when clicked during run

    def __init__(self, person_name: str, first_image_path: str = None, swap_manager: FaceSwapManager = None, parent=None):
        super().__init__(parent)
        self.setObjectName("personBadge")
        # Remove frame specific stuff
        # self.setFrameShape(QFrame.Shape.StyledPanel)
        # self.setFrameShadow(QFrame.Shadow.Raised)

        self.person_name = person_name
        self.first_image_path = first_image_path
        self.swap_manager = swap_manager
        self.is_selected = False
        self._progress_text: Optional[str] = None # To store overlay text like "X/Y"

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

        # Avatar Widget (Replaced QLabel)
        self.avatar_size = 32 # Smaller avatar size like example
        self.avatar_widget = Avatar(size=self.avatar_size, parent=self)
        # Avatar component handles its own placeholder and loading

        # Name Label
        self.name_label = QLabel(self.person_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        # Adjust font size/weight if needed
        self.name_label.setStyleSheet("font-size: 10pt; background-color: transparent; border: none;")

        layout.addWidget(self.avatar_widget)
        layout.addWidget(self.name_label)
        # layout.addStretch() # No stretch needed for this style

        # Create the overlay widget (added last to be on top)
        self.progress_overlay = ProgressOverlay(self)
        
        self.setLayout(layout)

        # Size policy: Fixed height, expanding width (or fixed width? Let's try fixed first)
        # self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.avatar_size + 8) # Based on avatar size + vertical margins
        # Set a reasonable minimum width, actual width might depend on name length
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def resizeEvent(self, event):
        """Ensure the overlay covers the entire widget when resized."""
        super().resizeEvent(event)
        if hasattr(self, 'progress_overlay'):
            self.progress_overlay.setGeometry(self.rect())

    def _load_avatar(self):
        """Sets the image for the avatar widget."""
        # Delegate image loading and display to the Avatar widget
        self.avatar_widget.setImage(self.first_image_path)

    def mousePressEvent(self, event):
        """Handle mouse clicks to toggle the selected state OR request context menu."""
        if event.button() == Qt.MouseButton.LeftButton:
            is_running = self._is_automation_running()
            print(f"[DEBUG] PersonBadge '{self.person_name}' clicked. Automation running: {is_running}")
            
            if is_running:
                # If running, emit signal to request context menu
                print(f"[DEBUG] Emitting context_menu_requested for '{self.person_name}'")
                self.context_menu_requested.emit(self.person_name)
            else:
                # If not running, toggle selection as usual
                self.toggle_selection()
        # Allow right-click context menus if needed in the future by calling super
        # super().mousePressEvent(event)

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
        # NO LONGER NEEDED - Avatar handles its own styling
        # if self.avatar_widget.pixmap() and not self.avatar_widget.pixmap().isNull():
        #      ...
        # else:
        #      ...

    def _is_automation_running(self) -> bool:
        """Check if the automation process is running via the stored manager."""
        # Use the stored manager instance
        if self.swap_manager:
            return self.swap_manager.is_running()
        else:
            # Log an error or warning if manager is missing?
            # print(f"[WARN] PersonBadge {self.person_name} has no swap_manager instance.")
            return False

    # --- Methods to control the overlay --- #
    def set_progress_text(self, text: Optional[str]):
        """Sets the text for the progress overlay (e.g., "X/Y" or None to hide)."""
        self._progress_text = text
        self.progress_overlay.setText(text)
        # Make sure the overlay is properly sized and positioned
        if text is not None:
            self.progress_overlay.setGeometry(self.rect())
            self.progress_overlay.raise_()  # Ensure it's on top

    def show_progress_overlay(self, show: bool, text: str = ""):
        """Convenience method to show/hide the overlay."""
        self.set_progress_text(text if show else None)
    # -------------------------------------- #

    # --- Getters/Setters --- #
    def set_selected(self, selected: bool):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update_visuals()

    def get_person_name(self) -> str:
        return self.person_name

    # Add methods to get/set image paths later if needed

