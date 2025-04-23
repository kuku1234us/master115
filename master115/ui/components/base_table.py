import os
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import qtawesome as qta

from qt_base_app.theme.theme_manager import ThemeManager
from qt_base_app.models.settings_manager import SettingsManager, SettingType

# --- Helper functions ---

def format_file_size(size_bytes):
    """Format file size from bytes to human-readable format"""
    try:
        size_bytes = int(size_bytes)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f} GB"
    except (ValueError, TypeError):
        return "Unknown"

def format_modified_time(mod_time):
    """Format modified time (timestamp) to human-readable format"""
    try:
        timestamp = float(mod_time)
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return "Unknown"

# --- Custom item classes ---

class SizeAwareTableItem(QTableWidgetItem):
    """Custom QTableWidgetItem that correctly sorts file sizes"""
    def __init__(self, text, size_bytes):
        super().__init__(text)
        self.size_bytes = size_bytes

    def __lt__(self, other):
        if isinstance(other, SizeAwareTableItem):
            return self.size_bytes < other.size_bytes
        # Fallback comparison (might not be ideal, but prevents errors)
        try:
            # Extract numeric part for comparison if possible
            self_val = float(self.text().split()[0])
            other_val = float(other.text().split()[0])
            return self_val < other_val
        except:
            return super().__lt__(other)


class DateAwareTableItem(QTableWidgetItem):
    """Custom QTableWidgetItem that correctly sorts dates based on timestamp"""
    def __init__(self, text, timestamp):
        super().__init__(text)
        self.timestamp = timestamp

    def __lt__(self, other):
        if isinstance(other, DateAwareTableItem):
            return self.timestamp < other.timestamp
        # Fallback comparison
        try:
            # Attempt to parse dates from text if timestamps aren't comparable
            # Assumes the format set by format_modified_time
            self_dt = datetime.datetime.strptime(self.text(), "%Y-%m-%d %H:%M")
            other_dt = datetime.datetime.strptime(other.text(), "%Y-%m-%d %H:%M")
            return self_dt < other_dt
        except:
             return super().__lt__(other)

# --- Base Table Class ---

class BaseTable(QTableWidget):
    """
    A reusable base table widget with common styling, sorting,
    and optional column width persistence.

    Uses string identifiers in `column_types` for special handling:
    - 'filesize': Expects integer bytes, uses SizeAwareTableItem.
    - 'timestamp': Expects float timestamp, uses DateAwareTableItem.
    """
    # Constants
    USER_ROLE_DATA = Qt.ItemDataRole.UserRole # Role for storing arbitrary data (e.g., full path)

    def __init__(self, headers: List[str],
                 column_types: Optional[List[Union[type, str]]] = None, # Can mix types and string identifiers
                 table_name: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        """
        Initializes the BaseTable.

        Args:
            headers (List[str]): List of column header labels.
            column_types (Optional[List[Union[type, str]]], optional):
                List of expected data types or string identifiers ('filesize', 'timestamp')
                for columns. Used for creating appropriate QTableWidgetItems and sorting.
                Defaults to string type for all columns if None.
            table_name (Optional[str], optional): Name used for saving/loading column widths.
                                                  If None, persistence is disabled. Defaults to None.
            parent (Optional[QWidget], optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.headers = headers
        # Default to str type if column_types is None or too short
        self.column_types = column_types if column_types and len(column_types) == len(headers) else ([str] * len(headers))
        self.table_name = table_name
        self.setObjectName(table_name if table_name else "baseTableWidget")

        self.theme = ThemeManager.instance()
        self.settings = SettingsManager.instance()

        # Sorting state
        self.sort_column = 0 # Default to first column
        self.sort_order = Qt.SortOrder.AscendingOrder

        # Sort indicator icons
        self.sort_up_icon = qta.icon('fa5s.sort-up', color=self.theme.get_color('text', 'secondary'))
        self.sort_down_icon = qta.icon('fa5s.sort-down', color=self.theme.get_color('text', 'secondary'))

        self._setup_ui()
        self._connect_signals()

        if self.table_name:
            self._load_column_widths()
        else:
            # Apply some default width if not loading
             for i in range(self.columnCount()):
                 self.setColumnWidth(i, 150)


        self._update_sort_indicators()

    def _setup_ui(self):
        """Configure the basic appearance and behavior of the table."""
        self.setColumnCount(len(self.headers))
        self.setHorizontalHeaderLabels(self.headers)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Don't stretch last section by default, allow specific columns to be stretched if needed by subclasses
        # self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.setSortingEnabled(False)  # Disable Qt's automatic sorting
        self.setShowGrid(False)

        # Set default row height
        self.verticalHeader().setDefaultSectionSize(22) # Match existing style

        # Style the table
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.theme.get_color('background', 'primary')}; /* Base background */
                alternate-background-color: {self.theme.get_color('background', 'alternate_row')};
                border: 1px solid {self.theme.get_color('border', 'primary')}; /* Primary border */
                border-radius: 4px;
                /* padding: 5px; */ /* Remove padding to align items better */
                selection-background-color: {self.theme.get_color('background', 'selected_row')};
                selection-color: {self.theme.get_color('text', 'primary')};
                gridline-color: transparent; /* Ensure grid lines are hidden */
            }}
            QTableWidget::item {{
                padding: 0px 8px; /* Match playlist_playmode padding */
                height: 22px;
                min-height: 22px;
                border-bottom: 1px solid {self.theme.get_color('border', 'secondary')}; /* Subtle row separator */
                border-right: none;
                border-left: none;
                border-top: none;
                 color: {self.theme.get_color('text', 'primary')}; /* Default text color */
            }}
            QTableWidget::item:selected {{
                background-color: {self.theme.get_color('background', 'selected_row')};
                color: {self.theme.get_color('text', 'selected_row')}; /* Text color for selected row */
                border-radius: 0px;
                border: none;
                border-bottom: 1px solid {self.theme.get_color('border', 'selected_row')}; /* Separator for selected */
            }}
            QHeaderView::section {{
                background-color: {self.theme.get_color('background', 'tertiary')};
                color: {self.theme.get_color('text', 'secondary')};
                padding: 0px 8px; /* Match item padding */
                height: 24px; /* Slightly taller header */
                border: none;
                border-bottom: 1px solid {self.theme.get_color('border', 'secondary')};
                border-right: 1px solid {self.theme.get_color('border', 'secondary')};
            }}
            QHeaderView::section:last {{
                 border-right: none; /* No border on the far right */
            }}
            QHeaderView::section:hover {{
                background-color: {self.theme.get_color('background', 'quaternary')};
            }}
        """)

    def _connect_signals(self):
        """Connect signals for sorting and resizing."""
        self.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        if self.table_name:
            self.horizontalHeader().sectionResized.connect(self._on_column_resized)

    def _on_header_clicked(self, column_index):
        """Handle column header clicks for sorting."""
        if self.sort_column == column_index:
            new_order = Qt.SortOrder.DescendingOrder if self.sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.sort_order = new_order
        else:
            self.sort_column = column_index
            self.sort_order = Qt.SortOrder.AscendingOrder

        self._update_sort_indicators()
        # Trigger the manual sort using Qt's mechanism but with our custom items
        self.sortItems(column_index, self.sort_order)

        # Ensure row heights are maintained after sorting (might be redundant if setItem handles it)
        # for row in range(self.rowCount()):
        #     self.setRowHeight(row, 22)

    def _update_sort_indicators(self):
        """Update the sort indicators in headers."""
        header = self.horizontalHeader()
        for col in range(header.count()):
            # Ensure header item exists before trying to set icon
            header_item = self.horizontalHeaderItem(col)
            if not header_item:
                 # Create a default item if none exists (can happen initially)
                 header_item = QTableWidgetItem(self.headers[col])
                 self.setHorizontalHeaderItem(col, header_item)
            header_item.setIcon(QIcon()) # Clear previous icon

        # Set icon on the current sort column
        header_item = self.horizontalHeaderItem(self.sort_column)
        if header_item: # Check again after potential creation
            icon = self.sort_up_icon if self.sort_order == Qt.SortOrder.AscendingOrder else self.sort_down_icon
            header_item.setIcon(icon)

    def _on_column_resized(self, column_index, old_width, new_width):
        """Save column widths when resized (if table_name is set)."""
        # Only save if the table name is defined
        if self.table_name:
            self._save_column_widths()

    def _get_column_widths_setting_key(self) -> str:
        """Constructs the key for storing column widths in settings."""
        # Ensure table_name is valid for use in a key
        safe_table_name = ''.join(c if c.isalnum() else '_' for c in self.table_name)
        return f'ui/tables/{safe_table_name}/column_widths'

    def _save_column_widths(self):
        """Save current column widths to settings."""
        if not self.table_name:
            return

        column_widths = {
            # Use header text as part of the key for slightly more robustness if columns reorder?
            # Or stick to index based key f'col_{i}'
            f'col_{i}': self.columnWidth(i) for i in range(self.columnCount())
        }
        key = self._get_column_widths_setting_key()
        self.settings.set(key, column_widths, SettingType.DICT)
        # print(f"[BaseTable] Saved column widths for '{self.table_name}': {column_widths}") # Debug

    def _load_column_widths(self):
        """Load column widths from settings."""
        if not self.table_name:
            return

        key = self._get_column_widths_setting_key()
        # Define reasonable default widths if nothing is saved
        default_widths = {f'col_{i}': 150 for i in range(self.columnCount())}
        # Try loading from settings, falling back to defaults
        column_widths = self.settings.get(key, default_widths, SettingType.DICT)

        # print(f"[BaseTable] Loading column widths for '{self.table_name}': {column_widths}") # Debug

        # Apply loaded/default widths
        for i in range(self.columnCount()):
            col_key = f'col_{i}'
            # Get width for this column key, fall back to default if key missing
            width = column_widths.get(col_key, default_widths.get(col_key, 150))
            self.setColumnWidth(i, width)

    # --- Data Population Methods ---

    def clear_table(self):
        """Removes all rows from the table."""
        # self.setRowCount(0) # Efficient way to clear
        # More thorough clear if needed:
        while self.rowCount() > 0:
            self.removeRow(0)


    def add_row(self, row_data: List[Any], user_data: Optional[Any] = None):
        """
        Adds a single row to the table, creating appropriate items based on column_types.

        Args:
            row_data (List[Any]): List of data for each cell in the row.
            user_data (Optional[Any], optional): Optional data to store with the
                                                first column item using USER_ROLE_DATA.
                                                Defaults to None.
        """
        if len(row_data) != self.columnCount():
            print(f"[BaseTable] Warning: Row data length ({len(row_data)}) != column count ({self.columnCount()}). Skipping row.")
            return

        row_position = self.rowCount()
        self.insertRow(row_position)
        self.setRowHeight(row_position, 22) # Ensure consistent row height

        for col_index, cell_data in enumerate(row_data):
            # Determine the type hint for this column
            col_type_hint = self.column_types[col_index] if col_index < len(self.column_types) else str
            # Create the appropriate item
            item = self._create_item(cell_data, col_type_hint)

            # Store user data in the first column's item if provided
            if col_index == 0 and user_data is not None:
                item.setData(self.USER_ROLE_DATA, user_data)
                # Add tooltip if user_data looks like a path/string
                if isinstance(user_data, (str, Path)):
                    item.setToolTip(str(user_data))

            # Set the item in the table
            self.setItem(row_position, col_index, item)

    def set_table_data(self, data: List[List[Any]], user_data_list: Optional[List[Any]] = None):
        """
        Clears the table and populates it with new data efficiently.

        Args:
            data (List[List[Any]]): A list of rows, where each row is a list of cell data.
            user_data_list (Optional[List[Any]], optional): Optional list of user data
                                                            to associate with each row (stored
                                                            in the first column's item). Length must
                                                            match the number of rows in `data`.
                                                            Defaults to None.
        """
        self.clear_table()
        self.setUpdatesEnabled(False) # Optimize bulk update performance
        try:
            for i, row_data in enumerate(data):
                # Get corresponding user data if available
                user_data = user_data_list[i] if user_data_list and i < len(user_data_list) else None
                # Add the row using the helper method
                self.add_row(row_data, user_data=user_data)
        finally:
            self.setUpdatesEnabled(True) # Re-enable updates to show changes

        # Apply initial sort after setting data, if needed
        if self.rowCount() > 0:
            self.sortItems(self.sort_column, self.sort_order)
        self._update_sort_indicators() # Ensure indicator matches initial sort

    def _create_item(self, data: Any, item_type_hint: Union[type, str]) -> QTableWidgetItem:
        """
        Internal helper to create the appropriate QTableWidgetItem based on data
        and the type hint provided in `column_types`.
        """
        # Handle special string identifiers first
        if item_type_hint == 'filesize':
            try:
                size_bytes = int(data)
                return SizeAwareTableItem(format_file_size(size_bytes), size_bytes)
            except (ValueError, TypeError, AttributeError):
                 return QTableWidgetItem("Invalid Size") # Fallback for invalid size data
        elif item_type_hint == 'timestamp':
            try:
                timestamp = float(data)
                return DateAwareTableItem(format_modified_time(timestamp), timestamp)
            except (ValueError, TypeError, AttributeError):
                return QTableWidgetItem("Invalid Date") # Fallback for invalid timestamp data

        # Handle standard Python types if hint is a type object
        elif isinstance(item_type_hint, type):
            if item_type_hint == int:
                # Standard QTableWidgetItem sorts numerically if data is numeric
                item = QTableWidgetItem()
                try:
                    item.setData(Qt.ItemDataRole.EditRole, int(data))
                except (ValueError, TypeError):
                     item.setData(Qt.ItemDataRole.EditRole, str(data)) # Fallback to string
                return item
            elif item_type_hint == float:
                 item = QTableWidgetItem()
                 try:
                    item.setData(Qt.ItemDataRole.EditRole, float(data))
                 except (ValueError, TypeError):
                     item.setData(Qt.ItemDataRole.EditRole, str(data)) # Fallback to string
                 return item
                 # return QTableWidgetItem(f"{data:.2f}") # Example formatting if needed
            elif item_type_hint == bool:
                 # Represent bools clearly
                 return QTableWidgetItem("Yes" if bool(data) else "No")
            elif item_type_hint == datetime.datetime:
                 try:
                     # Format datetime objects consistently
                     return QTableWidgetItem(data.strftime("%Y-%m-%d %H:%M"))
                 except AttributeError: # Handle case where data isn't a datetime object
                     return QTableWidgetItem(str(data))

        # Default to string conversion for any other type or if hint wasn't a type
        return QTableWidgetItem(str(data))

    def get_row_user_data(self, row: int) -> Optional[Any]:
        """Retrieves the user data stored in the first column of the specified row."""
        if 0 <= row < self.rowCount():
            item = self.item(row, 0) # Assume user data is in the first column
            if item:
                return item.data(self.USER_ROLE_DATA)
        return None

    def get_selected_rows_user_data(self) -> List[Any]:
        """Returns a list of user data for all currently selected rows."""
        selected_data = []
        # Use selectedIndexes() which gives items across all columns for selected rows
        # Use a set to get unique row numbers efficiently
        selected_rows = set(index.row() for index in self.selectedIndexes())
        for row in sorted(list(selected_rows)):
            user_data = self.get_row_user_data(row)
            if user_data is not None: # Optionally filter out rows without user data
                 selected_data.append(user_data)
        return selected_data 