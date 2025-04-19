import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox, QLineEdit,
    QPushButton, QCheckBox, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt

from qt_base_app.theme import ThemeManager
from qt_base_app.models import SettingsManager, SettingType, Logger

# Conditionally import webdriver_manager check variable if needed
# Although not directly used here, it's used for default setting value
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

class PreferencesPage(QWidget):
    """Page for configuring application preferences, including browser paths."""

    # Reuse keys for consistency
    CHROME_PATH_KEY = 'exploration/chrome_path'
    DRIVER_PATH_KEY = 'exploration/driver_path'
    USE_WEBDRIVER_MANAGER_KEY = 'exploration/use_webdriver_manager'

    # Default paths from main.py exploration
    DEFAULT_CHROME_PATH = "C:\\Users\\Administrator\\AppData\\Local\\115Chrome\\Application\\115chrome.exe"
    DEFAULT_DRIVER_PATH = "D:\\projects\\chromedriver\\chromedriver.exe"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreferencesPage")
        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()
        self.logger = Logger.instance()
        self.caller = "PreferencesPage"

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Align group box to top

        # --- Browser Configuration Group ---
        browser_group = QGroupBox("Browser Configuration (Auto-Saved)")
        config_layout = QGridLayout(browser_group)

        self.chrome_path_label = QLabel("115chrome Path:")
        self.chrome_path_edit = QLineEdit()
        self.chrome_path_button = QPushButton("Browse...")

        self.driver_path_label = QLabel("ChromeDriver Path:")
        self.driver_path_edit = QLineEdit()
        self.driver_path_button = QPushButton("Browse...")

        self.use_wdm_checkbox = QCheckBox("Use WebDriver Manager (requires webdriver-manager package)")

        config_layout.addWidget(self.chrome_path_label, 0, 0)
        config_layout.addWidget(self.chrome_path_edit, 0, 1)
        config_layout.addWidget(self.chrome_path_button, 0, 2)
        config_layout.addWidget(self.driver_path_label, 1, 0)
        config_layout.addWidget(self.driver_path_edit, 1, 1)
        config_layout.addWidget(self.driver_path_button, 1, 2)
        config_layout.addWidget(self.use_wdm_checkbox, 2, 0, 1, 3) # Span across columns

        main_layout.addWidget(browser_group)
        # Add other preference sections below if needed
        # main_layout.addStretch() # Remove stretch if you want sections stacked

        self.setLayout(main_layout)

        # Apply theme background
        bg_color = self.theme.get_color('background', 'content')
        self.setStyleSheet(f"QWidget#PreferencesPage {{ background-color: {bg_color}; }}")

        # --- Connect Signals for Auto-Saving --- #
        self.chrome_path_button.clicked.connect(self._browse_chrome_path)
        self.driver_path_button.clicked.connect(self._browse_driver_path)
        # Connect textChanged *after* initial loading to prevent premature saves
        self.chrome_path_edit.textChanged.connect(self._save_chrome_path)
        self.driver_path_edit.textChanged.connect(self._save_driver_path)
        self.use_wdm_checkbox.stateChanged.connect(self._save_use_wdm)
        self.use_wdm_checkbox.stateChanged.connect(self._toggle_driver_path_edit) # Also toggle UI

    def _toggle_driver_path_edit(self):
        """Enable/disable manual driver path based on checkbox state."""
        use_wdm = self.use_wdm_checkbox.isChecked()
        self.driver_path_edit.setEnabled(not use_wdm)
        self.driver_path_button.setEnabled(not use_wdm)
        if not WEBDRIVER_MANAGER_AVAILABLE:
             self.use_wdm_checkbox.setEnabled(False)
             self.use_wdm_checkbox.setToolTip("webdriver-manager package not found.")
             self.use_wdm_checkbox.setChecked(False)

    def _browse_chrome_path(self):
        """Open file dialog to select 115chrome executable."""
        current_path = self.chrome_path_edit.text()
        initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else self.DEFAULT_CHROME_PATH
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select 115chrome Executable", initial_dir, "Executable files (*.exe)"
        )
        if file_name:
            # Setting text will trigger textChanged signal and auto-save
            self.chrome_path_edit.setText(file_name)

    def _browse_driver_path(self):
        """Open file dialog to select chromedriver executable."""
        current_path = self.driver_path_edit.text()
        initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else self.DEFAULT_DRIVER_PATH
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select ChromeDriver Executable", initial_dir, "Executable files (*.exe)"
        )
        if file_name:
            # Setting text will trigger textChanged signal and auto-save
            self.driver_path_edit.setText(file_name)

    def _load_settings(self):
        """Load saved settings and populate the UI."""
        self.logger.debug(self.caller, "Loading preferences...")
        # Block signals temporarily during loading to prevent triggering save slots
        self.chrome_path_edit.blockSignals(True)
        self.driver_path_edit.blockSignals(True)
        self.use_wdm_checkbox.blockSignals(True)

        chrome_path = self.settings.get(self.CHROME_PATH_KEY, self.DEFAULT_CHROME_PATH, SettingType.PATH)
        driver_path = self.settings.get(self.DRIVER_PATH_KEY, self.DEFAULT_DRIVER_PATH, SettingType.PATH)
        # Default use_wdm to False if not available, otherwise True
        default_use_wdm = WEBDRIVER_MANAGER_AVAILABLE
        use_wdm = self.settings.get(self.USE_WEBDRIVER_MANAGER_KEY, default_use_wdm, SettingType.BOOL)

        self.chrome_path_edit.setText(str(chrome_path) if chrome_path else "")
        self.driver_path_edit.setText(str(driver_path) if driver_path else "")

        if WEBDRIVER_MANAGER_AVAILABLE:
            self.use_wdm_checkbox.setChecked(use_wdm)
        else:
             self.use_wdm_checkbox.setChecked(False)

        # Unblock signals
        self.chrome_path_edit.blockSignals(False)
        self.driver_path_edit.blockSignals(False)
        self.use_wdm_checkbox.blockSignals(False)

        self._toggle_driver_path_edit() # Update enabled state after loading
        self.logger.debug(self.caller, "Preferences loaded.")

    # --- Auto-Save Slots --- #

    def _save_chrome_path(self):
        path_str = self.chrome_path_edit.text()
        path_obj = Path(path_str) if path_str else None
        self.settings.set(self.CHROME_PATH_KEY, path_obj, SettingType.PATH)
        self.settings.sync() # Auto-save
        self.logger.debug(self.caller, f"Auto-saved chrome path: {path_str}")

    def _save_driver_path(self):
        # Only save if WDM is not checked
        if not self.use_wdm_checkbox.isChecked():
            path_str = self.driver_path_edit.text()
            path_obj = Path(path_str) if path_str else None
            self.settings.set(self.DRIVER_PATH_KEY, path_obj, SettingType.PATH)
            self.settings.sync() # Auto-save
            self.logger.debug(self.caller, f"Auto-saved driver path: {path_str}")
        else:
            # Clear the setting if WDM is checked
            if self.settings.contains(self.DRIVER_PATH_KEY):
                 self.settings.remove(self.DRIVER_PATH_KEY)
                 self.settings.sync()
                 self.logger.debug(self.caller, "Cleared driver path setting because WDM is enabled.")


    def _save_use_wdm(self):
        use_wdm = self.use_wdm_checkbox.isChecked()
        self.settings.set(self.USE_WEBDRIVER_MANAGER_KEY, use_wdm, SettingType.BOOL)
        self.settings.sync() # Auto-save
        self.logger.debug(self.caller, f"Auto-saved Use WDM: {use_wdm}")
        # If WDM was just checked, clear the manual path setting
        if use_wdm:
            self._save_driver_path() # Call this to clear the setting if needed 