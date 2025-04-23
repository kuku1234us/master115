# ./master115/ui/faceswap_components/review_queue_item.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap

from qt_base_app.models import Logger

class ReviewQueueItem(QWidget):
    """
    Represents a single item in the review queue, displaying a thumbnail.
    Designed to be used as a custom widget within a QListWidget.
    """
    def __init__(self, person_name: str, source_filename: str, result_files: list[str], parent=None):
        """
        Initialize the item.

        Args:
            person_name (str): The name of the person whose face was swapped.
            source_filename (str): The filename of the original source image.
            result_files (list[str]): List of paths to the generated result images in Temp/.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setObjectName("ReviewQueueItem")
        self.logger = Logger.instance()
        self.caller = "ReviewQueueItem"

        self.person_name = person_name
        self.source_filename = source_filename
        self.result_files = result_files # Store the list of files

        self._setup_ui()
        self._load_thumbnail() # Load thumbnail on init

    def _setup_ui(self):
        """Set up the UI elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # Small margins
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Thumbnail Label
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_size = QSize(100, 100) # Target size for thumbnail
        self.thumbnail_label.setFixedSize(self.thumbnail_size)
        self.thumbnail_label.setObjectName("ThumbnailLabel")
        # Placeholder styling
        self.thumbnail_label.setStyleSheet(f"""
            #ThumbnailLabel {{
                background-color: #555555; /* Dark grey placeholder */
                border: 1px solid #777777;
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.thumbnail_label)

        # Optional: Add text labels later if needed
        # self.person_label = QLabel(self.person_name)
        # self.source_label = QLabel(self.source_filename)
        # layout.addWidget(self.person_label)
        # layout.addWidget(self.source_label)

        self.setLayout(layout)
        # Adjust widget size hint to fit content
        self.adjustSize()

    def _load_thumbnail(self):
        """Loads the thumbnail from the first result file."""
        if not self.result_files:
            self.logger.warn(self.caller, f"No result files provided for {self.person_name}/{self.source_filename}")
            self.thumbnail_label.setText("?")
            return

        first_file = self.result_files[0]
        pixmap = QPixmap(first_file)

        if pixmap.isNull():
            self.logger.warn(self.caller, f"Failed to load thumbnail: {first_file}")
            self.thumbnail_label.setText("ERR")
            self.thumbnail_label.setStyleSheet(f"""
                #ThumbnailLabel {{
                    background-color: #8B0000; /* Dark red error */
                    color: white;
                    border: 1px solid #777777;
                    border-radius: 4px;
                    font-weight: bold;
                }}
            """)
            return

        # Scale the pixmap
        scaled_pixmap = pixmap.scaled(
            self.thumbnail_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.thumbnail_label.setPixmap(scaled_pixmap)
        # Clear background/border styles to show pixmap
        self.thumbnail_label.setStyleSheet("border: none; background-color: transparent;")
        self.thumbnail_label.setText("") # Clear placeholder/error text

    # --- Getters ---
    def get_person_name(self) -> str:
        return self.person_name

    def get_source_filename(self) -> str:
        return self.source_filename

    def get_result_files(self) -> list[str]:
        return self.result_files 