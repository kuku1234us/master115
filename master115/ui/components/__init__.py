"""
UI components for the Music Player application.
"""
from .activity_item import ActivityItem

# Import the sidebar components from qt_base_app instead
from qt_base_app.components.sidebar import SidebarWidget, MenuItem, MenuSection

__all__ = [
    # 'DashboardCard',
    # 'StatsCard',
    'ActivityItem',
    'SidebarWidget',
    'MenuItem',
    'MenuSection'
] 