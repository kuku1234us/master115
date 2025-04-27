import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout,
    QApplication, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize, QByteArray
from PyQt6.QtGui import QKeyEvent, QResizeEvent

# Local Imports
from .result_image_display import ResultImageDisplay # Will be created next
from qt_base_app.models import Logger
from qt_base_app.models import SettingsManager # Import SettingsManager

class ReviewPopupDialog(QDialog):
    """
    Modal dialog for reviewing a group of face swap results for a single
    source image and person.
    """

    # --- Signals --- #
    # Signal requesting navigation to the next item in the main list
    request_next_item = pyqtSignal()
    # Signal requesting navigation to the previous item in the main list
    request_previous_item = pyqtSignal()
    # Signal indicating review is complete for the current item, 
    # providing the original source path to identify it for removal.
    # DEPRECATED review_complete = pyqtSignal(str)
    # Signal with review decision data: original_source_path, approved_paths, unapproved_paths
    review_processed = pyqtSignal(str, str, list, list)

    # --- Add settings key --- #
    GEOMETRY_SETTING_KEY = "ui/review_popup/geometry"

    # Update constructor signature
    def __init__(self, 
                 person_name: str,
                 original_source_path: str,
                 result_image_paths: List[str],
                 ai_root_dir_str: str, # Added AI root for potential future use
                 parent=None):
        """
        Initialize the dialog.

        Args:
            person_name (str): Name of the person reviewed.
            original_source_path (str): Path to the original source image.
            result_image_paths (List[str]): List of paths to the generated result images.
            ai_root_dir_str (str): The configured AI Root directory path.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = "ReviewPopupDialog"
        self.settings = SettingsManager.instance() # Get settings instance

        # Store initial data directly from arguments
        self.person_name = person_name
        self.original_source_path = original_source_path
        self.result_paths = result_image_paths or []
        self.ai_root_dir = Path(ai_root_dir_str) # Store as Path object
        self.source_filename: str = "Unknown Source"
        self.result_displays: List[ResultImageDisplay] = []

        self.setWindowTitle("Face Swap Review") # Generic initial title
        self.setModal(False) # Make it non-modal now, managed by FaceReviewPage
        self.setMinimumSize(800, 600) # Start with a reasonable minimum size

        self._setup_ui()
        self._update_display_data() # Use helper method to load data

        # --- Restore Geometry --- #
        saved_geometry = self.settings.get(self.GEOMETRY_SETTING_KEY)
        if isinstance(saved_geometry, QByteArray) and not saved_geometry.isEmpty():
            self.logger.debug(self.caller, "Restoring saved dialog geometry.")
            if not self.restoreGeometry(saved_geometry):
                self.logger.warn(self.caller, "Failed to restore saved geometry.")
        else:
             self.logger.debug(self.caller, "No saved geometry found, using default.")
        # ------------------------ #

    def _setup_ui(self):
        """Set up the main layout and widgets for the dialog."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # --- Title Label --- #
        self.title_label = QLabel()
        self.title_label.setObjectName("DialogTitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        self.main_layout.addWidget(self.title_label)
        # ------------------- #

        # --- Scroll Area for Images --- #
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

    def _update_display_data(self):
        """Updates the dialog's title and populates images based on current data."""
        self.logger.debug(self.caller, f"Updating display for: {self.original_source_path}")
        
        # Update source filename from path
        if self.original_source_path:
            try:
                self.source_filename = Path(self.original_source_path).name
            except Exception as e:
                self.logger.warn(f"Could not get filename from source path '{self.original_source_path}': {e}")
                self.source_filename = "Unknown Source"
        else:
            self.source_filename = "Unknown Source"
            
        # Update Title Label
        self.title_label.setText(f"Review: {self.person_name} / {self.source_filename}")

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
        # Trigger size update after populating
        self._update_image_container_size()

    def resizeEvent(self, event: QResizeEvent):
        """Handle widget resize event by recalculating image container size."""
        super().resizeEvent(event)
        self._update_image_container_size()
        
    def showEvent(self, event):
        """Ensure content size is updated when dialog is shown (after potential geometry restore)."""
        super().showEvent(event)
        # Update content size after the dialog is shown and geometry is set
        self._update_image_container_size()

    def _update_image_container_size(self):
        """Calculates and sets the size of the image container based on viewport height."""
        # 1. Give the container the full viewport height
        viewport_height = self.scroll_area.viewport().height()
        # Prevent setting zero height if viewport isn't ready or no displays
        if viewport_height <= 0 or not self.result_displays:
            # Set a default minimum size for the container if needed
            # self.image_container_widget.setMinimumSize(100, 100) 
            return

        # Calculate dimensions for all ResultImageDisplay widgets and container
        total_width = 0
        left_margin, _, right_margin, _ = self.image_layout.getContentsMargins()

        # First pass: Set fixed height on all widgets
        # This might trigger individual resizeEvents in ResultImageDisplay
        for w in self.result_displays:
            w.setFixedHeight(viewport_height)

        # Give Qt a chance to process the height changes and potential resizes
        QApplication.processEvents()

        # Second pass: Calculate and set the total width based on actual widget sizes
        for w in self.result_displays:
            display_width = w.width()
            # Use sizeHint as a fallback if width is still not properly calculated
            if display_width <= 10:
                hint_width = w.sizeHint().width()
                if hint_width > 10: # Use hint if reasonable
                    display_width = hint_width
                elif w._original_pixmap and w._original_pixmap.height() > 0:
                    aspect_ratio = w._original_pixmap.width() / w._original_pixmap.height()
                    display_width = int(viewport_height * aspect_ratio)
                else:
                    display_width = viewport_height # Default fallback
            
            total_width += display_width

        # Add layout spacing and margins
        spacing = self.image_layout.spacing()
        if spacing == -1: spacing = self.style().layoutSpacing(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding, Qt.Orientation.Horizontal)
        if len(self.result_displays) > 1:
             total_width += spacing * (len(self.result_displays) - 1)
             
        total_width += left_margin + right_margin

        # Set the container dimensions
        self.image_container_widget.setFixedHeight(viewport_height)
        # Add a small buffer to width just in case? Sometimes needed.
        self.image_container_widget.setFixedWidth(int(total_width * 1.01)) 

        # Force layout update seems redundant if we set fixed size
        # self.image_layout.activate()
        self.logger.debug(self.caller, f"Set container width to {int(total_width * 1.01)}px for {len(self.result_displays)} images based on viewport height {viewport_height}")

    # --- Event Handling --- #

    def keyPressEvent(self, event: QKeyEvent):
        """Handle hotkey presses."""
        key = event.key()
        self.logger.debug(self.caller, f"keyPressEvent received key: {key} (Text: '{event.text()}')") # Log ALL key presses

        # TODO: Implement hotkey logic (0-9, +, Up/Down/PgUp/PgDn)
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
             self.logger.debug(self.caller, f"Digit key {key - Qt.Key.Key_0} pressed, calling _handle_digit_key...")
             self._handle_digit_key(key - Qt.Key.Key_0)
        elif key == Qt.Key.Key_0:
             self.logger.debug(self.caller, "Digit key 0 pressed, calling _handle_digit_key...")
             self._handle_digit_key(10) # Handle 0 as 10th item if needed
        elif key == Qt.Key.Key_Plus:
             self._handle_plus_key()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
             self.logger.debug(self.caller, "Up arrow or Page Up pressed - navigating to previous item")
             # Emit signal to inform FaceReviewPage to navigate to previous item
             self.request_previous_item.emit()
             # Don't close dialog - FaceReviewPage handles navigation
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
             self.logger.debug(self.caller, "Down arrow or Page Down pressed - navigating to next item")
             # Emit signal to inform FaceReviewPage to navigate to next item
             self.request_next_item.emit()
             # Don't close dialog - FaceReviewPage handles navigation
        elif key == Qt.Key.Key_Minus:
            self._handle_minus_key()
        elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self._handle_enter_key()
        elif key == Qt.Key.Key_Escape:
            self.reject() # Close on Escape
        else:
            super().keyPressEvent(event) # Pass other keys to base class

    # --- Hotkey Action Methods (Placeholders) --- #

    def _handle_digit_key(self, number: int):
        """Toggles the approval state for the image corresponding to the digit."""
        self.logger.debug(self.caller, f"_handle_digit_key called for number: {number}")
        # Only toggle visible items
        index = number - 1 # Convert 1-based number to 0-based index
        # Find the nth *visible* widget
        visible_widgets = [w for w in self.result_displays if w.isVisible()]
        self.logger.debug(self.caller, f"Found {len(visible_widgets)} visible widgets.")
        if 0 <= index < len(visible_widgets):
             target_widget = visible_widgets[index]
             self.logger.debug(self.caller, f"Attempting to toggle approval for visible widget at index {index} (Path: {target_widget.get_image_path().name})")
             target_widget.toggle_approval()
        else:
             self.logger.debug(self.caller, f"Index {index} is out of range for visible widgets (0 to {len(visible_widgets)-1}).")

    def _handle_minus_key(self):
        """Hides and deselects all currently approved images."""
        self.logger.debug(self.caller, "'-' key pressed. Hiding approved items.")
        items_hidden = False
        for widget in self.result_displays:
            # Process only visible widgets that are currently approved
            if widget.isVisible() and widget.get_approval_state():
                self.logger.debug(self.caller, f"Hiding and deselecting: {widget.get_image_path().name}")
                widget.toggle_approval() # Deselect (turn off checkmark)
                widget.setVisible(False)
                items_hidden = True

        if items_hidden:
            # Update layout if items were hidden
            QApplication.processEvents() # Allow visibility changes to process
            self._update_image_container_size() # Recalculate container size
            # --- Re-number visible items --- #
            visible_widgets = [w for w in self.result_displays if w.isVisible()]
            self.logger.debug(self.caller, f"Re-numbering {len(visible_widgets)} visible items.")
            for new_index, widget in enumerate(visible_widgets):
                 widget.set_display_number(new_index + 1)
            # ----------------------------- #
        else:
             self.logger.debug(self.caller, "No visible approved items found to hide.")

    def _handle_enter_key(self):
        """Hides non-approved images and deselects the ones that remain visible."""
        self.logger.debug(self.caller, "Enter key pressed. Hiding non-approved & deselecting remaining.")
        items_processed = False
        visible_widgets_after = []

        for widget in self.result_displays:
            if widget.isVisible():
                if not widget.get_approval_state():
                    # Hide non-approved visible items
                    self.logger.debug(self.caller, f"Hiding non-approved image: {widget.get_image_path().name}")
                    widget.setVisible(False)
                    items_processed = True
                else:
                    # Deselect approved visible items
                    self.logger.debug(self.caller, f"Deselecting initially approved image: {widget.get_image_path().name}")
                    widget.set_approval_state(False)
                    visible_widgets_after.append(widget) # Add to list for re-numbering
                    # No need to set items_processed = True here, as just deselecting doesn't require layout update

        if items_processed: # Only update layout etc. if items were actually hidden
            # Update layout if items were hidden
            QApplication.processEvents() # Allow visibility changes to process
            self._update_image_container_size() # Recalculate container size

            # --- Re-number remaining visible items --- #
            self.logger.debug(self.caller, f"Re-numbering {len(visible_widgets_after)} visible items.")
            for new_index, widget in enumerate(visible_widgets_after):
                 widget.set_display_number(new_index + 1)
            # --------------------------------------- #
        else:
             self.logger.debug(self.caller, "No visible non-approved items found to hide.")
             # Even if nothing was hidden, we might still need to deselect approved items
             if not visible_widgets_after:
                 # Check if there were any visible items initially that were approved
                 processed_deselection = False
                 for widget in self.result_displays:
                      if widget.isVisible() and widget.get_approval_state():
                           widget.set_approval_state(False)
                           processed_deselection = True
                 if processed_deselection:
                      self.logger.debug(self.caller, "Deselected all visible approved items (no items hidden).")

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
                self.person_name,
                self.original_source_path,
                approved_result_paths,
                unapproved_result_paths
            )
            # --- Let the receiver (FaceReviewPage) close the dialog --- #
            # self.accept() 
            # ---------------------------------------------------------- #
        else:
            self.logger.error(self.caller, "Cannot process review, original_source_path is missing!")
            # Optionally show error to user
            self.reject() # Close dialog on error

    def closeEvent(self, event):
        """Save geometry when the dialog is closed."""
        self.logger.debug(self.caller, "Saving dialog geometry on close.")
        geometry_data = self.saveGeometry()
        self.settings.set(self.GEOMETRY_SETTING_KEY, geometry_data) # QByteArray is handled by QSettings
        super().closeEvent(event)

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

    # --- Public Method to Load New Data --- #
    def load_review_item(self, 
                         person_name: str, 
                         original_source_path: str, 
                         result_image_paths: List[str]):
        """Updates the dialog with data for a new review item."""
        self.logger.debug(self.caller, f"****************** Loading new review item: {person_name} / {Path(original_source_path).name}")
        
        # Update internal data storage
        self.person_name = person_name
        self.original_source_path = original_source_path
        self.result_paths = result_image_paths or []
        
        # Update the UI elements based on the new data
        self._update_display_data()
    # -------------------------------------- #


