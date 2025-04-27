from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QCursor, QIcon

# Try importing qtawesome, handle if not found
try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

from qt_base_app.theme.theme_manager import ThemeManager

class IconButton(QPushButton):
    """
    A reusable button component that displays only an icon,
    with a tooltip and specific styling (flat, hover effect).
    """
    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        parent=None,
        icon_color_key: tuple = ('icon', 'primary'), # Use theme key tuple
        icon_size: QSize = QSize(16, 16), # Default icon size
        fixed_size: QSize = None, # Optional fixed size for the button
        bg_hover_color_key: tuple = ('background', 'hover')
    ):
        """
        Initialize the IconButton.

        Args:
            icon_name (str): The identifier for the qtawesome icon (e.g., 'fa5s.folder-open').
            tooltip (str): The text to display on hover.
            parent (QWidget, optional): The parent widget. Defaults to None.
            icon_color_key (tuple, optional): Theme dictionary keys for the icon color.
                                             Defaults to ('icon', 'primary').
            icon_size (QSize, optional): The size of the icon. Defaults to QSize(16, 16).
            fixed_size (QSize, optional): Optional fixed size for the button itself. Defaults to None.
            bg_hover_color_key (tuple, optional): Theme keys for hover background color. Defaults to ('background', 'tertiary').
        """
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        # Ensure stylesheet background colors are applied
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._setup_icon(icon_name, icon_color_key, icon_size)
        self._apply_style(tooltip, fixed_size, bg_hover_color_key, icon_size)

    def _setup_icon(self, icon_name: str, color_key: tuple, size: QSize):
        """Sets the button's icon."""
        if HAS_QTAWESOME:
            try:
                color = self.theme.get_color(*color_key)
                icon = qta.icon(icon_name, color=color)
                self.setIcon(icon)
                self.setIconSize(size)
            except Exception as e:
                print(f"Error setting icon '{icon_name}': {e}")
                # Optionally set fallback text if icon fails
                # self.setText("?")
        else:
            # Fallback if qtawesome is not available
            # You might set simple text or leave it blank
            print("Warning: qtawesome not found. IconButton will not display icons.")
            # self.setText("?") # Example fallback

    def _apply_style(self, tooltip: str, fixed_size: QSize, hover_key: tuple, icon_size: QSize):
        """Applies styling properties to the button."""
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        
        # Define padding used in stylesheet
        style_padding = 8 # Corresponds to padding: 4px; below

        # Calculate button size based on icon size and padding, unless fixed_size is given
        if fixed_size:
            # Use fixed_size for both width and height
            self.setFixedSize(fixed_size, fixed_size)
            # Adjust policy if fixed size is set
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button_width = fixed_size
            button_height = fixed_size
        else:
             # Calculate desired button dimension
             button_dimension = icon_size.width() + (2 * style_padding)
             calculated_size = QSize(button_dimension, button_dimension)
             self.setFixedSize(calculated_size) 
             self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
             button_width = button_dimension
             button_height = button_dimension

        # Calculate border-radius for circular effect if button is square
        radius_str = "4px" # Default radius
        if button_width == button_height and button_width > 0:
            radius_str = f"{int(button_width / 2)}px"

        # Generate hover background color string - simplified
        hover_bg = self.theme.get_color(*hover_key) # Get hover color directly

        self.setStyleSheet(f"""
            QPushButton {{
                border: none;
                padding: {style_padding}px;
                /* Use calculated radius */
                border-radius: {radius_str};
                background-color: transparent;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:pressed {{
                background-color: {self.theme.get_color('background', 'tertiary')}; /* Slightly darker press */
            }}
        """)
