from PyQt6.QtWidgets import QListWidget
from PyQt6.QtCore import Qt

class PlaylistListView(QListWidget):
    """
    Widget to display a list of playlists.
    (Currently a placeholder layout)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlistListView")

        # Updated styling to match page background
        self.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #555;
                color: white;
            }
        """)
        self.setMinimumHeight(200) # Ensure it has some initial size 