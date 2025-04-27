from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QSizePolicy, QFrame, QAbstractItemView, QListView
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from pathlib import Path
from typing import Optional, List, Tuple

# Framework imports
from qt_base_app.models import SettingsManager, Logger, SettingType
from qt_base_app.theme import ThemeManager
from master115.models.review_manager import ReviewManager

# Component Imports
from ..faceswap_components.review_queue_item import ReviewQueueItem
from ..components.round_button import RoundButton
from ..faceswap_components.review_popup_dialog import ReviewPopupDialog

# Need PreferencesPage constants
try:
    from .preferences_page import PreferencesPage
except ImportError:
    class PreferencesPage:
        AI_ROOT_DIR_KEY = 'ai/root_dir'
        DEFAULT_AI_ROOT_DIR = "D:/AIRoot/"

class FaceReviewPage(QWidget):
    """Page for reviewing and approving/rejecting face swap results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FaceReviewPage")
        self.settings = SettingsManager.instance()
        self.logger = Logger.instance()
        self.caller = "FaceReviewPage"

        # Get the ReviewManager instance
        self.theme = ThemeManager.instance()
        self.review_manager = ReviewManager.instance()

        # Store button reference
        self.current_review_dialog: Optional[ReviewPopupDialog] = None
        self.refresh_button: Optional[RoundButton] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main UI elements for the review page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15) # Some padding
        layout.setSpacing(10)

        # --- Result Review Queue --- #
        self.review_queue_list = QListWidget()
        self.review_queue_list.setObjectName("ReviewQueueList")
        # Set ViewMode to IconMode for a grid-like appearance
        self.review_queue_list.setViewMode(QListView.ViewMode.IconMode)
        # Allow items to resize and flow
        self.review_queue_list.setResizeMode(QListView.ResizeMode.Adjust)
        # Adjust spacing between items
        self.review_queue_list.setSpacing(10)
        # Set selection mode and behavior
        self.review_queue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.review_queue_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        # Ensure items are not draggable/movable by default
        self.review_queue_list.setMovement(QListView.Movement.Static)

        # TODO: Connect itemClicked signal later for popup
        self.review_queue_list.itemClicked.connect(self._on_review_item_clicked)

        # --- Apply Custom Styling for Selection --- #
        # sidebar_bg = self.theme.get_color('background', 'sidebar') # No longer needed for selection
        alt_row_bg = self.theme.get_color('background', 'alternate_row') # Get alternate row color
        secondary_bg = self.theme.get_color('background', 'secondary')
        text_color = self.theme.get_color('text', 'primary')
        border_color = self.theme.get_color('border', 'primary')

        stylesheet = f"""
            QListWidget {{
                background-color: {secondary_bg};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QListWidget::item {{
                /* Reset border/background for non-selected items */
                border: none; 
                background-color: transparent; 
                padding: 5px; /* Add some padding around items */
                border-radius: 4px; /* Match parent border-radius */
            }}
            QListWidget::item:selected {{ 
                background-color: {alt_row_bg}; /* Use alternate row color for selection */
                color: {text_color};
            }}
            QListWidget::item:hover:!selected {{
                 background-color: {self.theme.get_color('background', 'hover')}; /* Optional: hover effect */
            }}
        """
        self.review_queue_list.setStyleSheet(stylesheet)
        # ------------------------------------------ #

        layout.addWidget(self.review_queue_list)

        # --- Add Refresh Button (Overlay) --- #
        self.refresh_button = RoundButton(
            parent=self.review_queue_list, # Parent for positioning
            icon_name='fa5s.sync-alt',
            size=36, # Slightly smaller size for overlay
            icon_size=18,
            bg_opacity=0.7
        )
        self.refresh_button.setToolTip("Refresh Review List")
        self.refresh_button.clicked.connect(self._load_review_items)
        self.refresh_button.show() # Ensure it's visible
        # Initial positioning will be handled by resizeEvent
        # ------------------------------------ #

        self.setLayout(layout)

    def showEvent(self, event):
        """Override showEvent to reload results when the page becomes visible."""
        super().showEvent(event)
        # Trigger initial position update for the button
        self._position_refresh_button()
        self.logger.debug(self.caller, "Page shown, loading review items...")
        self._load_review_items()

    def resizeEvent(self, event):
        """Override resizeEvent to reposition the refresh button."""
        super().resizeEvent(event)
        self._position_refresh_button()

    def _position_refresh_button(self):
        """Positions the refresh button in the bottom-right corner of the list widget."""
        if not self.refresh_button:
            return
            
        list_widget_size = self.review_queue_list.size()
        button_size = self.refresh_button.size()
        margin = 10 # Margin from the edges

        # Calculate position
        x = list_widget_size.width() - button_size.width() - margin
        y = list_widget_size.height() - button_size.height() - margin

        self.refresh_button.move(x, y)

    def _load_review_items(self):
        """Loads pending review items from the ReviewManager and populates the list."""
        self.review_queue_list.clear()

        # --- Get data by scanning Temp directory --- #
        review_items_data = self.review_manager.scan_temp_for_review_items()
        # ------------------------------------------ #

        if not review_items_data:
            self.logger.info(self.caller, "No items found in Temp directory for review.")
            # TODO: Optionally display 'No items to review' message
            return

        self.logger.info(self.caller, f"Found {len(review_items_data)} items for review by scanning Temp. Populating list.")

        # Populate the list widget
        for review_data in review_items_data: # Already sorted by ReviewManager
            person_name = review_data.get('person_name')
            source_stem = review_data.get('source_stem')
            result_paths = review_data.get('result_image_paths', [])

            if not person_name or not source_stem or not result_paths:
                self.logger.warn(self.caller, f"Skipping invalid review data from scan: {review_data}")
                continue

            # Create the custom widget
            item_widget = ReviewQueueItem(person_name, source_stem, result_paths)

            # Create a QListWidgetItem
            list_item = QListWidgetItem(self.review_queue_list)
            list_item.setSizeHint(item_widget.sizeHint())

            # Store the identifying data and result paths within the item
            list_item.setData(Qt.ItemDataRole.UserRole + 1, person_name)
            list_item.setData(Qt.ItemDataRole.UserRole + 2, source_stem) 
            # Store result paths directly for easier retrieval
            list_item.setData(Qt.ItemDataRole.UserRole + 3, result_paths) 

            # Set the custom widget for the item
            self.review_queue_list.addItem(list_item)
            self.review_queue_list.setItemWidget(list_item, item_widget)
            # -------------------------------- #

    def _handle_review_processed(self, person_name: str, source_stem: str, approved: bool | None):
        """Handles the result of a review decision from the ReviewManager."""
        self.logger.debug(self.caller, f"Handling processed review for: {person_name}/{source_stem}, Approved: {approved}")

        # Remove the item from the UI list first
        removed_index = self._remove_review_item_widget(person_name, source_stem)

        if removed_index != -1:
            self.logger.info(self.caller, f"Successfully removed {person_name}/{source_stem} from review list at index {removed_index}.")
            # Navigate to the next item *after* successful removal
            self._navigate_to_next_available(removed_index)
            
            # Optional: Update status or counts if needed
            # self._update_status_bar() # Example if you have a status bar

        else:
            self.logger.error(self.caller, f"Failed to remove {person_name}/{source_stem} from list after processing. UI may be inconsistent.")
            # Decide how to handle this - maybe refresh the whole list?
            # self.load_review_queue() # Or just log the error

    # ------------------------------------- #

    # --- Method reinstated and adapted --- #

    @pyqtSlot(QListWidgetItem)
    def _on_review_item_clicked(self, item: QListWidgetItem):
        """Opens the ReviewPopupDialog for the clicked item."""
        # Simply delegate to the centralized display method
        self._display_review_item(item)

    def _navigate_next_item(self):
        """Handles navigation request to the next item."""
        current_row = self.review_queue_list.currentRow()
        count = self.review_queue_list.count()
        if count == 0:
            return # Nothing to navigate to
        next_row = (current_row + 1) % count

        next_item = self.review_queue_list.item(next_row)
        if next_item:
            self._display_review_item(next_item)
        else:
            self.logger.error(self.caller, f"_navigate_to_next_available: Could not find item at index {next_row} despite count={count}.")

    def _navigate_previous_item(self):
        """Handles navigation request to the previous item."""
        current_row = self.review_queue_list.currentRow()
        count = self.review_queue_list.count()
        if count == 0:
            return # Nothing to navigate to
        prev_row = (current_row - 1 + count) % count

        prev_item = self.review_queue_list.item(prev_row)
        if prev_item:
            self._display_review_item(prev_item)

    @pyqtSlot(int)
    def _on_dialog_finished(self, result_code: int):
        """Slot called when the ReviewPopupDialog is closed."""
        sender_dialog = self.sender()
        if sender_dialog == self.current_review_dialog:
            self.logger.debug(self.caller, f"Review dialog finished with code: {result_code}")
            self.current_review_dialog = None # Clear the reference
        else:
            # This might happen if signals cross, log it
            self.logger.warn(self.caller, "Finished signal received from an unexpected dialog instance.")

        # Optional: Refocus the main window or list if needed
        # self.review_queue_list.setFocus()

    # --- Cleanup --- #
    def closeEvent(self, event):
        """Ensure the popup is closed if the main window closes."""
        if self.current_review_dialog:
            self.current_review_dialog.close() # Close the dialog gracefully
        super().closeEvent(event)
    # ------------- #

    # --- Helper Methods --- #

    def _get_data_for_item(self, item: QListWidgetItem) -> Optional[Tuple[str, str, List[str]]]:
        """Retrieves data stored in the list item."""
        if not item:
            return None
        person_name = item.data(Qt.ItemDataRole.UserRole + 1)
        source_stem = item.data(Qt.ItemDataRole.UserRole + 2)
        result_paths = item.data(Qt.ItemDataRole.UserRole + 3)

        # Validate retrieved data
        if not person_name or not isinstance(person_name, str) or \
           not source_stem or not isinstance(source_stem, str) or \
           not result_paths or not isinstance(result_paths, list):
            self.logger.error(self.caller, f"Invalid or missing data found in QListWidgetItem. P: {person_name}, S: {source_stem}, R: {len(result_paths) if result_paths else 'None'}")
            return None

        return person_name, source_stem, result_paths

    def _display_review_item(self, item: QListWidgetItem):
        """Handles displaying the given item, either by updating or creating the dialog."""
        if not item:
            self.logger.warn(self.caller, "_display_review_item called with None item.")
            return

        item_data = self._get_data_for_item(item)
        if item_data is None:
            self.logger.error(self.caller, "Could not retrieve valid data from list item to display review.")
            return

        person_name, source_stem, result_paths = item_data

        # Check if dialog exists and is visible
        if self.current_review_dialog and self.current_review_dialog.isVisible():
            # Update existing dialog
            self.logger.info(self.caller, f"Updating existing dialog for: {person_name} / {source_stem}")
            try:
                # Call dialog's method to load new item data (which now expects source_stem)
                self.current_review_dialog.load_review_item(
                    person_name=person_name,
                    source_stem=source_stem, # Pass stem
                    result_image_paths=result_paths
                )
            except Exception as e:
                 self.logger.error(self.caller, f"Error calling load_review_item: {e}", exc_info=True)

            self.current_review_dialog.raise_()
            self.current_review_dialog.activateWindow()
        else:
            # Create new dialog
            self.logger.info(self.caller, f"Opening new dialog for: {person_name} / {source_stem}")

            ai_root_path = self.settings.get(
                SettingsManager.AI_ROOT_DIR_KEY,
                None, # SettingsManager handles default/validation
                SettingType.PATH
            )
            if not ai_root_path:
                 self.logger.error(self.caller, "Cannot open review dialog, AI Root Dir is invalid.")
                 return
            ai_root_dir_str = str(ai_root_path)

            # Instantiate dialog with source_stem
            self.current_review_dialog = ReviewPopupDialog(
                person_name=person_name,
                source_stem=source_stem, # Pass stem instead of full path
                result_image_paths=result_paths,
                ai_root_dir_str=ai_root_dir_str,
                parent=self # Set parent to manage lifecycle
            )

            # Connect signals
            self.current_review_dialog.review_processed.connect(self._handle_review_processed)
            self.current_review_dialog.request_next_item.connect(self._navigate_next_item)
            self.current_review_dialog.request_previous_item.connect(self._navigate_previous_item)
            self.current_review_dialog.finished.connect(
                self._on_dialog_finished, Qt.ConnectionType.QueuedConnection
            )

            self.current_review_dialog.show()
            self.current_review_dialog.activateWindow()
            self.current_review_dialog.raise_()

        # Ensure the list selection matches the displayed item
        self.review_queue_list.setCurrentItem(item)

    def _remove_review_item_widget(self, person_name: str, source_stem: str) -> int:
        """Finds and removes the QListWidgetItem associated with the given keys, returns the row index."""
        item_to_remove = None
        row_index = -1
        for i in range(self.review_queue_list.count()):
            item = self.review_queue_list.item(i)
            item_person = item.data(Qt.ItemDataRole.UserRole + 1)
            item_stem = item.data(Qt.ItemDataRole.UserRole + 2)

            if item_person == person_name and item_stem == source_stem:
                item_to_remove = item
                row_index = i
                break

        if item_to_remove:
            self.logger.info(self.caller, f"Removing item: {person_name} / {source_stem}")
            # takeItem removes the item from the list and returns it
            removed_item = self.review_queue_list.takeItem(row_index)
            # Ensure the widget associated with the item is deleted
            widget = self.review_queue_list.itemWidget(removed_item)
            if widget:
                 widget.deleteLater()
            # No need to manually delete removed_item itself if using takeItem
            # del removed_item
            return row_index # Return the index where the item was removed
        else:
            self.logger.warn(self.caller, f"Could not find list item to remove for {person_name}/{source_stem}")
            return -1 # Indicate item not found

    def _navigate_to_next_available(self, removed_row_index: int):
        """Selects the next available item in the list and triggers its display in the dialog."""
        count = self.review_queue_list.count() # Get count *after* removal
        if count == 0:
            self.logger.info(self.caller, "Review queue empty after removal.")
            # Close the dialog if it's still open and the list is empty
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.logger.debug(self.caller, "Closing review dialog as queue is empty.")
                self.current_review_dialog.close()
            return

        # Calculate next index, ensuring it's within bounds
        next_row = removed_row_index
        if next_row >= count:
            next_row = count - 1 # Stay at the last item if removed item was last
        if next_row < 0:
            next_row = 0 # Should not happen, but safety check
            
        next_item = self.review_queue_list.item(next_row)

        if next_item:
            self.logger.info(self.caller, f"Navigating after removal: Displaying item at index {next_row}.")
            # Display the next item (will update existing dialog if open)
            self._display_review_item(next_item)
            # Ensure the list selection follows the display
            self.review_queue_list.setCurrentItem(next_item)
        else:
            self.logger.error(self.caller, f"_navigate_to_next_available: Could not find item at index {next_row} despite count={count}. Closing dialog.")
            # Close dialog if we can't find the next item (shouldn't happen if count > 0)
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.current_review_dialog.close()