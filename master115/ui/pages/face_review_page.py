from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QSizePolicy, QFrame, QAbstractItemView, QListView
)
from PyQt6.QtCore import Qt, pyqtSlot
from pathlib import Path
from typing import Optional, List

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

        # --- Connect to ReviewManager signal --- #
        self.review_manager.review_item_added.connect(self._on_review_item_added)
        # Connect removed signal
        self.review_manager.review_item_removed.connect(self._handle_review_item_removed)
        # -------------------------------------- #

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

        # --- Get data from ReviewManager --- #
        pending_reviews = ReviewManager.instance().get_pending_reviews()
        # --------------------------------- #

        if not pending_reviews:
            self.logger.info(self.caller, "No items pending review found by ReviewManager.")
            # TODO: Optionally display 'No items to review' message
            return

        self.logger.info(self.caller, f"Found {len(pending_reviews)} items pending review. Populating list.")

        # Populate the list widget
        # The data is now a list of dicts from ReviewManager
        # Sort by original source path for consistent ordering
        for review_item in sorted(pending_reviews, key=lambda x: x.get('original_source_path', '_')):
            original_source_path = review_item.get('original_source_path')
            result_files = review_item.get('result_image_paths', [])

            if not original_source_path or not result_files:
                self.logger.warn(self.caller, f"Skipping invalid review item: {review_item}")
                continue

            # --- Infer Person Name and Source Filename from Result Paths --- #
            # This assumes the naming convention: Person Face_Stem Source_Stem.jpg
            first_result_name = Path(result_files[0]).name
            parts = first_result_name.split(' ', 2) 
            person_name = "Unknown" # Default
            source_filename_stem = "Unknown" # Default
            if len(parts) >= 3:
                person_name = parts[0]
                # Try to extract source stem - fragile if names have many spaces
                try:
                    source_filename_stem = parts[2].rsplit('.', 1)[0] 
                except IndexError:
                    pass # Keep default if rsplit fails
            else:
                 self.logger.warn(self.caller, f"Could not reliably parse person/source from result: {first_result_name}")
            # ----------------------------------------------------------- #

            # Create the custom widget
            item_widget = ReviewQueueItem(person_name, source_filename_stem, result_files)

            # Create a QListWidgetItem
            list_item = QListWidgetItem(self.review_queue_list) # Add item to list
            # Set the size hint for the list item based on the widget's size
            list_item.setSizeHint(item_widget.sizeHint())
            # Store the full review item dictionary for later retrieval on click
            list_item.setData(Qt.ItemDataRole.UserRole, review_item)

            # Associate the custom widget with the list item
            self.review_queue_list.addItem(list_item)
            self.review_queue_list.setItemWidget(list_item, item_widget)

    @pyqtSlot(dict)
    def _on_review_item_added(self, review_item: dict):
        """Adds a single new item widget to the list when signaled by ReviewManager."""
        self.logger.debug(self.caller, f"Received signal for new review item: {review_item.get('original_source_path')}")

        original_source_path = review_item.get('original_source_path')
        result_files = review_item.get('result_image_paths', [])

        if not original_source_path or not result_files:
            self.logger.warn(self.caller, f"Skipping invalid review item received via signal: {review_item}")
            return

        # --- Infer Person Name and Source Filename from Result Paths (same logic as load) --- #
        first_result_name = Path(result_files[0]).name
        parts = first_result_name.split(' ', 2)
        person_name = "Unknown"
        source_filename_stem = "Unknown"
        if len(parts) >= 3:
            person_name = parts[0]
            try:
                source_filename_stem = parts[2].rsplit('.', 1)[0]
            except IndexError:
                pass
        else:
             self.logger.warn(self.caller, f"Could not reliably parse person/source from result: {first_result_name}")
        # ----------------------------------------------------------- #

        # Create the custom widget
        item_widget = ReviewQueueItem(person_name, source_filename_stem, result_files)

        # Create a QListWidgetItem
        list_item = QListWidgetItem(self.review_queue_list) # Add item to list
        list_item.setSizeHint(item_widget.sizeHint())

        # Store the full review item dictionary (same as in _load_review_items)
        list_item.setData(Qt.ItemDataRole.UserRole, review_item)

        # Associate the custom widget with the list item
        # Note: addItem might be sufficient if adding at the end is acceptable
        # self.review_queue_list.addItem(list_item) 
        self.review_queue_list.setItemWidget(list_item, item_widget)
        # Consider inserting in sorted order if needed, though load on show handles that.

    @pyqtSlot(str, list, list)
    def _handle_review_processed(self, original_source_path: str, approved_paths: List[str], unapproved_paths: List[str]):
        """Receives review decision from dialog and calls ReviewManager."""
        self.logger.debug(self.caller, f"Review decision received for {original_source_path}. Approved: {len(approved_paths)}, Unapproved: {len(unapproved_paths)}")
        # Call the manager to process the decision and handle files/JSON
        self.review_manager.process_review_decision(
            original_source_path,
            approved_paths,
            unapproved_paths
        )
        # The manager will emit review_item_removed if successful

    @pyqtSlot(str)
    def _handle_review_item_removed(self, original_source_path: str):
        """Removes the corresponding item from the UI list after manager confirms removal."""
        self.logger.debug(self.caller, f"Received confirmation to remove item {original_source_path} from UI.")
        item_to_remove = None
        row_to_remove = -1
        for row in range(self.review_queue_list.count()):
            item = self.review_queue_list.item(row)
            if item:
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_data, dict) and item_data.get('original_source_path') == original_source_path:
                    item_to_remove = item
                    row_to_remove = row
                    break
        
        if item_to_remove is not None and row_to_remove != -1:
            self.logger.info(self.caller, f"Removing item {Path(original_source_path).name} from list widget.")
            # Remove the item from the list widget
            self.review_queue_list.takeItem(row_to_remove)
            # Automatically navigate to the next item
            self.logger.debug(self.caller, "Item removed, navigating to next review item.")
            # Need to ensure the removed item isn't selected before navigating
            # It might be safer to recalculate next based on remaining items
            self._navigate_to_next_available(row_to_remove) # Use a helper to find next available
        else:
            self.logger.warn(self.caller, f"Could not find item {original_source_path} in list widget to remove.")

    def _navigate_to_next_available(self, removed_row_index: int):
        """Finds and navigates to the next item after one was removed, wrapping around."""
        count = self.review_queue_list.count()
        if count == 0:
            self.logger.debug(self.caller, "No more items to review.")
            # If dialog is somehow still open, close it
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.current_review_dialog.accept()
            return
            
        # Calculate the next index with wrap-around
        # If removed_row_index was the last item (index count before removal), 
        # removed_row_index % count will be 0, wrapping to the start.
        # Otherwise, it stays at the same index, which now holds the next item.
        next_row = removed_row_index % count 
        
        next_item = self.review_queue_list.item(next_row)
        if next_item:
            review_item_data = next_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(review_item_data, dict):
                self.logger.error(self.caller, f"Next item at index {next_row} has invalid data.")
                # Fallback: Close the dialog if data is bad
                if self.current_review_dialog and self.current_review_dialog.isVisible():
                    self.current_review_dialog.reject()
                return

            # Check if the dialog we were just in is still open
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                 self.logger.debug(self.caller, f"Updating existing review dialog with item at index {next_row}.")
                 self.current_review_dialog.load_review_item(review_item_data)
                 self.review_queue_list.setCurrentItem(next_item) # Ensure list selection matches
            else:
                 # Dialog wasn't open, so open it normally (this path shouldn't be hit after '+' typically)
                 self.logger.debug(self.caller, f"No dialog open, opening new one for item at index {next_row}.")
                 self.review_queue_list.setCurrentItem(next_item)
                 self._on_review_item_clicked(next_item) # Call the original click handler

        else:
            # Should not happen if count > 0
            self.logger.error(self.caller, f"Could not find next item at index {next_row} after removal.")
            # Fallback: Close the dialog if item not found
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.current_review_dialog.reject()

    def _on_review_item_clicked(self, item: QListWidgetItem):
        """Opens the ReviewPopupDialog for the clicked item."""
        if self.current_review_dialog and self.current_review_dialog.isVisible():
            self.logger.warn(self.caller, "Review dialog is already open.")
            self.current_review_dialog.raise_() # Bring existing dialog to front
            self.current_review_dialog.activateWindow()
            return

        review_item_data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(review_item_data, dict):
            self.logger.error(self.caller, f"Clicked item missing or has invalid data: {review_item_data}")
            # Maybe show a status bar message?
            return

        self.logger.debug(self.caller, f"Opening review dialog for: {review_item_data.get('original_source_path')}")
        
        # Create and execute the dialog
        self.current_review_dialog = ReviewPopupDialog(review_item_data, parent=self)
        # Connect dialog signals to handler methods
        self.current_review_dialog.review_processed.connect(self._handle_review_processed)
        self.current_review_dialog.navigate_next.connect(self._navigate_next_item)
        self.current_review_dialog.navigate_previous.connect(self._navigate_previous_item)
        
        result = self.current_review_dialog.exec()
        # Dialog is closed now
        self.logger.debug(self.caller, f"Review dialog closed with result: {result}")
        self.current_review_dialog = None # Clear reference

    def _navigate_next_item(self):
        """Navigate to the next item in the review queue."""
        self.logger.debug(self.caller, "Navigating to next review item")
        
        # If there are no items, we're done
        if self.review_queue_list.count() == 0:
            if self.current_review_dialog:
                self.current_review_dialog.accept() # Close dialog
            return
        
        # Get current selected item index
        current_row = -1
        current_items = self.review_queue_list.selectedItems()
        if current_items:
            current_row = self.review_queue_list.row(current_items[0])
        
        # Calculate next row with wrap-around
        next_row = (current_row + 1) % self.review_queue_list.count()
        
        # Select the next item
        next_item = self.review_queue_list.item(next_row)
        if next_item:
            self.review_queue_list.setCurrentItem(next_item)
            # Close current dialog if open
            if self.current_review_dialog:
                self.current_review_dialog.accept()
            # Open new dialog for the next item
            self._on_review_item_clicked(next_item)

    def _navigate_previous_item(self):
        """Navigate to the previous item in the review queue."""
        self.logger.debug(self.caller, "Navigating to previous review item")
        
        # If there are no items, we're done
        if self.review_queue_list.count() == 0:
            if self.current_review_dialog:
                self.current_review_dialog.accept() # Close dialog
            return
        
        # Get current selected item index
        current_row = -1
        current_items = self.review_queue_list.selectedItems()
        if current_items:
            current_row = self.review_queue_list.row(current_items[0])
        
        # Calculate previous row with wrap-around
        prev_row = (current_row - 1) % self.review_queue_list.count()
        
        # Select the previous item
        prev_item = self.review_queue_list.item(prev_row)
        if prev_item:
            self.review_queue_list.setCurrentItem(prev_item)
            # Close current dialog if open
            if self.current_review_dialog:
                self.current_review_dialog.accept()
            # Open new dialog for the previous item
            self._on_review_item_clicked(prev_item)