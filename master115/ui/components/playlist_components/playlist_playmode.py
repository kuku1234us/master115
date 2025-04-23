# ui/components/playlist_components/playlist_playmode.py

import os
import datetime
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMenu, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QCursor
import qtawesome as qta

from qt_base_app.theme.theme_manager import ThemeManager
from qt_base_app.models.settings_manager import SettingsManager, SettingType
from music_player.models.playlist import Playlist
from music_player.models import player_state
from .selection_pool import SelectionPoolWidget, format_file_size, format_modified_time
from music_player.ui.components.icon_button import IconButton
from .selection_pool import DateAwareTableItem

# Define common audio file extensions (can be moved to a shared location)
AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.wav', '.ogg', '.aac', '.m4a', '.wma', 
    '.opus', '.aiff', '.ape', '.mpc'
}

class SizeAwareTableItem(QTableWidgetItem):
    """Custom QTableWidgetItem that correctly sorts file sizes"""
    def __init__(self, text, size_bytes):
        super().__init__(text)
        self.size_bytes = size_bytes
        
    def __lt__(self, other):
        if isinstance(other, SizeAwareTableItem):
            return self.size_bytes < other.size_bytes
        return super().__lt__(other)

class DateAwareTableItem(QTableWidgetItem):
    """Custom QTableWidgetItem that correctly sorts dates"""
    def __init__(self, text, timestamp):
        super().__init__(text)
        self.timestamp = timestamp
        
    def __lt__(self, other):
        if isinstance(other, DateAwareTableItem):
            return self.timestamp < other.timestamp
        return super().__lt__(other)

class PlaylistPlaymodeWidget(QWidget):
    """
    Widget representing the Play Mode of the Playlists page.
    Displays the contents of a selected playlist with a breadcrumb navigation.
    """
    # Signals to be emitted to the parent PlaylistsPage
    back_requested = pyqtSignal()  # Signal to go back to Dashboard Mode
    track_selected_for_playback = pyqtSignal(str) # Emits filepath when a track is selected for playback
    playlist_play_requested = pyqtSignal(Playlist) # Signal to request playing the entire current playlist

    def __init__(self, parent=None):
        """
        Initializes the PlaylistPlaymodeWidget.

        Args:
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setObjectName("playlistPlaymodeWidget")
        
        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()
        self.current_playlist = None  # The currently loaded playlist
        
        # Column indices
        self.COL_FILENAME = 0
        self.COL_SIZE = 1
        self.COL_MODIFIED = 2
        self.COL_DATE_ADDED = 3 # New column index
        
        # Sorting state
        self.sort_column = self.COL_FILENAME
        self.sort_order = Qt.SortOrder.AscendingOrder
        
        # Sort indicator icons
        self.sort_up_icon = qta.icon('fa5s.sort-up', color=self.theme.get_color('text', 'secondary'))
        self.sort_down_icon = qta.icon('fa5s.sort-down', color=self.theme.get_color('text', 'secondary'))
        
        # Allow for absolute positioning of children
        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # Enable Drag and Drop
        self.setAcceptDrops(True)
        
        self._setup_ui()
        self._connect_signals() # Connect signals after UI setup
        
        # Load column widths from settings
        self._load_column_widths()
        
        # Set initial sort indicator
        self._update_sort_indicators()
    
    def _setup_ui(self):
        # Create a breadcrumb container that will be positioned absolutely
        self.breadcrumb_container = QWidget(self)
        self.breadcrumb_container.setObjectName("breadcrumbContainer")
        self.breadcrumb_container.setFixedHeight(32)  # Fixed height for the breadcrumb
        
        # Style the breadcrumb container
        self.breadcrumb_container.setStyleSheet(f"""
            #breadcrumbContainer {{
                background-color: transparent;
            }}
        """)
        
        # Breadcrumb layout
        breadcrumb_layout = QHBoxLayout(self.breadcrumb_container)
        breadcrumb_layout.setContentsMargins(16, 0, 16, 0)
        breadcrumb_layout.setSpacing(8)
        
        # Back button with plain text "<"
        self.back_button = QPushButton("<")
        self.back_button.setToolTip("Back to playlists")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFixedWidth(24)
        self.back_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                padding: 4px;
                color: {self.theme.get_color('text', 'primary')};
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme.get_color('background', 'secondary')}40;
                border-radius: 4px;
            }}
        """)
        
        # Playlist name label with 9pt regular font
        self.playlist_name_label = QLabel("Loading...")
        self.playlist_name_label.setStyleSheet(f"""
            color: {self.theme.get_color('text', 'primary')};
            font-size: 9pt;
            font-weight: normal;
        """)
        
        # Play Playlist Button - Use IconButton
        self.play_playlist_button = IconButton(
            icon_name='fa5s.play',
            tooltip="Play this playlist",
            icon_color_key=('text', 'primary'), # Use primary text color for icon
            fixed_size=QSize(24, 24),      # Keep original fixed size
            icon_size=QSize(12, 12),       # Keep original icon size
            parent=self
        )
        
        breadcrumb_layout.addWidget(self.back_button)
        breadcrumb_layout.addWidget(self.playlist_name_label)
        breadcrumb_layout.addWidget(self.play_playlist_button) # Add the play button
        breadcrumb_layout.addStretch(1)  # Push content to the left
        
        # Position the breadcrumb at the very top
        self.breadcrumb_container.setGeometry(0, 0, self.width(), 32)
        
        # Create a content widget for tracks that will be positioned below the breadcrumb
        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("contentWidget")
        
        # Content layout
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(16, 8, 16, 16)
        content_layout.setSpacing(16) # Add spacing between list and pool
        
        # --- Track Table ---
        self.tracks_table = QTableWidget()
        self.tracks_table.setColumnCount(4)
        self.tracks_table.setHorizontalHeaderLabels(["Filename", "Size", "Modified", "Date Added"])
        self.tracks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tracks_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tracks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tracks_table.setAlternatingRowColors(True)
        self.tracks_table.verticalHeader().setVisible(False)
        self.tracks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tracks_table.horizontalHeader().setStretchLastSection(True)
        self.tracks_table.horizontalHeader().setSortIndicatorShown(True)
        self.tracks_table.setSortingEnabled(False)  # Disable automatic sorting
        self.tracks_table.setShowGrid(False)
        self.tracks_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Set default row height for the vertical header
        self.tracks_table.verticalHeader().setDefaultSectionSize(22)
        
        # Set initial column widths
        self.tracks_table.setColumnWidth(self.COL_FILENAME, 250)
        self.tracks_table.setColumnWidth(self.COL_SIZE, 80)
        self.tracks_table.setColumnWidth(self.COL_MODIFIED, 170)
        self.tracks_table.setColumnWidth(self.COL_DATE_ADDED, 170)
        
        self.tracks_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                alternate-background-color: {self.theme.get_color('background', 'alternate_row')};
                border: none;
                padding: 5px;
                selection-background-color: {self.theme.get_color('background', 'selected_row')};
                selection-color: {self.theme.get_color('text', 'primary')};
            }}
            QTableWidget::item {{
                padding: 0px 8px;
                height: 22px;
                min-height: 22px;
            }}
            QTableWidget::item:selected {{
                background-color: {self.theme.get_color('background', 'selected_row')};
                color: {self.theme.get_color('text', 'primary')};
                border-radius: 0px;
            }}
            QHeaderView::section {{
                background-color: {self.theme.get_color('background', 'tertiary')};
                color: {self.theme.get_color('text', 'secondary')};
                padding: 0px 5px;
                height: 22px;
                border: none;
                border-right: 1px solid {self.theme.get_color('border', 'secondary')};
            }}
            QHeaderView::section:hover {{
                background-color: {self.theme.get_color('background', 'quaternary')};
            }}
        """)
        
        # Add empty message when no tracks
        self.empty_label = QLabel("No tracks in this playlist")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {self.theme.get_color('text', 'secondary')}; font-style: italic;")
        self.empty_label.hide()
        
        # Add components to content layout
        content_layout.addWidget(self.tracks_table)
        content_layout.addWidget(self.empty_label)
        
        # --- Selection Pool --- 
        self.selection_pool_widget = SelectionPoolWidget(parent=self.content_widget)
        content_layout.addWidget(self.selection_pool_widget)
        
        # Position the content below the breadcrumb
        self.content_widget.setGeometry(0, 32, self.width(), self.height() - 32)
    
    def _connect_signals(self):
        """Connect signals after UI elements are created."""
        self.back_button.clicked.connect(self.back_requested)
        self.selection_pool_widget.add_selected_requested.connect(self._handle_add_selected_from_pool)
        self.tracks_table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.tracks_table.doubleClicked.connect(self._on_track_double_clicked)
        self.tracks_table.customContextMenuRequested.connect(self._show_tracks_context_menu)
        self.play_playlist_button.clicked.connect(self._on_play_playlist_requested) # Connect the new button
        
        # Connect column resize signal
        self.tracks_table.horizontalHeader().sectionResized.connect(self._on_column_resized)
    
    def _show_tracks_context_menu(self, position):
        """Display context menu for tracks table"""
        if not self.current_playlist or self.tracks_table.rowCount() == 0:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {self.theme.get_color('background', 'primary')};
                color: {self.theme.get_color('text', 'primary')};
                border: 1px solid {self.theme.get_color('border', 'primary')};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 5px 15px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: {self.theme.get_color('background', 'secondary')};
            }}
        """)
        
        selected_items = self.tracks_table.selectedItems()
        if selected_items:
            # Find unique rows since multiple columns can be selected
            selected_rows = set()
            for item in selected_items:
                selected_rows.add(item.row())
            
            # Copy to clipboard action
            copy_action = menu.addAction("Copy Path")
            copy_action.triggered.connect(lambda: self._copy_selected_paths_to_clipboard())
            
            # Remove from playlist action
            remove_action = menu.addAction("Remove from Playlist")
            remove_action.triggered.connect(lambda: self._call_remove_helper_for_selected())
            
            menu.addSeparator()
            
            # Playback actions
            play_action = menu.addAction("Play Now")
            play_action.triggered.connect(lambda: self._play_selected_track())
            
            # Only enable if a single track is selected
            if len(selected_rows) == 1:
                play_action.setEnabled(True)
            else:
                play_action.setEnabled(False)
        
        menu.exec(QCursor.pos())
    
    def _copy_selected_paths_to_clipboard(self):
        """Copy selected track paths to clipboard"""
        selected_paths = []
        for item in self.tracks_table.selectedItems():
            if item.column() == self.COL_FILENAME:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path:
                    selected_paths.append(path)
        
        if selected_paths:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(selected_paths))
    
    def _remove_selected_tracks(self):
        """Remove selected tracks from the playlist"""
        if not self.current_playlist:
            return
            
        # Get tracks to remove
        tracks_to_remove = []
        rows_to_remove = []
        
        for item in self.tracks_table.selectedItems():
            if item.column() == self.COL_FILENAME:
                row = item.row()
                if row not in rows_to_remove:  # Avoid duplicates
                    rows_to_remove.append(row)
                    track_path = item.data(Qt.ItemDataRole.UserRole)
                    if track_path:
                        tracks_to_remove.append(track_path)
        
        if not tracks_to_remove:
            return
            
        # Remove from playlist
        for track_path in tracks_to_remove:
            self.current_playlist.remove_track(track_path)
            
        # Save the updated playlist
        if self.current_playlist.save():
            # Remove from UI
            for row in sorted(rows_to_remove, reverse=True):
                self.tracks_table.removeRow(row)
                
            # Show empty message if needed
            if self.tracks_table.rowCount() == 0:
                self.tracks_table.hide()
                self.empty_label.show()
    
    def _remove_from_playlist_add_to_pool(self, paths_to_remove: List[str]):
        """Removes tracks from the playlist, saves, adds to pool, and updates UI."""
        if not self.current_playlist or not paths_to_remove:
            return

        rows_to_remove = set()
        actual_paths_removed = []

        # Get rows corresponding to paths and remove from playlist model
        for path in paths_to_remove:
            # Find the row for this path (inefficient for large lists, but okay for context menu/delete)
            items = self.tracks_table.findItems(Path(path).name, Qt.MatchFlag.MatchExactly)
            path_found_in_model = False
            for item in items:
                if item.column() == self.COL_FILENAME and item.data(Qt.ItemDataRole.UserRole) == path:
                     if self.current_playlist.remove_track(path):
                         rows_to_remove.add(item.row())
                         actual_paths_removed.append(path)
                         path_found_in_model = True
                         break # Found the matching item and removed from model
            if not path_found_in_model:
                print(f"[PlayMode] Warning: Path '{path}' selected but not found in playlist model for removal.")

        if not actual_paths_removed:
            print("[PlayMode] No tracks were actually removed from the playlist model.")
            return

        # Save the updated playlist
        if self.current_playlist.save():
            # Remove from UI Table
            for row in sorted(list(rows_to_remove), reverse=True):
                self.tracks_table.removeRow(row)

            # Add removed tracks to selection pool
            self.selection_pool_widget.add_tracks(actual_paths_removed)

            # Show empty message if needed
            if self.tracks_table.rowCount() == 0:
                self.tracks_table.hide()
                self.empty_label.show()
            print(f"[PlayMode] Removed {len(actual_paths_removed)} tracks from playlist and added to pool.")
            return True # Indicate success
        else:
            print("[PlayMode] Error saving playlist after removing tracks.")
            # Consider reverting changes? For now, UI is inconsistent.
            return False # Indicate failure

    def _add_selected_to_pool(self):
        """Add selected tracks to selection pool"""
        selected_paths = []
        for item in self.tracks_table.selectedItems():
            if item.column() == self.COL_FILENAME:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path:
                    selected_paths.append(path)
        
        if selected_paths:
            self.selection_pool_widget.add_tracks(selected_paths)
    
    def _play_selected_track(self):
        """Play the selected track"""
        selected_items = self.tracks_table.selectedItems()
        if selected_items and self.current_playlist:
            # Get the first selected item's row
            row = None
            for item in selected_items:
                if item.column() == self.COL_FILENAME:
                    row = item.row()
                    break
                    
            if row is not None:
                filename_item = self.tracks_table.item(row, self.COL_FILENAME)
                if filename_item:
                    track_path = filename_item.data(Qt.ItemDataRole.UserRole)
                    if track_path and track_path in self.current_playlist.tracks:
                        # Set this playlist as the current one
                        player_state.set_current_playlist(self.current_playlist)
                        
                        # Emit signal with filepath instead of calling player_state directly
                        self.track_selected_for_playback.emit(track_path)
    
    def _on_header_clicked(self, column_index):
        """Handle column header clicks for sorting"""
        if self.sort_column == column_index:
            # Toggle sort order if clicking the same column again
            new_order = Qt.SortOrder.DescendingOrder if self.sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.sort_order = new_order
        else:
            # Set new sort column with default ascending order
            self.sort_column = column_index
            self.sort_order = Qt.SortOrder.AscendingOrder
            
        # Update sort indicator in headers
        self._update_sort_indicators()
            
        # Sort the items
        self.tracks_table.sortItems(column_index, self.sort_order)
        
        # Update the Playlist object with the new sort order
        self._update_playlist_sort_order()
        
        # Ensure row heights are maintained after sorting
        for row in range(self.tracks_table.rowCount()):
            self.tracks_table.setRowHeight(row, 22)
    
    def _update_sort_indicators(self):
        """Update the sort indicators in headers"""
        header = self.tracks_table.horizontalHeader()
        
        # Clear all previous indicators
        for col in range(header.count()):
            header_item = self.tracks_table.horizontalHeaderItem(col)
            if header_item:
                header_item.setIcon(QIcon())
        
        # Add indicator to the sorted column
        header_item = self.tracks_table.horizontalHeaderItem(self.sort_column)
        if header_item:
            if self.sort_order == Qt.SortOrder.AscendingOrder:
                header_item.setIcon(self.sort_up_icon)
            else:
                header_item.setIcon(self.sort_down_icon)
    
    def _on_track_double_clicked(self, index):
        """Handle double-click on a track item to play it"""
        if self.current_playlist and index.isValid():
            # Get the full path from the filename column of the selected row
            row = index.row()
            filename_item = self.tracks_table.item(row, self.COL_FILENAME)
            if filename_item:
                track_path = filename_item.data(Qt.ItemDataRole.UserRole)
                if track_path:
                    # Set this playlist as the current one
                    player_state.set_current_playlist(self.current_playlist)
                    
                    # Emit signal with filepath instead of calling player_state directly
                    self.track_selected_for_playback.emit(track_path)
    
    def _on_column_resized(self, column, oldWidth, newWidth):
        """Save column widths when resized"""
        self._save_column_widths()
    
    def _save_column_widths(self):
        """Save column widths to settings"""
        column_widths = {
            'filename': self.tracks_table.columnWidth(self.COL_FILENAME),
            'size': self.tracks_table.columnWidth(self.COL_SIZE),
            'modified': self.tracks_table.columnWidth(self.COL_MODIFIED),
            'date_added': self.tracks_table.columnWidth(self.COL_DATE_ADDED)
        }
        self.settings.set('ui/playlist_table/column_widths', column_widths, SettingType.DICT)
        
    def _load_column_widths(self):
        """Load column widths from settings"""
        default_widths = {
            'filename': 250,
            'size': 80,
            'modified': 170,
            'date_added': 170 # Add default for new column
        }
        column_widths = self.settings.get('ui/playlist_table/column_widths', default_widths, SettingType.DICT)
        
        self.tracks_table.setColumnWidth(self.COL_FILENAME, column_widths['filename'])
        self.tracks_table.setColumnWidth(self.COL_SIZE, column_widths['size'])
        self.tracks_table.setColumnWidth(self.COL_MODIFIED, column_widths['modified'])
        # Load width for new column
        self.tracks_table.setColumnWidth(self.COL_DATE_ADDED, column_widths.get('date_added', 170)) # Use .get with default
    
    def resizeEvent(self, event):
        # Update widget sizes when the parent widget is resized
        super().resizeEvent(event)
        width = event.size().width()
        height = event.size().height()
        
        # Update breadcrumb width to match parent
        self.breadcrumb_container.setFixedWidth(width)
        
        # Update content area size
        self.content_widget.setGeometry(0, 32, width, height - 32)
    
    def load_playlist(self, playlist: Playlist):
        """
        Load a playlist into the view and display its tracks.
        
        Args:
            playlist (Playlist): The playlist to display and play
        """
        # Explicitly check for None, don't rely on boolean evaluation of Playlist object
        if playlist is None:
            return
            
        self.current_playlist = playlist
        
        # Update the playlist name immediately in the breadcrumb
        display_name = playlist.name if playlist.name else "Untitled Playlist"
        self.playlist_name_label.setText(display_name)
        self.playlist_name_label.repaint() # Force repaint
        
        # Clear and populate the tracks table
        self.tracks_table.setRowCount(0)
        
        if not playlist.tracks:
            self.tracks_table.hide()
            self.empty_label.show()
            # Don't return here, still need to potentially clear pool if needed
        else: # Only show table if there are tracks
            self.empty_label.hide()
            self.tracks_table.show()
            
            for row, track_data in enumerate(playlist.tracks):
                # Extract file info from the dictionary
                track_path = track_data.get('path', '') # Get path safely
                added_time_str = track_data.get('added_time', '') # Get added time safely
                
                if not track_path:
                    print(f"Warning: Skipping playlist item at row {row} due to missing path.")
                    continue # Skip this item if path is missing
                    
                path = Path(track_path)
                filename = path.name # This should be just the filename
                print(f"[PlayMode] Setting filename for row {row}: {filename} (from path: {track_path})") # DEBUG
                
                # Get file size and modified time if available
                try:
                    file_stats = path.stat()
                    file_size = format_file_size(file_stats.st_size)
                    file_size_bytes = file_stats.st_size
                    modified_time = format_modified_time(file_stats.st_mtime)
                    modified_timestamp = file_stats.st_mtime
                except Exception:
                    file_size = "Unknown"
                    file_size_bytes = 0
                    modified_time = "Unknown"
                    modified_timestamp = 0
                
                # Insert new row
                self.tracks_table.insertRow(row)
                # Set fixed row height explicitly
                self.tracks_table.setRowHeight(row, 22)
                
                # Filename
                filename_item = QTableWidgetItem() # Create empty item first
                filename_item.setText(str(filename)) # Explicitly set text, ensuring it's a string
                filename_item.setData(Qt.ItemDataRole.UserRole, track_path)  # Store full path
                # Store original index in UserRole+1 to retrieve later for sorting
                filename_item.setData(Qt.ItemDataRole.UserRole + 1, row) 
                filename_item.setToolTip(track_path)  # Show full path on hover
                self.tracks_table.setItem(row, self.COL_FILENAME, filename_item)
                
                # File size with correct sorting
                size_item = SizeAwareTableItem(file_size, file_size_bytes)
                self.tracks_table.setItem(row, self.COL_SIZE, size_item)
                
                # Modified time with correct sorting
                modified_item = DateAwareTableItem(modified_time, modified_timestamp)
                self.tracks_table.setItem(row, self.COL_MODIFIED, modified_item)
                
                # Date Added column
                added_timestamp = 0
                added_time_display = "Unknown"
                if added_time_str:
                    try:
                        # Parse ISO string to datetime object
                        added_dt = datetime.datetime.fromisoformat(added_time_str)
                        added_timestamp = added_dt.timestamp()
                        added_time_display = added_dt.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        added_time_display = "Invalid Date"
                        
                added_item = DateAwareTableItem(added_time_display, added_timestamp)
                self.tracks_table.setItem(row, self.COL_DATE_ADDED, added_item)
                
            # Auto sort after loading
            self.tracks_table.sortItems(self.sort_column, self.sort_order)
            
            # Update the sort indicators
            self._update_sort_indicators()

            # Update the playlist object with the initial sort order
            self._update_playlist_sort_order()
            
            # Ensure row heights are maintained after sorting
            for row in range(self.tracks_table.rowCount()):
                self.tracks_table.setRowHeight(row, 22)
    
    def keyPressEvent(self, event):
        """Handle key press events, specifically the Delete key for the tracks table."""
        # Ensure the event comes from the tracks table or this widget has focus
        if self.tracks_table.hasFocus() or self.hasFocus():
            if event.key() == Qt.Key.Key_Delete:
                if self.tracks_table.selectedItems():
                    print("[PlayMode] Delete key pressed, removing selected tracks from playlist and adding to pool.")
                    
                    # --- Get selected paths FIRST --- 
                    selected_paths = []
                    for item in self.tracks_table.selectedItems():
                         if item.column() == self.COL_FILENAME:
                             path = item.data(Qt.ItemDataRole.UserRole)
                             if path:
                                 selected_paths.append(path)
                                 
                    if not selected_paths:
                        event.ignore() # No valid tracks selected
                        return
                        
                    # Call the helper method
                    if self._remove_from_playlist_add_to_pool(selected_paths):
                        event.accept() # Indicate we handled the event
                    else: # Helper returned False (e.g., save failed)
                        event.ignore()
                        return # Stop further processing
                         
        # If not handled, pass to parent
        super().keyPressEvent(event)
        
    def get_current_playlist(self) -> Playlist:
        """
        Returns the currently loaded playlist.
        
        Returns:
            Playlist: The current playlist or None if none is loaded
        """
        return self.current_playlist

    def _get_current_sorted_indices(self) -> List[int]:
        """Retrieves the original indices of tracks in their current display order."""
        sorted_indices = []
        for display_row in range(self.tracks_table.rowCount()):
            item = self.tracks_table.item(display_row, self.COL_FILENAME)
            if item:
                original_index = item.data(Qt.ItemDataRole.UserRole + 1)
                if isinstance(original_index, int):
                    sorted_indices.append(original_index)
                else:
                    # This shouldn't happen if load_playlist worked correctly
                    print(f"[PlayMode] Warning: Could not retrieve original index from row {display_row}")
            else:
                 print(f"[PlayMode] Warning: Could not get item for row {display_row} column {self.COL_FILENAME}")
        return sorted_indices

    def _update_playlist_sort_order(self):
        """Gets the current sort order from the table and updates the Playlist object."""
        if self.current_playlist and hasattr(self.current_playlist, 'update_sort_order'):
            sorted_indices = self._get_current_sorted_indices()
            print(f"[PlayMode] Updating playlist with sorted indices: {sorted_indices}")
            self.current_playlist.update_sort_order(sorted_indices)
        elif not self.current_playlist:
             print("[PlayMode] Cannot update sort order: No current playlist.")
        else: # Playlist object doesn't have the method (safety check)
             print("[PlayMode] Warning: Current playlist object does not support update_sort_order.")

    def _handle_add_selected_from_pool(self, tracks_to_add: list):
        """
        Handles adding tracks from the selection pool to the current playlist.
        This function ensures that the global current_playing_playlist reference is maintained.
        
        Args:
            tracks_to_add (list): List of full track file paths.
        """
        # Explicitly check for None
        if self.current_playlist is None:
            print("[PlayMode] _handle_add_selected_from_pool: No current playlist. Aborting.")
            return
        if not tracks_to_add:
            print("[PlayMode] _handle_add_selected_from_pool: No tracks to add. Aborting.")
            return
            
        # Make sure we're using the global reference
        if player_state.get_current_playlist() is not self.current_playlist:
            print("[PlayMode] Updating global current_playing_playlist reference")
            player_state.set_current_playlist(self.current_playlist)
        
        added_count = 0
        for track_path in tracks_to_add:
            if self.current_playlist.add_track(track_path):
                added_count += 1
            # else: # Optionally print if track already exists 
                # print(f"[PlayMode] _handle_add_selected_from_pool: Failed to add (already exists?): {track_path}")
                
        if added_count > 0:
            # Save the updated playlist
            save_success = self.current_playlist.save()
            if not save_success:
                print(f"Error: Failed to save playlist '{self.current_playlist.name}' after adding tracks.")
                # Consider how to handle save failure - rollback?
                return # Stop if save failed
                
            # Refresh the track list view to show the newly added tracks
            self.load_playlist(self.current_playlist)
            
            # Remove the added tracks from the selection pool
            self.selection_pool_widget.remove_tracks(tracks_to_add)

            # Update the sort order in the playlist object
            self._update_playlist_sort_order()

    def _on_play_playlist_requested(self):
        """Emit signal to request playback of the entire current playlist."""
        if self.current_playlist:
            print(f"[PlayMode] Play playlist requested for: {self.current_playlist.name}")
            self.playlist_play_requested.emit(self.current_playlist)
        else:
            print("[PlayMode] Play playlist requested but no playlist loaded.")

    def _call_remove_helper_for_selected(self):
        """Helper function to get selected paths and call the removal logic."""
        selected_paths = []
        for item in self.tracks_table.selectedItems():
            if item.column() == self.COL_FILENAME:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path:
                    selected_paths.append(path)
        if selected_paths:
            if self._remove_from_playlist_add_to_pool(selected_paths):
                # Update the sort order after successful removal
                self._update_playlist_sort_order()

    def _process_dropped_paths(self, paths_to_process: List[str]) -> List[str]:
        """Processes a list of dropped file/folder paths, returning valid audio files.

        Filters extensions and removes duplicates already present in the current playlist
        or the selection pool.

        Args:
            paths_to_process: List of paths from the drop event.

        Returns:
            List of unique, valid, absolute audio file paths.
        """
        print(f"[PlayMode] Processing dropped paths: {paths_to_process}") # Debug
        audio_files_found = []
        for path_str in paths_to_process:
            try:
                p = Path(path_str)
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                    audio_files_found.append(str(p.resolve())) # Store resolved path
                elif p.is_dir():
                    print(f"[PlayMode] Scanning dropped folder: {p}") # Debug
                    for root, _, files in os.walk(p):
                        for filename in files:
                            if Path(filename).suffix.lower() in AUDIO_EXTENSIONS:
                                full_path = os.path.join(root, filename)
                                audio_files_found.append(str(Path(full_path).resolve())) # Store resolved path
            except Exception as e:
                print(f"[PlayMode] Error processing dropped path {path_str}: {e}")

        print(f"[PlayMode] Found {len(audio_files_found)} potential audio files.") # Debug
        if not audio_files_found:
            return [] # Nothing to add

        # --- Filter out duplicates from playlist and pool --- 
        # Get current playlist tracks (normalized)
        current_playlist_tracks_set = set()
        if self.current_playlist:
            current_playlist_tracks_set = set(os.path.normpath(p.get('path', '')) for p in self.current_playlist.tracks)

        # Get current selection pool tracks (normalized - accessing internal set)
        current_pool_tracks_set = self.selection_pool_widget._pool_paths

        files_to_add = []
        for file_path in audio_files_found:
            norm_path = os.path.normpath(file_path) # Normalize path for comparison
            if norm_path not in current_playlist_tracks_set and norm_path not in current_pool_tracks_set:
                files_to_add.append(file_path) # Add the original resolved path
            # else: # Debugging
                # reason = "playlist" if norm_path in current_playlist_tracks_set else "pool"
                # print(f"[PlayMode] Skipping duplicate ({reason}): {norm_path}")

        print(f"[PlayMode] Filtered duplicates, {len(files_to_add)} files remain to be added.") # Debug
        return files_to_add

    # --- Drag and Drop Handling ---
    
    def dragEnterEvent(self, event):
        """Accept drag events if they contain file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            print("[PlayMode] Drag Enter accepted.") # Debug
        else:
            event.ignore()
            print("[PlayMode] Drag Enter ignored.") # Debug

    def dragMoveEvent(self, event):
        """Accept move events during drag."""
        if event.mimeData().hasUrls(): # Check again for safety
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle dropped files/folders based on drop location."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        event.acceptProposedAction()
        urls = event.mimeData().urls()
        paths_to_process = [url.toLocalFile() for url in urls]

        # Remove the unconditional pre-filtering
        # files_to_add = self._process_dropped_paths(paths_to_process)
        # if not files_to_add:
        #     print("[PlayMode] No valid audio files to add after processing drop.")
        #     return

        # Determine drop location
        drop_pos = event.position().toPoint() # Use toPoint() for QPoint
        selection_pool_rect = self.selection_pool_widget.geometry()

        if selection_pool_rect.contains(drop_pos):
            # --- Dropped onto Selection Pool --- 
            # Process paths to filter existing playlist/pool items before adding to pool
            files_to_add_to_pool = self._process_dropped_paths(paths_to_process)
            if files_to_add_to_pool:
                print(f"[PlayMode] Adding {len(files_to_add_to_pool)} files to selection pool.") # Debug
                self.selection_pool_widget.add_tracks(files_to_add_to_pool)
            else:
                 print("[PlayMode] No new files to add to selection pool after filtering.")
        else:
            # --- Dropped onto Playlist Area (Modified Logic) --- 
            print(f"[PlayMode] Processing drop onto playlist area.") # Debug
            if self.current_playlist is None:
                print("[PlayMode] Cannot add tracks: No playlist loaded.")
                return

            # Get sets for efficient lookup
            # Extract the 'path' from the track dictionary before normalizing
            current_playlist_tracks_set = set(os.path.normpath(p.get('path', '')) for p in self.current_playlist.tracks)
            current_pool_tracks_set = self.selection_pool_widget._pool_paths
            
            files_added_to_playlist = []
            files_to_remove_from_pool = []
            playlist_updated = False

            # Iterate through dropped items, scan folders, and process files one by one
            for path_str in paths_to_process:
                potential_audio_files = []
                try:
                    p = Path(path_str)
                    if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                        potential_audio_files.append(str(p.resolve()))
                    elif p.is_dir():
                        for root, _, files in os.walk(p):
                            for filename in files:
                                if Path(filename).suffix.lower() in AUDIO_EXTENSIONS:
                                    full_path = os.path.join(root, filename)
                                    potential_audio_files.append(str(Path(full_path).resolve()))
                except Exception as e:
                    print(f"[PlayMode] Error processing path {path_str} during drop: {e}")
                    continue # Skip this path if error

                # Process the found audio files for this dropped item
                for file_path in potential_audio_files:
                    norm_path = os.path.normpath(file_path)
                    
                    # Skip if already in the current playlist
                    if norm_path in current_playlist_tracks_set:
                        continue
                        
                    # Try adding to the playlist
                    if self.current_playlist.add_track(file_path): 
                        playlist_updated = True
                        files_added_to_playlist.append(file_path)
                        print(f"[PlayMode] Added to playlist: {file_path}")
                        # Check if it was in the pool
                        if norm_path in current_pool_tracks_set:
                            files_to_remove_from_pool.append(file_path)
                            print(f"[PlayMode] Marked for removal from pool: {file_path}")
                            # Update the pool set immediately to prevent re-adding if dropped multiple times quickly
                            current_pool_tracks_set.discard(norm_path)
                            
            # --- Post-processing --- 
            if playlist_updated:
                print(f"[PlayMode] Playlist updated with {len(files_added_to_playlist)} files. Saving...")
                if self.current_playlist.save():
                    print(f"[PlayMode] Saved playlist '{self.current_playlist.name}'.")
                    # Refresh the playlist view
                    self.load_playlist(self.current_playlist)
                else:
                    print(f"[PlayMode] Error saving playlist '{self.current_playlist.name}' after drop.")
            else:
                print("[PlayMode] No new tracks were added to the playlist.")

            if files_to_remove_from_pool:
                print(f"[PlayMode] Removing {len(files_to_remove_from_pool)} files from selection pool.")
                self.selection_pool_widget.remove_tracks(files_to_remove_from_pool)

            # Update sort order if playlist was modified (added to or removed from pool)
            if playlist_updated or files_to_remove_from_pool:
                 self._update_playlist_sort_order()
