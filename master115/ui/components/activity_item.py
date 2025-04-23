"""
ActivityItem component for the music player application.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
import qtawesome as qta


class ActivityItem(QWidget):
    """
    An activity item with a colored indicator, title, and subtitle.
    """
    def __init__(self, title, subtitle, icon_name, color, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.icon_name = icon_name
        self.color = color
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the activity item."""
        # Main layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 4, 0, 4)
        self.layout.setSpacing(12)
        
        # Create icon indicator
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setPixmap(qta.icon(self.icon_name, color=self.color, options=[{'antialiasing': True}]).pixmap(16, 16))
        self.icon_label.setStyleSheet(f"""
            background-color: {self.color.replace(')', ' / 20%)')};
            border-radius: 10px;
            padding: 2px;
        """)
        
        # Create content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        
        # Create title and subtitle
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #fafafa;
        """)
        
        self.subtitle_label = QLabel(self.subtitle)
        self.subtitle_label.setStyleSheet("""
            font-size: 12px;
            color: #a1a1aa;
        """)
        
        # Add to layouts
        self.content_layout.addWidget(self.title_label)
        self.content_layout.addWidget(self.subtitle_label)
        
        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.content_widget, 1)  # Stretch factor 1 