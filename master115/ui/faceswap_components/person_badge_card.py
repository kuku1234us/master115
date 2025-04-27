from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer

from qt_base_app.components.base_card import BaseCard
from qt_base_app.theme import ThemeManager
from qt_base_app.models import Logger, SettingsManager
from .person_badge import PersonBadge
from ...models.people_manager import PeopleManager, PersonData
# Note: FaceSwapManager is NOT needed here, this is display/selection only

class PersonBadgeCard(QWidget):
    """A reusable card displaying a grid of selectable PersonBadges.
    Implements single selection logic.
    """
    # Signals
    person_selected = pyqtSignal(str) # Emits name of selected person, or None if deselected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PersonBadgeCardWidget")
        self.logger = Logger.instance()
        self.caller = "PersonBadgeCard"
        self.theme = ThemeManager.instance()
        self.people_manager = PeopleManager.instance()
        self.settings = SettingsManager.instance()

        self._badge_widgets: Dict[str, PersonBadge] = {} # Cache badge widgets by name
        self._currently_selected_badge: Optional[PersonBadge] = None
        self._current_cols: int = 0 # Track the current number of columns for responsiveness

        self._setup_ui()
        
        # Load persons immediately on creation or defer?
        # Deferring to showEvent might be better for performance if tab isn't visible initially.
        # Let's load on creation for now, consistent with spec draft.
        self.load_persons()

    def _setup_ui(self):
        """Set up the container card and grid layout."""
        # Use a main layout for the widget itself to contain the card
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Person Picker Card (Using BaseCard, no title) --- #
        self.container_card = BaseCard() # Renamed from person_picker_card for clarity
        self.container_card.setObjectName("PersonBadgeContainerCard")
        
        # Set background transparent and remove padding, keep border
        card_border_color = self.theme.get_color('border', 'primary')
        self.container_card.setStyleSheet(f"""
            #PersonBadgeContainerCard {{
                background-color: transparent; 
                border: 1px solid {card_border_color};
                border-radius: 8px; 
                padding: 0px; /* Match PeopleGrid's card padding */
            }}
        """)
        
        # --- Layout for Person Badges (Using QGridLayout within BaseCard's content area) --- #
        self.person_grid_layout = QGridLayout()
        self.person_grid_layout.setSpacing(10)
        self.person_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.container_card.add_layout(self.person_grid_layout)

        # Add the BaseCard to the main widget layout
        main_layout.addWidget(self.container_card, 0, 0)
        self.setLayout(main_layout)

    def _clear_person_grid(self):
        """Removes all widgets from the person grid layout."""
        self.logger.debug(self.caller, "Clearing existing person badges from layout.")
        # Use the layout we stored directly
        layout = self.person_grid_layout
        if layout is not None:
            # Remove widgets from layout
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater() # Ensure proper cleanup
        else:
            # This should ideally not happen if _setup_ui ran correctly
            self.logger.error(self.caller, "person_grid_layout is None during _clear_person_grid! UI setup may have failed.")

        self._badge_widgets.clear()
        self._currently_selected_badge = None # Clear selection reference

    def load_persons(self, force_rescan: bool = False):
        """Scans for persons using PeopleManager and populates the grid."""
        self._clear_person_grid()
        self.logger.debug(self.caller, f"Loading persons (force_rescan={force_rescan})...")

        persons_data: List[PersonData] = self.people_manager.get_persons(force_rescan=force_rescan)

        if not persons_data:
            # Display a message within the card if no persons found
            # Ensure the grid layout is removed if it exists, before adding label
            if self.person_grid_layout and self.person_grid_layout.parentWidget():
                 # We might need to remove the layout from its parent first
                 # This interaction depends heavily on BaseCard implementation
                 # For now, just clear the BaseCard content area directly if possible
                 # Assuming BaseCard has a clear() or similar method, or we add widgets directly
                 pass # Let's rely on adding the info_label to overwrite/handle layout
                 
            msg = "No persons found in Faces directory."
            if not self.people_manager._get_ai_root():
                 msg = "AI Root Directory not set or invalid. Please check Preferences."
            # Use a QLabel for the message
            info_label = QLabel(msg)
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Add the label to the container card's content area
            # Check if container_card has an add_widget method or similar
            if hasattr(self.container_card, 'add_widget'):
                 self.container_card.clear() # Assume BaseCard might have this
                 self.container_card.add_widget(info_label)
            else: # Fallback: try setting the label as the central widget if applicable
                 # This is less ideal, assumes BaseCard structure
                 self.logger.warn(self.caller, "BaseCard has no add_widget/clear method. Setting label directly.")
                 # Might need self.container_card.setContentWidget(info_label)
                 pass # Avoid making assumptions about BaseCard

            self.logger.info(self.caller, msg)
            self.person_selected.emit(None) # Emit None as no selection possible
            return
        
        # Ensure the grid layout is associated with the container card
        # This check replaces the problematic isinstance(self.container_card.layout()...)
        # We primarily rely on _setup_ui having added it.
        # If it's not there (e.g., after showing the 'no persons' message), re-add it.
        # This part is tricky without BaseCard details. Let's assume _setup_ui handles it.
        if self.person_grid_layout is None:
             self.logger.error(self.caller, "person_grid_layout is None in load_persons. Cannot populate.")
             return
        # Check if the layout has a parent (it should be the BaseCard's content area)
        # This is an indirect check
        if self.person_grid_layout.parent() is None:
             self.logger.warn(self.caller, "person_grid_layout has no parent in load_persons. Re-adding to card.")
             # Assume BaseCard has add_layout or similar
             if hasattr(self.container_card, 'add_layout'):
                 # Might need to clear the info_label first if it was added
                 if hasattr(self.container_card, 'clear'): self.container_card.clear()
                 self.container_card.add_layout(self.person_grid_layout)
             else:
                 self.logger.error(self.caller, "Cannot re-add layout to BaseCard.")
                 return

        self.logger.info(self.caller, f"Found {len(persons_data)} persons. Populating badges.")
        
        # Calculate grid columns dynamically
        row, col = 0, 0
        badge_min_width = 120 # From PersonBadge
        try:
             # Access the content widget of BaseCard if possible
             content_area = self.container_card.content_widget if hasattr(self.container_card, 'content_widget') else self.container_card
             card_content_width = content_area.width() - 2 * self.person_grid_layout.contentsMargins().left()
        except AttributeError:
             card_content_width = self.width() - 40 # Fallback

        if card_content_width <= 0: card_content_width = 4 * (badge_min_width + 10) # Ensure positive width
        max_cols = max(1, int(card_content_width / (badge_min_width + self.person_grid_layout.spacing())))
        self.logger.debug(self.caller, f"Calculated max_cols: {max_cols} (width: {card_content_width})")

        # Populate grid
        for person in persons_data:
            person_name = person.name
            first_image = self.people_manager.get_first_image_path(person_name)
            if first_image is None:
                self.logger.warn(self.caller, f"No first image for {person_name}.")

            badge = PersonBadge(
                person_name=person_name,
                first_image_path=first_image,
                swap_manager=None # Pass None, this card doesn't need swap manager signals
            )
            # Connect the toggled signal to our single selection handler
            badge.toggled.connect(self._on_badge_toggled)
            # Note: Context menu signal is not needed for reports page, so not connected here

            self.person_grid_layout.addWidget(badge, row, col)
            self._badge_widgets[person_name] = badge

            col += 1
            if col >= max_cols:
                col = 0
                row += 1
                
        # Emit initial selection state (None)
        self.person_selected.emit(None)

    @pyqtSlot(str, bool)
    def _on_badge_toggled(self, toggled_person_name: str, is_selected: bool):
        """Handles badge toggles, enforces single selection, and emits signal."""
        sender_badge = self.sender()
        if not isinstance(sender_badge, PersonBadge):
            return

        if is_selected:
            # If a badge was turned ON
            if self._currently_selected_badge and self._currently_selected_badge is not sender_badge:
                # If there was a different badge selected, turn it OFF
                self.logger.debug(self.caller, f"Deselecting previous: {self._currently_selected_badge.get_person_name()}")
                self._currently_selected_badge.set_selected(False) # This triggers update_visuals internally
            
            # Update the currently selected badge reference
            self._currently_selected_badge = sender_badge
            selected_name_to_emit = toggled_person_name
            self.logger.debug(self.caller, f"Selected: {selected_name_to_emit}")

        else:
            # If a badge was turned OFF (potentially by clicking it again)
            if self._currently_selected_badge is sender_badge:
                # If the badge being turned off IS the currently selected one, clear selection
                self._currently_selected_badge = None
                selected_name_to_emit = None
                self.logger.debug(self.caller, "Selection cleared.")
            else:
                # This case shouldn't happen with single selection logic, but handle defensively
                # If some other badge was turned off (not the selected one), do nothing to selection state
                self.logger.warn(self.caller, f"Badge {toggled_person_name} turned off but wasn't the selected one.")
                return # Don't emit signal in this unexpected case
        
        # Emit the final selection state
        self.person_selected.emit(selected_name_to_emit)

    # --- Public Methods --- #

    def get_selected_person_name(self) -> Optional[str]:
        """Returns the name of the currently selected person, or None."""
        if self._currently_selected_badge:
            return self._currently_selected_badge.get_person_name()
        return None

    def refresh_persons(self):
        """Forces a rescan and reloads the person badges."""
        self.logger.info(self.caller, "Refreshing persons list...")
        self.load_persons(force_rescan=True)
        
    def showEvent(self, event):
        """Load persons when the card becomes visible if not already populated."""
        super().showEvent(event)
        if not self._badge_widgets: # Check if badges dict is empty
            self.logger.debug(self.caller, "PersonBadgeCard shown and empty, loading persons.")
            self.load_persons()
            # Need to trigger initial layout calculation after loading
            QTimer.singleShot(0, self._relayout_badges) 
        else:
            self.logger.debug(self.caller, "PersonBadgeCard shown, already populated.") 
            # Also trigger relayout in case size changed while hidden
            QTimer.singleShot(0, self._relayout_badges)
            
    def _calculate_columns(self) -> int:
        """Calculate the optimal number of columns based on current width."""
        badge_min_width = 120 # Minimum width from PersonBadge
        # Ensure layout exists before accessing properties
        if self.person_grid_layout is None:
             self.logger.error(self.caller, "_calculate_columns called but person_grid_layout is None.")
             return 1 # Fallback
             
        spacing = self.person_grid_layout.spacing()
        margins = self.person_grid_layout.contentsMargins()

        try:
            # Use the container card's content area width if available
            content_area = self.container_card.content_widget if hasattr(self.container_card, 'content_widget') else self.container_card
            # Subtract horizontal margins
            available_width = content_area.width() - margins.left() - margins.right()
        except AttributeError:
            # Fallback to the PersonBadgeCard widget itself
            available_width = self.width() - margins.left() - margins.right() - 20 # Adjust for potential parent layout margins

        if available_width <= 0:
            # If width is zero or negative (e.g., widget not shown yet), default to a reasonable number
            return 4

        # Calculation based on available width and item width + spacing
        effective_item_width = badge_min_width + spacing
        if effective_item_width <= 0: # Avoid division by zero
            self.logger.warn(self.caller, "Effective item width is zero or negative. Defaulting to 1 column.")
            return 1
            
        num_cols_float = (available_width + spacing) / effective_item_width
        num_cols = max(1, int(num_cols_float))

        # self.logger.debug(self.caller, f"Calculated max_cols: {num_cols} (width: {available_width})")
        return num_cols
        
    def _relayout_badges(self):
        """Rearrange existing badges in the grid based on current width."""
        if not self._badge_widgets or self.person_grid_layout is None: # Nothing to layout or no layout
            return
            
        new_cols = self._calculate_columns()
        if new_cols == self._current_cols:
            return # No change needed
            
        self.logger.debug(self.caller, f"Relayout triggered. Columns changing from {self._current_cols} to {new_cols}")
        self._current_cols = new_cols
        
        # Temporarily remove widgets from layout without deleting them
        badges_to_relayout = list(self._badge_widgets.values())
        for badge in badges_to_relayout:
            self.person_grid_layout.removeWidget(badge)
            
        # Re-add widgets in the new grid configuration
        row, col = 0, 0
        # Ensure consistent order (e.g., alphabetical by name)
        sorted_badge_names = sorted(self._badge_widgets.keys())
        for name in sorted_badge_names:
             badge = self._badge_widgets[name]
             self.person_grid_layout.addWidget(badge, row, col)
             col += 1
             if col >= self._current_cols:
                 col = 0
                 row += 1
                 
        # Trigger update to ensure layout changes are painted
        self.person_grid_layout.update()
        self.update()

    def resizeEvent(self, event): # Overridden method
        """Handle widget resize events to recalculate columns and relayout."""
        super().resizeEvent(event) # Call base implementation
        # Use QTimer.singleShot to debounce or delay slightly, preventing excessive calculations during resize drag
        QTimer.singleShot(0, self._relayout_badges) # 0ms delay schedules it for the next event loop iteration 