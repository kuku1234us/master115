import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout,
    QApplication, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtGui import QKeyEvent, QResizeEvent

# Local Imports
from .result_image_display import ResultImageDisplay # Will be created next
from qt_base_app.models import Logger

class ReviewPopupDialog(QDialog):
    """
    Modal dialog for reviewing a group of face swap results for a single
    source image and person.
    """

    # --- Signals --- #
    # Signal requesting navigation to the next item in the main list
    navigate_next = pyqtSignal()
    # Signal requesting navigation to the previous item in the main list
    navigate_previous = pyqtSignal()
    # Signal indicating review is complete for the current item, 
    # providing the original source path to identify it for removal.
    review_complete = pyqtSignal(str)
    # Signal with review decision data: original_source_path, approved_paths, unapproved_paths
    review_processed = pyqtSignal(str, list, list)

    def __init__(self, review_item: Dict[str, Any], parent=None):
        """
        Initialize the dialog.

        Args:
            review_item (Dict[str, Any]): Dictionary containing review data from ReviewManager.
                                           Expected keys: 'original_source_path', 'completed_source_path', 'result_image_paths'.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = "ReviewPopupDialog"

        # Store initial data
        self.current_review_item = review_item
        self.original_source_path: Optional[str] = None
        self.result_paths: List[str] = []
        self.person_name: str = "Unknown Person"
        self.source_filename: str = "Unknown Source"
        self.result_displays: List[ResultImageDisplay] = []

        self.setWindowTitle("Face Swap Review") # Generic initial title
        self.setModal(True) # Make it modal
        self.setMinimumSize(800, 600) # Start with a reasonable minimum size

        self._setup_ui()
        self.load_review_item(self.current_review_item) # Load initial data

    def _setup_ui(self):
        """Set up the main layout and widgets for the dialog."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # --- Scroll Area for Images ---
        self.scroll_area = QScrollArea()
        # Ensure scroll area expands vertically
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidgetResizable(False) # Let content determine its size
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Only horizontal scroll needed

        # Install event filter to intercept keyboard events from scroll area
        self.scroll_area.installEventFilter(self)
        # Set strong focus policy to ensure dialog gets keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Content widget and layout for the scroll area
        self.image_container_widget = QWidget()
        self.image_layout = QHBoxLayout(self.image_container_widget)
        self.image_layout.setContentsMargins(5, 5, 5, 5)
        self.image_layout.setSpacing(10)
        self.image_layout.setAlignment(Qt.AlignmentFlag.AlignLeft) # Align images left

        self.scroll_area.setWidget(self.image_container_widget)
        self.main_layout.addWidget(self.scroll_area, 1) # Give scroll area stretch factor

    def load_review_item(self, review_item: Dict[str, Any]):
        """Loads the data for a specific review item into the dialog."""
        self.logger.debug(self.caller, f"Loading review item: {review_item.get('original_source_path')}")
        self.current_review_item = review_item

        # Extract data (with defaults/error handling)
        self.original_source_path = self.current_review_item.get('original_source_path')
        self.result_paths = self.current_review_item.get('result_image_paths', [])

        # Infer display names (same logic as before)
        self.person_name = "Unknown Person"
        self.source_filename = "Unknown Source"
        if self.result_paths:
             try:
                 first_result_name = Path(self.result_paths[0]).name
                 parts = first_result_name.split(' ', 2)
                 if len(parts) >= 3:
                     self.person_name = parts[0]
                     self.source_filename = parts[2].rsplit('.', 1)[0]
             except Exception as e:
                 self.logger.warn(self.caller, f"Could not parse names from first result path {self.result_paths[0]}: {e}")
        else:
            self.logger.warn(self.caller, "No result paths found in review item.")
            if self.original_source_path:
                 # Fallback to using original source filename if possible
                 try:
                     self.source_filename = Path(self.original_source_path).name
                 except Exception:
                      pass # Keep default

        # Update Title
        self.setWindowTitle(f"Review: {self.person_name} / {self.source_filename}")

        self._populate_images()

    def _populate_images(self):
        """Creates ResultImageDisplay widgets and adds them to the layout."""
        # Clear existing widgets
        self.result_displays = []
        while self.image_layout.count():
             item = self.image_layout.takeAt(0)
             widget = item.widget()
             if widget:
                 widget.deleteLater()

        if not self.result_paths:
             error_label = QLabel("No result images found for this item.")
             error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             self.image_layout.addWidget(error_label)
             return

        for index, image_path_str in enumerate(self.result_paths):
             try:
                 image_path = Path(image_path_str)
                 if image_path.is_file():
                     # Create and add the display widget
                     display_widget = ResultImageDisplay(image_path, index, parent=self.image_container_widget)
                     self.image_layout.addWidget(display_widget)
                     self.result_displays.append(display_widget)
                 else:
                     self.logger.warn(self.caller, f"Result image file not found: {image_path_str}")
                     # Add placeholder for missing files
                     placeholder = QLabel(f"Image {index+1}\nNot Found")
                     placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                     placeholder.setWordWrap(True)
                     placeholder.setFrameShape(QWidget.Shape.Box)
                     placeholder.setStyleSheet("border: 1px dashed gray; color: gray; min-width: 150px; min-height: 150px;")
                     self.image_layout.addWidget(placeholder)
             except Exception as e:
                 self.logger.error(self.caller, f"Error creating display widget for {image_path_str}: {e}", exc_info=True)
                 # Add error placeholder
                 placeholder = QLabel(f"Image {index+1}\nLoad Error")
                 placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                 placeholder.setWordWrap(True)
                 placeholder.setFrameShape(QWidget.Shape.Box)
                 placeholder.setStyleSheet("border: 1px dashed red; color: red; min-width: 150px; min-height: 150px;")
                 self.image_layout.addWidget(placeholder)

        # Explicitly activate the layout to force recalculation after adding widgets
        self.image_layout.activate()

    def resizeEvent(self, event: QResizeEvent):
        """Resize the image container and its children to the viewport height."""
        super().resizeEvent(event)

        # 1. Give the container the full viewport height
        viewport_height = self.scroll_area.viewport().height()
        # Prevent setting zero height if viewport isn't ready
        if viewport_height > 0 and self.result_displays:
            # Calculate dimensions for all ResultImageDisplay widgets and container 
            total_width = 0
            left_margin, _, right_margin, _ = self.image_layout.getContentsMargins()
            
            # First pass: Set fixed height on all widgets 
            for w in self.result_displays:
                w.setFixedHeight(viewport_height)
            
            # Make sure we process all Qt events to ensure image scaling happens
            QApplication.processEvents()
            
            # Second pass: Calculate and set the total width based on actual widget sizes
            for w in self.result_displays:
                # Get the actual width from each display after height scaling
                display_width = w.width()
                if display_width <= 10:  # Fallback if width not yet available
                    if w._original_pixmap and w._original_pixmap.height() > 0:
                        # Calculate width based on aspect ratio
                        aspect_ratio = w._original_pixmap.width() / w._original_pixmap.height()
                        display_width = int(viewport_height * aspect_ratio)
                    else:
                        display_width = viewport_height  # Default if no image
                
                total_width += display_width
                
            # Add layout spacing and margins
            total_width += self.image_layout.spacing() * (len(self.result_displays) - 1)
            total_width += left_margin + right_margin
            
            # Set the container dimensions
            self.image_container_widget.setFixedHeight(viewport_height)
            self.image_container_widget.setFixedWidth(total_width)
            
            # Force layout update
            self.image_layout.activate()
            self.logger.debug(self.caller, f"Set container width to {total_width}px for {len(self.result_displays)} images")

    # --- Event Handling --- #

    def keyPressEvent(self, event: QKeyEvent):
        """Handle hotkey presses."""
        key = event.key()

        # TODO: Implement hotkey logic (0-9, +, Up/Down/PgUp/PgDn)
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
             self._handle_digit_key(key - Qt.Key.Key_0)
        elif key == Qt.Key.Key_0:
             self._handle_digit_key(10) # Handle 0 as 10th item if needed
        elif key == Qt.Key.Key_Plus:
             self._handle_plus_key()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
             self.logger.debug(self.caller, "Up arrow or Page Up pressed - navigating to previous item")
             # Emit signal to inform FaceReviewPage to navigate to previous item
             self.navigate_previous.emit()
             # Don't close dialog - FaceReviewPage handles navigation
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
             self.logger.debug(self.caller, "Down arrow or Page Down pressed - navigating to next item")
             # Emit signal to inform FaceReviewPage to navigate to next item
             self.navigate_next.emit()
             # Don't close dialog - FaceReviewPage handles navigation
        elif key == Qt.Key.Key_Escape:
            self.reject() # Close on Escape
        else:
            super().keyPressEvent(event) # Pass other keys to base class

    # --- Hotkey Action Methods (Placeholders) --- #

    def _handle_digit_key(self, number: int):
        """Toggles the approval state for the image corresponding to the digit."""
        index = number - 1 # Convert 1-based number to 0-based index
        if 0 <= index < len(self.result_displays):
            self.logger.debug(self.caller, f"Toggling approval for image #{number}")
            self.result_displays[index].toggle_approval()
        else:
            self.logger.debug(self.caller, f"Digit key {number} pressed, but no corresponding image found.")

    def _handle_plus_key(self):
        """Handles the '+' key press: Gathers decisions and emits signal."""
        self.logger.debug(self.caller, "'+' key pressed. Gathering review decisions...")

        approved_result_paths: List[str] = []
        unapproved_result_paths: List[str] = []

        # 1. Iterate through displayed images and categorize paths
        for display_widget in self.result_displays:
            img_path_str = str(display_widget.get_image_path().resolve()) # Use resolved string path
            if display_widget.get_approval_state():
                approved_result_paths.append(img_path_str)
            else:
                unapproved_result_paths.append(img_path_str)

        self.logger.debug(self.caller, f"Approved: {len(approved_result_paths)}, Unapproved: {len(unapproved_result_paths)}")

        # 2. Emit signal with decisions
        if self.original_source_path:
            # Emit the signal with the original path and lists of result paths
            self.review_processed.emit(
                self.original_source_path,
                approved_result_paths,
                unapproved_result_paths
            )
        else:
            self.logger.error(self.caller, "Cannot process review, original_source_path is missing!")
            # Optionally show error to user
            self.reject() # Close dialog on error

    def eventFilter(self, watched_object, event):
        """Filter events for child widgets to intercept navigation keys from scroll area."""
        if watched_object == self.scroll_area and event.type() == event.Type.KeyPress:
            key = event.key()
            # If it's one of our navigation keys, handle it in the dialog
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                self.logger.debug(self.caller, f"Intercepted navigation key from scroll area: {key}")
                # Process the key in our keyPressEvent handler
                self.keyPressEvent(event)
                # Tell Qt we've handled this event
                return True
        # For other events, use standard event processing
        return super().eventFilter(watched_object, event)


