"""
Reusable Search Input Field component.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from qt_base_app.theme.theme_manager import ThemeManager

class SearchField(QWidget):
    """
    A reusable search input field widget with a placeholder and a search icon.
    """
    textChanged = pyqtSignal(str)

    def __init__(self, placeholder: str = "Search...", parent: QWidget = None):
        """
        Initialize the SearchField.

        Args:
            placeholder (str): The placeholder text to display when the input is empty. Defaults to "Search...".
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setObjectName("searchFieldWidget")
        # Enable background styling for the widget
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.theme = ThemeManager.instance()

        self._setup_ui(placeholder)
        self._connect_signals()

    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)  # add some padding
        layout.setSpacing(8)

        # LineEdit for text input
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # expand horizontally

        # Label for the search icon
        self.icon_label = QLabel()
        self.icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._render_icon()  # render the SVG icon

        layout.addWidget(self.line_edit)
        layout.addWidget(self.icon_label)

        # Set a fixed height based on the QLineEdit plus margins.
        self.line_edit.setFixedHeight(24)  # Adjust height to match styling
        # Calculate the final height of the widget; here margin top + bottom = 4+4 = 8
        final_height = self.line_edit.height() + 8
        self.setFixedHeight(final_height)
        # Calculate border radius for a "pill" shape (half of the final height)
        border_radius = final_height // 2

        # Retrieve colors from the theme
        bg_color = self.theme.get_color('background', 'tertiary')  # e.g., "#27272a"
        text_color = self.theme.get_color('text', 'primary')
        placeholder_color = self.theme.get_color('text', 'secondary')
        border_color = self.theme.get_color('border', 'primary')

        # Update the widget's stylesheet using the computed border_radius.
        self.setStyleSheet(f"""
            QWidget#searchFieldWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {border_radius}px;
            }}
            QLineEdit {{
                background-color: transparent;
                border: none;
                color: {text_color};
                padding: 2px;
                font-size: 9pt;
            }}
            QLineEdit::placeholder {{
                color: {placeholder_color};
            }}
        """)

    def _render_icon(self):
        """Renders the search icon SVG with the theme color."""
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
        icon_color = self.theme.get_color('text', 'secondary')

        renderer = QSvgRenderer(svg_data)
        icon_size = QSize(16, 16)  # desired icon size
        pixmap = QPixmap(icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)  # ensure transparent background

        painter = QPainter(pixmap)
        renderer.render(painter)
        # Apply color overlay to the icon
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(icon_color))
        painter.end()

        self.icon_label.setPixmap(pixmap)
        self.icon_label.setFixedSize(icon_size)

    def _connect_signals(self):
        self.line_edit.textChanged.connect(self.textChanged)

    def text(self) -> str:
        """Return the current text in the search field."""
        return self.line_edit.text()

    def setText(self, text: str):
        """Set the text in the search field."""
        self.line_edit.setText(text)

    def clear(self):
        """Clear the text in the search field."""
        self.line_edit.clear()

    def setPlaceholderText(self, text: str):
        """Set the placeholder text."""
        self.line_edit.setPlaceholderText(text)

    # Override sizeHint and minimumSizeHint if necessary for layout integration
    def sizeHint(self) -> QSize:
        # Provide a reasonable default size hint
        return QSize(200, self.height())

    def minimumSizeHint(self) -> QSize:
        # Ensure it can shrink but maintain height
        return QSize(100, self.height())
