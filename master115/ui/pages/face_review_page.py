from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QSizePolicy, QFrame, QAbstractItemView, QListView
)
from PyQt6.QtCore import Qt
from pathlib import Path

# Framework imports
from qt_base_app.models import SettingsManager, Logger, SettingType

# Component Imports
from ..faceswap_components.review_queue_item import ReviewQueueItem

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
        # Set selection mode (single selection is fine for now)
        self.review_queue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Ensure items are not draggable/movable by default
        self.review_queue_list.setMovement(QListView.Movement.Static)

        # TODO: Connect itemClicked signal later for popup
        # self.review_queue_list.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.review_queue_list)

        self.setLayout(layout)

    def showEvent(self, event):
        """Override showEvent to reload results when the page becomes visible."""
        super().showEvent(event)
        self.logger.debug(self.caller, "Page shown, loading review items...")
        self._load_review_items()

    def _load_review_items(self):
        """Scans the Temp directory, groups results, and populates the list widget."""
        self.review_queue_list.clear()

        ai_root_raw = self.settings.get(PreferencesPage.AI_ROOT_DIR_KEY, PreferencesPage.DEFAULT_AI_ROOT_DIR, SettingType.PATH)
        if not ai_root_raw:
            self.logger.warn(self.caller, "AI Root Directory not set.")
            # TODO: Optionally display a message in the list widget area
            return

        ai_root_path = Path(ai_root_raw)
        temp_dir = ai_root_path / "Temp"

        if not temp_dir.is_dir():
            self.logger.warn(self.caller, f"Temp directory not found: {temp_dir}")
            # TODO: Optionally display a message
            return

        self.logger.info(self.caller, f"Scanning for review items in: {temp_dir}")
        
        # Group files by (Person_Name, Source_Filename)
        results_by_group = {}
        try:
            for item in temp_dir.glob("*.jpg"): # Assuming JPG results for now
                if item.is_file():
                    filename = item.name
                    parts = filename.split(' ', 2) # Split into Person, Face, Source parts
                    if len(parts) >= 3:
                        person_name = parts[0]
                        # Reconstruct source filename potentially containing spaces
                        # Find the last occurrence of a known image extension to split source and face
                        source_and_face = parts[1:]
                        source_filename_parts = []
                        face_filename = "" # Should be parts[1]
                        # This parsing logic might need refinement if filenames are complex
                        # For now, assume simple: Person Face Source.jpg
                        face_filename = parts[1]
                        source_filename_parts = parts[2].rsplit('.', 1) # Remove .jpg
                        if len(source_filename_parts) > 0:
                            source_filename = source_filename_parts[0]
                        else:
                            self.logger.warn(self.caller, f"Could not parse source filename from: {filename}")
                            continue # Skip this file

                        group_key = (person_name, source_filename)
                        if group_key not in results_by_group:
                            results_by_group[group_key] = []
                        results_by_group[group_key].append(str(item.resolve()))
                    else:
                        self.logger.warn(self.caller, f"Skipping file with unexpected naming format: {filename}")
        except OSError as e:
            self.logger.error(self.caller, f"Error scanning Temp directory {temp_dir}: {e}")
            # TODO: Optionally display an error message
            return

        if not results_by_group:
            self.logger.info(self.caller, "No items found in Temp directory for review.")
            # TODO: Optionally display 'No items to review' message
            return

        self.logger.info(self.caller, f"Found {len(results_by_group)} groups to review. Populating list.")

        # Populate the list widget
        for (person_name, source_filename), result_files in sorted(results_by_group.items()):
            # Create the custom widget
            item_widget = ReviewQueueItem(person_name, source_filename, sorted(result_files))

            # Create a QListWidgetItem
            list_item = QListWidgetItem(self.review_queue_list) # Add item to list
            # Set the size hint for the list item based on the widget's size
            list_item.setSizeHint(item_widget.sizeHint())
            # Store data if needed (e.g., for sorting or filtering later)
            # list_item.setData(Qt.ItemDataRole.UserRole, {"person": person_name, "source": source_filename})

            # Associate the custom widget with the list item
            self.review_queue_list.addItem(list_item)
            self.review_queue_list.setItemWidget(list_item, item_widget)

    # TODO: Implement _on_item_clicked method to handle popup dialog
    # def _on_item_clicked(self, item: QListWidgetItem):
    #     widget = self.review_queue_list.itemWidget(item)
    #     if isinstance(widget, ReviewQueueItem):
    #         self.logger.debug(self.caller, f"Clicked: {widget.get_person_name()} on {widget.get_source_filename()}")
    #         # --- Trigger Popup Dialog Here --- #
    #         pass # Placeholder for Milestone 3 