from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from qt_base_app.theme import ThemeManager

class SearchPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel("Search Page")
        title_font = self.theme.get_typography('h1')
        title_color = self.theme.get_color('text', 'primary')
        title_label.setStyleSheet(f"""
            font-size: {title_font['size']}px;
            font-weight: {title_font['weight']};
            color: {title_color};
            """)

        layout.addWidget(title_label)
        self.setLayout(layout)

        # Set background color from theme
        bg_color = self.theme.get_color('background', 'content')
        self.setStyleSheet(f"background-color: {bg_color};") 