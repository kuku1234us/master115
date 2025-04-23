from typing import List, Dict

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from qt_base_app.components.base_card import BaseCard
from qt_base_app.theme import ThemeManager
from qt_base_app.models import Logger
from .person_badge import PersonBadge
from ...models.people_manager import PeopleManager
from ...models.face_swap_models import PersonData # For type hinting

class PeopleGrid(QWidget):
    """A widget displaying a grid of selectable PersonBadges."""
    # Signals
    selection_changed = pyqtSignal(list) # Emits list of selected person names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PeopleGridWidget")
        self.logger = Logger.instance()
        self.caller = "PeopleGrid"
        self.theme = ThemeManager.instance()
        self.people_manager = PeopleManager.instance()

        self.person_badges: Dict[str, PersonBadge] = {} # {person_name: badge_widget}
        
        self._setup_ui()
        # Defer loading until shown or explicitly called
        # self.load_persons()

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

    def _clear_person_grid(self):
        """Removes all widgets from the person grid layout."""
        while self.person_grid_layout.count():
            item = self.person_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.person_badges.clear() # Clear the tracking dictionary

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

            # --- Create ACTUAL PersonBadge --- #
            badge = PersonBadge(person_name=person_name, first_image_path=first_image)
            badge.toggled.connect(self._on_badge_toggled) # Connect signal
            # ---------------------------------- #

            self.person_grid_layout.addWidget(badge, row, col)
            self.person_badges[person_name] = badge # Store reference

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
        return [name for name, badge in self.person_badges.items() if badge.is_selected]

    def set_enabled(self, enabled: bool):
        """Enables or disables interaction with all badges in the grid."""
        # Consider disabling the card itself for visual feedback
        self.person_picker_card.setEnabled(enabled)
        # Also disable individual badges to prevent interaction
        for badge in self.person_badges.values():
            badge.setEnabled(enabled)
        self.logger.debug(self.caller, f"PeopleGrid enabled state set to: {enabled}")
        
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
        if not self.person_badges:
            self.logger.debug(self.caller, "PeopleGrid shown and empty, loading persons.")
            self.load_persons()
        else:
            self.logger.debug(self.caller, "PeopleGrid shown, already populated.") 