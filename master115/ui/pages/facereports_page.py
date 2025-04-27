from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from qt_base_app.models import Logger
# Import the new report component
from ..faceswap_components.face_usage_report import FaceUsageReport

class FaceReportsPage(QWidget):
    """Container page for displaying face swap related reports using tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FaceReportsPage")
        self.logger = Logger.instance()
        self.caller = "FaceReportsPage"
        
        # Make background transparent
        self.setAutoFillBackground(True)
        self.setStyleSheet("QWidget#FaceReportsPage { background-color: transparent; }")

        self._setup_ui()
        # Add the initial tabs now that the component exists
        self._add_initial_tabs()

    def _setup_ui(self):
        """Set up the main tab widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Use full page area

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("ReportsTabWidget")
        # Make tab widget background transparent too
        # Ensure the panes *within* the tabs have their own backgrounds later.
        self.tab_widget.setStyleSheet("QTabWidget#ReportsTabWidget::pane { border: none; background-color: transparent; } QTabWidget { background-color: transparent; }")

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def _add_initial_tabs(self):
        """Create and add the initial report tabs."""
        try:
            # Import and create FaceUsageReport
            face_usage_widget = FaceUsageReport(self) # Pass self as parent
            self.tab_widget.addTab(face_usage_widget, "Face Usage")
            self.logger.info(self.caller, "Added 'Face Usage' report tab.")
        # except ImportError: # No longer needed as import is at top
        #     self.logger.error(self.caller, "FaceUsageReport component not found yet.")
        except Exception as e:
            self.logger.error(self.caller, f"Error adding initial tabs: {e}", exc_info=True) 