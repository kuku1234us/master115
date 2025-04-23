from PyQt6.QtCore import pyqtSignal, QObject, QThread # Added QtCore imports
from PyQt6.QtWidgets import QApplication # Added QApplication import

from qt_base_app.window import BaseWindow
from qt_base_app.models import Logger, SettingsManager # Import SettingsManager
from .pages.home_page.home_page import HomePage
from .pages import SearchPage, PreferencesPage # Other pages remain the same
from .pages.pixnova_page import PixnovaPage # Import the new page
# --- Import new AI pages ---
from .pages.face_dashboard_page import FaceDashboardPage
from .pages.face_review_page import FaceReviewPage
# ---------------------------

# --- Import Browser ---
from master115.models.chrome115_browser import Chrome115Browser
# --- REMOVE Worker import from HomePage --- #
# from master115.ui.pages.home_page.home_page import BrowserWorker
from typing import Optional # For type hinting
# ---------------------------------

# --- Define BrowserWorker Class Directly Here --- #
class BrowserWorker(QObject):
    """Worker to handle browser start in a separate thread."""
    started = pyqtSignal(bool) # Signal with success status
    error = pyqtSignal(str)   # Optional: Signal for specific errors

    def __init__(self, browser_instance):
        super().__init__()
        self.browser = browser_instance
        self._is_cancelled = False

    def run(self):
        """Runs the browser start process."""
        if self._is_cancelled:
            self.started.emit(False)
            return
        try:
            # Make sure Logger is accessible if needed inside thread
            logger = Logger.instance() # Get instance inside run method
            success = self.browser.start()
            if self._is_cancelled:
                 logger.info("BrowserWorker", "Cancellation detected after start attempt, quitting.")
                 if self.browser.is_running(): self.browser.quit()
                 success = False
            self.started.emit(success)
        except Exception as e:
             try: logger.error("BrowserWorker", f"Exception during browser start: {e}", exc_info=True)
             except: print(f"Worker Error: {e}")
             self.error.emit(str(e))
             self.started.emit(False)

    def cancel(self):
         """Flags the worker to cancel the operation."""
         self._is_cancelled = True
# ----------------------------------------------- #

class MainWindow(BaseWindow):
    # --- Signals for browser state ---
    browserStarted = pyqtSignal(object) # Emits the browser instance on success
    browserStopped = pyqtSignal()       # Emitted when browser stops or fails to start
    # ---------------------------------

    def __init__(self, config_path: str, **kwargs):
        # --- Browser Management Attributes (Define BEFORE super init) ---
        self.browser = Chrome115Browser.instance() # Hold the singleton instance
        self.worker_thread: Optional[QThread] = None
        self.browser_worker: Optional[BrowserWorker] = None
        self.is_starting: bool = False # Flag to track browser startup
        # -------------------------------------------------------------

        # BaseWindow loads the config, sets up logger based on it
        super().__init__(config_path=config_path, **kwargs)

        # Logger is now configured, we can use it
        self.logger = Logger.instance()
        self.logger.info("main_window", f"Main window initialized with config: {config_path}")
        self.logger.info("main_window", f"Browser instance obtained: {self.browser}")

        # --- Application-specific setup --- #
        self.initialize_pages()
        self.logger.info("main_window", "Application pages initialized.")

        # Get the SettingsManager singleton instance
        settings_manager = SettingsManager.instance()

        # Show the initial page specified in config or a default
        # Use the settings_manager instance to get persistent settings
        initial_page = settings_manager.get('window/initial_page', 'home')
        self.show_page(initial_page)


    def initialize_pages(self):
        """Create instances of all pages and add them to the content stack."""
        # Instantiate pages
        home_widget = HomePage(self)       # Pass self as parent
        search_widget = SearchPage(self)
        prefs_widget = PreferencesPage(self)
        pixnova_widget = PixnovaPage(self) # Instantiate PixnovaPage
        # --- Instantiate AI pages ---
        face_dashboard_widget = FaceDashboardPage(self)
        face_review_widget = FaceReviewPage(self)
        # ----------------------------

        # Add pages to the stack using the IDs from the YAML config
        self.add_page('home', home_widget)
        self.add_page('search', search_widget)
        self.add_page('preferences', prefs_widget)
        self.add_page('pixnova', pixnova_widget) # Add PixnovaPage with its ID
        # --- Add AI pages ---
        self.add_page('face_dashboard', face_dashboard_widget)
        self.add_page('face_review', face_review_widget)
        # ---------------------

    # --- Browser Control Methods --- #

    def start_browser(self):
        """Initiates the browser start process in a background thread."""
        if self.browser.is_running() or self.is_starting:
            self.logger.warn("main_window", "Start Browser requested, but already running or starting.")
            return

        self.is_starting = True
        self.update_global_button_states() # Method to potentially update all relevant pages
        QApplication.processEvents()

        self.worker_thread = QThread()
        # Pass the browser instance managed by MainWindow
        self.browser_worker = BrowserWorker(self.browser)
        self.browser_worker.moveToThread(self.worker_thread)

        # Connect signals
        self.browser_worker.started.connect(self._on_browser_started)
        self.browser_worker.error.connect(self._on_browser_start_error)
        self.worker_thread.started.connect(self.browser_worker.run)
        self.worker_thread.finished.connect(self._on_worker_finished)

        self.logger.info("main_window", "Starting browser worker thread...")
        self.worker_thread.start()

    def stop_browser_start(self):
        """Attempts to cancel the browser startup process."""
        if not self.is_starting or not self.browser_worker:
            self.logger.warn("main_window", "Stop start requested, but not in starting state or worker missing.")
            self.is_starting = False # Reset flag
            self.update_global_button_states()
            return

        self.logger.info("main_window", "Cancellation requested for browser startup.")
        self.browser_worker.cancel()
        # Actual stop/quit and signal emission happens in worker or _on_browser_started

    def quit_browser(self):
        """Quits the Selenium-controlled browser."""
        if not self.browser.is_running() and not self.is_starting:
             self.logger.info("main_window", "Quit browser requested, but already stopped.")
             return # Nothing to do

        if self.is_starting:
             self.logger.info("main_window", "Quit requested during startup. Attempting cancellation.")
             self.stop_browser_start()
             # We expect the worker/slots to handle the actual quit and signal emission
             return

        self.logger.info("main_window", "Quitting browser...")
        # --- Ensure quit only happens if running ---
        if self.browser.is_running():
            self.browser.quit()
            self.logger.info("main_window", "Browser quit completed.")
            self.browserStopped.emit() # Emit signal ONLY if it was running
        else:
             self.logger.info("main_window", "Quit browser called, but browser was not running.")
        # -------------------------------------------
        # Always update UI state after quit attempt
        self.update_global_button_states() # Update UI

    # --- Slots for Worker Signals --- #
    def _on_browser_started(self, success):
        """Slot called when the BrowserWorker finishes the start attempt."""
        self.logger.info("main_window", f"Browser start attempt finished. Success: {success}")
        # Capture the state *before* resetting is_starting
        was_cancelled = self.browser_worker._is_cancelled if self.browser_worker else False
        self.is_starting = False # Done starting

        if success:
            self.browserStarted.emit(self.browser) # Emit signal with instance
        else:
            # Ensure browser is actually quit if start failed or was cancelled
            if self.browser.is_running(): self.browser.quit()
            # Emit stopped only if it wasn't a manual cancellation causing the 'failure'
            # Or emit always? Let's emit always for simplicity, PixnovaPage handles None browser.
            self.browserStopped.emit() # Emit stopped signal on failure/cancellation

        self.update_global_button_states() # Update UI

        # Trigger thread cleanup (it might still be running briefly)
        if self.worker_thread and self.worker_thread.isRunning():
             self.worker_thread.quit()
             self.worker_thread.wait(1000)

    def _on_browser_start_error(self, error_message):
         """Slot called if the worker emits an error signal."""
         self.logger.error("main_window", f"Browser start worker reported error: {error_message}")
         self.is_starting = False
         self.browserStopped.emit() # Emit stopped signal on error
         self.update_global_button_states()
         # Trigger thread cleanup
         if self.worker_thread and self.worker_thread.isRunning():
              self.worker_thread.quit()
              self.worker_thread.wait(1000)

    def _on_worker_finished(self):
        """Slot called when the worker thread finishes execution."""
        self.logger.debug("main_window", "Browser worker thread finished.")
        # Ensure is_starting is False if thread finishes unexpectedly
        # This might happen if the thread crashes before emitting 'started'
        if self.is_starting:
             self.logger.warn("main_window", "Worker finished but starting flag still true. Resetting state.")
             self.is_starting = False
             # Assume failure if it finished without emitting started(True)
             if not self.browser.is_running():
                  self.browserStopped.emit()
             self.update_global_button_states()

        self.browser_worker = None
        if self.worker_thread:
            # Ensure the thread is properly finished before deleting
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(500) # Brief wait
            self.worker_thread.deleteLater() # Schedule for safe deletion
            self.worker_thread = None

    def update_global_button_states(self):
        """Notify relevant pages to update their UI based on browser state."""
        # This method now primarily tells HomePage to update its UI
        # based on the state managed here in MainWindow.

        # Find HomePage instance within the content stack (assuming self.content_stack)
        home_page_widget: Optional[HomePage] = None
        if hasattr(self, 'content_stack') and self.content_stack is not None:
            for i in range(self.content_stack.count()):
                widget = self.content_stack.widget(i)
                if isinstance(widget, HomePage):
                    home_page_widget = widget
                    break # Found it
        else:
            self.logger.error("main_window", "Cannot find content_stack attribute in MainWindow to update HomePage state.")
            return # Cannot proceed

        # If found, update its state
        if home_page_widget:
             is_running = self.browser.is_running()
             home_page_widget._update_button_states(self.is_starting, is_running)
        else:
            self.logger.warn("main_window", "HomePage instance not found in content_stack during update.")

        # PixnovaPage updates via its own connected slots, no direct call needed.


    def closeEvent(self, event):
        """Ensure browser is quit when the main window closes."""
        self.logger.info("main_window", "Main window closing, ensuring browser is quit.")
        # Prevent race conditions if closing happens during startup cancellation
        if self.is_starting and self.browser_worker:
            self.browser_worker.cancel()
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.wait(1000) # Wait a bit longer for cancellation
        self.quit_browser() # Attempt to quit gracefully
        super().closeEvent(event)

    # Add other application-specific methods below if needed
    # def custom_method(self):
    #     pass 