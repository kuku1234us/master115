import os
from pathlib import Path
from typing import List # Add List for type hinting
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout, 
    QSizePolicy, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon # Import QIcon
import qtawesome as qta # Import qtawesome

# Placeholder for PersonBadge - Replace with actual import later
# from ..faceswap_components.person_badge import PersonBadge

# Import necessary components and models
from ..faceswap_components.person_badge import PersonBadge # Use actual PersonBadge
from ..faceswap_components.people_grid import PeopleGrid # IMPORT THE NEW GRID
from qt_base_app.models import Logger # SettingsManager not needed directly here
from qt_base_app.components.base_card import BaseCard # Import BaseCard
from qt_base_app.theme import ThemeManager # Import ThemeManager
from ..components.icon_button import IconButton # Import IconButton
from ...models.faceswap_manager import FaceSwapManager # Import the manager

# PeopleManager is used by PeopleGrid, not directly here anymore
# from ...models.people_manager import PeopleManager

# Need PreferencesPage constants
try:
    from .preferences_page import PreferencesPage
except ImportError:
    class PreferencesPage:
        AI_ROOT_DIR_KEY = 'ai/root_dir'
        DEFAULT_AI_ROOT_DIR = "D:/AIRoot/"

class FaceDashboardPage(QWidget):
    """Page for controlling and monitoring the face swap automation process."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FaceDashboardPage")
        self.logger = Logger.instance()
        self.caller = "FaceDashboardPage"
        self.theme = ThemeManager.instance() # Keep theme for styling
        self.swap_manager = FaceSwapManager(parent=self) # Instantiate the manager WITH parent

        self._setup_ui()
        # Initial load when the widget is created
        # self._load_persons() # Defer loading until showEvent or explicit call

    def _setup_ui(self):
        """Set up the main UI elements for the dashboard."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Instantiate and Add PeopleGrid --- #
        self.people_grid = PeopleGrid(parent=self)
        layout.addWidget(self.people_grid)
        # Connect the selection changed signal if needed by the dashboard itself
        # self.people_grid.selection_changed.connect(self._on_people_selection_changed) 
        
        # --- Control Buttons (UI Setup is correct) --- #
        # Create a horizontal layout for the buttons
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(10)
        
        # Replace QPushButton with IconButton
        self.start_stop_button = IconButton(
            icon_name='fa5s.play',
            tooltip="Start Automation Process",
            icon_color_key=('text', 'primary'), # Specify light icon color
            parent=self
        )
        self.kill_button = IconButton(
            icon_name='fa5s.skull-crossbones',
            tooltip="Force Kill Automation Process",
            icon_color_key=('text', 'primary'), # Specify light icon color
            parent=self
        )
        
        # Add buttons to the horizontal layout
        self.controls_layout.addWidget(self.start_stop_button)
        self.controls_layout.addWidget(self.kill_button)
        self.controls_layout.addStretch() # Push buttons to the left
        
        # Add the controls layout to the main vertical layout
        layout.addLayout(self.controls_layout)

        # --- Status Log (Styling remains the same) --- #
        self.status_log = QTextEdit()
        self.status_log.setObjectName("StatusLog")
        self.status_log.setReadOnly(True)
        # Set a minimum height and allow vertical expansion
        self.status_log.setMinimumHeight(150) # Increased height
        self.status_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Basic styling (can be enhanced)
        log_bg_color = self.theme.get_color('background', 'secondary')
        log_text_color = self.theme.get_color('text', 'primary')
        card_border_color = self.theme.get_color('border', 'primary')
        self.status_log.setStyleSheet(f"""
            #StatusLog {{
                background-color: {log_bg_color};
                color: {log_text_color};
                border: 1px solid {card_border_color}; 
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        
        # Add the status log to the main layout
        layout.addWidget(self.status_log)

        self.setLayout(layout)
        
        # --- Connect Signals --- #
        self.start_stop_button.clicked.connect(self._on_start_stop_clicked)
        self.kill_button.clicked.connect(self._on_kill_clicked)

        # Connect signals from the FaceSwapManager to UI update slots
        self.swap_manager.log_message.connect(self._log_message)
        self.swap_manager.process_started.connect(self._update_ui_for_start)
        self.swap_manager.process_finished.connect(self._update_ui_for_stop)
        self.swap_manager.process_killed.connect(self._update_ui_for_stop) # Same UI reset on kill

        # Set initial button states
        self.kill_button.setEnabled(False)

    def showEvent(self, event):
        """Override showEvent to potentially refresh persons when page becomes visible."""
        super().showEvent(event)
        self.logger.debug(self.caller, "Page shown.")
        if not self.swap_manager.is_running(): 
            # Let PeopleGrid handle its own loading in its showEvent or via refresh
            # If you want to force a refresh every time dashboard is shown:
            # self.logger.debug(self.caller, "Requesting PeopleGrid refresh.")
            # self.people_grid.refresh_persons() 
            pass # Assuming PeopleGrid handles initial load correctly
        else:
            self.logger.debug(self.caller, "Automation is running, skipping person refresh trigger.")

    # --- Control Button Slots --- #

    def _on_start_stop_clicked(self):
        if self.swap_manager.is_running():
            self.swap_manager.stop_process()
            # UI update (button disabling) will be handled by process_started/finished signals
            self.start_stop_button.setToolTip("Stopping...") # Indicate stop requested
            self.start_stop_button.setEnabled(False) # Temporarily disable to prevent spam
        else:
            selected_names = self.people_grid.get_selected_person_names()
            # Optional: Add basic validation here if needed before calling manager
            if not selected_names:
                 self._log_message("Error: No persons selected. Please select persons from the grid.")
                 return
            self.swap_manager.start_process(selected_names)
            # UI update (button icon, disabling grid) handled by process_started signal

    def _on_kill_clicked(self):
        self.logger.warning(self.caller, "Kill button clicked.")
        # Call the manager to handle the kill request
        if self.swap_manager.is_running(): # Only kill if manager says it's running
            self.swap_manager.kill_process()
        else:
            self._log_message("Kill clicked, but process is not running.")
        # UI update will be handled by the process_killed signal connection

    # --- Manager Signal Slots --- #

    @pyqtSlot(str)
    def _log_message(self, message: str):
        """Appends a message from the worker or internal logic to the status log."""
        self.status_log.append(message)
        # Optional: Log worker messages via main logger too (can be noisy)
        # self.logger.debug("Worker/Internal", message)

    # --- UI Update Slots --- #

    @pyqtSlot()
    def _update_ui_for_start(self):
        """Updates UI elements when the process starts."""
        self.logger.info(self.caller, "Updating UI for process start.")
        stop_icon_color = self.theme.get_color('text', 'primary')
        stop_icon = qta.icon('fa5s.stop', color=stop_icon_color) # type: ignore
        self.start_stop_button.setIcon(stop_icon)
        self.start_stop_button.setToolTip("Request Automation Process Stop")
        self.start_stop_button.setEnabled(True) # Re-enable if it was disabled during stop request
        self.kill_button.setEnabled(True)
        self.people_grid.set_enabled(False) # Disable person selection grid

    @pyqtSlot()
    def _update_ui_for_stop(self): # Renamed from _reset_ui_after_stop
        """Resets the UI elements and internal state to their non-running state."""
        self.logger.info(self.caller, "Updating UI for process stop/finish/kill.")
        play_icon_color = self.theme.get_color('text', 'primary')
        play_icon = qta.icon('fa5s.play', color=play_icon_color) # type: ignore
        self.start_stop_button.setIcon(play_icon)
        self.start_stop_button.setToolTip("Start Automation Process")
        self.start_stop_button.setEnabled(True)
        self.kill_button.setEnabled(False) # Disable kill button
        self.people_grid.set_enabled(True) # Re-enable person selection grid