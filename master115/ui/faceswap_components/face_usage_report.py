from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy # Added QLabel for placeholder
from PyQt6.QtCore import Qt # Import Qt namespace
from PyQt6.QtCore import pyqtSlot # Import pyqtSlot
from typing import Optional # Import Optional

from qt_base_app.models import Logger, SettingsManager # Import SettingsManager
from qt_base_app.models.settings_manager import SettingType # Import SettingType enum
from master115.models.people_manager import PeopleManager # Import PeopleManager
from .person_badge_card import PersonBadgeCard
from .face_histogram import FaceHistogram # Import the new histogram widget

# Standard library imports for data gathering
import os
from pathlib import Path
from collections import defaultdict

class FaceUsageReport(QWidget):
    """Widget displaying the face usage report for a selected person."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FaceUsageReport")
        self.logger = Logger.instance()
        self.caller = "FaceUsageReport"

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the layout with PersonBadgeCard and placeholder for histogram."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 1. Person Badge Card (Top)
        self.person_card = PersonBadgeCard(self)
        # Prevent the card from expanding vertically too much
        # Keep horizontal policy, set vertical policy to Maximum
        current_horizontal_policy = self.person_card.sizePolicy().horizontalPolicy()
        self.person_card.setSizePolicy(current_horizontal_policy, QSizePolicy.Policy.Maximum)
        layout.addWidget(self.person_card)

        # 2. Histogram Widget (Bottom)
        self.histogram_widget = FaceHistogram(self)
        # No need to set size policy here, FaceHistogram handles its own expansion
        # Remove placeholder styling
        # self.histogram_widget.setStyleSheet("...") 
        layout.addWidget(self.histogram_widget, 1) # Give histogram area stretch factor

        self.setLayout(layout)

    def _connect_signals(self):
        """Connect signals from child widgets."""
        self.person_card.person_selected.connect(self._on_person_selected)

    @pyqtSlot(str)
    def _on_person_selected(self, person_name: Optional[str]):
        """Slot to handle person selection. Gathers data and updates histogram."""
        self.logger.info(self.caller, f"Person selected in report tab: {person_name}")
        if person_name:
            # Trigger data gathering and histogram update
            self._load_and_display_histogram(person_name)
        else:
            # Clear histogram when deselected
            self.histogram_widget.set_data([], []) # Call set_data with empty lists

    def _load_and_display_histogram(self, person_name: str):
        """Loads usage data for the person and tells the histogram to display it."""
        settings = SettingsManager.instance()
        ai_root = settings.get('ai/root_dir', setting_type=SettingType.PATH)
        if not ai_root or not os.path.isdir(ai_root):
            self.logger.error(self.caller, f"AI Root directory is not set or invalid: {ai_root}")
            self.histogram_widget.set_data([], []) # Clear histogram on error
            # TODO: Maybe display an error message in the histogram?
            return

        face_swapped_dir = Path(ai_root) / "FaceSwapped"
        if not face_swapped_dir.is_dir():
            self.logger.warn(self.caller, f"FaceSwapped directory not found: {face_swapped_dir}")
            self.histogram_widget.set_data([], []) # No data to show
            return

        # --- Now, gather data ---
        # 1. Get ALL faces for the selected person
        people_manager = PeopleManager.instance()
        person_data = people_manager.get_person_data_by_names([person_name])
        if not person_data or not person_data[0].faces:
            self.logger.warn(self.caller, f"Could not find face data for person: {person_name}")
            self.histogram_widget.set_data([], [])
            return
        all_face_stems = sorted([face.path.stem for face in person_data[0].faces])
        if not all_face_stems:
             self.logger.warn(self.caller, f"Person {person_name} has no face stems listed.")
             self.histogram_widget.set_data([], [])
             return

        # 2. Scan FaceSwapped directory and count usage for this person's faces
        self.logger.debug(self.caller, f"Scanning {face_swapped_dir} for usage of {person_name}...")
        usage_counts = defaultdict(int)
        try:
            for filename in os.listdir(face_swapped_dir):
                parts = filename.split(' ')
                if len(parts) >= 3:
                    file_person_name = parts[0]
                    face_stem = parts[1]
                    if file_person_name == person_name:
                        # Only count if the stem is actually one of the person's faces
                        if face_stem in all_face_stems:
                            usage_counts[face_stem] += 1
                        # else: # Log if a stem appears that doesn't belong? Optional.
                        #    self.logger.debug(f"Found stem '{face_stem}' for {person_name} not in original faces list.")

        except OSError as e:
            self.logger.error(self.caller, f"Error reading FaceSwapped directory: {e}", exc_info=True)
            self.histogram_widget.set_data([], [])
            return

        self.logger.debug(self.caller, f"Usage counts for {person_name}: {dict(usage_counts)}")

        # 3. Prepare final lists for histogram (paths and counts for ALL faces)
        final_face_image_paths = []
        final_counts_ordered = []
        
        for face_stem in all_face_stems: # Iterate through ALL stems for the person
            original_path = people_manager.find_face_image_path(person_name, face_stem)
            if original_path:
                final_face_image_paths.append(original_path)
                # Get count from usage_counts, defaulting to 0 if not found
                final_counts_ordered.append(usage_counts[face_stem]) 
            else:
                # This shouldn't happen if get_person_data_by_names worked, but log defensively
                self.logger.error(self.caller, f"Consistency Error: Could not find original image path for face stem '{face_stem}' of person {person_name}, although it was listed in PersonData.")
                # Skip this face if path is missing
                
        if not final_face_image_paths:
             self.logger.warn(self.caller, f"Could not resolve any original image paths for {person_name}, even though faces were listed.")
             self.histogram_widget.set_data([], [])
             return

        # Update the histogram widget with data for ALL faces
        self.logger.info(self.caller, f"Updating histogram for {person_name} with {len(final_face_image_paths)} faces (including zeros).")
        self.histogram_widget.set_data(final_face_image_paths, final_counts_ordered) 