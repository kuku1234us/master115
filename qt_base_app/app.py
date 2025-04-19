"""
Main entry point for Qt base applications.
"""
import sys
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional, Type, Union, Tuple, Any

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont, QFontDatabase

from .window.base_window import BaseWindow
from .theme.theme_manager import ThemeManager
from .models.resource_locator import ResourceLocator
from .models.logger import Logger


def setup_dark_title_bar(app):
    """Set up dark title bar for Windows applications."""
    logger = Logger.instance()
    if platform.system() == "Windows":
        import ctypes
        app.setStyle("Fusion")
        
        # Tell Windows to use dark title bar
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        get_parent = ctypes.windll.user32.GetParent
        
        def apply_dark_title_bar(window_id):
            """Apply dark title bar to a specific window."""
            if window_id:
                try:
                    # Convert window id to int for Windows API
                    hwnd = int(window_id)
                    value = 0x01  # True
                    value_ptr = ctypes.byref(ctypes.c_int(value))
                    value_size = ctypes.sizeof(ctypes.c_int)
                    
                    # Apply to parent window (the actual window frame)
                    parent_hwnd = get_parent(hwnd)
                    if parent_hwnd:
                        set_window_attribute(
                            parent_hwnd,
                            DWMWA_USE_IMMERSIVE_DARK_MODE,
                            value_ptr,
                            value_size
                        )
                    else:
                        # If no parent, try applying to the window itself
                        set_window_attribute(
                            hwnd,
                            DWMWA_USE_IMMERSIVE_DARK_MODE,
                            value_ptr,
                            value_size
                        )
                except Exception as e:
                    logger.error("app", f"Failed to apply dark title bar: {e}")
        
        # Apply to all new windows
        app.focusWindowChanged.connect(
            lambda window: apply_dark_title_bar(window.winId()) if window else None
        )


def load_custom_fonts(fonts_dir_relative: str, font_mappings: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Load custom fonts and return font family names.
    
    Args:
        fonts_dir_relative: Relative path to the fonts directory from the application root
        font_mappings: Dictionary mapping font filenames to category keys, default to standard mapping if None
        
    Returns:
        Dictionary of font family names by category
    """
    logger = Logger.instance()
    # Default font mappings if none provided
    if font_mappings is None:
        font_mappings = {
            "Geist-Regular.ttf": "default",
            "GeistMono-Regular.ttf": "monospace",
            "ICARubrikBlack.ttf": "title"
        }
    
    # Initialize font families dictionary
    font_families = {
        "default": None,      # Default UI font
        "monospace": None,    # Monospace font
        "title": None         # Title font
    }
    
    # Get absolute path using the helper
    fonts_dir_abs = ResourceLocator.get_path(fonts_dir_relative)

    # Add custom fonts if available using the absolute path
    if os.path.isdir(fonts_dir_abs):
        logger.info("app", f"Loading fonts from: {fonts_dir_abs}")
        for font_file, category in font_mappings.items():
            font_path = os.path.join(fonts_dir_abs, font_file)
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id >= 0:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        font_families[category] = families[0]
                else:
                    logger.warning("app", f"Failed to load font: {font_path}")
    else:
         logger.warning("app", f"Fonts directory not found at {fonts_dir_abs}")

    return font_families


def apply_application_styles(app: QApplication, font_families: Dict[str, str], custom_stylesheet: Optional[str] = None) -> None:
    """
    Apply global application styles and fonts.
    
    Args:
        app: QApplication instance to apply styles to
        font_families: Dictionary of font family names by category
        custom_stylesheet: Optional additional CSS to apply
    """
    # Set application-wide font to the default font if available
    if font_families.get("default"):
        app_font = QFont(font_families["default"])
        app_font.setPointSize(10)  # Set a reasonable default size
        app.setFont(app_font)

        # Create stylesheet for specific components
        # Ensure fonts are quoted correctly in CSS
        default_font_css = f"'{font_families['default']}'" if font_families.get('default') else 'sans-serif'
        title_font_css = f"'{font_families['title']}'" if font_families.get('title') else default_font_css
        mono_font_css = f"'{font_families['monospace']}'" if font_families.get('monospace') else 'monospace'

        stylesheet = f"""
            * {{
                font-family: {default_font_css};
            }}

            QLabel#pageTitle {{
                font-family: {title_font_css};
                font-size: 20px;
                font-weight: bold;
            }}
        """

        # Apply additional custom stylesheet if provided
        if custom_stylesheet:
            stylesheet += "\n" + custom_stylesheet

        # Apply stylesheet to application
        app.setStyleSheet(stylesheet)


def set_application_icon(app: QApplication, window: QWidget, icon_paths: List[str]) -> None:
    """
    Set application and window icons, trying multiple formats in order.
    
    Args:
        app: QApplication instance
        window: Main application window
        icon_paths: List of icon paths to try in order of preference
    """
    logger = Logger.instance()
    app_icon = None
    
    for icon_path in icon_paths:
        # Get absolute path
        icon_path_abs = ResourceLocator.get_path(icon_path)
        if os.path.exists(icon_path_abs):
            app_icon = QIcon(icon_path_abs)
            logger.info("app", f"Using icon: {icon_path_abs}")
            break
    
    # Apply icon if found (to both app and window)
    if app_icon:
        app.setWindowIcon(app_icon)
        window.setWindowIcon(app_icon)
    else:
        paths_str = ", ".join(icon_paths)
        logger.warning("app", f"No valid icon found in: {paths_str}")


def create_application(
    window_class: Type[QWidget] = BaseWindow,
    config_path: Optional[str] = None,
    icon_paths: Optional[List[str]] = None,
    fonts_dir: Optional[str] = None,
    font_mappings: Optional[Dict[str, str]] = None,
    custom_stylesheet: Optional[str] = None,
    **window_kwargs
) -> Tuple[QApplication, QWidget]:
    """
    Create and configure the application and main window with custom settings.
    
    Args:
        window_class: Class to instantiate for the main window (default: BaseWindow)
        config_path: Optional path to the application configuration file
        icon_paths: List of icon paths to try in order (e.g., .ico first, then .png)
        fonts_dir: Relative path to fonts directory
        font_mappings: Dictionary mapping font filenames to category keys
        custom_stylesheet: Optional additional CSS to apply to the application
        **window_kwargs: Additional keyword arguments to pass to window_class constructor
        
    Returns:
        tuple: (QApplication instance, window instance)
    """
    # Create application
    app = QApplication(sys.argv)
    
    # Initialize theme manager
    theme = ThemeManager.instance()
    
    # Set up dark title bar for Windows
    setup_dark_title_bar(app)
    
    # Load fonts if directory specified
    font_families = {}
    if fonts_dir:
        font_families = load_custom_fonts(fonts_dir, font_mappings)
        apply_application_styles(app, font_families, custom_stylesheet)
    
    # Resolve config path if provided
    if config_path:
        config_path = ResourceLocator.get_path(config_path)
    
    # Create main window
    window = window_class(config_path, **window_kwargs)
    
    # Set application icon if paths provided
    if icon_paths:
        set_application_icon(app, window, icon_paths)
    
    return app, window


def run_application(app: QApplication, window: QWidget) -> int:
    """
    Run the application.
    
    Args:
        app: QApplication instance
        window: Main window instance
    
    Returns:
        int: Application exit code
    """
    window.show()
    return app.exec() 