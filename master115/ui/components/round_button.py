"""
Reusable round button component that supports both icon and text modes.
"""
from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from qt_base_app.theme.theme_manager import ThemeManager

# Import QtAwesome for icons if available
try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

class RoundButton(QPushButton):
    """
    A circular button that can display either an icon or short text.
    Maintains consistent styling with a semi-transparent background.
    """
    
    def __init__(
        self,
        parent=None,
        icon_name=None,  # QtAwesome icon name (e.g., "fa5s.folder-open")
        text=None,       # Alternative text if no icon or icon not available
        size=48,         # Button diameter in pixels
        icon_size=24,    # Icon size in pixels
        bg_opacity=0.5   # Background opacity (0.0 to 1.0)
    ):
        super().__init__(parent)
        
        self.theme = ThemeManager.instance()
        self.diameter = size  # Renamed from size
        self.icon_size = icon_size
        
        # Set fixed size using diameter
        self.setFixedSize(self.diameter, self.diameter)
        
        # Set cursor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Get background color with opacity
        tertiary_bg_hex = self.theme.get_color('background', 'tertiary')
        rgb_tuple = self._hex_to_rgb(tertiary_bg_hex)
        rgba_color = f"rgba({rgb_tuple[0]}, {rgb_tuple[1]}, {rgb_tuple[2]}, {bg_opacity})"
        
        # Calculate font size based on button size
        # For text mode, font height should be approximately 2/3 of button diameter
        font_height = int(self.diameter * 0.67) # Use diameter
        if text and len(text) > 1:
            # For multi-character text, reduce size to fit
            font_height = int(font_height * 0.6)
        
        # Set up base styling
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {rgba_color};
                border-radius: {self.diameter/2}px; /* Use diameter */
                padding: 0px;  /* Remove padding to maximize text space */
                border: none;
                font-family: "Arial Black", "Arial", sans-serif;  /* Use Arial Black with fallbacks */
                font-weight: 900;  /* Keep 900 weight as backup */
                font-size: {font_height}px;
                color: {self.theme.get_color('text', 'primary')};
                text-align: center;
                line-height: {self.diameter}px;  /* Use diameter */
            }}
            QPushButton:hover {{
                background-color: rgba({rgb_tuple[0]}, {rgb_tuple[1]}, {rgb_tuple[2]}, {min(bg_opacity + 0.2, 1.0)});
            }}
        """)
        
        # Set up icon or text
        if icon_name and HAS_QTAWESOME:
            self.setIcon(qta.icon(icon_name, color=self.theme.get_color('text', 'primary')))
            self.setIconSize(QSize(icon_size, icon_size))
        elif text:
            self.setText(text)
        
    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple."""
        try:
            if hex_color.startswith('#') and len(hex_color) == 7:
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except (ValueError, AttributeError):
            pass
        return (45, 45, 45)  # Fallback color
        
    def set_icon(self, icon_name):
        """Set or update the button's icon."""
        if HAS_QTAWESOME:
            self.setIcon(qta.icon(icon_name, color=self.theme.get_color('text', 'primary')))
            self.setIconSize(QSize(self.icon_size, self.icon_size))
            # Clear any existing text
            self.setText("")
            
    def set_text(self, text):
        """Set or update the button's text."""
        self.setText(text)
        # Clear any existing icon
        self.setIcon(QIcon())
        # Update font size based on text length
        font_height = int(self.diameter * 0.67)  # Use diameter
        if len(text) > 1:
            font_height = int(font_height * 0.6)
        # Update text styling
        self.setStyleSheet(self.styleSheet().replace(
            f"font-size: {self.diameter}px;", # Target the diameter value used initially
            f"font-size: {font_height}px;"
        )) 