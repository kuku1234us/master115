"""
Base card component for Qt applications.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from ..theme.theme_manager import ThemeManager


class BaseCard(QFrame):
    """
    A base card component that can be extended for specific use cases.
    Provides a standard card layout with a title and content area.
    
    Args:
        title: Optional title for the card
        parent: Parent widget
        border_style: Optional custom border style (default: 1px solid border)
        background_style: Optional custom background style (default: transparent)
    """
    def __init__(self, title="", parent=None, border_style=None, background_style=None):
        super().__init__(parent)
        self.title = title
        self.theme = ThemeManager.instance()
        self.border_style = border_style
        self.background_style = background_style
        
        # Enable background styling
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Set object name for styling
        self.setObjectName("baseCard")
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the card UI layout."""
        # Apply card styling - customizable background and border
        if self.border_style is None:
            self.border_style = f"1px solid {self.theme.get_color('border', 'primary')}"
            
        if self.background_style is None:
            self.background_style = "transparent"
            
        self.setStyleSheet(f"""
            #baseCard {{
                background-color: {self.background_style};
                border: {self.border_style};
                border-radius: 8px;
            }}
        """)
        
        # Create layout with more compact padding (16px)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(16)
        
        # Add title if provided
        if self.title:
            # Create title with styling similar to the original
            self.title_label = QLabel(self.title)
            self.title_label.setObjectName("cardTitle")
            self.title_label.setStyleSheet(f"""
                color: {self.theme.get_color('text', 'primary')};
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 4px;
                background-color: transparent;
            """)
            self.layout.addWidget(self.title_label)
        
        # Create content area
        self.content_widget = QWidget()
        self.content_widget.setObjectName("cardContent")
        self.content_widget.setStyleSheet(f"""
            color: {self.theme.get_color('text', 'primary')};
            background-color: transparent;
        """)
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, self.title and 8 or 0, 0, 0)
        self.content_layout.setSpacing(12)  # Medium spacing between content items
        
        # Add content widget to layout
        self.layout.addWidget(self.content_widget)
    
    def add_widget(self, widget):
        """
        Add a widget to the card's content area.
        
        Args:
            widget: The widget to add
        """
        self.content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """
        Add a layout to the card's content area.
        
        Args:
            layout: The layout to add
        """
        self.content_layout.addLayout(layout)
    
    def clear(self):
        """Remove all widgets from the content area."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() 