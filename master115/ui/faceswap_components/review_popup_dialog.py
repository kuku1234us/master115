import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout,
    QApplication, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize, QByteArray, QTimer, QPropertyAnimation, QEasingCurve, QAbstractAnimation
from PyQt6.QtGui import QKeyEvent, QResizeEvent

# Local Imports
from .result_image_display import ResultImageDisplay # Will be created next
from qt_base_app.models import Logger
from qt_base_app.models import SettingsManager # Import SettingsManager

# <<< ADDED Subclass >>>
class InterceptingScrollArea(QScrollArea):
    """A QScrollArea that ignores arrow key presses, allowing them to propagate."""
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Check for all arrow keys and PageUp/PageDown
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
                   Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            event.ignore() # Allow parent widget (dialog) to handle these
        else:
            # Handle other keys (like Home, End if needed) normally
            super().keyPressEvent(event)

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
    # DEPRECATED review_complete = pyqtSignal(str)
    # Signal with review decision data: person_name, source_stem, approved_paths, unapproved_paths
    review_processed = pyqtSignal(str, str, list, list)

    # --- Add settings key --- #
    GEOMETRY_SETTING_KEY = "ui/review_popup/geometry"

    # Update constructor signature
    def __init__(self, 
                 person_name: str,
                 source_stem: str, # Changed from original_source_path
                 result_image_paths: List[str],
                 ai_root_dir_str: str, # Keep for now, might be useful later
                 parent=None):
        """
        Initialize the dialog.

        Args:
            person_name (str): Name of the person reviewed.
            source_stem (str): Stem of the original source image filename.
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
        self.source_stem = source_stem # Store stem
        # self.original_source_path = original_source_path # Removed
        self.result_paths = result_image_paths or []
        self.ai_root_dir = Path(ai_root_dir_str) # Store as Path object
        # self.source_filename: str = "Unknown Source" # No longer needed directly
        self.result_displays: List[ResultImageDisplay] = []
        self._scroll_animation: QPropertyAnimation | None = None # Add member variable

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
        self.scroll_area = InterceptingScrollArea()
        # Ensure scroll area expands vertically
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidgetResizable(False) # Let content determine its size
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Only horizontal scroll needed

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
        self.logger.debug(self.caller, f"Updating display for: {self.source_stem}")
        
        # Update Title Label
        self.title_label.setText(f"Review: {self.person_name} / {self.source_stem}")

        self._populate_images()

    def _populate_images(self):
        """Creates ResultImageDisplay widgets and adds them to the layout."""
        self.logger.debug(self.caller, f"Populating images for {self.source_stem}")
        # Clear existing widgets first
        self.result_displays = []
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.result_paths:
            self.logger.warn(self.caller, "No result paths found, displaying message.")
            error_label = QLabel("No result images found for this item.")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_layout.addWidget(error_label)
            # Ensure container size is updated even when empty
            self._update_image_container_size()
            return

        # Create and add new widgets
        for index, image_path_str in enumerate(self.result_paths):
            try:
                image_path = Path(image_path_str)
                if image_path.is_file():
                    display_widget = ResultImageDisplay(image_path, index, parent=self.image_container_widget)
                    self.image_layout.addWidget(display_widget)
                    self.result_displays.append(display_widget)
                else:
                    self.logger.warn(self.caller, f"Result image file not found: {image_path_str}")
                    placeholder = QLabel(f"Image {index+1}\nNot Found")
                    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder.setWordWrap(True)
                    placeholder.setFrameShape(QWidget.Shape.Box)
                    placeholder.setStyleSheet("border: 1px dashed gray; color: gray; min-width: 150px; min-height: 150px;")
                    self.image_layout.addWidget(placeholder)
            except Exception as e:
                self.logger.error(self.caller, f"Error creating display widget for {image_path_str}: {e}", exc_info=True)
                placeholder = QLabel(f"Image {index+1}\nLoad Error")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setWordWrap(True)
                placeholder.setFrameShape(QWidget.Shape.Box)
                placeholder.setStyleSheet("border: 1px dashed red; color: red; min-width: 150px; min-height: 150px;")
                self.image_layout.addWidget(placeholder)

        # Trigger size update *after* adding all widgets
        self._update_image_container_size()
        self.logger.debug(self.caller, f"Finished populating {len(self.result_displays)} images.")

    def resizeEvent(self, event: QResizeEvent):
        """Handle widget resize event by recalculating image container size."""
        super().resizeEvent(event)
        self._update_image_container_size()
        
    def showEvent(self, event):
        """Ensure content size is updated when dialog is shown (after potential geometry restore)."""
        super().showEvent(event)
        # Delay initial size update slightly to ensure viewport is ready
        QTimer.singleShot(0, self._update_image_container_size)

    def _update_image_container_size(self):
        """
        Sets the fixed height of child image displays and the container,
        then schedules the width calculation.
        """
        # 1. Get available height
        viewport_height = self.scroll_area.viewport().height()

        # 2. Handle empty/invalid state
        if viewport_height <= 0:
            self.logger.debug(self.caller, "_update_image_container_size: Skipping update (viewport <= 0).")
            return
        # Also handle if called before result_displays exists (though unlikely now)
        if not hasattr(self, 'result_displays'):
             self.logger.debug(self.caller, "_update_image_container_size: Skipping update (result_displays not initialized).")
             return

        self.logger.debug(self.caller, f"_update_image_container_size: Setting heights to {viewport_height}px")

        # 3. Set fixed height on all child image displays
        for widget in self.result_displays:
            if widget: # Check if widget is valid
                widget.setFixedHeight(viewport_height)
            else:
                # This shouldn't happen if _populate_images clears correctly
                self.logger.warn(self.caller, "Encountered an invalid (None) widget during height setting.")

        # 4. Set the container's height only.
        self.image_container_widget.setFixedHeight(viewport_height)

        # 5. Schedule the width calculation to run after events are processed
        QTimer.singleShot(0, self._calculate_and_set_container_width)

    def _calculate_and_set_container_width(self):
        """
        Calculates the required width based on child widgets and sets
        the fixed width of the image container. Called via QTimer.singleShot.
        """
        # Check if viewport height is still valid (might have changed)
        viewport_height = self.scroll_area.viewport().height()
        if viewport_height <= 0 or not hasattr(self, 'result_displays') or not self.result_displays:
            # If no valid widgets or height, maybe reset width or do nothing?
            # Setting minimum width prevents complete collapse if called unexpectedly
            self.image_container_widget.setMinimumWidth(10)
            self.logger.debug(self.caller, "_calculate_and_set_container_width: Skipping width calculation (invalid state).")
            return

        self.logger.debug(self.caller, "_calculate_and_set_container_width: Calculating total width...")

        total_width = 0
        left_margin, _, right_margin, _ = self.image_layout.getContentsMargins()
        valid_widgets = [w for w in self.result_displays if w]

        for i, w in enumerate(valid_widgets):
            # Query width *after* event loop has likely processed resize
            display_width = w.width()
            # Fallback logic (important if width() is still unreliable)
            if display_width <= 10:
                hint_width = w.sizeHint().width()
                if hint_width > 10:
                    self.logger.debug(self.caller, f"Widget {i}: Using sizeHint width {hint_width}")
                    display_width = hint_width
                elif hasattr(w, '_original_pixmap') and w._original_pixmap and w._original_pixmap.height() > 0:
                    aspect_ratio = w._original_pixmap.width() / w._original_pixmap.height()
                    calculated_width = int(viewport_height * aspect_ratio)
                    # Ensure minimum width for very tall/thin images
                    display_width = max(calculated_width, 50)
                    self.logger.debug(self.caller, f"Widget {i}: Calculating width from aspect ratio: {display_width}")
                else:
                    display_width = max(viewport_height // 2, 100) # Fallback (wider than tall)
                    self.logger.debug(self.caller, f"Widget {i}: Falling back to calculated width {display_width}")

            total_width += display_width

        # Add layout spacing and margins
        spacing = self.image_layout.spacing()
        if spacing == -1: spacing = self.style().layoutSpacing(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding, Qt.Orientation.Horizontal)
        if len(valid_widgets) > 1:
            total_width += spacing * (len(valid_widgets) - 1)
        total_width += left_margin + right_margin

        # Set the container's calculated width (add small buffer?)
        # final_width = int(total_width * 1.01) # Optional buffer
        final_width = int(total_width)
        # Ensure a minimum width if calculation goes wrong
        final_width = max(final_width, 100)
        self.image_container_widget.setFixedWidth(final_width)

        self.logger.debug(self.caller, f"_calculate_and_set_container_width: Set container width to {final_width}px for {len(valid_widgets)} images.")

        # <<< ADDED: Reset scrollbar to minimum after width is set >>>
        scrollbar = self.scroll_area.horizontalScrollBar()
        if scrollbar:
            self.logger.debug(self.caller, "Resetting scrollbar to minimum.")
            # Stop any ongoing scroll animation before setting value directly
            if self._scroll_animation and self._scroll_animation.state() == QAbstractAnimation.State.Running:
                 self.logger.debug(self.caller, "Stopping scroll animation before resetting position.")
                 self._scroll_animation.stop() # Slot will set self._scroll_animation to None
            # Set value directly for instant reset
            scrollbar.setValue(scrollbar.minimum())
        # <<< END ADDED CODE >>>

    # --- Event Handling --- #

    def keyPressEvent(self, event: QKeyEvent):
        """Handle hotkey presses."""
        key = event.key()
        self.logger.debug(self.caller, f"keyPressEvent received key: {key} (Text: '{event.text()}')")
        
        handled = False # Flag to track if we processed the key

        # Digit keys (1-9, 0)
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
             self._handle_digit_key(key - Qt.Key.Key_0)
             handled = True
        elif key == Qt.Key.Key_0:
             self._handle_digit_key(10)
             handled = True
        # Action keys
        elif key == Qt.Key.Key_Plus:
             self._handle_plus_key()
             handled = True
        elif key == Qt.Key.Key_Minus:
            self._handle_minus_key()
            handled = True
        elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self._handle_enter_key()
            handled = True
        # Vertical Navigation (Signals emitted here)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
             self.request_previous_item.emit()
             handled = True
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
             self.request_next_item.emit()
             handled = True
        # Horizontal Scrolling
        elif key == Qt.Key.Key_Left:
             self.logger.debug(self.caller, "Left arrow pressed - scrolling left")
             self._scroll_left()
             handled = True
        elif key == Qt.Key.Key_Right:
             self.logger.debug(self.caller, "Right arrow pressed - scrolling right")
             self._scroll_right()
             handled = True
        # Scroll to Start/End
        elif key == Qt.Key.Key_Slash or key == Qt.Key.Key_Home: # Added Home
             self.logger.debug(self.caller, f"Slash/Home key ({key}) pressed - scrolling to start")
             self._scroll_to_start()
             handled = True
        elif key == Qt.Key.Key_Asterisk or key == Qt.Key.Key_End: # Added End
             self.logger.debug(self.caller, f"Asterisk/End key ({key}) pressed - scrolling to end")
             self._scroll_to_end()
             handled = True
        # Other
        elif key == Qt.Key.Key_Escape:
            self.reject() # Close on Escape
            handled = True
            
        # Explicitly accept the event if handled
        if handled:
            event.accept()
        else:
            # Pass unhandled keys to the base class
            super().keyPressEvent(event)

    # --- Scrolling Helper Methods ---

    def _get_first_visible_photo_width(self) -> int:
        """Gets the width of the first visible ResultImageDisplay widget."""
        if not hasattr(self, 'result_displays') or not self.result_displays:
            return 200 # Default width if no displays exist

        for widget in self.result_displays:
             # Ensure widget is valid and visible before getting width
             if widget and widget.isVisible():
                 # <<< Return only the widget width >>>
                 width = widget.width()
                 # Return a reasonable minimum if width isn't calculated yet
                 return width if width > 10 else 200

        return 200 # Default if none are visible

    def _animate_scroll(self, target_value: int):
        """Animates the horizontal scrollbar to the target value."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        if not scrollbar: return

        current_value = scrollbar.value()

        # Clamp target value just in case
        target_value = max(scrollbar.minimum(), target_value)
        target_value = min(scrollbar.maximum(), target_value)

        if current_value == target_value:
            # Already at the target, no need to animate
            return

        # Stop existing animation if running
        if self._scroll_animation and self._scroll_animation.state() == QAbstractAnimation.State.Running:
            self.logger.debug(self.caller, "Stopping existing scroll animation.")
            # Stop should trigger the finished signal, leading to cleanup by the slot
            self._scroll_animation.stop()
            # Do NOT set to None here, let the slot handle it after finished signal
            # Optional: self._scroll_animation = None # Safer potentially -> Removed

        self.logger.debug(self.caller, f"Animating scroll from {current_value} to {target_value}")

        # Create and configure the animation
        self._scroll_animation = QPropertyAnimation(scrollbar, b"value", self)
        self._scroll_animation.setDuration(250) # Duration in milliseconds
        self._scroll_animation.setStartValue(current_value)
        self._scroll_animation.setEndValue(target_value)
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # <<< Connect the finished signal BEFORE starting >>>
        self._scroll_animation.finished.connect(self._on_scroll_animation_finished)

        # Start animation - DeleteWhenStopped ensures cleanup after 'finished' signal
        self._scroll_animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_scroll_animation_finished(self):
        """Slot called when the scroll animation finishes or is stopped."""
        self.logger.debug(self.caller, "Scroll animation finished signal received.")
        # Set the reference to None *after* Qt has finished with the object
        # Check if it's the *current* animation finishing before nullifying
        # (Though with DeleteWhenStopped, this check might be redundant, but safer)
        # if self._scroll_animation and not self._scroll_animation.state() == QAbstractAnimation.State.Running:
        self._scroll_animation = None

    def _scroll_left(self):
        """Scrolls the horizontal scrollbar left by 1.5 photo widths (animated)."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        if not scrollbar: return

        photo_width = self._get_first_visible_photo_width()
        scroll_amount = int(photo_width * 1.5)
        target_value = scrollbar.value() - scroll_amount
        self._animate_scroll(target_value) # Use animation helper

    def _scroll_right(self):
        """Scrolls the horizontal scrollbar right by 1.5 photo widths (animated)."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        if not scrollbar: return

        photo_width = self._get_first_visible_photo_width()
        scroll_amount = int(photo_width * 1.5)
        target_value = scrollbar.value() + scroll_amount
        self._animate_scroll(target_value) # Use animation helper

    def _scroll_to_start(self):
        """Scrolls the horizontal scrollbar all the way to the left (minimum, animated)."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        if scrollbar:
            self._animate_scroll(scrollbar.minimum()) # Use animation helper

    def _scroll_to_end(self):
        """Scrolls the horizontal scrollbar all the way to the right (maximum, animated)."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        if scrollbar:
            self._animate_scroll(scrollbar.maximum()) # Use animation helper

    # --- Hotkey Action Methods ---

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
        """Handles the '+' key press: Gathers decisions and emits signal if any items are approved."""
        self.logger.debug(self.caller, "'+' key pressed. Gathering review decisions...")

        # <<< ADDED CHECK: Ensure at least one item is approved >>>
        any_approved = False
        for display_widget in self.result_displays:
            if display_widget.get_approval_state():
                any_approved = True
                break # Found one, no need to check further
        
        if not any_approved:
            self.logger.info(self.caller, "'+' key pressed, but no images are approved. Doing nothing.")
            # Optionally provide user feedback (e.g., status bar message, brief popup) if desired
            return
        # <<< END ADDED CHECK >>>

        approved_result_paths: List[str] = []
        unapproved_result_paths: List[str] = []

        # 1. Iterate through displayed images and categorize paths
        #    (This loop now runs only if at least one item was approved)
        for display_widget in self.result_displays:
            img_path_str = str(display_widget.get_image_path().resolve()) # Use resolved string path
            if display_widget.get_approval_state():
                approved_result_paths.append(img_path_str)
            else:
                unapproved_result_paths.append(img_path_str)

        self.logger.debug(self.caller, f"Approved: {len(approved_result_paths)}, Unapproved: {len(unapproved_result_paths)}")

        # 2. Emit signal with decisions
        if self.source_stem:
            # Emit the signal with the original path and lists of result paths
            self.review_processed.emit(
                self.person_name,
                self.source_stem,
                approved_result_paths,
                unapproved_result_paths
            )
            # --- Let the receiver (FaceReviewPage) close the dialog ---
            # self.accept()
            # ---------------------------------------------------------- #
        else:
            self.logger.error(self.caller, "Cannot process review, source_stem is missing!")
            # Optionally show error to user
            self.reject() # Close dialog on error

    def closeEvent(self, event):
        """Save geometry when the dialog is closed."""
        self.logger.debug(self.caller, "Saving dialog geometry on close.")
        geometry_data = self.saveGeometry()
        self.settings.set(self.GEOMETRY_SETTING_KEY, geometry_data) # QByteArray is handled by QSettings
        super().closeEvent(event)

    # --- Public Method to Load New Data --- #
    def load_review_item(self, 
                         person_name: str, 
                         source_stem: str, 
                         result_image_paths: List[str]):
        """Updates the dialog with data for a new review item."""
        self.logger.debug(self.caller, f"****************** Loading new review item: {person_name} / {source_stem}")
        
        # Update internal data storage
        self.person_name = person_name
        self.source_stem = source_stem # Store stem
        self.result_paths = result_image_paths or []
        
        # Update the UI elements based on the new data
        self._update_display_data()
    # -------------------------------------- #


