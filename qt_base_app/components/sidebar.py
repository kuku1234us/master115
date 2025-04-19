"""
Sidebar component for Qt applications.
"""
from pathlib import Path
import yaml
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QGraphicsOpacityEffect, QFrame,
    QToolButton
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QSize, 
    pyqtSignal, QParallelAnimationGroup
)
from PyQt6.QtGui import QColor, QPalette
import qtawesome as qta

from ..theme.theme_manager import ThemeManager
from ..models.settings_manager import SettingsManager, SettingType


class MenuItem(QPushButton):
    """Menu item for the sidebar."""
    def __init__(self, item_id, title, icon_name, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.title = title
        self.icon_name = icon_name
        self.theme = ThemeManager.instance()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the menu item."""
        # Create a layout for the button content
        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(16, 4, 16, 4)
        self.button_layout.setSpacing(0)  # Reduced from 8 to 4 to decrease the gap
        
        # Central widget to hold icon for better centering
        self.icon_container = QWidget()
        self.icon_container.setFixedWidth(22)
        icon_layout = QHBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)
        
        # Use QToolButton for icons with increased size
        self.icon_button = QToolButton()
        self.icon_button.setFixedSize(28, 28)
        self.icon_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        # Center the icon in the button
        self.icon_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.icon_button.setIconSize(QSize(14, 14))
        # Connect the icon button's click to the parent button's click
        self.icon_button.clicked.connect(self.click)
        self.update_icon(self.theme.get_color('text', 'secondary'))
        
        # Add icon to container with centering
        icon_layout.addWidget(self.icon_button, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Add text label
        self.text_label = QLabel(self.title)
        self.text_label.setStyleSheet(f"""
            color: {self.theme.get_color('text', 'secondary')};
            font-size: {self.theme.get_typography('text')['size']}px;
        """)
        
        # Add the icon container and text to layout
        self.button_layout.addWidget(self.icon_container)
        self.button_layout.addWidget(self.text_label)
        self.button_layout.addStretch()
        
        # Button styling
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName(f"menuItem_{self.item_id}")
        
        # Basic styling
        self.setStyleSheet(f"""
            background-color: {self.theme.get_color('background', 'secondary')};
            border: none;
            border-radius: 4px;
            height: 34px;
            margin: 2px 8px;
        """)
    
    def update_icon(self, color):
        """Update the icon with the given color."""
        if hasattr(self, 'icon_name'):
            icon = qta.icon(self.icon_name, color=color, options=[{'antialiasing': True, 'scale_factor': 1.0}])
            if hasattr(self, 'icon_button'):
                self.icon_button.setIcon(icon)
                self.icon_button.setIconSize(QSize(14, 14))

    def setText(self, text):
        """Override setText to update our custom label."""
        if hasattr(self, 'text_label'):
            self.text_label.setText(text)
        else:
            super().setText(text)


class MenuSection(QWidget):
    """Section in the sidebar menu with a title and items."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.items = []
        self.theme = ThemeManager.instance()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the menu section."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 10, 0, 10)
        self.layout.setSpacing(0)
        
        # Set background to match sidebar
        self.setStyleSheet(f"background-color: {self.theme.get_color('background', 'sidebar')};")
        
        if self.title:
            section_title = QLabel(self.title.upper())
            section_title.setObjectName("sectionTitle")
            section_title.setStyleSheet(f"""
                #sectionTitle {{
                    color: {self.theme.get_color('text', 'muted')};
                    font-size: {self.theme.get_typography('small')['size']}px;
                    font-weight: bold;
                    padding-left: 16px;
                    margin-bottom: 5px;
                    background-color: transparent;
                }}
            """)
            self.layout.addWidget(section_title)
    
    def add_item(self, item):
        """Add a menu item to the section."""
        self.items.append(item)
        self.layout.addWidget(item)


class SidebarWidget(QWidget):
    """Collapsible sidebar widget that can be toggled between expanded and collapsed states."""
    # Signal emitted when a menu item is clicked
    item_clicked = pyqtSignal(str, str)  # id, page
    # Signal emitted when sidebar is toggled
    toggled = pyqtSignal(bool)  # is_expanded
    
    def __init__(self, parent=None, config_path=None):
        super().__init__(parent)
        self.parent = parent
        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()
        
        # Set expanded state from settings
        self.expanded = self.settings.get('ui/sidebar/expanded', True, SettingType.BOOL)
        
        self.animation = None
        self.menu_items = {}
        self.config_path = config_path
        
        # Set fixed width when expanded
        self.expanded_width = self.theme.get_dimension('sidebar', 'expanded_width')
        self.collapsed_width = self.theme.get_dimension('sidebar', 'collapsed_width')
        self.setFixedWidth(self.expanded_width if self.expanded else self.collapsed_width)
        
        # Set object name for styling
        self.setObjectName("sidebar")
        
        # Apply the correct background color
        self.setStyleSheet(self.theme.get_stylesheet('sidebar'))
        
        # Set explicit background color via palette too
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, 
                        QColor(self.theme.get_color('background', 'sidebar')))
        self.setPalette(palette)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create title section
        self.setup_title()
        
        # Create scrollable area for menu items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.menu_widget = QWidget()
        self.menu_widget.setStyleSheet(self.theme.get_stylesheet('sidebar'))
        self.menu_layout = QVBoxLayout(self.menu_widget)
        self.menu_layout.setContentsMargins(0, 10, 0, 10)
        self.menu_layout.setSpacing(0)
        
        self.scroll_area.setWidget(self.menu_widget)
        
        # Add widgets to layout
        self.layout.addWidget(self.scroll_area)
        
        # Load menu items from configuration
        self.load_menu_items()
        
        # If we start in collapsed state, apply it without animation
        if not self.expanded:
            self._apply_collapsed_state()
    
    def setup_title(self):
        """Set up the title section of the sidebar."""
        # Get title and icon from config
        if self.config_path:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    title = config.get('sidebar', {}).get('title', 'Application')
                    icon_name = config.get('sidebar', {}).get('icon', 'fa5s.bars')
            except Exception:
                title = "Application"
                icon_name = "fa5s.bars"
        else:
            title = "Application"
            icon_name = "fa5s.bars"
        
        self.title_header = QWidget()
        self.title_header.setObjectName("titleHeader")
        self.title_header.setMinimumHeight(50)
        self.title_header.setMaximumHeight(50)
        
        self.title_layout = QHBoxLayout(self.title_header)
        self.title_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_icon = QLabel()
        icon = qta.icon(icon_name, color=self.theme.get_color('text', 'primary'),
                       options=[{'antialiasing': True}])
        self.title_icon.setPixmap(icon.pixmap(24, 24))
        
        self.title = QLabel(title)
        self.title.setObjectName("titleLabel")
        typography = self.theme.get_typography('title')
        self.title.setStyleSheet(f"""
            #titleLabel {{
                color: {self.theme.get_color('text', 'primary')};
                font-size: 16px;
                font-weight: {typography['weight']};
            }}
        """)
        
        self.title_layout.addWidget(self.title_icon)
        self.title_layout.addWidget(self.title)
        self.title_layout.addStretch()
        
        self.layout.addWidget(self.title_header)
    
    def load_menu_items(self):
        """Load menu items from configuration."""
        # Clear existing items
        while self.menu_layout.count():
            item = self.menu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Load sections and items from config
        if self.config_path:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    sections = config.get('sidebar', {}).get('sections', [])
            except Exception:
                sections = []
        else:
            sections = []
        
        for section_data in sections:
            section = MenuSection(section_data.get('title', ''))
            
            for item_data in section_data.get('items', []):
                item_id = item_data.get('id')
                title = item_data.get('title', '')
                icon = item_data.get('icon', 'fa5s.circle')
                page = item_data.get('page', '')
                
                menu_item = MenuItem(item_id, title, icon)
                menu_item.clicked.connect(
                    (lambda item_id=item_id, page=page: 
                     lambda checked=False: self.on_item_clicked(item_id, page))()
                )
                
                section.add_item(menu_item)
                self.menu_items[item_id] = menu_item
            
            self.menu_layout.addWidget(section)
        
        # Add a stretch at the end to push all items to the top
        self.menu_layout.addStretch()
        
        # Set dashboard as initially selected
        self.set_selected_item('dashboard')
    
    def set_selected_item(self, item_id):
        """Set an item as selected without emitting the clicked signal."""
        if item_id in self.menu_items:
            selected_item = self.menu_items[item_id]
            selected_item.setStyleSheet(f"""
                background-color: {self.theme.get_color('background', 'tertiary')};
                border: none;
                border-radius: 4px;
                height: 34px;
                margin: 2px 8px;
            """)
            
            if hasattr(selected_item, 'text_label'):
                selected_item.text_label.setStyleSheet(f"""
                    color: {self.theme.get_color('text', 'primary')};
                    font-size: {self.theme.get_typography('text')['size']}px;
                """)
            
            if hasattr(selected_item, 'icon_button'):
                selected_item.update_icon(self.theme.get_color('text', 'primary'))
            
            # Initialize all other items to normal state
            for key, item in self.menu_items.items():
                if key != item_id:
                    item.setStyleSheet(f"""
                        background-color: {self.theme.get_color('background', 'secondary')};
                        border: none;
                        border-radius: 4px;
                        height: 34px;
                        margin: 2px 8px;
                    """)
                    
                    if hasattr(item, 'text_label'):
                        item.text_label.setStyleSheet(f"""
                            color: {self.theme.get_color('text', 'secondary')};
                            font-size: {self.theme.get_typography('text')['size']}px;
                        """)
                    
                    if hasattr(item, 'icon_button'):
                        item.update_icon(self.theme.get_color('text', 'secondary'))
    
    def on_item_clicked(self, item_id, page):
        """Handle menu item click."""
        # Update selected state
        self.set_selected_item(item_id)
        
        # Emit signal with item id and page
        self.item_clicked.emit(item_id, page)
    
    def toggle_sidebar(self):
        """Toggle the sidebar between expanded and collapsed states."""
        self.expanded = not self.expanded
        
        # Save the state to settings
        self.settings.set('ui/sidebar/expanded', self.expanded, SettingType.BOOL)
        self.settings.sync()  # Ensure settings are saved immediately
        
        if self.expanded:
            self._expand_sidebar()
        else:
            self._collapse_sidebar()
        
        # Emit signal with the new expanded state
        self.toggled.emit(self.expanded)
    
    def _expand_sidebar(self):
        """Expand the sidebar."""
        # Create animation group for all animations to run in parallel
        self.animation_group = QParallelAnimationGroup()
        
        # Width animations
        self.width_animation = QPropertyAnimation(self, b"minimumWidth")
        self.width_animation.setDuration(300)
        self.width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.width_animation_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_animation_max.setDuration(300)
        self.width_animation_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Add width animations to group
        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.width_animation_max)
        
        # Expand sidebar
        self.width_animation.setStartValue(self.collapsed_width)
        self.width_animation.setEndValue(self.expanded_width)
        self.width_animation_max.setStartValue(self.collapsed_width)
        self.width_animation_max.setEndValue(self.expanded_width)
        
        # Show the title label in expanded state
        if hasattr(self, 'title'):
            self.title.setVisible(True)
        
        # Animate section titles and menu items
        for i in range(self.menu_layout.count()):
            item = self.menu_layout.itemAt(i)
            if item and item.widget():
                section = item.widget()
                if isinstance(section, MenuSection):
                    # Find the section title label and menu items
                    for j in range(section.layout.count()):
                        child_item = section.layout.itemAt(j)
                        if child_item and child_item.widget():
                            if isinstance(child_item.widget(), QLabel):
                                label = child_item.widget()
                                label.setVisible(True)
                                opacity_effect = QGraphicsOpacityEffect(label)
                                opacity_effect.setOpacity(0.0)
                                label.setGraphicsEffect(opacity_effect)
                                opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
                                opacity_anim.setDuration(200)
                                opacity_anim.setStartValue(0.0)
                                opacity_anim.setEndValue(1.0)
                                self.animation_group.addAnimation(opacity_anim)
                            elif isinstance(child_item.widget(), MenuItem):
                                menu_item = child_item.widget()
                                if hasattr(menu_item, 'text_label'):
                                    # Show text label and restore margins
                                    menu_item.text_label.setVisible(True)
                                    self._finish_expand_item(menu_item)  # Apply expanded margins
                                    opacity_effect = QGraphicsOpacityEffect(menu_item.text_label)
                                    opacity_effect.setOpacity(0.0)
                                    menu_item.text_label.setGraphicsEffect(opacity_effect)
                                    opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
                                    opacity_anim.setDuration(200)
                                    opacity_anim.setStartValue(0.0)
                                    opacity_anim.setEndValue(1.0)
                                    self.animation_group.addAnimation(opacity_anim)
        
        # Start all animations together
        self.animation_group.start()
    
    def _collapse_sidebar(self):
        """Collapse the sidebar."""
        # Create animation group for all animations to run in parallel
        self.animation_group = QParallelAnimationGroup()
        
        # Width animations
        self.width_animation = QPropertyAnimation(self, b"minimumWidth")
        self.width_animation.setDuration(300)
        self.width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.width_animation_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_animation_max.setDuration(300)
        self.width_animation_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Add width animations to group
        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.width_animation_max)
        
        # Collapse sidebar
        self.width_animation.setStartValue(self.expanded_width)
        self.width_animation.setEndValue(self.collapsed_width)
        self.width_animation_max.setStartValue(self.expanded_width)
        self.width_animation_max.setEndValue(self.collapsed_width)
        
        # Hide the title label immediately in collapsed state
        if hasattr(self, 'title'):
            self.title.setVisible(False)
        
        # Center the icons in collapsed state
        for i in range(self.menu_layout.count()):
            item = self.menu_layout.itemAt(i)
            if item and item.widget():
                section = item.widget()
                if isinstance(section, MenuSection):
                    # Find the section title label and menu items
                    for j in range(section.layout.count()):
                        child_item = section.layout.itemAt(j)
                        if child_item and child_item.widget():
                            if isinstance(child_item.widget(), QLabel):
                                label = child_item.widget()
                                opacity_effect = QGraphicsOpacityEffect(label)
                                label.setGraphicsEffect(opacity_effect)
                                opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
                                opacity_anim.setDuration(200)
                                opacity_anim.setStartValue(1.0)
                                opacity_anim.setEndValue(0.0)
                                opacity_anim.finished.connect(lambda lbl=label: lbl.setVisible(False))
                                self.animation_group.addAnimation(opacity_anim)
                            elif isinstance(child_item.widget(), MenuItem):
                                menu_item = child_item.widget()
                                if hasattr(menu_item, 'text_label'):
                                    # Hide text label
                                    opacity_effect = QGraphicsOpacityEffect(menu_item.text_label)
                                    menu_item.text_label.setGraphicsEffect(opacity_effect)
                                    opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
                                    opacity_anim.setDuration(200)
                                    opacity_anim.setStartValue(1.0)
                                    opacity_anim.setEndValue(0.0)
                                    opacity_anim.finished.connect(lambda btn=menu_item: self._finish_collapse_item(btn))
                                    self.animation_group.addAnimation(opacity_anim)
        
        # Start all animations together
        self.animation_group.start()
    
    def _finish_collapse_item(self, item):
        """Finish the collapse animation for a menu item."""
        if hasattr(item, 'text_label'):
            item.text_label.setVisible(False)
            # Center by using equal horizontal margins
            item.button_layout.setContentsMargins(10, 4, 10, 4)
            item.setToolTip(item.title)
    
    def _finish_expand_item(self, item):
        """Finish the expand animation for a menu item."""
        if hasattr(item, 'text_label'):
            # Restore original margins
            item.button_layout.setContentsMargins(16, 4, 16, 4)
            item.setToolTip("")
    
    def _apply_collapsed_state(self):
        """Apply collapsed state without animation (for initial state)."""
        # Set width to collapsed width
        self.setFixedWidth(self.collapsed_width)
        
        # Hide the title label
        if hasattr(self, 'title'):
            self.title.setVisible(False)
        
        # Hide section titles and adjust menu items
        for i in range(self.menu_layout.count()):
            item = self.menu_layout.itemAt(i)
            if item and item.widget():
                section = item.widget()
                if isinstance(section, MenuSection):
                    # Find the section titles and menu items
                    for j in range(section.layout.count()):
                        child_item = section.layout.itemAt(j)
                        if child_item and child_item.widget():
                            if isinstance(child_item.widget(), QLabel):
                                # Hide section titles
                                child_item.widget().setVisible(False)
                            elif isinstance(child_item.widget(), MenuItem):
                                # Apply collapsed state to menu items
                                menu_item = child_item.widget()
                                self._finish_collapse_item(menu_item)
                                # Center the button layout horizontally by setting small, equal margins
                                menu_item.button_layout.setContentsMargins(10, 4, 10, 4) 