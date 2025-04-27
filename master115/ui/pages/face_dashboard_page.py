import os
from pathlib import Path
from typing import List, Optional # Added Optional
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout, 
    QSizePolicy, QPushButton, QTextEdit,
    QMenu, QApplication # Added QMenu, QApplication
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon, QAction, QCursor # Added QAction, QCursor
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
from ..components.round_button import RoundButton # Import RoundButton for clear logs
from ...models.faceswap_manager import FaceSwapManager # Import the manager
# Import settings manager to load/save toggle states
from qt_base_app.models import SettingsManager, SettingType

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
        self.settings = SettingsManager.instance() # Get settings instance

        # --- State for toggles --- # 
        # Load initial state from settings
        self._run_headless = self.settings.get(
            SettingsManager.AI_FACE_SWAP_RUN_HEADLESS_KEY,
            True, # Default if not found
            SettingType.BOOL
        )
        self._move_source_file = self.settings.get(
            SettingsManager.AI_FACE_SWAP_MOVE_SOURCE_KEY,
            True, # Default if not found
            SettingType.BOOL
        )
        # --- Log Filtering State --- #
        self._full_log_content: Optional[str] = None # Stores all logs during run
        self._active_log_filter: Optional[str] = None # Stores active worker_id filter
        # --------------------------- #

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
        self.people_grid = PeopleGrid(swap_manager=self.swap_manager, parent=self)
        layout.addWidget(self.people_grid)
        # Connect signals AFTER adding the widget
        # self.people_grid._connect_manager_signals() # This should be called internally by PeopleGrid now
        
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
        # --- Headless Toggle Button --- #
        self.headless_toggle_button = IconButton(
            # Icon set in _update_headless_button_visuals
            icon_name='fa5s.eye', # Provide a default icon name
            tooltip="Toggle Browser Visibility", # Tooltip set in _update_headless_button_visuals
            icon_color_key=('text', 'primary'),
            parent=self
        )
        # --- Add Move Source Toggle Button --- #
        self.move_source_toggle_button = IconButton(
            # Icon set in _update_move_source_button_visuals
            icon_name='fa5s.archive', # Use 'archive' icon
            tooltip="Toggle Moving Source Files to Completed", # Tooltip set in _update_move_source_button_visuals
            icon_color_key=('text', 'primary'),
            parent=self
        )
        # ---------------------------------- #
        
        # Add buttons to the horizontal layout
        self.controls_layout.addWidget(self.start_stop_button)
        self.controls_layout.addWidget(self.kill_button)
        self.controls_layout.addWidget(self.headless_toggle_button) # Add the headless button
        self.controls_layout.addWidget(self.move_source_toggle_button) # Add the new move button
        self.controls_layout.addStretch() # Push buttons to the left
        
        # Add the controls layout to the main vertical layout
        layout.addLayout(self.controls_layout)

        # --- Status Log Container --- #
        self.log_area_container = QWidget()
        log_layout = QGridLayout(self.log_area_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        # --- Status Log --- #
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
                padding: 5px 30px 5px 5px; /* Add padding-right for buttons */
            }}
        """)
        
        # Add status log to grid layout
        log_layout.addWidget(self.status_log, 0, 0)

        # --- Log Overlay Buttons --- #
        self.copy_log_button = IconButton(
            icon_name='fa5s.copy',
            tooltip="Copy Logs",
            fixed_size=18, # Smaller size
            icon_color_key=('text', 'secondary'),
            parent=self.log_area_container # Parent is the container
        )
        self.cancel_filter_button = IconButton(
            icon_name='fa5s.undo-alt', # Use 'undo' or similar icon
            tooltip="Clear Log Filter",
            fixed_size=18,
            icon_color_key=('text', 'secondary'),
            parent=self.log_area_container
        )
        self.cancel_filter_button.setVisible(False) # Initially hidden
        
        # Create a Round Button for clearing logs
        self.clear_log_button = RoundButton(
            parent=self.log_area_container,
            icon_name='fa5s.trash',  # Trash can icon
            size=32,                 # Slightly larger than the icon buttons
            icon_size=16,            # Icon size within the button
            bg_opacity=0.4           # Semi-transparent background
        )
        self.clear_log_button.setToolTip("Clear All Logs")
        
        # Position the round button in the bottom-right corner of the log area
        self.clear_log_button.move(
            self.log_area_container.width() - self.clear_log_button.width() - 10,  # Position will be updated in resizeEvent
            self.log_area_container.height() - self.clear_log_button.height() - 10
        )

        # Layout for buttons inside the log area
        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 5, 5, 5) # Align R/T
        buttons_layout.setSpacing(2)
        buttons_layout.addWidget(self.copy_log_button)
        buttons_layout.addWidget(self.cancel_filter_button)
        buttons_layout.addStretch()

        # Add buttons layout to the same grid cell, aligned top-right
        log_layout.addLayout(buttons_layout, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        # --------------------------- #

        # Add the log container to the main layout
        layout.addWidget(self.log_area_container)

        self.setLayout(layout)
        
        # --- Connect Signals --- #
        self.start_stop_button.clicked.connect(self._on_start_stop_clicked)
        self.kill_button.clicked.connect(self._on_kill_clicked)
        self.headless_toggle_button.clicked.connect(self._toggle_headless_mode) # Connect new button
        self.move_source_toggle_button.clicked.connect(self._toggle_move_source_mode) # Connect the new button
        self.copy_log_button.clicked.connect(self._copy_log_content) # Connect copy button
        self.cancel_filter_button.clicked.connect(self._cancel_log_filter) # Connect cancel filter button
        self.clear_log_button.clicked.connect(self._clear_log_content) # Connect clear button

        # Connect signals from the FaceSwapManager to UI update slots
        self.swap_manager.log_message.connect(self._log_message)
        self.swap_manager.process_started.connect(self._update_ui_for_start)
        self.swap_manager.process_finished.connect(self._update_ui_for_stop)
        self.swap_manager.process_killed.connect(self._update_ui_for_stop) # Same UI reset on kill
        # This signal is now connected directly in PeopleGrid._connect_manager_signals()
        # self.swap_manager.person_progress_updated.connect(self.people_grid._on_person_progress_updated)

        # Connect grid filter request
        self.people_grid.filter_requested_for_person.connect(self._show_filter_context_menu)

        # Set initial button states
        self.kill_button.setEnabled(False)
        self._update_headless_button_visuals() # Set initial icon/tooltip for headless toggle
        self._update_move_source_button_visuals() # Set initial icon/tooltip for move toggle

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
            # Pass both toggle states to the manager
            self.swap_manager.start_process(
                selected_person_names=selected_names,
                run_headless=self._run_headless,
                move_source_file=self._move_source_file
            )
            # UI update (button icon, disabling grid) handled by process_started signal

    def _on_kill_clicked(self):
        self.logger.warning(self.caller, "Kill button clicked.")
        # Call the manager to handle the kill request
        if self.swap_manager.is_running(): # Only kill if manager says it's running
            self.swap_manager.kill_process()
        else:
            self._log_message("Kill clicked, but process is not running.")
        # UI update will be handled by the process_killed signal connection

    def _toggle_headless_mode(self):
        """Toggles the headless mode state and updates the button visuals."""
        self._run_headless = not self._run_headless
        # Persist the setting
        self.settings.set(SettingsManager.AI_FACE_SWAP_RUN_HEADLESS_KEY, self._run_headless, SettingType.BOOL)
        self.logger.info(self.caller, f"Headless mode toggled to: {self._run_headless}")
        self._update_headless_button_visuals()

    def _toggle_move_source_mode(self):
        """Toggles the move source file state and updates the button visuals."""
        self._move_source_file = not self._move_source_file
        # Persist the setting
        self.settings.set(SettingsManager.AI_FACE_SWAP_MOVE_SOURCE_KEY, self._move_source_file, SettingType.BOOL)
        self.logger.info(self.caller, f"Move source file mode toggled to: {self._move_source_file}")
        self._update_move_source_button_visuals()

    def _update_headless_button_visuals(self):
        """Updates the icon and tooltip of the headless toggle button."""
        icon_color = self.theme.get_color('text', 'primary')
        if self._run_headless:
            icon = qta.icon('fa5s.eye-slash', color=icon_color) # type: ignore
            tooltip = "Toggle Browser Visibility (Currently Hidden/Headless)"
        else:
            icon = qta.icon('fa5s.eye', color=icon_color) # type: ignore
            tooltip = "Toggle Browser Visibility (Currently Visible)"
        self.headless_toggle_button.setIcon(icon)
        self.headless_toggle_button.setToolTip(tooltip)

    def _update_move_source_button_visuals(self):
        """Updates the icon and tooltip of the move source toggle button."""
        icon_color = self.theme.get_color('text', 'primary')
        if self._move_source_file:
            icon = qta.icon('fa5s.archive', color=icon_color) # Use 'archive' icon
            tooltip = "Toggle Source File Archiving (Currently Moving to Completed)"
        else:
            icon = qta.icon('fa5s.ban', color=icon_color) # Placeholder icon for "Move Disabled"
            tooltip = "Toggle Source File Archiving (Currently NOT Moving to Completed)"
        self.move_source_toggle_button.setIcon(icon)
        self.move_source_toggle_button.setToolTip(tooltip)

    # --- Manager Signal Slots --- #

    @pyqtSlot(str)
    def _log_message(self, message: str):
        """Appends a message from the worker or internal logic to the status log."""
        # Store every message in the full log content if the process is running
        if self.swap_manager.is_running() and self._full_log_content is not None:
            self._full_log_content += message + "\n"

        # If a filter is active, only append if the message matches
        if self._active_log_filter:
            filter_tag = f"[{self._active_log_filter}]"
            if filter_tag in message:
                self.status_log.append(message)
        else:
            # If no filter is active, append all messages
            self.status_log.append(message)

        # Scroll to bottom might need adjustment if filtering is frequent
        self.status_log.verticalScrollBar().setValue(self.status_log.verticalScrollBar().maximum())

    # --- UI Update Slots --- #

    @pyqtSlot(dict) # Updated to accept dict
    def _update_ui_for_start(self, person_totals: dict):
        """Updates UI elements when the process starts."""
        self.logger.info(self.caller, "Updating UI for process start.")
        stop_icon_color = self.theme.get_color('text', 'primary')
        stop_icon = qta.icon('fa5s.stop', color=stop_icon_color) # type: ignore
        self.start_stop_button.setIcon(stop_icon)
        self.start_stop_button.setToolTip("Request Automation Process Stop")
        self.start_stop_button.setEnabled(True) # Re-enable if it was disabled during stop request
        self.kill_button.setEnabled(True)
        self.headless_toggle_button.setEnabled(False) # Disable toggle during run
        self.people_grid.set_enabled(False) # Disable person selection grid
        self.move_source_toggle_button.setEnabled(False) # Disable toggle during run
        
        # Reset log area for new run
        self.status_log.clear()
        self._full_log_content = "" # Initialize empty full log
        self._active_log_filter = None
        self.cancel_filter_button.setVisible(False)
        
        # Set initial progress on badges - THIS IS HANDLED BY PeopleGrid._on_process_started signal now
        # self.people_grid.set_initial_progress(person_totals)

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
        self.headless_toggle_button.setEnabled(True) # Re-enable toggle after run
        self.people_grid.set_enabled(True) # Re-enable person selection grid
        self.move_source_toggle_button.setEnabled(True) # Re-enable toggle after run
        
        # Clear progress overlays - THIS IS HANDLED BY PeopleGrid._on_process_finished_or_killed signal now
        # self.people_grid.clear_progress_overlays()
        
        # Reset filter state if it was active
        if self._active_log_filter:
             self._cancel_log_filter(log_cancel=False) # Reset internal state without logging
             
        # Keep logs visible after run, but clear filter state vars
        self._full_log_content = None # Clear full log reference after run
        self._active_log_filter = None
        self.cancel_filter_button.setVisible(False)

    # --- Context Menu and Filtering Slots --- #

    @pyqtSlot(str)
    def _show_filter_context_menu(self, person_name: str):
        """Shows a context menu to filter logs by worker ID for the given person."""
        print(f"[DEBUG] _show_filter_context_menu called for person: {person_name}")
        
        if not self.swap_manager.is_running():
            print(f"[DEBUG] Context menu requested for {person_name}, but process not running.")
            self.logger.debug(self.caller, f"Context menu requested for {person_name}, but process not running.")
            return

        worker_ids = self.swap_manager.get_active_worker_ids_for_person(person_name)
        print(f"[DEBUG] Worker IDs for {person_name}: {worker_ids}")
        
        if not worker_ids:
            print(f"[DEBUG] No active workers found for {person_name} to show context menu.")
            self.logger.debug(self.caller, f"No active workers found for {person_name} to show context menu.")
            # Optionally show a disabled menu or a message?
            return

        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_stylesheet("menu")) # Apply theme

        for worker_id in worker_ids:
            action = QAction(worker_id, self)
            action.setData(worker_id) # Store worker_id for the slot
            action.triggered.connect(self._apply_log_filter)
            menu.addAction(action)

        print(f"[DEBUG] Showing context menu with {len(worker_ids)} workers")
        # Show menu at cursor position
        menu.exec(QCursor.pos())

    @pyqtSlot()
    def _apply_log_filter(self):
        """Filters the log display based on the selected worker ID from the context menu."""
        action = self.sender()
        if not isinstance(action, QAction):
            return

        worker_id = action.data()
        if not worker_id or self._full_log_content is None: # Check full_log_content too
            self.logger.warn(self.caller, "Apply log filter called with invalid action data or no full log content.")
            return

        self.logger.info(self.caller, f"Applying log filter for worker: {worker_id}")
        self._active_log_filter = worker_id
        filter_tag = f"[{worker_id}]"
        
        # Filter the full log content
        # Ensure self._full_log_content is not None before splitting
        if self._full_log_content:
             all_lines = self._full_log_content.strip().split('\n')
             filtered_lines = [line for line in all_lines if filter_tag in line]
             filtered_text = "\n".join(filtered_lines)
        else:
             filtered_text = "" # Should not happen if filter applied during run
        
        self.status_log.setPlainText(filtered_text) # Update display
        self.cancel_filter_button.setVisible(True) # Show cancel button
        self.status_log.verticalScrollBar().setValue(self.status_log.verticalScrollBar().maximum()) # Scroll to bottom

    @pyqtSlot()
    def _cancel_log_filter(self, log_cancel=True):
        """Restores the full log view and hides the cancel button."""
        if log_cancel:
             self.logger.info(self.caller, "Cancelling log filter.")
        if self._full_log_content is not None:
            self.status_log.setPlainText(self._full_log_content.strip()) # Restore full view
        else:
             self.status_log.clear() # Should not happen if filter was active, but clear just in case
             
        self._active_log_filter = None
        self.cancel_filter_button.setVisible(False)
        self.status_log.verticalScrollBar().setValue(self.status_log.verticalScrollBar().maximum()) # Scroll to bottom

    @pyqtSlot()
    def _copy_log_content(self):
        """Copies the currently displayed log content to the clipboard."""
        current_log_text = self.status_log.toPlainText()
        if current_log_text:
            try:
                clipboard = QApplication.clipboard()
                clipboard.setText(current_log_text)
                self.logger.info(self.caller, "Current log view copied to clipboard.")
                self._log_message("--- Logs copied to clipboard --- ")
            except Exception as e:
                self.logger.error(self.caller, f"Failed to copy logs to clipboard: {e}")
                self._log_message("--- Error copying logs to clipboard --- ")
        else:
            self.logger.info(self.caller, "Copy logs requested, but log view is empty.")
            self._log_message("--- Log view is empty, nothing to copy --- ")

    @pyqtSlot()
    def _clear_log_content(self):
        """Clears all content from the log area."""
        self.logger.info(self.caller, "Clearing all log content.")
        self.status_log.clear()
        
        # Reset other log-related state if needed
        if self.swap_manager.is_running():
            self._full_log_content = "" # Reset the full log content if running
        else:
            self._full_log_content = None # Set to None if not running
            
        # Clear any active filters
        self._active_log_filter = None
        self.cancel_filter_button.setVisible(False)
        
        # Add a message indicating logs were cleared
        self._log_message("--- Log cleared ---")

    # Add a method to handle the resize event for the log container
    def resizeEvent(self, event):
        """Handle resizing of the widget."""
        super().resizeEvent(event)
        # Update the position of the round clear button
        if hasattr(self, 'clear_log_button') and hasattr(self, 'log_area_container'):
            self.clear_log_button.move(
                self.log_area_container.width() - self.clear_log_button.width() - 10,
                self.log_area_container.height() - self.clear_log_button.height() - 10
            )