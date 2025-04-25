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
            person_name = review_item.get('person_name', 'Unknown') # Directly get person_name

            if not original_source_path or not result_files or person_name == 'Unknown':
                self.logger.warn(self.caller, f"Skipping invalid review item (missing data): {review_item}")
                continue

            # --- Get Source Filename Stem --- #
            # Keep this for display purposes, but don't rely on it for identification
            try:
                source_filename_stem = Path(original_source_path).stem
            except Exception as e:
                 self.logger.warn(self.caller, f"Could not extract source stem from {original_source_path}: {e}")
                 source_filename_stem = "Unknown Source"
            # --------------------------------- #

            # Create the custom widget
            # Pass the actual person_name
            item_widget = ReviewQueueItem(person_name, source_filename_stem, result_files)

            # Create a QListWidgetItem
            list_item = QListWidgetItem(self.review_queue_list)
            # Set the size hint based on the custom widget's size hint
            list_item.setSizeHint(item_widget.sizeHint())

            # Store the identifying data within the item
            # Using Qt.UserRole + 1, + 2 for custom data
            list_item.setData(Qt.ItemDataRole.UserRole + 1, person_name)
            list_item.setData(Qt.ItemDataRole.UserRole + 2, original_source_path)

            # Set the custom widget for the item
            self.review_queue_list.addItem(list_item)
            self.review_queue_list.setItemWidget(list_item, item_widget)
            # -------------------------------- #

    @pyqtSlot(dict)
    def _on_review_item_added(self, review_item: dict):
        """Slot called when a new review item is added by the ReviewManager."""
        self.logger.debug(self.caller, f"Signal received: review_item_added for {review_item.get('original_source_path')}")

        original_source_path = review_item.get('original_source_path')
        result_files = review_item.get('result_image_paths', [])
        person_name = review_item.get('person_name', 'Unknown') # Directly get person_name

        if not original_source_path or not result_files or person_name == 'Unknown':
            self.logger.warn(self.caller, f"Received invalid review item to add: {review_item}")
            return

        # --- Check if item already exists (using person_name and source_path) --- #
        # This prevents duplicates if _load_review_items runs after the signal
        for i in range(self.review_queue_list.count()):
            item = self.review_queue_list.item(i)
            existing_person = item.data(Qt.ItemDataRole.UserRole + 1)
            existing_source = item.data(Qt.ItemDataRole.UserRole + 2)
            if existing_person == person_name and existing_source == original_source_path:
                self.logger.debug(self.caller, f"Item {person_name}/{original_source_path} already exists in list. Skipping add.")
                return
        # ------------------------------------------------------------------------ #

        # --- Get Source Filename Stem --- #
        try:
            source_filename_stem = Path(original_source_path).stem
        except Exception as e:
            self.logger.warn(self.caller, f"Could not extract source stem from {original_source_path}: {e}")
            source_filename_stem = "Unknown Source"
        # --------------------------------- #

        self.logger.info(self.caller, f"Adding review item: {person_name} - {source_filename_stem}")

        # Create the custom widget
        item_widget = ReviewQueueItem(person_name, source_filename_stem, result_files)

        # Create a QListWidgetItem
        list_item = QListWidgetItem(self.review_queue_list) # Add item directly
        # Set the size hint based on the custom widget's size hint
        list_item.setSizeHint(item_widget.sizeHint())

        # Store the identifying data within the item
        list_item.setData(Qt.ItemDataRole.UserRole + 1, person_name)
        list_item.setData(Qt.ItemDataRole.UserRole + 2, original_source_path)

        # Set the custom widget for the item
        # No need to call addItem again if we passed the parent in constructor
        self.review_queue_list.setItemWidget(list_item, item_widget)

        # Optionally scroll or highlight the newly added item if needed
        # self.review_queue_list.scrollToItem(list_item)

    @pyqtSlot(str, str, list, list)
    def _handle_review_processed(self, person_name: str, original_source_path: str, approved_paths: List[str], unapproved_paths: List[str]):
        """Receives review decision from dialog and calls ReviewManager."""
        self.logger.debug(self.caller, f"Review decision received for {person_name}/{Path(original_source_path).name}")
        
        # Call the manager to process the decision and handle files/JSON
        ReviewManager.instance().process_review_decision(
            person_name,
            original_source_path,
            approved_paths,
            unapproved_paths
        )
        # ReviewManager will emit review_item_removed if successful, 
        # which will trigger _handle_review_item_removed to update the UI.
        
        # --- REMOVE premature dialog closing --- #
        # # Close the dialog after processing
        # if self.current_review_dialog:
        #     self.current_review_dialog.accept() # Close the dialog cleanly
        # --------------------------------------- #

    @pyqtSlot(str, str)
    def _handle_review_item_removed(self, person_name: str, original_source_path: str):
        """Slot called when a review item is removed (processed or deleted)."""
        self.logger.debug(self.caller, f"Signal received: review_item_removed for {person_name}/{original_source_path}")
        self._remove_review_item_widget(person_name, original_source_path)

    def _remove_review_item_widget(self, person_name: str, original_source_path: str):
        """Finds and removes the QListWidgetItem associated with the given source path."""
        item_to_remove = None
        row_index = -1
        for i in range(self.review_queue_list.count()):
            item = self.review_queue_list.item(i)
            # Check both person_name and original_source_path
            item_person = item.data(Qt.ItemDataRole.UserRole + 1)
            item_source = item.data(Qt.ItemDataRole.UserRole + 2)

            if item_person == person_name and item_source == original_source_path:
                item_to_remove = item
                row_index = i
                break

        if item_to_remove:
            # Get the currently selected item *before* removing
            current_selection = self.review_queue_list.currentItem()
            is_removing_selected = (current_selection == item_to_remove)
            
            self.logger.info(self.caller, f"Removing item: {person_name} - {Path(original_source_path).stem}")
            # takeItem removes the item from the list and returns it
            removed_item = self.review_queue_list.takeItem(row_index) 
            # We might need to manually delete the item widget if Qt doesn't
            del removed_item 

            # If the removed item was the selected one, try to select the next logical item
            if is_removing_selected:
                self._navigate_to_next_available(row_index)

        else:
            self.logger.warn(self.caller, f"Could not find item to remove for {person_name}/{original_source_path}")

    def _navigate_to_next_available(self, removed_row_index: int):
        """Selects the next available item in the list and triggers its display."""
        count = self.review_queue_list.count()
        if count == 0:
            self.logger.info(self.caller, "Review queue empty after removal.")
            # Close the dialog if it's open and the queue is now empty
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.logger.debug(self.caller, "Closing review dialog as queue is empty.")
                self.current_review_dialog.close() # Use close() instead of accept()
            return
            
        # Calculate the next index (handles wrap-around or staying at current index)
        next_row = removed_row_index % count 
        
        next_item = self.review_queue_list.item(next_row)
        if next_item:
            self.logger.info(self.caller, f"Navigating to next available item at index {next_row}")
            # Select the item in the list
            self.review_queue_list.setCurrentItem(next_item) 
            # Trigger the standard click handler to open/update the dialog for this item
            self._on_review_item_clicked(next_item)
        else:
            # Should not happen if count > 0
            self.logger.error(self.caller, f"Could not find next item at index {next_row} despite count={count}.")
            # Attempt to close the dialog as a fallback
            if self.current_review_dialog and self.current_review_dialog.isVisible():
                self.current_review_dialog.close()

    def _on_review_item_clicked(self, item: QListWidgetItem):
        """Opens the ReviewPopupDialog for the clicked item."""
        if self.current_review_dialog and self.current_review_dialog.isVisible():
            self.logger.warn(self.caller, "Review dialog is already open.")
            self.current_review_dialog.raise_() # Bring existing dialog to front
            self.current_review_dialog.activateWindow()
            return

        # --- Retrieve Identifiers from the item --- #
        person_name = item.data(Qt.ItemDataRole.UserRole + 1)
        original_source_path = item.data(Qt.ItemDataRole.UserRole + 2)
        
        if not person_name or not original_source_path:
            self.logger.error(self.caller, f"Missing person_name or original_source_path in clicked item data.")
            return
        # -------------------------------------------- #

        # --- Fetch full details from ReviewManager --- #
        review_details = ReviewManager.instance().get_review_details(person_name, original_source_path)
        if not review_details:
            self.logger.error(self.caller, f"Could not retrieve review details from ReviewManager for {person_name}/{original_source_path}")
            # Optionally inform user via status bar
            return
        result_image_paths = review_details.get('result_image_paths', [])
        # -------------------------------------------- #
        
        # --- Check if dialog is already open --- #
        if self.current_review_dialog and self.current_review_dialog.isVisible():
            # Dialog IS open, update its content instead of creating a new one
            self.logger.info(self.caller, f"Updating existing review dialog for: {person_name} / {Path(original_source_path).name}")
            self.current_review_dialog.load_review_item(
                person_name=person_name,
                original_source_path=original_source_path,
                result_image_paths=result_image_paths
            )
            self.current_review_dialog.raise_()
            self.current_review_dialog.activateWindow()
            # Ensure list selection matches (might be redundant if navigation already did it)
            self.review_queue_list.setCurrentItem(item)
            return # Don't proceed to create a new dialog
        # ---------------------------------------- #

        # --- Dialog is NOT open, proceed to create it --- #
        self.logger.info(self.caller, f"Opening new review dialog for: Person='{person_name}', Source='{original_source_path}'")

        # --- Get AI Root Directory --- #
        ai_root_path = self.settings.get(
            SettingsManager.AI_ROOT_DIR_KEY, 
            None, # SettingsManager handles default/validation
            SettingType.PATH
        )
        if not ai_root_path:
             self.logger.error(self.caller, "Cannot open review dialog, AI Root Dir is invalid.")
             return
        ai_root_dir_str = str(ai_root_path) # Convert Path to string for dialog
        # ----------------------------- #

        # Create and show the popup dialog
        # Pass individual arguments now
        self.current_review_dialog = ReviewPopupDialog(
            person_name=person_name,
            original_source_path=original_source_path,
            result_image_paths=result_image_paths,
            ai_root_dir_str=ai_root_dir_str,
            parent=self # Set parent to manage lifecycle
        )
        
        # Connect dialog signals to handler methods
        self.current_review_dialog.review_processed.connect(self._handle_review_processed)
        self.current_review_dialog.request_next_item.connect(self._navigate_next_item)
        self.current_review_dialog.request_previous_item.connect(self._navigate_previous_item)
        self.current_review_dialog.finished.connect(
            self._on_dialog_finished, Qt.ConnectionType.QueuedConnection
        )
        
        self.current_review_dialog.show()
        self.current_review_dialog.activateWindow() # Ensure it has focus
        self.current_review_dialog.raise_() # Bring it to the front

        # Select the item in the list view when opening the dialog
        self.review_queue_list.setCurrentItem(item)

    def _navigate_next_item(self):
        """Navigates to the next item in the list and opens its review dialog."""
        current_row = self.review_queue_list.currentRow()
        next_row = (current_row + 1) % self.review_queue_list.count() # Wrap around
        if self.review_queue_list.count() > 0:
            next_item = self.review_queue_list.item(next_row)
            if next_item:
                 # Close existing dialog first if open
                if self.current_review_dialog and self.current_review_dialog.isVisible():
                    # We need to accept (close) it cleanly before opening the next
                    # Using accept() assumes it won't trigger unwanted side-effects
                    self.current_review_dialog.accept() 
                    # Let the finished signal clear the reference
                
                # Set the selection *before* potentially triggering the dialog
                self.review_queue_list.setCurrentRow(next_row) 
                # Simulate a click to open the dialog for the new item
                # Using itemClicked signal might be cleaner than calling _on_review_item_clicked directly
                self._on_review_item_clicked(next_item) 
                # self.review_queue_list.itemClicked.emit(next_item) # Alternative if direct call causes issues

    def _navigate_previous_item(self):
        """Navigates to the previous item in the list and opens its review dialog."""
        current_row = self.review_queue_list.currentRow()
        prev_row = (current_row - 1 + self.review_queue_list.count()) % self.review_queue_list.count() # Wrap around
        if self.review_queue_list.count() > 0:
            prev_item = self.review_queue_list.item(prev_row)
            if prev_item:
                # Close existing dialog first if open
                if self.current_review_dialog and self.current_review_dialog.isVisible():
                    self.current_review_dialog.accept() 
                
                self.review_queue_list.setCurrentRow(prev_row)
                # Simulate a click
                self._on_review_item_clicked(prev_item)
                # self.review_queue_list.itemClicked.emit(prev_item) # Alternative

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