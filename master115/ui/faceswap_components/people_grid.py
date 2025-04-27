from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer

from qt_base_app.components.base_card import BaseCard
from qt_base_app.theme import ThemeManager
from qt_base_app.models import Logger, SettingsManager, SettingType
from .person_badge import PersonBadge
from ...models.people_manager import PeopleManager, PersonData
from ...models.faceswap_manager import FaceSwapManager

class PeopleGrid(QWidget):
    """A widget displaying a grid of selectable PersonBadges."""
    # Signals
    selection_changed = pyqtSignal(list) # Emits list of selected person names
    filter_requested_for_person = pyqtSignal(str) # Relays request for filter menu

    def __init__(self, swap_manager: FaceSwapManager, parent=None):
        super().__init__(parent)
        self.setObjectName("PeopleGridWidget")
        self.logger = Logger.instance()
        self.caller = "PeopleGrid"
        self.theme = ThemeManager.instance()
        self.people_manager = PeopleManager.instance()
        self.swap_manager = swap_manager
        self.settings = SettingsManager.instance()

        self._grid_populated = False # Track if grid has been populated
        self._info_label: Optional[QLabel] = None # Label for messages like "No persons"
        self._badge_widgets: Dict[str, PersonBadge] = {} # Cache badge widgets by name

        self._setup_ui()
        self._connect_manager_signals() # Connect signals from the swap_manager

    def _setup_ui(self):
        """Set up the container card and grid layout."""
        # Use QVBoxLayout to hold the card, allowing margins around the card if needed
        # Or just set the BaseCard as the main layout element if it fills the whole widget
        # For now, let's assume PeopleGrid *is* the card-like structure
        main_layout = QGridLayout(self) # Use grid layout directly for the widget
        main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the widget itself
        
        # --- Person Picker Card (Using BaseCard, no title) --- #
        self.person_picker_card = BaseCard()
        self.person_picker_card.setObjectName("PersonPickerCard")
        
        # Set background transparent and remove padding, keep border
        card_border_color = self.theme.get_color('border', 'primary')
        self.person_picker_card.setStyleSheet(f"""
            #PersonPickerCard {{
                background-color: transparent; /* Changed background */
                border: 1px solid {card_border_color};
                border-radius: 8px; /* Match BaseCard default */
                padding: 0px; /* Removed padding */
            }}
        """)
        
        # --- Layout for Person Badges (Using QGridLayout within BaseCard's content area) --- #
        self.person_grid_layout = QGridLayout() # Create layout separately
        self.person_grid_layout.setSpacing(10)
        self.person_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Add the grid layout to the BaseCard's content area
        self.person_picker_card.add_layout(self.person_grid_layout)

        # Add the BaseCard to the main widget layout
        main_layout.addWidget(self.person_picker_card, 0, 0)
        
        self.setLayout(main_layout)

    def _connect_manager_signals(self):
        """Connect signals from the provided FaceSwapManager to update badge overlays."""
        # Ensure the manager instance exists and is of the correct type
        if self.swap_manager and isinstance(self.swap_manager, FaceSwapManager):
            self.logger.debug(self.caller, "Connecting to provided FaceSwapManager signals.")
            self.swap_manager.process_started[dict].connect(self._on_process_started)
            self.swap_manager.person_progress_updated[str, int, int].connect(self._on_person_progress_updated)
            self.swap_manager.process_finished.connect(self._on_process_finished_or_killed)
            self.swap_manager.process_killed.connect(self._on_process_finished_or_killed)
        else:
            self.logger.error(self.caller, "Invalid or missing FaceSwapManager instance provided. Cannot connect signals.")

    def _clear_person_grid(self):
        """Removes all widgets from the person grid layout."""
        while self.person_grid_layout.count():
            item = self.person_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._badge_widgets.clear() # Clear the tracking dictionary

    def load_persons(self, force_rescan: bool = False):
        """Scans for persons using PeopleManager and populates the grid."""
        self._clear_person_grid()
        self.logger.debug(self.caller, f"Loading persons (force_rescan={force_rescan})...")

        # Get person data using the manager
        persons_data: List[PersonData] = self.people_manager.get_persons(force_rescan=force_rescan)

        if not persons_data:
            # Display a message within the card if no persons found
            self.person_picker_card.clear() # Clear previous widgets/layouts in card
            msg = "No persons found in Faces directory."
            if not self.people_manager._get_ai_root(): # Check if root cause is missing AI dir
                 msg = "AI Root Directory not set or invalid. Please check Preferences."
            self.person_picker_card.add_widget(QLabel(msg))
            self.logger.info(self.caller, msg)
            self.selection_changed.emit([]) # Emit empty selection
            return
        
        # Ensure the grid layout is back in the card if it was cleared
        if self.person_picker_card.layout is None:
            self.person_picker_card.add_layout(self.person_grid_layout)
            
        self.logger.info(self.caller, f"Found {len(persons_data)} persons. Populating badges.")
        
        # Calculate grid columns dynamically (similar to original logic)
        row, col = 0, 0
        badge_min_width = 120 # Minimum width from PersonBadge (adjust if changed)
        # Use card's content widget width for calculation if available
        try:
             card_content_width = self.person_picker_card.content_widget.width() - 20 # Account for spacing/margins
        except AttributeError: # If content_widget doesn't exist yet or card is hidden
             card_content_width = self.width() - 40 # Fallback to widget width

        if card_content_width <= 0:
             # Fallback if width calculation yields non-positive
             card_content_width = 4 * (badge_min_width + self.person_grid_layout.spacing()) 

        max_cols = max(1, int(card_content_width / (badge_min_width + self.person_grid_layout.spacing())))
        self.logger.debug(self.caller, f"Calculated max_cols: {max_cols} (based on width: {card_content_width})")

        # Populate the grid layout
        for person in persons_data:
            person_name = person.name
            # Get the first image path using the helper from PeopleManager
            first_image = self.people_manager.get_first_image_path(person_name)

            if first_image is None:
                self.logger.warn(self.caller, f"Could not get first image for {person_name}, badge might be empty.")

            # --- Create ACTUAL PersonBadge, pass swap_manager --- #
            badge = PersonBadge(
                person_name=person_name,
                first_image_path=first_image,
                swap_manager=self.swap_manager
            )
            badge.toggled.connect(self._on_badge_toggled) # Connect signal
            # Connect the new context menu request signal
            badge.context_menu_requested.connect(self.filter_requested_for_person)
            # -------------------------------------------------- #

            self.person_grid_layout.addWidget(badge, row, col)
            self._badge_widgets[person_name] = badge # Store reference

            col += 1
            if col >= max_cols:
                col = 0
                row += 1
                
        # Emit initial selection state (likely empty)
        self.selection_changed.emit(self.get_selected_person_names())

    # Handler for badge toggle signal
    @pyqtSlot(str, bool) # Explicitly define the slot signature
    def _on_badge_toggled(self, person_name, is_selected):
        # We don't need to log here, PersonBadge might do it
        # Just emit the updated selection list
        self.selection_changed.emit(self.get_selected_person_names())

    # --- Public Methods --- #

    def get_selected_person_names(self) -> List[str]:
        """Returns a list of names of the currently selected persons."""
        return [name for name, badge in self._badge_widgets.items() if badge.is_selected]

    def set_enabled(self, enabled: bool):
        """Enables or disables interaction with the grid's container card."""
        # ONLY disable the container card for visual feedback.
        # Do NOT disable individual badges, as they need clicks for context menu.
        # self.person_picker_card.setEnabled(enabled)  # Commenting out this line to allow child widget interaction
        
        # IMPORTANT: Do not disable the individual badges when the grid is disabled
        # because we still need them to receive mouse events for context menus
        # When automation is running and the grid is disabled, make sure badges stay enabled
        if not enabled:
            for badge in self._badge_widgets.values():
                badge.setEnabled(True)  # Ensure badges remain clickable even when grid is disabled
                
        self.logger.debug(self.caller, f"PeopleGrid container card enabled state set to: {enabled}")
        
    def refresh_persons(self):
        """Forces a rescan and reloads the person badges."""
        self.logger.info(self.caller, "Refreshing persons list...")
        self.load_persons(force_rescan=True)
        
    # Override showEvent to load persons when the widget becomes visible
    # Note: This might cause loading every time the tab is switched.
    # Consider connecting to a signal from the parent page if loading should be less frequent.
    def showEvent(self, event):
        """Load persons when the grid becomes visible."""
        super().showEvent(event)
        # Only load if the grid is currently empty, to avoid reloading on every tab switch
        # unless the underlying data might have changed. 
        # A manual refresh button or signal might be better.
        if not self._badge_widgets:
            self.logger.debug(self.caller, "PeopleGrid shown and empty, loading persons.")
            self.load_persons()
        else:
            self.logger.debug(self.caller, "PeopleGrid shown, already populated.") 

    # --- Slots for FaceSwapManager Signals --- #

    @pyqtSlot(dict)
    def _on_process_started(self, totals_dict: dict):
        """Shows initial progress overlays when the process starts."""
        self.logger.info(self.caller, f"Process started, received totals: {totals_dict}")
        for person_name, total in totals_dict.items():
            if person_name in self._badge_widgets:
                 self.logger.debug(self.caller, f"Setting initial progress for {person_name}: 0/{total}")
                 badge = self._badge_widgets[person_name]
                 # Only show overlay if the badge is selected (visual consistency)
                 if badge.is_selected:
                    badge.set_progress_text(f"0/{total}")
                 else:
                     badge.set_progress_text(None) # Ensure non-selected don't show it
            else:
                 self.logger.warn(self.caller, f"Received total for unknown person badge: {person_name}")

    @pyqtSlot(str, int, int)
    def _on_person_progress_updated(self, person_name: str, completed: int, total: int):
        """Updates the progress overlay for a specific person."""
        if person_name in self._badge_widgets:
            # self.logger.debug(self.caller, f"Updating progress for {person_name}: {completed}/{total}")
            badge = self._badge_widgets[person_name]
            # Update text regardless of current selection state (in case selection changed mid-run?)
            badge.set_progress_text(f"{completed}/{total}")
        else:
             # This might happen if a worker finishes after the grid was cleared/reloaded
             self.logger.warn(self.caller, f"Received progress update for unknown/removed person badge: {person_name}")

    @pyqtSlot()
    def _on_process_finished_or_killed(self):
        """Clears all progress overlays when the process ends."""
        self.logger.info(self.caller, "Process finished or killed, clearing progress overlays.")
        for badge in self._badge_widgets.values():
            badge.set_progress_text(None)
        # Optionally re-enable the grid if it was disabled? UI updates handled by FaceDashboardPage.
    # ---------------------------------------- # 