import qtawesome
from enum import Enum, auto

from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import pyqtSignal, QSize

# Framework imports (assuming Logger, ThemeManager might be used for styling later)
# from qt_base_app.theme import ThemeManager
# from qt_base_app.models import Logger

class BrowserButtonState(Enum):
    """Defines the possible states for the BrowserButton."""
    IDLE = auto()      # Browser not running, ready to start
    STARTING = auto()  # Browser start initiated, can be cancelled
    RUNNING = auto()   # Browser is running, can be quit

class BrowserButton(QPushButton):
    """
    A QPushButton managing browser start, cancel, and quit actions.

    Emits signals based on its current state when clicked:
    - start_requested: Emitted when clicked in IDLE state.
    - cancel_requested: Emitted when clicked in STARTING state.
    - quit_requested: Emitted when clicked in RUNNING state.
    """
    start_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    # Icons for different states
    ICON_START = "fa5s.play-circle"
    ICON_CANCEL = "fa5s.stop-circle" # Using stop for cancel
    # ICON_WAITING = "fa5s.spinner" # Spinner might require animation handling
    ICON_QUIT = "fa5s.power-off"

    # Text for different states
    TEXT_START = "Start Browser"
    TEXT_CANCEL = "Cancel Startup"
    TEXT_QUIT = "Quit Browser"

    # Tooltips
    TOOLTIP_START = "Start the 115chrome browser"
    TOOLTIP_CANCEL = "Cancel the browser startup process"
    TOOLTIP_QUIT = "Quit the 115chrome browser and WebDriver"

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.theme = ThemeManager.instance() # Optional for styling
        # self.logger = Logger.instance()     # Optional for logging within button

        self._state: BrowserButtonState = BrowserButtonState.IDLE
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed) # Standard button height
        self.setIconSize(QSize(16, 16)) # Adjust icon size as needed

        self.clicked.connect(self._on_click)
        self.set_state(BrowserButtonState.IDLE) # Set initial appearance

    def set_state(self, new_state: BrowserButtonState):
        """
        Sets the button's visual state and behavior.

        Args:
            new_state: The BrowserButtonState to transition to.
        """
        self._state = new_state
        self._update_appearance()

    def get_state(self) -> BrowserButtonState:
         """Returns the current state of the button."""
         return self._state

    def _update_appearance(self):
        """Updates the button's text, icon, and tooltip based on the current state."""
        if self._state == BrowserButtonState.IDLE:
            self.setText(self.TEXT_START)
            self.setIcon(qtawesome.icon(self.ICON_START))
            self.setToolTip(self.TOOLTIP_START)
            self.setEnabled(True)
            self.setDown(False) # Ensure button is not visually stuck down
        elif self._state == BrowserButtonState.STARTING:
            self.setText(self.TEXT_CANCEL)
            self.setIcon(qtawesome.icon(self.ICON_CANCEL)) # Use stop icon for cancel
            self.setToolTip(self.TOOLTIP_CANCEL)
            self.setEnabled(True)
            # Consider visual indication like setDown(True) or style change?
            self.setDown(True) # Make it look pressed while waiting
        elif self._state == BrowserButtonState.RUNNING:
            self.setText(self.TEXT_QUIT)
            self.setIcon(qtawesome.icon(self.ICON_QUIT))
            self.setToolTip(self.TOOLTIP_QUIT)
            self.setEnabled(True)
            self.setDown(False) # Ensure button is not visually stuck down

    def _on_click(self):
        """Handles the button click and emits the appropriate signal."""
        # self.logger.debug(f"BrowserButton clicked in state: {self._state}")
        if self._state == BrowserButtonState.IDLE:
            # Important: We don't change state here directly.
            # The controlling widget (HomePage) will change our state
            # AFTER it successfully initiates the start process.
            self.start_requested.emit()
        elif self._state == BrowserButtonState.STARTING:
            # The controlling widget will change state upon receiving this signal
            # or when the process is actually cancelled/finished.
            self.cancel_requested.emit()
        elif self._state == BrowserButtonState.RUNNING:
            # The controlling widget will change state AFTER quitting.
            self.quit_requested.emit()
