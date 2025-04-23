import os
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox, QLineEdit,
    QPushButton, QCheckBox, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, QStandardPaths

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

        # --- Add User Data Directory Row --- #
        self.user_data_dir_label = QLabel("User Data Dir:")
        self.user_data_dir_edit = QLineEdit()
        self.user_data_dir_edit.setPlaceholderText("(Optional) Leave blank to use default profile")
        self.user_data_dir_button = QPushButton("Browse...")
        # ----------------------------------- #

        # --- AI Configuration ---
        self.ai_root_label = QLabel("AI Root Directory:")
        self.ai_root_edit = QLineEdit()
        self.ai_root_button = QPushButton("Browse...")
        # ------------------------

        config_layout.addWidget(self.chrome_path_label, 0, 0)
        config_layout.addWidget(self.chrome_path_edit, 0, 1)
        config_layout.addWidget(self.chrome_path_button, 0, 2)
        config_layout.addWidget(self.driver_path_label, 1, 0)
        config_layout.addWidget(self.driver_path_edit, 1, 1)
        config_layout.addWidget(self.driver_path_button, 1, 2)
        config_layout.addWidget(self.use_wdm_checkbox, 2, 0, 1, 3) # Span across columns

        # --- Add User Data Dir widgets to layout --- #
        config_layout.addWidget(self.user_data_dir_label, 3, 0)
        config_layout.addWidget(self.user_data_dir_edit, 3, 1)
        config_layout.addWidget(self.user_data_dir_button, 3, 2)
        # ------------------------------------------- #

        # --- Add AI Root Dir widgets to layout ---
        config_layout.addWidget(self.ai_root_label, 4, 0)
        config_layout.addWidget(self.ai_root_edit, 4, 1)
        config_layout.addWidget(self.ai_root_button, 4, 2)
        # -----------------------------------------

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
        self.user_data_dir_button.clicked.connect(self._browse_user_data_dir)
        self.ai_root_button.clicked.connect(self._browse_ai_root)
        # Connect textChanged *after* initial loading to prevent premature saves
        self.chrome_path_edit.textChanged.connect(self._save_chrome_path)
        self.driver_path_edit.textChanged.connect(self._save_driver_path)
        self.use_wdm_checkbox.stateChanged.connect(self._save_use_wdm)
        self.use_wdm_checkbox.stateChanged.connect(self._toggle_driver_path_edit) # Also toggle UI
        self.user_data_dir_edit.textChanged.connect(self._save_user_data_dir)
        self.ai_root_edit.textChanged.connect(lambda text: self._save_setting(SettingsManager.AI_ROOT_DIR_KEY, text, SettingType.PATH))

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
        # Use the key and default from SettingsManager
        key = 'exploration/chrome_path' # Define key locally or get from SettingsManager if added there
        default_path = "C:/Users/Administrator/AppData/Local/115Chrome/Application/115chrome.exe" # Define default locally or get from SettingsManager
        current_path = self.chrome_path_edit.text()
        initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else default_path
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select 115chrome Executable", initial_dir, "Executable files (*.exe)"
        )
        if file_name:
            # Setting text will trigger textChanged signal and auto-save
            self.chrome_path_edit.setText(file_name)

    def _browse_driver_path(self):
        """Open file dialog to select chromedriver executable."""
        # Use the key and default from SettingsManager
        key = 'exploration/driver_path' # Define key locally or get from SettingsManager if added there
        default_path = "D:/projects/chromedriver/chromedriver.exe" # Define default locally or get from SettingsManager
        current_path = self.driver_path_edit.text()
        initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else default_path
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select ChromeDriver Executable", initial_dir, "Executable files (*.exe)"
        )
        if file_name:
            # Setting text will trigger textChanged signal and auto-save
            self.driver_path_edit.setText(file_name.replace('/', '\\') if file_name else "")

    def _browse_user_data_dir(self):
        """Open directory dialog to select Chrome User Data Directory."""
        # Define default locally or get from SettingsManager if added there
        default_parent = os.path.dirname("C:/Users/Administrator/AppData/Local/115Chrome/User Data")
        current_path = self.user_data_dir_edit.text()
        # Start browsing from the parent of the current dir, or the default parent
        initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(current_path) else default_parent
        
        dir_name = QFileDialog.getExistingDirectory(
            self, "Select Chrome User Data Directory", initial_dir
        )
        if dir_name:
            # Use forward slashes consistently internally
            normalized_path = dir_name.replace('\\', '/')
            self.user_data_dir_edit.setText(normalized_path)

    def _browse_ai_root(self):
        """Open directory dialog to select the AI Root Directory."""
        current_path = self.ai_root_edit.text()
        # Start browsing from the current dir, or the default from SettingsManager, or fallback to home
        default_ai_root = self.settings.get(SettingsManager.AI_ROOT_DIR_KEY, SettingsManager.DEFAULT_AI_ROOT_DIR, SettingType.STRING)
        initial_dir = current_path if current_path and os.path.exists(current_path) else default_ai_root
        if not os.path.exists(initial_dir):
             initial_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)

        dir_name = QFileDialog.getExistingDirectory(
            self, "Select AI Root Directory", initial_dir
        )
        if dir_name:
            # Use forward slashes consistently internally
            normalized_path = dir_name.replace('\\', '/')
            self.ai_root_edit.setText(normalized_path)

    def _load_settings(self):
        """Load saved settings and populate the UI."""
        self.logger.debug(self.caller, "Loading preferences...")
        # Block signals temporarily during loading to prevent triggering save slots
        self.chrome_path_edit.blockSignals(True)
        self.driver_path_edit.blockSignals(True)
        self.use_wdm_checkbox.blockSignals(True)
        self.user_data_dir_edit.blockSignals(True)
        self.ai_root_edit.blockSignals(True)

        # Use keys and defaults from SettingsManager where available/defined
        chrome_key = 'exploration/chrome_path'
        driver_key = 'exploration/driver_path'
        use_wdm_key = 'exploration/use_webdriver_manager'
        user_data_key = 'exploration/user_data_dir'
        
        # Get defaults from SettingsManager if defined, otherwise use local fallbacks
        default_chrome = self.settings._defaults.get(chrome_key, ("C:/Users/Administrator/AppData/Local/115Chrome/Application/115chrome.exe", SettingType.PATH))[0]
        default_driver = self.settings._defaults.get(driver_key, ("D:/projects/chromedriver/chromedriver.exe", SettingType.PATH))[0]
        default_use_wdm = self.settings._defaults.get(use_wdm_key, (WEBDRIVER_MANAGER_AVAILABLE, SettingType.BOOL))[0]
        # No default for user_data_dir in settings manager, default handled by browser class
        default_ai_root = SettingsManager.DEFAULT_AI_ROOT_DIR # This one IS defined in SettingsManager

        chrome_path = self.settings.get(chrome_key, default_chrome, SettingType.PATH)
        driver_path = self.settings.get(driver_key, default_driver, SettingType.PATH)
        # Default use_wdm to False if not available, otherwise True
        use_wdm = self.settings.get(use_wdm_key, default_use_wdm, SettingType.BOOL)
        # --- Load User Data Dir setting --- #
        # Important: The default is handled by Chrome115Browser, load None if not set here
        user_data_dir = self.settings.get(user_data_key, None, SettingType.STRING)
        # ---------------------------------- #
        ai_root_dir = self.settings.get(SettingsManager.AI_ROOT_DIR_KEY, default_ai_root, SettingType.PATH)

        self.chrome_path_edit.setText(str(chrome_path).replace('\\', '/') if chrome_path else "")
        self.driver_path_edit.setText(str(driver_path).replace('\\', '/') if driver_path else "")
        self.user_data_dir_edit.setText(user_data_dir if user_data_dir else "")
        self.ai_root_edit.setText(str(ai_root_dir).replace('\\', '/') if ai_root_dir else "")

        if WEBDRIVER_MANAGER_AVAILABLE:
            self.use_wdm_checkbox.setChecked(use_wdm)
        else:
             self.use_wdm_checkbox.setChecked(False)

        # Unblock signals
        self.chrome_path_edit.blockSignals(False)
        self.driver_path_edit.blockSignals(False)
        self.use_wdm_checkbox.blockSignals(False)
        self.user_data_dir_edit.blockSignals(False)
        self.ai_root_edit.blockSignals(False)

        self._toggle_driver_path_edit() # Update enabled state after loading
        self.logger.debug(self.caller, "Preferences loaded.")

    # --- Auto-Save Slots --- #

    def _save_chrome_path(self):
        path_str = self.chrome_path_edit.text()
        path_obj = Path(path_str) if path_str else None
        # Use key from SettingsManager if defined, else local key
        chrome_key = 'exploration/chrome_path' 
        self.settings.set(chrome_key, path_obj, SettingType.PATH)
        self.settings.sync() # Auto-save
        self.logger.debug(self.caller, f"Auto-saved chrome path: {path_str}")

    def _save_driver_path(self):
        # Only save if WDM is not checked
        if not self.use_wdm_checkbox.isChecked():
            path_str = self.driver_path_edit.text()
            path_obj = Path(path_str) if path_str else None
            # Use key from SettingsManager if defined, else local key
            driver_key = 'exploration/driver_path'
            self.settings.set(driver_key, path_obj, SettingType.PATH)
            self.settings.sync() # Auto-save
            self.logger.debug(self.caller, f"Auto-saved driver path: {path_str}")
        else:
            # Clear the setting if WDM is checked
            driver_key = 'exploration/driver_path'
            if self.settings.contains(driver_key):
                 self.settings.remove(driver_key)
                 self.settings.sync()
                 self.logger.debug(self.caller, "Cleared driver path setting because WDM is enabled.")

    def _save_user_data_dir(self):
        path_str = self.user_data_dir_edit.text().strip() # Get text and strip whitespace
        # Save as string, or remove the setting if the field is empty
        user_data_key = 'exploration/user_data_dir'
        if path_str:
            # Optional: Validate if path exists? Maybe not, let browser handle it.
            self.settings.set(user_data_key, path_str, SettingType.STRING)
            self.logger.debug(self.caller, f"Auto-saved user data dir: {path_str}")
        elif self.settings.contains(user_data_key):
            # If field is cleared, remove the setting so browser uses its default
            self.settings.remove(user_data_key)
            self.logger.debug(self.caller, "Cleared user data dir setting.")
        # Sync is needed after set or remove
        self.settings.sync()

    def _save_setting(self, key: str, text_value: str, setting_type: SettingType):
        """Auto-save the AI Root Directory path."""
        value_to_save = None
        save = False
        
        text_value = text_value.strip()
        
        if text_value: 
            try:
                 if setting_type == SettingType.PATH:
                     value_to_save = Path(text_value)
                 elif setting_type == SettingType.STRING:
                      value_to_save = text_value
                 # Add other types as needed
                 else:
                     # Attempt direct conversion for simple types if needed later
                     value_to_save = setting_type.value(text_value) 
                     
                 save = True
                 self.logger.debug(self.caller, f"Attempting to save {key}: {value_to_save}")
                 
            except Exception as e:
                self.logger.error(self.caller, f"Invalid value '{text_value}' for setting {key} (type {setting_type}): {e}")
                save = False # Don't save invalid values
                # Optionally provide UI feedback here (e.g., red border)
                
        elif self.settings.contains(key):
             # If field is cleared, check if we should remove or revert to default
             default_value, _ = self.settings._defaults.get(key, (None, None))
             if default_value is not None:
                 # Revert to default
                 value_to_save = default_value
                 save = True
                 self.logger.debug(self.caller, f"{key} cleared, reverting to default: {default_value}")
                 # Update UI to show the default we just saved (requires mapping key back to widget)
                 self._update_ui_field(key, default_value) 
             else:
                 # Remove the setting if no default exists
                 self.settings.remove(key)
                 save = False # No need to call set later
                 self.logger.debug(self.caller, f"Cleared setting {key} (no default).")
                 self.settings.sync() # Sync removal

        if save and value_to_save is not None:
             self.settings.set(key, value_to_save, setting_type)
             self.settings.sync()
             self.logger.debug(self.caller, f"Auto-saved {key}: {value_to_save}")
             
    def _update_ui_field(self, key: str, value: Any):
        """Updates the corresponding UI field when a setting is reverted to default."""
        widget = None
        # Map key back to the widget (this mapping needs maintenance)
        if key == SettingsManager.AI_ROOT_DIR_KEY:
            widget = self.ai_root_edit
        elif key == 'exploration/chrome_path':
            widget = self.chrome_path_edit
        elif key == 'exploration/driver_path':
            widget = self.driver_path_edit
        elif key == 'exploration/user_data_dir':
             widget = self.user_data_dir_edit
            
        if widget and isinstance(widget, QLineEdit):
             widget.blockSignals(True)
             widget.setText(str(value).replace('\\', '/') if value is not None else "")
             widget.blockSignals(False)

    def _save_use_wdm(self):
        use_wdm = self.use_wdm_checkbox.isChecked()
        # Use key from SettingsManager if defined, else local key
        wdm_key = 'exploration/use_webdriver_manager'
        self.settings.set(wdm_key, use_wdm, SettingType.BOOL)
        self.settings.sync() # Auto-save
        self.logger.debug(self.caller, f"Auto-saved Use WDM: {use_wdm}")
        # If WDM was just checked, clear the manual path setting
        if use_wdm:
            self._save_driver_path() # Call this to clear the setting if needed 