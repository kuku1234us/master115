# master115/ui/pages/pixnova_page.py

import os # Import os for path validation
import time
from pathlib import Path # Import Path for type hints if needed
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication # Import QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, pyqtSlot, QByteArray
from selenium.webdriver.common.by import By # Import By for selectors
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests # <--- Add requests import
from PyQt6.QtGui import QPixmap
# --- Pillow Imports --- #
import io
from PIL import Image
# -------------------- #

from qt_base_app.models import Logger
from qt_base_app.theme import ThemeManager
from master115.models.chrome_tab import ChromeTab
from master115.models.chrome115_browser import Chrome115Browser
# --- Import Optional for type hinting ---
from typing import Optional
# -------------------------------------

# === Worker Class for Face Swap Workflow ===
class FaceSwapWorker(QObject):
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    thumbnailReady = pyqtSignal(QByteArray) # New signal for the result image URL
    finished = pyqtSignal(bool, str, str)

    SOURCE_IMAGE_PATH = r"D:\sourceimage.jpg"
    FACE_IMAGE_PATH   = r"D:\face01.jpg"

    # XPaths
    SOURCE_INPUT_XPATH = "//div[@id='sourceImage']//input[@type='file']"
    SOURCE_BUTTON_LOADING_XPATH = "//div[@id='sourceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    FACE_INPUT_XPATH = "//div[@id='faceImage']//input[@type='file']"
    FACE_BUTTON_LOADING_XPATH = "//div[@id='faceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    # -- XPath targeting the button element within pane-1 (for clickability check) --
    START_SWAP_BUTTON_XPATH = (
        "//div[@id='pane-1']"  # Stay inside the Photo-swap pane
        "//button[.//span[normalize-space()='Start face swapping']]" # Match exact text
    )
    PROGRESS_BAR_CONTAINER_XPATH = "//div[contains(@class, 'operate-container')]//div[contains(@class, 'loading-container')]"
    # --- Result XPaths --- #
    RESULT_IMAGE_XPATH = "//div[contains(@class, 'result-container')]//img[contains(@class, 'el-image__inner') and @src]"
    # --- Download Button XPath (for potential future use/inspection) --- #
    DOWNLOAD_BUTTON_XPATH = "//div[contains(@class, 'result-container')]//button[.//i[contains(@class, 'bi-download')]]"
    # ------------------------------------------------------------------ #

    def __init__(self, tab: ChromeTab, logger: Logger):
        super().__init__()
        self.tab = tab
        self.logger = logger
        self.caller = "FaceSwapWorker"
        self._is_cancelled = False # Add cancellation flag if needed later

    def _wait_for_upload(self, input_xpath: str, file_path: str, spinner_xpath: str) -> bool:
        """Handles uploading a file and waiting for spinner completion."""
        try:
            self.progress.emit(f"Finding input for {Path(file_path).name}...")
            upload_input = self.tab.find_element(By.XPATH, input_xpath, wait_time=10)
            if not upload_input:
                self.error.emit(f"Cannot find upload input: {input_xpath}")
                return False

            self.progress.emit(f"Uploading {Path(file_path).name}...")
            upload_input.send_keys(file_path)
            time.sleep(0.5) # Brief pause after send_keys

            self.progress.emit("Waiting for upload to start (spinner appear)...")
            driver = self.tab._ensure_focus_and_get_driver()
            if not driver: raise Exception("WebDriver not available")
            try:
                # --- Reduced wait time for spinner APPEARANCE --- #
                WebDriverWait(driver, 2).until( # Reduced from 5s
                    EC.presence_of_element_located((By.XPATH, spinner_xpath))
                )
                self.logger.info(self.caller, f"Spinner appeared for {Path(file_path).name}.")
            except TimeoutException:
                 self.logger.warn(self.caller, f"Spinner appearance not detected quickly for {Path(file_path).name}. Continuing...")

            self.progress.emit("Waiting for upload to finish (spinner disappear)...")
            WebDriverWait(driver, 120).until(
                EC.invisibility_of_element_located((By.XPATH, spinner_xpath))
            )
            self.logger.info(self.caller, f"Spinner disappeared for {Path(file_path).name}.")
            self.progress.emit(f"Upload of {Path(file_path).name} complete.")
            return True

        except Exception as e:
            self.error.emit(f"Error during upload of {Path(file_path).name}: {e}")
            self.logger.error(self.caller, f"Upload error for {Path(file_path).name}: {e}", exc_info=True)
            return False

    def run(self):
        """Executes the full face swap workflow."""
        result_url: Optional[str] = None # Keep internal Optional for logic
        if not self.tab or not self.tab.browser.is_running():
            self.error.emit("Browser or Pixnova tab not available.")
            self.finished.emit(False, "Setup Error: Browser/Tab not ready.", "")
            return

        # Step 1: Upload Source Image
        if not self._wait_for_upload(self.SOURCE_INPUT_XPATH, self.SOURCE_IMAGE_PATH, self.SOURCE_BUTTON_LOADING_XPATH):
            self.finished.emit(False, "Source Upload Failed", "")
            return

        time.sleep(1) # Small pause between uploads

        # Step 2: Upload Face Image
        if not self._wait_for_upload(self.FACE_INPUT_XPATH, self.FACE_IMAGE_PATH, self.FACE_BUTTON_LOADING_XPATH):
            self.finished.emit(False, "Face Upload Failed", "")
            return

        # --- Removed extra sleep, wait below handles timing --- #
        # time.sleep(2.5) 

        # Step 3: Wait for Start Button in pane-1 to be Clickable, then Click
        try:
            # Use the XPath that just locates the button in the correct pane
            start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
            
            self.progress.emit("Waiting for 'Start' button in pane-1 to become clickable...")
            driver = self.tab._ensure_focus_and_get_driver()
            if not driver: raise Exception("WebDriver not available")

            # --- Wait specifically for the button in pane-1 to be CLICKABLE --- # 
            WebDriverWait(driver, 60).until( # Keep 60s timeout for server check robustness
                EC.element_to_be_clickable(start_button_locator)
            )
            self.logger.info(self.caller, "'Start face swapping' button in pane-1 is clickable.")
            # ------------------------------------------------------------------- #

            self.progress.emit("Clicking 'Start face swapping'...")
            # Click using the same locator
            if not self.tab.click(start_button_locator, wait_time=10): 
                 self.error.emit("Failed to click 'Start face swapping' button (was clickable, but click failed).")
                 self.finished.emit(False, "Start Click Failed", "")
                 return
            self.logger.info(self.caller, "Clicked 'Start face swapping' button.")
            self.progress.emit("Start button clicked.")
        except TimeoutException:
             self.error.emit("Timeout waiting for 'Start' button in pane-1 to become clickable.")
             self.logger.error(self.caller, "Timeout waiting for start button clickable state.")
             self.finished.emit(False, "Start Button Clickable Timeout", "")
             return
        except Exception as e:
            self.error.emit(f"Error finding/clicking start button: {e}")
            self.logger.error(self.caller, f"Start button error: {e}", exc_info=True)
            self.finished.emit(False, "Start Button Error", "")
            return

        # Step 4: Wait for Swap Processing (Progress Bar Appearance and Disappearance)
        try:
            self.progress.emit("Waiting for swap process to start (progress bar appear)...")
            driver = self.tab._ensure_focus_and_get_driver()
            if not driver: raise Exception("WebDriver not available")

            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH))
            )
            self.logger.info(self.caller, "Progress bar appeared.")
            self.progress.emit("Face swapping in progress (waiting for progress bar disappear)...")

            WebDriverWait(driver, 300).until( # Wait up to 5 minutes for swap to complete
                EC.invisibility_of_element_located((By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH))
            )
            self.logger.info(self.caller, "Progress bar disappeared.")
            self.progress.emit("Swap process likely complete.")

        except TimeoutException:
             self.error.emit("Timeout waiting for face swap progress bar.")
             self.logger.error(self.caller, "Face swap process timed out.")
             self.finished.emit(False, "Swap Timeout", "")
             return
        except Exception as e:
            self.error.emit(f"Error waiting for swap process: {e}")
            self.logger.error(self.caller, f"Swap wait error: {e}", exc_info=True)
            self.finished.emit(False, "Swap Wait Error", "")
            return

        # Step 5: Find Result Image, Fetch Data, and Emit
        image_data = QByteArray() # Initialize empty byte array
        try:
            self.progress.emit("Waiting for result image...")
            driver = self.tab._ensure_focus_and_get_driver()
            if not driver: raise Exception("WebDriver not available")

            result_image_locator = (By.XPATH, self.RESULT_IMAGE_XPATH)
            # --- Wait for VISIBILITY first --- #
            result_image_element = WebDriverWait(driver, 15).until(
                 EC.visibility_of_element_located(result_image_locator)
            )
            self.logger.info(self.caller, "Result image element is visible.")
            time.sleep(0.5) # Small pause for src attribute to stabilize?

            result_url = result_image_element.get_attribute('src')
            if result_url:
                 self.logger.info(self.caller, f"Found result image URL: {result_url}")
                 # --- Fetch the image data --- #
                 self.progress.emit(f"Fetching result image from {result_url[:50]}...")
                 try:
                     response = requests.get(result_url, timeout=15) # Increased timeout
                     response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                     image_data = QByteArray(response.content)
                     self.logger.info(self.caller, f"Successfully fetched {len(image_data)} bytes for result image.")
                 except requests.exceptions.RequestException as req_err:
                      self.logger.error(self.caller, f"Failed to fetch result image: {req_err}")
                      self.error.emit("Failed to download result image.") # Emit specific error
                 # -------------------------- #
            else:
                 self.logger.warn(self.caller, "Result image found but 'src' attribute is empty or missing.")
                 self.error.emit("Found result container but no image source URL.") # Emit specific error

        except TimeoutException:
             self.logger.warn(self.caller, "Timeout waiting for result image visibility.")
             self.error.emit("Result image did not appear.") # Emit specific error
             # Continue to finished signal, URL/data will be empty
        except Exception as e:
            self.logger.error(self.caller, f"Error getting result image: {e}", exc_info=True)
            self.error.emit("Error processing result image.") # Emit specific error
            # Continue to finished signal, URL/data will be empty

        # --- Emit image data (even if empty on error) --- #
        self.thumbnailReady.emit(image_data)

        # Step 6: Save Page Source for Inspection (after result is visible)
        source_save_path = None
        if result_url: # Only save if we at least found the result container area
            self.progress.emit("Saving page source for inspection...")
            try:
                source_save_path = self.tab.save_source(filename_prefix="pixnova_result_page")
                if source_save_path:
                     self.logger.info(self.caller, f"Saved post-result page source to {source_save_path}")
                else:
                     self.logger.warn(self.caller, "Attempted to save page source, but save_source returned None.")
            except Exception as e:
                self.logger.error(self.caller, f"Error saving page source: {e}", exc_info=True)

        # --- Determine final status and emit finished signal --- #
        # Pass original result_url (or "" if None/fetch failed) to finished signal
        final_url_to_emit = result_url if result_url is not None else ""
        # Determine success based on whether we got image data
        success = not image_data.isEmpty()
        final_message = "Face swap workflow completed."
        if success:
             final_message += " Result image fetched."
        else:
             final_message += " Could not fetch result image."

        self.finished.emit(success, final_message, final_url_to_emit)

class PixnovaPage(QWidget):
    """Page for interacting with the Pixnova AI face swap service."""

    PIXNOVA_URL = "https://pixnova.ai/ai-face-swap/#playground"
    # --- Define file paths as class attributes --- #
    SOURCE_IMAGE_PATH = r"D:\sourceimage.jpg"
    FACE_IMAGE_PATH   = r"D:\face01.jpg"
    # -------------------------------------------- #
    # BIG_IMAGE_PATH = r"D:\bigimage.jpg" # No longer needed for specific observe button

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PixnovaPage")
        self.theme = ThemeManager.instance()
        self.logger = Logger.instance()
        self.caller = "PixnovaPage"
        self.pixnova_tab: Optional[ChromeTab] = None
        self.browser: Optional[Chrome115Browser] = None
        # --- Worker Thread --- #
        self.worker_thread: Optional[QThread] = None
        self.face_swap_worker: Optional[FaceSwapWorker] = None
        # --- Store last image data for saving --- #
        self._last_image_data: Optional[QByteArray] = None
        # ---------------------------------------- #

        # --- Connect to MainWindow Signals ---
        main_window = parent
        if hasattr(main_window, 'browserStarted'):
            main_window.browserStarted.connect(self.on_browser_started)
            self.logger.debug(self.caller, "Connected to browserStarted signal.")
        else:
            self.logger.warn(self.caller, "Parent window missing 'browserStarted' signal.")

        if hasattr(main_window, 'browserStopped'):
            main_window.browserStopped.connect(self.on_browser_stopped)
            self.logger.debug(self.caller, "Connected to browserStopped signal.")
        else:
            self.logger.warn(self.caller, "Parent window missing 'browserStopped' signal.")
        # ------------------------------------

        self._setup_ui()

        # --- Set Initial State AFTER UI setup ---
        # Check initial state from parent (MainWindow)
        initial_browser_instance = None
        if hasattr(main_window, 'browser') and main_window.browser is not None:
            if hasattr(main_window.browser, 'is_running') and main_window.browser.is_running():
                 initial_browser_instance = main_window.browser

        if initial_browser_instance:
             self.on_browser_started(initial_browser_instance)
        else:
             self.on_browser_stopped() # Set initial disabled state
        # ---------------------------------------

    # --- Define state update method EARLY --- #
    def _update_test_button_state(self):
        """Enables/disables the Test FaceSwap button based on browser/file/worker state."""
        files_ok = os.path.exists(self.SOURCE_IMAGE_PATH) and os.path.exists(self.FACE_IMAGE_PATH)
        browser_ready = self.browser is not None and self.browser.is_running()
        worker_running = self.worker_thread is not None and self.worker_thread.isRunning()

        can_run_test = browser_ready and files_ok and not worker_running

        # Ensure button exists before setting state (in case called before _setup_ui finishes)
        if hasattr(self, 'test_faceswap_button'):
            self.test_faceswap_button.setEnabled(can_run_test)

            # Update tooltip based on primary reason for being disabled
            if not files_ok:
                self.test_faceswap_button.setToolTip(f"Required file(s) not found.")
            elif not browser_ready:
                 self.test_faceswap_button.setToolTip("Browser is not running.")
            elif worker_running:
                 self.test_faceswap_button.setToolTip("Test already in progress...")
            else:
                 self.test_faceswap_button.setToolTip(f"Uploads source/face images and starts swap.")
    # ---------------------------------------- #

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.info_label = QLabel("Use this page to automate Pixnova AI face swap.")
        main_layout.addWidget(self.info_label)

        self.open_button = QPushButton("Open Pixnova Face Swap Page")
        self.open_button.setToolTip(f"Opens a new tab to {self.PIXNOVA_URL}")
        main_layout.addWidget(self.open_button)

        # --- Add Test FaceSwap Button --- #
        self.test_faceswap_button = QPushButton("Test FaceSwap")
        self.test_faceswap_button.setToolTip(f"Uploads source/face images and starts swap.")
        # Check if files exist
        files_ok = os.path.exists(self.SOURCE_IMAGE_PATH) and os.path.exists(self.FACE_IMAGE_PATH)
        if not files_ok:
             self.test_faceswap_button.setDisabled(True)
             self.test_faceswap_button.setToolTip(f"Required file(s) not found (source: {self.SOURCE_IMAGE_PATH}, face: {self.FACE_IMAGE_PATH})")
        main_layout.addWidget(self.test_faceswap_button)
        # --------------------------------- #

        # --- Add Status Label --- #
        self.status_label = QLabel("Status: Idle")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        # ------------------------ #

        # --- Add Result Image Label (Initially Hidden) --- #
        self.result_image_label = QLabel("") # Placeholder text removed
        self.result_image_label.setObjectName("ResultImageLabel")
        self.result_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_image_label.setMinimumSize(200, 200) # Give it a default size
        self.result_image_label.setStyleSheet("QLabel#ResultImageLabel { border: 1px solid gray; background-color: #f0f0f0; }") # Basic styling
        self.result_image_label.hide()
        main_layout.addWidget(self.result_image_label)
        # ----------------------------------------------- #

        # --- Add Result URL Label (Initially Hidden, Fallback) --- #
        self.result_url_label = QLabel("")
        self.result_url_label.setWordWrap(True)
        self.result_url_label.setObjectName("ResultUrlLabel")
        self.result_url_label.hide()
        main_layout.addWidget(self.result_url_label)
        # --------------------------------------------- #

        main_layout.addStretch()
        self.setLayout(main_layout)

        # Apply theme background
        bg_color = self.theme.get_color('background', 'content')
        self.setStyleSheet(f"QWidget#PixnovaPage {{ background-color: {bg_color}; }}")

        # --- Connections ---
        self.open_button.clicked.connect(self._open_pixnova_tab)
        self.test_faceswap_button.clicked.connect(self._run_face_swap_test) # Connect new button
        # --------------------------

    def _open_pixnova_tab(self):
        """Opens the Pixnova URL in a new browser tab."""
        if not self.browser or not self.browser.is_running():
            self.logger.error(self.caller, "Open Pixnova clicked, but browser is not available/running.")
            return

        self.logger.info(self.caller, f"Opening Pixnova URL: {self.PIXNOVA_URL}")
        # Store the specific tab instance when opened
        self.pixnova_tab = self.browser.open_tab(url=self.PIXNOVA_URL, tab_class=ChromeTab)

        if self.pixnova_tab:
            self.logger.info(self.caller, f"Successfully requested to open new tab for Pixnova (Handle: {self.pixnova_tab.get_handle()}).")
            # Enable upload button if browser is running and file exists
            self._update_test_button_state()
        else:
            self.logger.error(self.caller, "Failed to open new tab for Pixnova.")
            self.pixnova_tab = None
            self._update_test_button_state()

    def _run_face_swap_test(self):
        """Starts the FaceSwapWorker in a background thread."""
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.logger.warn(self.caller, "Face swap test requested, but worker is already running.")
            return

        if not self.pixnova_tab:
            # Attempt to get active tab if specific one isn't stored
            if self.browser:
                active_handle = self.browser.get_active_tab_handle()
                if active_handle: self.pixnova_tab = self.browser.get_tab_by_handle(active_handle)

            if not self.pixnova_tab:
                self.logger.error(self.caller, "Face swap test requested, but Pixnova tab is not assigned/active.")
                self.status_label.setText("Status: Error - Open or focus Pixnova tab first.")
                return

        if not (os.path.exists(self.SOURCE_IMAGE_PATH) and os.path.exists(self.FACE_IMAGE_PATH)):
            self.logger.error(self.caller, "Face swap test requested, but required files not found.")
            self.status_label.setText("Status: Error - Source or face image file missing.")
            return

        # --- Reset UI elements and stored data before starting --- #
        self.status_label.setText("Status: Starting face swap test...")
        if hasattr(self, 'result_image_label'): self.result_image_label.hide()
        if hasattr(self, 'result_url_label'): self.result_url_label.hide()
        self._last_image_data = None # Clear previous image data
        # ------------------------------------------------------- #
        self._update_test_button_state() # Disable button
        QApplication.processEvents()

        self.worker_thread = QThread()
        self.face_swap_worker = FaceSwapWorker(self.pixnova_tab, self.logger)
        self.face_swap_worker.moveToThread(self.worker_thread)

        # --- Connect to thumbnailReady signal --- #
        self.face_swap_worker.thumbnailReady.connect(self._display_result_image)
        # -------------------------------------- #
        self.face_swap_worker.progress.connect(self._update_status)
        self.face_swap_worker.error.connect(self._handle_swap_error)
        self.face_swap_worker.finished.connect(self._on_swap_finished)
        self.worker_thread.started.connect(self.face_swap_worker.run)
        self.worker_thread.finished.connect(self._cleanup_worker)

        self.logger.info(self.caller, "Starting face swap worker thread...")
        self.worker_thread.start()

    # --- Slots for FaceSwapWorker --- #
    @pyqtSlot(str)
    def _update_status(self, message):
        """Updates the status label."""
        self.status_label.setText(f"Status: {message}")

    @pyqtSlot(str)
    def _handle_swap_error(self, error_message):
        """Handles errors reported by the worker."""
        self.logger.error(self.caller, f"FaceSwap Worker Error: {error_message}")
        self.status_label.setText(f"Status: Error - {error_message}")
        # finished signal should still fire to clean up

    @pyqtSlot(bool, str, str)
    def _on_swap_finished(self, success: bool, message: str, download_url: str):
        """Handles the finished signal from the worker."""
        self.logger.info(self.caller, f"FaceSwap Worker Finished. Success: {success}, Message: {message}, URL: {download_url}")
        final_message = f"Status: {message}"

        # --- Attempt to save using Pillow if successful and data exists --- #
        save_success = False
        output_filename = None
        if success and self._last_image_data and not self._last_image_data.isEmpty():
            try:
                # Define Output Path
                output_dir = Path("./output_images")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = output_dir / f"pixnova_result_{timestamp}.jpg"
                quality_pil = 75

                # Use Pillow to open WEBP data and save as JPEG
                image_stream = io.BytesIO(self._last_image_data.data())
                img = Image.open(image_stream)
                # Ensure RGB mode for JPG saving
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(str(output_filename), "JPEG", quality=quality_pil)
                self.logger.info(self.caller, f"Result image saved successfully via Pillow as JPEG (Quality {quality_pil}) to: {output_filename}")
                final_message += f" Saved as {output_filename.name}."
                save_success = True
            except Exception as e:
                self.logger.error(self.caller, f"Error saving result image via Pillow to {output_filename}: {e}", exc_info=True)
                final_message += " (Error saving JPG)"
        elif success:
             self.logger.warn(self.caller, "Swap succeeded but no image data was available to save.")
             final_message += " (Save skipped - no image data)"
        # ---------------------------------------------------------------- #

        # Display fallback URL text only if image display/save failed but URL exists
        if not save_success and not success and download_url and hasattr(self, 'result_url_label'):
             self.result_url_label.setText(f'Failed to load/save image. Result URL: <a href="{download_url}">{download_url}</a>')
             self.result_url_label.setOpenExternalLinks(True)
             self.result_url_label.show()
        elif not download_url:
             # Add clarification if no URL was found, regardless of success
             final_message += " (No result URL found)"

        self.status_label.setText(final_message)
        self._cleanup_worker() # Ensure cleanup happens

    def _cleanup_worker(self):
        """Cleans up the worker thread and re-enables the button."""
        self.face_swap_worker = None
        if self.worker_thread:
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(500)
            self.worker_thread.deleteLater()
            self.worker_thread = None
        self._update_test_button_state() # Re-enable button

    # --- Slots for Browser State Changes ---
    def on_browser_started(self, browser_instance):
        """Slot connected to a signal indicating the browser has started."""
        self.logger.info(self.caller, "Slot: Browser started signal received.")
        self.browser = browser_instance
        if self.browser:
            self.open_button.setEnabled(True)
            self.open_button.setToolTip(f"Opens a new tab to {self.PIXNOVA_URL}")
            self._update_test_button_state()
        else:
            self.logger.warn(self.caller, "Browser started signal received, but instance was None.")
            self.on_browser_stopped()

    def on_browser_stopped(self):
        """Slot connected to a signal indicating the browser has stopped."""
        self.logger.info(self.caller, "Slot: Browser stopped signal received.")
        self.browser = None
        self.pixnova_tab = None
        self.open_button.setEnabled(False)
        self.open_button.setToolTip("Browser is not running.")
        self._update_test_button_state()

    # --- Slot for Thumbnail Data --- #
    @pyqtSlot(QByteArray)
    def _display_result_image(self, image_data: QByteArray):
        """Displays the result image QPixmap in the UI and stores data for saving."""
        # --- Store image data for potential saving --- #
        self._last_image_data = image_data
        # --------------------------------------------- #

        if not hasattr(self, 'result_image_label'):
            self.logger.error(self.caller, "Cannot display image, result_image_label is missing.")
            return

        if image_data.isEmpty():
            self.logger.warn(self.caller, "Received empty image data for thumbnail.")
            self.result_image_label.setText("Failed to load result image.")
            self.result_image_label.show()
            # Fallback URL display is handled in _on_swap_finished
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            self.logger.info(self.caller, f"Successfully loaded image data into QPixmap ({pixmap.width()}x{pixmap.height()}).")
            # Scale pixmap to fit the label while keeping aspect ratio
            scaled_pixmap = pixmap.scaled(self.result_image_label.size(),
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            self.result_image_label.setPixmap(scaled_pixmap)
            self.result_image_label.show()
            if hasattr(self, 'result_url_label'): self.result_url_label.hide() # Hide URL text if image loads
        else:
            self.logger.error(self.caller, "Failed to load image data into QPixmap.")
            self.result_image_label.setText("Error displaying result image.")
            self.result_image_label.show()
            # Fallback URL display handled in _on_swap_finished
    # ----------------------------- #
