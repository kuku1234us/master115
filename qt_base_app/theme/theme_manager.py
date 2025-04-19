"""
Theme manager for Qt applications.
"""
from pathlib import Path
import yaml
from typing import Dict, Any
import os
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication
import sys

from ..models.resource_locator import ResourceLocator
from ..models.logger import Logger


class ThemeManager:
    """
    Singleton class for managing application theme.
    Loads theme configuration from YAML file and provides access to theme properties.
    """
    _instance = None
    _theme_data: Dict[str, Any] = {}
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._load_theme()
        return cls._instance

    @classmethod
    def instance(cls):
        """Get the singleton instance of ThemeManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, config_relative_path=os.path.join("qt_base_app", "theme", "theme.yaml")):
        """Initialize ThemeManager"""
        if hasattr(ThemeManager, '_initialized') and ThemeManager._initialized:
             # Prevent re-initialization if already done
             return
             
        if ThemeManager._instance is not None and ThemeManager._instance != self:
             raise Exception("ThemeManager is a singleton")
             
        ThemeManager._instance = self
        
        # Get absolute path using ResourceLocator
        # Ensure the path uses the correct separator for the OS
        normalized_relative_path = os.path.normpath(config_relative_path)
        self.config_path = ResourceLocator.get_path(normalized_relative_path)
        
        self.config = self._load_theme_config()
        ThemeManager._initialized = True # Mark as initialized

    def _load_theme(self):
        """Load theme configuration from YAML file."""
        logger = Logger.instance()
        theme_path = Path(__file__).parent / 'theme.yaml'
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                self._theme_data = yaml.safe_load(f)
        except Exception as e:
            logger.error("ThemeManager", f"Error loading theme configuration: {e}")
            self._theme_data = {}

    def _load_theme_config(self):
        """Load theme configuration from YAML file."""
        logger = Logger.instance()
        try:
            # Try multiple possible locations for the theme file
            possible_paths = [
                self.config_path,  # Original path
                os.path.join(os.path.dirname(sys.executable), 'qt_base_app', 'theme', 'theme.yaml'),  # PyInstaller bundle
                os.path.join(os.path.dirname(__file__), 'theme.yaml'),  # Development environment
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                        if config_data:
                            return config_data
                    
            logger.warning("ThemeManager", f"Theme config not found in any of the expected locations")
            return self._get_default_theme_config()
            
        except Exception as e:
            logger.error("ThemeManager", f"Error loading theme config: {e}")
            return self._get_default_theme_config()

    def _get_default_theme_config(self):
        """Provide hardcoded default theme settings if loading fails."""
        logger = Logger.instance()
        logger.warning("ThemeManager", "Using default theme configuration.")
        # Define a basic default theme structure
        return {
            "name": "Default Dark",
            "type": "dark",
            "colors": {
                "primary": "#BB86FC",
                "secondary": "#03DAC6",
                "background": {
                    "primary": "#121212",
                    "secondary": "#1E1E1E",
                    "tertiary": "#2C2C2C",
                    "sidebar": "#1A1A1A"
                },
                "surface": "#1E1E1E",
                "error": "#CF6679",
                "text": {
                    "primary": "#FFFFFF",
                    "secondary": "#B3B3B3",
                    "disabled": "#7F7F7F",
                    "muted": "#888888"
                },
                "border": "#333333",
                "shadow": "#000000"
            },
            "typography": {
                "default": {"family": "Geist", "size": 10, "weight": "normal"},
                "title": {"family": "ICA Rubrik", "size": 16, "weight": "bold"},
                "small": {"family": "Geist", "size": 9, "weight": "normal"},
                "monospace": {"family": "GeistMono", "size": 9, "weight": "normal"}
            },
            "dimensions": {
                "sidebar": {"expanded_width": 200, "collapsed_width": 60},
                "header": {"height": 50}
            },
            "stylesheets": {
                "sidebar": "QWidget#sidebar { background-color: #1A1A1A; border-right: 1px solid #333333; }",
                "header": "QWidget#header { background-color: #1E1E1E; border-bottom: 1px solid #333333; }"
            }
        }

    def get_color(self, *path: str) -> str:
        """
        Get a color value from the theme.
        
        Args:
            *path: The path to the color in the theme configuration
                  e.g., 'background', 'primary' for colors.background.primary
        
        Returns:
            str: The color value or a default if not found
        """
        current = self.config.get('colors', {})
        for key in path:
            current = current.get(key, {})
        return current if isinstance(current, str) else "#000000"

    def get_dimension(self, *path: str) -> int:
        """
        Get a dimension value from the theme.
        
        Args:
            *path: The path to the dimension in the theme configuration
                  e.g., 'sidebar', 'expanded_width' for dimensions.sidebar.expanded_width
        
        Returns:
            int: The dimension value or 0 if not found
        """
        current = self.config.get('dimensions', {})
        for key in path:
            current = current.get(key, {})
        return current if isinstance(current, int) else 0

    def get_typography(self, *path: str) -> Dict[str, int]:
        """
        Get typography settings from the theme.
        
        Args:
            *path: The path to the typography settings
                  e.g., 'title' for typography.title
        
        Returns:
            Dict[str, int]: Dictionary with 'size' and 'weight' or defaults
        """
        current = self.config.get('typography', {})
        for key in path:
            current = current.get(key, {})
        
        if isinstance(current, dict) and 'size' in current and 'weight' in current:
            return current
        return {'size': 14, 'weight': 400}

    def get_stylesheet(self, component: str) -> str:
        """
        Get stylesheet for a specific component.
        
        Args:
            component: The component name ('window', 'sidebar', 'card', etc.)
        
        Returns:
            str: The stylesheet for the component
        """
        if component == 'window':
            return f"""
                QMainWindow {{
                    background-color: {self.get_color('background', 'primary')};
                }}
                QScrollBar:vertical {{
                    background: {self.get_color('background', 'secondary')};
                    width: 6px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {self.get_color('background', 'tertiary')};
                    min-height: 20px;
                    border-radius: 3px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """
        elif component == 'card':
            return f"""
                background-color: {self.get_color('background', 'card')};
                border: 1px solid {self.get_color('border', 'primary')};
                border-radius: {self.get_dimension('card', 'border_radius')}px;
                padding: {self.get_dimension('card', 'padding')}px;
            """
        elif component == 'sidebar':
            return f"""
                background-color: {self.get_color('background', 'sidebar')};
            """
        
        return ""  # Return empty stylesheet for unknown components 

    def apply_theme(self, app: QApplication):
        """Apply the loaded theme to the application (placeholder)."""
        logger = Logger.instance()
        # In a full implementation, this would apply stylesheets, palettes, etc.
        # For now, it primarily ensures the config is loaded.
        logger.info("ThemeManager", f"Theme '{self.config.get('name', 'Unknown')}' loaded.")
        # Example: app.setStyleSheet(self.get_stylesheet('global'))

    def get_resource_path(self, relative_resource_path: str) -> str:
        """
        Gets the absolute path for a resource relative to the application/bundle root.
        Useful for finding theme-related files like qt_material XML.
        """
        return ResourceLocator.get_path(relative_resource_path) 