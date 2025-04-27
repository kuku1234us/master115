# ./master115/models/face_swap_worker.py
import time
import threading
import io # For image conversion
from pathlib import Path
from typing import List, Optional
import os # Import os for path validation and size check

# --- Selenium Imports --- #
from selenium.webdriver.remote.webdriver import WebDriver # Type hinting
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# --- Other Imports --- #
import requests
from PIL import Image
# --- Local Imports --- #
from PyQt6.QtCore import QObject, pyqtSignal

# Import models (now from the same directory)
from .face_swap_models import PersonData, FaceData, SourceImageData, SwapTaskData
from .webdriver_utils import initialize_chrome_driver # Import the driver initializer
from qt_base_app.models import Logger

class FaceSwapWorker(QObject):
    """
    Worker object to handle the face swapping process for a single face
    across multiple source images using WebDriver.
    """
    # --- Constants --- #
    PIXNOVA_URL = "https://pixnova.ai/ai-face-swap/#playground"

    # XPaths (adapted from pixnova_page.py)
    # --- Scoped to pane-1 (Photo Face Swap Tab) --- #
    PANE_1_SELECTOR = "//div[@id='pane-1']"
    SOURCE_INPUT_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']//input[@type='file']"
    FACE_INPUT_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']//input[@type='file']"
    # --- Spinners (Button loading state) --- #
    SOURCE_BUTTON_LOADING_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    FACE_BUTTON_LOADING_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    # --------------------------------------- #
    START_SWAP_BUTTON_XPATH = (
        f"{PANE_1_SELECTOR}"
        "//button[.//span[normalize-space()='Start face swapping']]") # Match exact text
    PROGRESS_BAR_CONTAINER_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'operate-container')]//div[contains(@class, 'loading-container')]"
    RESULT_IMAGE_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'result-container')]//img[contains(@class, 'el-image__inner') and @src]"
    # --- Upload Confirmation XPaths (Thumbnails) --- #
    SOURCE_THUMBNAIL_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']/preceding-sibling::span[contains(@class,'el-avatar')]/img[@src]"
    FACE_THUMBNAIL_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']/preceding-sibling::span[contains(@class,'el-avatar')]/img[@src]"
    # --- Too Many Requests Popup XPaths --- #
    POPUP_TITLE_XPATH = "//h2[@id='swal2-title' and contains(text(), 'Too many requests')]"
    POPUP_OK_BUTTON_XPATH = "//div[contains(@class, 'swal2-popup')]//button[contains(@class, 'swal2-confirm') and contains(text(), 'Ok, got it!')]"
    # --- Progress Percentage XPath --- #
    PROGRESS_PERCENTAGE_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'loading-container')]//p/span[contains(@class, 'fs-3')]"
    # -----------------

    # --- Signals --- #
    # Emit log messages to be displayed in the UI
    log_message = pyqtSignal(str) 
    # Emit when a single swap task (one face on one source) is complete
    # Provides the completed SwapTaskData and the output path
    task_complete = pyqtSignal(SwapTaskData, str) 
    # Emit when a single swap task fails 
    # Provides the failed SwapTaskData and an error message
    task_failed = pyqtSignal(SwapTaskData, str) 
    # Emit when the worker has processed all its source images or stopped
    finished = pyqtSignal() 

    def __init__(self, 
                 person: PersonData, 
                 face: FaceData, 
                 source_images: List[SourceImageData],
                 temp_output_dir: Path,
                 stop_event: threading.Event, 
                 run_headless: bool,
                 parent=None):
        """
        Initialize the worker object.

        Args:
            person (PersonData): The person data associated with this face.
            face (FaceData): The specific face image this worker is responsible for.
            source_images (List[SourceImageData]): List of source images to process.
            temp_output_dir (Path): Directory where temporary results should be saved.
            stop_event (threading.Event): Shared event to signal graceful shutdown.
            run_headless (bool): Whether to run the browser in headless mode.
            parent (QObject, optional): Parent object. Defaults to None.
        """
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = f"FaceSwapWorker-{person.name}-{face.filename}" # Unique caller ID

        self.person = person
        self.face = face
        self.source_images = source_images
        self.temp_output_dir = temp_output_dir
        self.stop_event = stop_event
        self.run_headless = run_headless

        # Placeholder for WebDriver instance - Initialize in run()
        self.driver = None 

    def _cleanup_driver(self):
        """Safely quits the WebDriver instance if running in headless mode."""
        if self.driver:
            if self.run_headless: # Check the mode
                self.log_message.emit(f"[{self._worker_id()}] Cleaning up WebDriver (headless mode)...")
                self.logger.info(self.caller, "Quitting WebDriver (headless mode)...")
                try:
                    self.driver.quit()
                    self.logger.info(self.caller, "WebDriver quit successfully (headless).")
                except Exception as e:
                    self.logger.error(self.caller, f"Error quitting WebDriver (headless): {e}")
                finally:
                    # Ensure driver reference is removed even if quit fails in headless
                    self.driver = None
            else: # Not headless (visible mode)
                self.log_message.emit(f"[{self._worker_id()}] Skipping WebDriver cleanup for manual inspection (visible mode).")
                self.logger.info(self.caller, "Skipping WebDriver quit() for manual inspection (visible mode).")
                # Optional: Keep self.driver assigned for potential external inspection
                # For safety, ensure worker logic doesn't try to reuse it.
                pass

    def _worker_id(self) -> str:
        """Helper for shorter log messages."""
        # Extract filename without extension for brevity
        face_filename_no_ext = Path(self.face.filename).stem 
        return f"{self.person.name}/{face_filename_no_ext}"

    def _check_thumbnail_present(self, thumbnail_xpath: str, previous_src: Optional[str] = None) -> bool:
        """Checks if the specified thumbnail is present, visible, and its src has changed if previous_src is provided."""
        if not self.driver: return False
        try:
            elements = self.driver.find_elements(By.XPATH, thumbnail_xpath)
            if elements:
                current_src = elements[0].get_attribute('src')
                # Check if src is valid (not None, not empty, looks like a real URL)
                if current_src and (current_src.startswith('blob:') or current_src.startswith('http')):
                    # If previous_src was given, ensure current is different
                    if previous_src is not None:
                        if current_src != previous_src:
                            self.logger.debug(self.caller, f"Thumbnail src changed from '{previous_src[:60]}...' to '{current_src[:60]}...'")
                            return True # Src changed!
                        else:
                            return False # Src is the same as before, not updated yet
                    else:
                        # No previous_src given (first upload?), valid src is enough
                         self.logger.debug(self.caller, f"Thumbnail found with valid src: {current_src[:60]}... (no previous src check)")
                         return True
                # else: src is None, empty, or doesn't look valid
                #     self.logger.debug(f"Thumbnail found but src invalid: {current_src}")
            # else: elements is empty or first element not displayed
            return False
        except (NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
            self.logger.debug(self.caller, f"Thumbnail check failed or element gone for {thumbnail_xpath}: {e}")
            return False

    def _recover_image_state(self, source_image: SourceImageData) -> bool:
        """Checks and re-uploads face/source images if their thumbnails are missing."""
        try:
            self.log_message.emit(f"      -> Verifying images after recovery action...")
            # Check Face Thumbnail
            if not self._check_thumbnail_present(self.FACE_THUMBNAIL_XPATH):
                self.log_message.emit("        -> Face thumbnail missing. Re-uploading...")
                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH, self.FACE_BUTTON_LOADING_XPATH):
                    self.logger.error(self.caller,"Face re-upload failed during recovery state check.")
                    return False
                self.log_message.emit("        -> Face re-upload successful.")

            # Check Source Thumbnail
            if not self._check_thumbnail_present(self.SOURCE_THUMBNAIL_XPATH):
                self.log_message.emit("        -> Source thumbnail missing. Re-uploading...")
                if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH, self.SOURCE_BUTTON_LOADING_XPATH):
                    self.logger.error(self.caller, "Source re-upload failed during recovery state check.")
                    return False
                self.log_message.emit("        -> Source re-upload successful.")

            return True # Both images verified/recovered
        except Exception as e:
            self.logger.error(self.caller, f"Unexpected error during _recover_image_state: {e}", exc_info=True)
            return False

    def run(self):
        """The main execution method for the worker object."""
        worker_id_short = self._worker_id()
        self.logger.info(self.caller, f"Worker started for face '{self.face.filename}'. Short ID: {worker_id_short}")
        self.log_message.emit(f"[{worker_id_short}] Started.")

        try:
            # === Actual WebDriver Logic ===

            # --- 1. Initialize WebDriver & Navigate (with Retry) --- #
            self.log_message.emit(f"[{worker_id_short}] Initializing WebDriver...")
            driver_initialized = False
            navigation_successful = False
            init_attempts = 0
            max_init_attempts = 2 # Try initial + 1 retry
            last_init_error = None # Store last error

            while not navigation_successful and init_attempts < max_init_attempts:
                init_attempts += 1
                self.logger.info(self.caller, f"Attempt {init_attempts}/{max_init_attempts} to initialize WebDriver and navigate.")
                try:
                    # Initialize driver if not already done or if previous attempt failed
                    if not driver_initialized:
                        # Use the stored headless setting
                        self.driver = initialize_chrome_driver(headless=self.run_headless)
                        if not self.driver:
                            # If initialize_chrome_driver returns None, it's fatal, break loop
                            raise WebDriverException("initialize_chrome_driver returned None.")
                        driver_initialized = True # Mark as initialized for this loop cycle

                    # Attempt navigation
                    self.log_message.emit(f"[{worker_id_short}] Navigating to Pixnova (Attempt {init_attempts})...")
                    # Increase timeout for navigation slightly? Default is often long already.
                    self.driver.set_page_load_timeout(180) # Example: 3 minutes for page load
                    self.driver.get(self.PIXNOVA_URL)
                    navigation_successful = True # If get() returns without error, we succeeded
                    self.logger.info(self.caller, f"Navigation successful on attempt {init_attempts}.")

                except Exception as init_err:
                    # Log intermediate errors as warnings without traceback
                    is_final_attempt = (init_attempts == max_init_attempts)
                    log_level = self.logger.error if is_final_attempt else self.logger.warn
                    log_msg = f"Error during WebDriver init/nav (Attempt {init_attempts}/{max_init_attempts}): {init_err}"
                    log_level(self.caller, log_msg, exc_info=is_final_attempt) # Only log traceback on final attempt
                    
                    last_init_error = init_err # Store the error

                    # Reset flags for retry
                    navigation_successful = False
                    driver_initialized = False # Force re-init if get() failed

                    # Clean up the potentially broken driver before retrying or exiting
                    self._cleanup_driver()

                    if init_attempts < max_init_attempts:
                        self.log_message.emit(f"[{worker_id_short}] Init/Nav failed on attempt {init_attempts}. Retrying after cleanup...")
                        time.sleep(2) # Brief pause before retry
                    # else: loop will exit naturally after max attempts

            # --- Check if initialization and navigation ultimately succeeded --- 
            if not navigation_successful:
                # Final error message already logged by the loop's exception handler if it failed
                self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] WebDriver Init/Nav failed after {max_init_attempts} attempts.")
                # Ensure cleanup is attempted one last time if needed
                self._cleanup_driver()
                # Exit run method
                # self.finished.emit() will be called by the outer finally block
                return

            # --- 2. One-Time Face Upload --- #
            self.log_message.emit(f"[{worker_id_short}] Uploading face: {self.face.filename}...")
            try:
                # Use FACE_THUMBNAIL_XPATH for confirmation
                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH, self.FACE_BUTTON_LOADING_XPATH):
                    raise Exception(f"Face upload failed for {self.face.filename}") # Raise to stop worker
                self.log_message.emit(f"[{worker_id_short}] Face upload complete.")
            except Exception as face_upload_err:
                # Treat face upload errors as fatal
                self.logger.error(self.caller, f"Fatal Error during face upload: {face_upload_err}", exc_info=True)
                self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] Face Upload failed: {face_upload_err}")
                # self._cleanup_driver() # Cleanup happens in outer finally
                # self.finished.emit() # Emitted by outer finally
                return # Exit run method

            # --- 3. Process Source Images Loop --- #
            for source_image in self.source_images:
                # Check stop signal before starting next task
                if self.stop_event.is_set():
                    self.log_message.emit(f"[{worker_id_short}] Stop signal received. Aborting remaining tasks.")
                    break # Exit the loop

                self.log_message.emit(f"[{worker_id_short}] Processing source: {source_image.filename}")

                # Create SwapTaskData for signaling
                current_task = SwapTaskData(
                    person=self.person,
                    face=self.face,
                    source_image=source_image,
                    output_dir=self.temp_output_dir
                )

                # --- Retry Logic for Swap Process --- #
                max_retries = 5 # 1 initial attempt + 4 retries
                swap_successful = False
                last_task_error = None # Store the last error encountered
                for attempt in range(max_retries):
                    # Added logger call
                    self.logger.info(self.caller, f"Attempt {attempt + 1}/{max_retries} for {source_image.filename}") 
                    self.log_message.emit(f"  -> Attempt {attempt + 1}/{max_retries} for {source_image.filename}")

                    try:
                        # --- 3a. Upload Source Image (inside retry loop) --- #
                        # Added logger call
                        self.logger.info(self.caller, f"Uploading source: {source_image.filename}...")
                        self.log_message.emit(f"    -> Uploading source: {source_image.filename}...")
                        if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH, self.SOURCE_BUTTON_LOADING_XPATH):
                            raise Exception(f"Source upload failed for {source_image.filename} (Attempt {attempt + 1})")
                        # Added logger call
                        self.logger.info(self.caller, "Source upload complete.")
                        self.log_message.emit(f"    -> Source upload complete.")

                        # --- 3b. Click Start Button (inside retry loop) --- #
                        # Added logger call
                        self.logger.info(self.caller, "Waiting for Start button...")
                        self.log_message.emit(f"    -> Waiting for Start button...")
                        start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
                        
                        # --- Log Button State BEFORE Waiting --- #
                        try:
                            # Try finding immediately, don't wait long
                            button_element = self.driver.find_element(start_button_locator[0], start_button_locator[1])
                            is_displayed = button_element.is_displayed()
                            is_enabled = button_element.is_enabled()
                            self.logger.debug(self.caller, f"Start button state before explicit wait: Displayed={is_displayed}, Enabled={is_enabled}")
                        except NoSuchElementException:
                            self.logger.debug(self.caller, "Start button not immediately found before explicit wait.")
                        except Exception as button_check_err:
                             self.logger.warn(self.caller, f"Error checking start button state before wait: {button_check_err}")
                        # ---------------------------------------- #
                        
                        start_button = WebDriverWait(self.driver, 60).until(
                            EC.element_to_be_clickable(start_button_locator)
                        )
                        # Added logger call
                        self.logger.info(self.caller, "Clicking Start button...")
                        self.log_message.emit(f"    -> Clicking Start button...")
                        start_button.click()
                        # Added logger call
                        self.logger.info(self.caller, "Start button clicked.")
                        self.log_message.emit(f"    -> Start button clicked.")

                        # --- Check for and Handle 'Too many requests' popup ---
                        popup_handled = False
                        try:
                            # Added logger call
                            self.logger.debug(self.caller, "Checking for 'Too many requests' popup...")
                            self.log_message.emit(f"    -> Checking for 'Too many requests' popup...")
                            WebDriverWait(self.driver, 5).until(
                                EC.visibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
                            )
                            self.logger.warn(self.caller, "'Too many requests' popup detected.")
                            # Added logger call
                            self.logger.info(self.caller, "Popup detected. Dismissing...")
                            self.log_message.emit(f"    -> Popup detected. Dismissing...")
                            try:
                                ok_button = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, self.POPUP_OK_BUTTON_XPATH))
                                )
                                ok_button.click()
                                WebDriverWait(self.driver, 5).until(
                                    EC.invisibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
                                )
                                # Added logger call
                                self.logger.info(self.caller, "Popup dismissed.")
                                self.log_message.emit(f"    -> Popup dismissed.")
                                popup_handled = True
                            except Exception as popup_dismiss_err:
                                raise Exception(f"Failed to dismiss 'Too many requests' popup: {popup_dismiss_err}")
                        except TimeoutException:
                            # Added logger call
                            self.logger.debug(self.caller, "No popup detected.")
                            self.log_message.emit(f"    -> No popup detected.")
                            
                        # --- Verify State and Conditionally Re-upload/Wait/Click Start ---
                        needs_reupload = False
                        recovery_action_taken = popup_handled
                        try:
                            # Added logger call
                            self.logger.debug(self.caller, "Verifying image states...")
                            self.log_message.emit(f"    -> Verifying image states...")
                            if not self._check_thumbnail_present(self.FACE_THUMBNAIL_XPATH):
                                # Added logger call
                                self.logger.info(self.caller, "Face thumbnail missing. Re-uploading...")
                                self.log_message.emit("      -> Face thumbnail missing. Re-uploading...")
                                needs_reupload = True
                                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH, self.FACE_BUTTON_LOADING_XPATH):
                                    raise Exception("Failed to re-upload face after state check")
                                # Added logger call
                                self.logger.info(self.caller, "Face re-upload successful.")
                                self.log_message.emit("      -> Face re-upload successful.")
                                recovery_action_taken = True
                            if not self._check_thumbnail_present(self.SOURCE_THUMBNAIL_XPATH):
                                # Added logger call
                                self.logger.info(self.caller, "Source thumbnail missing. Re-uploading...")
                                self.log_message.emit("      -> Source thumbnail missing. Re-uploading...")
                                needs_reupload = True
                                if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH, self.SOURCE_BUTTON_LOADING_XPATH):
                                    raise Exception("Failed to re-upload source after state check")
                                # Added logger call
                                self.logger.info(self.caller, "Source re-upload successful.")
                                self.log_message.emit("      -> Source re-upload successful.")
                                recovery_action_taken = True
                            if recovery_action_taken:
                                # Added logger call
                                self.logger.info(self.caller, "Recovery action performed, re-validating Start button...")
                                self.log_message.emit(f"    -> Recovery action performed, re-validating Start button...")
                                # Added logger call
                                self.logger.debug(self.caller, "Waiting for Start button to be clickable...")
                                self.log_message.emit(f"    -> Waiting for Start button to be clickable...")
                                start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
                                
                                # --- Log Button State BEFORE Waiting (Recovery Path) --- #
                                try:
                                    button_element_recovery = self.driver.find_element(start_button_locator[0], start_button_locator[1])
                                    is_displayed_recovery = button_element_recovery.is_displayed()
                                    is_enabled_recovery = button_element_recovery.is_enabled()
                                    self.logger.debug(self.caller, f"Start button state before recovery wait: Displayed={is_displayed_recovery}, Enabled={is_enabled_recovery}")
                                except NoSuchElementException:
                                    self.logger.debug(self.caller, "Start button not immediately found before recovery wait.")
                                except Exception as button_check_recovery_err:
                                    self.logger.warn(self.caller, f"Error checking start button state before recovery wait: {button_check_recovery_err}")
                                # ------------------------------------------------------- #
                                
                                start_button_after_check = WebDriverWait(self.driver, 10).until(
                                    EC.element_to_be_clickable(start_button_locator)
                                )
                                if popup_handled and not needs_reupload:
                                     # Added logger call
                                     self.logger.debug(self.caller, "Popup handled, no re-upload needed. Waiting 3 seconds...")
                                     self.log_message.emit("    -> Popup handled, no re-upload needed. Waiting 3 seconds...")
                                     time.sleep(3)
                                start_button_after_check.click()
                                # Added logger call
                                self.logger.info(self.caller, "Start button re-clicked after recovery.")
                                self.log_message.emit(f"    -> Start button re-clicked after recovery.")
                            else:
                                # Added logger call
                                self.logger.debug(self.caller, "Initial state OK, no recovery needed.")
                                self.log_message.emit(f"    -> Initial state OK, no recovery needed.")
                        except Exception as state_check_err:
                            raise Exception(f"Error during state verification/recovery: {state_check_err}")

                        # --- 3c. Wait for Swap Completion (Robust Wait + Stall Detection) --- #
                        # Added logger call
                        self.logger.info(self.caller, f"Waiting for swap completion (Attempt {attempt + 1})...")
                        self.log_message.emit(f"    -> Waiting for swap completion (Attempt {attempt + 1})...")
                        start_wait_time = time.time()
                        overall_timeout = 300 # seconds (5 minutes)
                        stall_timeout = 15 # seconds
                        last_progress_value = "-1"
                        last_progress_time = time.time()
                        completion_status = "TIMEOUT"
                        while time.time() - start_wait_time < overall_timeout:
                            if self.stop_event.is_set():
                                # Added logger call
                                self.logger.info(self.caller, "Stop event detected during wait.")
                                self.log_message.emit(f"    -> Stop event detected during wait.")
                                completion_status = "STOPPED"
                                break
                            try:
                                result_elements = self.driver.find_elements(By.XPATH, self.RESULT_IMAGE_XPATH)
                                if result_elements and result_elements[0].is_displayed():
                                    src = result_elements[0].get_attribute('src')
                                    if src and src.startswith('http'):
                                        # Added logger call
                                        self.logger.info(self.caller, "Result image appeared.")
                                        self.log_message.emit(f"    -> Result image appeared.")
                                        completion_status = "SUCCESS"
                                        break
                            except NoSuchElementException:
                                pass
                            try:
                                progress_container = self.driver.find_element(By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH)
                                if not progress_container.is_displayed():
                                     # Added logger call
                                     self.logger.info(self.caller, "Progress bar disappeared (swap likely complete).")
                                     self.log_message.emit(f"    -> Progress bar disappeared.")
                                     completion_status = "SUCCESS"
                                     break
                                else:
                                    try:
                                        # --- Re-find the element EACH time ---
                                        progress_element = progress_container.find_element(By.XPATH, self.PROGRESS_PERCENTAGE_XPATH)
                                        # -----------------------------------
                                        current_progress = progress_element.text.strip()
                                        if current_progress != last_progress_value:
                                             # Added logger call (use debug?)
                                             self.logger.debug(self.caller, f"Progress: {current_progress}%") 
                                             self.log_message.emit(f"      -> Progress: {current_progress}%")
                                             last_progress_value = current_progress
                                             last_progress_time = time.time()
                                        elif time.time() - last_progress_time > stall_timeout:
                                            self.logger.warn(self.caller, f"Progress stalled at {current_progress}% for > {stall_timeout}s.")
                                            # Added logger call
                                            self.logger.warn(self.caller, f"Progress stalled at {current_progress}%. Triggering retry/fail.")
                                            self.log_message.emit(f"    -> Progress stalled at {current_progress}%. Triggering retry/fail.")
                                            completion_status = "STALLED"
                                            break
                                    except NoSuchElementException:
                                         self.logger.warn(self.caller, "Could not find progress percentage text while progress bar visible.")
                                         last_progress_time = time.time()
                            except NoSuchElementException:
                                # Added logger call
                                self.logger.debug(self.caller, "Progress container not found (likely finished).")
                                self.log_message.emit(f"    -> Progress container not found (likely finished).")
                                completion_status = "SUCCESS"
                                break
                            time.sleep(1)

                        # --- Handle Loop Outcome --- #
                        if completion_status == "SUCCESS":
                             # Added logger call
                             self.logger.info(self.caller, "Swap process completed successfully.")
                             self.log_message.emit(f"    -> Swap process completed successfully.")
                        elif completion_status == "STOPPED":
                             raise Exception("Stop event detected during wait")
                        elif completion_status == "STALLED":
                             last_task_error = TimeoutException(f"Progress stalled on attempt {attempt + 1}")
                             raise last_task_error
                        elif completion_status == "TIMEOUT":
                             self.logger.warn(self.caller, f"Swap timed out after {overall_timeout}s (Attempt {attempt + 1})")
                             last_task_error = TimeoutException(f"Swap overall timeout on attempt {attempt + 1}")
                             raise last_task_error

                        # --- 3d. Get Result & Save (Only if SUCCESS) --- #
                        # Added logger call
                        self.logger.info(self.caller, "Waiting for result image details...")
                        self.log_message.emit(f"    -> Waiting for result image details...")
                        result_image_locator = (By.XPATH, self.RESULT_IMAGE_XPATH)
                        result_image_element = WebDriverWait(self.driver, 10).until(
                            EC.visibility_of_element_located(result_image_locator)
                        )
                        time.sleep(0.5)
                        result_url = result_image_element.get_attribute('src')
                        if result_url and result_url.startswith('http'):
                            self.logger.info(self.caller, f"Found result image URL: {result_url[:60]}...")
                            # Added logger call
                            self.logger.info(self.caller, "Fetching result image...")
                            self.log_message.emit(f"    -> Fetching result image...")
                            response = requests.get(result_url, timeout=30)
                            response.raise_for_status()
                            webp_bytes = response.content

                            # Added logger call
                            self.logger.info(self.caller, "Saving result as JPG...")
                            self.log_message.emit(f"    -> Saving result as JPG...")
                            face_stem = Path(self.face.filename).stem
                            source_stem = Path(source_image.filename).stem
                            output_filename = f"{self.person.name} {face_stem} {source_stem}.jpg"
                    output_path = self.temp_output_dir / output_filename
                            output_path.parent.mkdir(parents=True, exist_ok=True)

                            image_stream = io.BytesIO(webp_bytes)
                            img = Image.open(image_stream)
                            if img.mode == 'RGBA': img = img.convert('RGB')
                            img.save(str(output_path), "JPEG", quality=75)

                            self.logger.info(self.caller, f"Saved result to {output_path}")
                            self.task_complete.emit(current_task, str(output_path))
                            swap_successful = True
                            break # Exit retry loop on success
                        else:
                            raise Exception(f"Result image URL not found or invalid: '{result_url}'")

                    except Exception as task_err:
                        # Catch errors within a single attempt
                        self.logger.error(self.caller, f"Error during attempt {attempt + 1}: {task_err}", exc_info=True)
                        last_task_error = task_err # Store the error

                        if attempt < max_retries - 1:
                            # Perform recovery actions before the next attempt
                            # Added logger call
                            self.logger.warn(self.caller, f"Error on attempt {attempt + 1}. Performing recovery for attempt {attempt + 2}...")
                            self.log_message.emit(f"  -> Error on attempt {attempt + 1}. Performing recovery for attempt {attempt + 2}...")
                            # --- Recovery try...except block --- #
                            try:
                                # Added logger call
                                self.logger.debug(self.caller, "Clearing local storage...")
                                self.log_message.emit(f"      -> Clearing local storage...")
                                self.driver.execute_script("window.localStorage.clear();")
                                # Added logger call
                                self.logger.debug(self.caller, "Clearing session storage...")
                                self.log_message.emit(f"      -> Clearing session storage...")
                                self.driver.execute_script("window.sessionStorage.clear();")
                                # Added logger call
                                self.logger.debug(self.caller, "Clearing cookies...")
                                self.log_message.emit(f"      -> Clearing cookies...")
                                self.driver.delete_all_cookies()
                                # Added logger call
                                self.logger.debug(self.caller, "Refreshing page...")
                                self.log_message.emit(f"      -> Refreshing page...")
                                self.driver.refresh()
                                time.sleep(2)
                                recovery_successful = self._recover_image_state(source_image)
                                if not recovery_successful:
                                    raise Exception("Recovery actions (clear storage/cookies/refresh/re-upload) failed.")
                                # Added logger call
                                self.logger.info(self.caller, f"Recovery complete. Waiting 3 seconds before attempt {attempt + 2}...")
                                self.log_message.emit(f"      -> Recovery complete. Waiting 3 seconds before attempt {attempt + 2}...")
                                time.sleep(3)
                            except Exception as reset_err:
                                self.logger.error(self.caller, f"Error during recovery actions: {reset_err}", exc_info=True)
                                # Added logger call
                                self.logger.error(self.caller, f"[FATAL] Error during recovery: {reset_err}. Failing task.")
                                self.log_message.emit(f"      -> [FATAL] Error during recovery: {reset_err}. Failing task.")
                                last_task_error = reset_err
                                break # Exit retry loop if recovery fails
                        else:
                            # Error on the final attempt
                            # Added logger call
                            self.logger.error(self.caller, f"Error on final attempt ({max_retries}). Error: {task_err}")
                            self.log_message.emit(f"  -> Error on final attempt ({max_retries}). Error: {task_err}")
                            break # Exit retry loop, failure will be handled below

                # --- After Retry Loop --- #
                if not swap_successful:
                    # If loop finished without success, emit failure
                    error_msg = f"Failed to process {current_task.source_image.filename} after {max_retries} attempts. Last error: {last_task_error}"
                    self.logger.error(self.caller, error_msg, exc_info=True)
                    self.log_message.emit(f"[ERROR] [{worker_id_short}] {error_msg}")
                    self.task_failed.emit(current_task, str(last_task_error))
                    
                    # Attempt final reset before NEXT source image (outside retry loop)
                    try: 
                        self.log_message.emit(f"  -> Attempting final reset after task failure...")
                        if self.driver: 
                            self.driver.refresh()
                            time.sleep(2)
                            self.log_message.emit(f"  -> Re-uploading face {self.face.filename} after failure...")
                            if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH, self.FACE_BUTTON_LOADING_XPATH):
                                self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] Failed to re-upload face during final reset, stopping worker.")
                                break
                        else:
                            self.log_message.emit(f"[WARN] [{worker_id_short}] Driver was not available for final reset attempt.")
                    except Exception as final_reset_err:
                        self.logger.error(self.caller, f"Error during final reset attempt: {final_reset_err}", exc_info=True)
                        self.log_message.emit(f"[WARN] [{worker_id_short}] Failed final reset attempt, subsequent tasks might still fail.")

            # --- End of Source Image Loop --- #

        except Exception as e:
            # Catch unexpected errors outside the task loop (likely during init/face upload)
            init_error_msg = f"Worker failed during initialization or general processing: {e}"
            self.logger.error(self.caller, init_error_msg, exc_info=True)
            self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] {init_error_msg}")

        finally:
            # --- Actual Cleanup --- #
            self._cleanup_driver() # Ensure driver is quit
            self.logger.info(self.caller, "Worker finished execution.")
            self.log_message.emit(f"[{worker_id_short}] Finished.")

        # Emit finished signal *after* all cleanup attempts in finally block
        self.finished.emit() # Signal that the object has finished execution 

    def _upload_file_and_wait(self, input_xpath: str, file_path: str, thumbnail_xpath: str, spinner_xpath: str) -> bool:
        """
        Handles uploading a file, waiting for the thumbnail to appear,
        with an extended timeout based on file size if a spinner is visible.
        """
        worker_id_short = self._worker_id()
        if not self.driver:
            self.log_message.emit(f"[ERROR] [{worker_id_short}] Driver not available for upload.")
            return False
        
        file_name = Path(file_path).name
        try:
            # --- Calculate Size-Based Timeout --- #
            size_bytes = os.path.getsize(file_path)
            size_kb = size_bytes / 1024
            # Approx 1 min per 500KB, minimum 30s, max of hard timeout
            hard_timeout = 360 # seconds (6 minutes)
            size_based_timeout = max(30.0, (size_kb / 500.0) * 60.0)
            size_based_timeout = min(size_based_timeout, float(hard_timeout)) # Cap at hard timeout
            self.log_message.emit(f"  -> File: {file_name}, Size: {size_kb:.2f} KB. Potential extended wait: {size_based_timeout:.1f}s (Hard limit: {hard_timeout}s)")
            # ------------------------------------ #

            self.log_message.emit(f"  -> Finding input for {file_name}...")
            upload_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )
            
            # --- Get current src BEFORE performing upload --- #
            previous_src: Optional[str] = None
            try:
                current_thumb_elements = self.driver.find_elements(By.XPATH, thumbnail_xpath)
                if current_thumb_elements:
                    previous_src = current_thumb_elements[0].get_attribute('src')
                    # Log only if it seems valid already
                    if previous_src and (previous_src.startswith('blob:') or previous_src.startswith('http')):
                         self.logger.debug(self.caller, f"Found previous thumbnail src before upload: {previous_src[:60]}...")
                # else: No initial thumbnail visible
            except Exception as e_get_prev:
                 self.logger.debug(self.caller, f"Could not get previous thumbnail src before upload: {e_get_prev}")
            # ------------------------------------------- #

            self.log_message.emit(f"  -> Uploading {file_name}...")
            self.logger.debug(self.caller, f"Uploading {file_name}...")
            upload_input.send_keys(file_path)

            # --- Polling Loop for Thumbnail OR Timeout --- #
            self.log_message.emit(f"  -> Waiting for {file_name} thumbnail (up to {hard_timeout}s, extended if spinner visible)..." )
            start_time = time.time()
            spinner_previously_seen = False # Track if spinner ever appeared
            
            while time.time() - start_time < hard_timeout:
                # 1. Check for SUCCESS condition (Thumbnail changed or appeared)
                if self._check_thumbnail_present(thumbnail_xpath, previous_src=previous_src):
                    self.logger.info(self.caller, f"Thumbnail appeared/changed for {file_name}.")
                    self.log_message.emit(f"  -> Thumbnail loaded for {file_name}.")
                    return True

                # 2. Check for Spinner and Potential Size Timeout
                try:
                    spinner_elements = self.driver.find_elements(By.XPATH, spinner_xpath)
                    spinner_currently_visible = spinner_elements and spinner_elements[0].is_displayed()
                except (NoSuchElementException, StaleElementReferenceException):
                     spinner_currently_visible = False # Treat errors as spinner not visible
                     
                if spinner_currently_visible:
                    spinner_previously_seen = True # Mark that we saw it at least once
                    # Log spinner visibility periodically if needed for debugging
                    # self.logger.debug(self.caller, f"Spinner visible for {file_name} at {time.time():.1f}s")
                    # Check if elapsed time exceeds the size-based limit WHILE spinner is showing
                    if time.time() - start_time > size_based_timeout:
                        self.logger.warn(self.caller, f"Upload timeout for {file_name} based on size ({size_based_timeout:.1f}s) while spinner still visible.")
                        self.log_message.emit(f"[ERROR] [{worker_id_short}] Upload time exceeded size limit ({size_based_timeout:.1f}s) for {file_name} while spinner active.")
                        return False
                # If spinner is not currently visible, we don't check size limit, just continue polling for thumbnail

                # 3. Wait briefly before next poll
                time.sleep(0.5)
            # --- End of Polling Loop --- #

            # If loop finishes, hard timeout was reached without thumbnail
            self.logger.error(self.caller, f"Hard timeout ({hard_timeout}s) reached waiting for {file_name} thumbnail.")
            self.log_message.emit(f"[ERROR] [{worker_id_short}] Hard timeout ({hard_timeout}s) waiting for {file_name} thumbnail.")
            # Optional: Log if spinner was ever seen during timeout
            if spinner_previously_seen:
                 self.logger.info(self.caller, f"Spinner was observed at some point during the hard timeout for {file_name}.")
            else:
                 self.logger.info(self.caller, f"Spinner was NOT observed during the hard timeout for {file_name}.")
            return False

        except FileNotFoundError:
             self.logger.error(self.caller, f"File not found for upload: {file_path}")
             self.log_message.emit(f"[ERROR] [{worker_id_short}] File not found: {file_name}")
             return False
        except Exception as e:
            # Log error and return False, let the main run() logic handle task failure
            self.logger.error(self.caller, f"Exception during upload/wait for {file_name}: {type(e).__name__}", exc_info=True)
            self.log_message.emit(f"[ERROR] [{worker_id_short}] Upload/Thumbnail error for {file_name}: {e}")
            return False 