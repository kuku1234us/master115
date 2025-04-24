# ./master115/models/face_swap_worker.py
import time
import threading
import io # For image conversion
from pathlib import Path
from typing import List

# --- Selenium Imports --- #
from selenium.webdriver.remote.webdriver import WebDriver # Type hinting
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
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
                 parent=None):
        """
        Initialize the worker object.

        Args:
            person (PersonData): The person data associated with this face.
            face (FaceData): The specific face image this worker is responsible for.
            source_images (List[SourceImageData]): List of source images to process.
            temp_output_dir (Path): Directory where temporary results should be saved.
            stop_event (threading.Event): Shared event to signal graceful shutdown.
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

        # Placeholder for WebDriver instance - Initialize in run()
        self.driver = None 

    def _cleanup_driver(self):
        """Safely quits the WebDriver instance."""
        if self.driver:
            self.log_message.emit(f"[{self._worker_id()}] Skipping WebDriver cleanup for manual inspection.")
            self.logger.info(self.caller, "Skipping WebDriver quit() for manual inspection.")
            pass # Explicitly do nothing further for cleanup

    def _worker_id(self) -> str:
        """Helper for shorter log messages."""
        # Extract filename without extension for brevity
        face_filename_no_ext = Path(self.face.filename).stem 
        return f"{self.person.name}/{face_filename_no_ext}"

    def _check_thumbnail_present(self, thumbnail_xpath: str) -> bool:
        """Checks if the specified thumbnail image element is present and visible."""
        if not self.driver: return False # Should not happen if called correctly
        try:
            # Use find_elements to avoid immediate exception if not found
            elements = self.driver.find_elements(By.XPATH, thumbnail_xpath)
            # Check if list is not empty and the first element is displayed
            if elements and elements[0].is_displayed():
                # Optional: Check src attribute is not empty/placeholder if needed
                # src = elements[0].get_attribute('src')
                # return bool(src and not src.startswith('data:image')) # Example check
                return True
            return False
        except (NoSuchElementException, WebDriverException) as e:
            # Log if needed, but typically just indicates not present or stale element
            self.logger.debug(self.caller, f"Thumbnail check failed or element gone for {thumbnail_xpath}: {e}")
            return False

    def _recover_image_state(self, source_image: SourceImageData) -> bool:
        """Checks and re-uploads face/source images if their thumbnails are missing."""
        try:
            self.log_message.emit(f"      -> Verifying images after recovery action...")
            # Check Face Thumbnail
            if not self._check_thumbnail_present(self.FACE_THUMBNAIL_XPATH):
                self.log_message.emit("        -> Face thumbnail missing. Re-uploading...")
                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH):
                    self.logger.error(self.caller,"Face re-upload failed during recovery state check.")
                    return False
                self.log_message.emit("        -> Face re-upload successful.")

            # Check Source Thumbnail
            if not self._check_thumbnail_present(self.SOURCE_THUMBNAIL_XPATH):
                self.log_message.emit("        -> Source thumbnail missing. Re-uploading...")
                if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH):
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

            # --- 1. Initialize WebDriver & Navigate --- #
            self.log_message.emit(f"[{worker_id_short}] Initializing WebDriver...")
            try:
                # Consider headless=True for production
                self.driver = initialize_chrome_driver(headless=False) # DEBUG: Run with visible browser
                if not self.driver:
                    raise WebDriverException("Failed to initialize WebDriver instance.")
                self.log_message.emit(f"[{worker_id_short}] Navigating to Pixnova...")
                self.driver.get(self.PIXNOVA_URL)
            except Exception as init_err:
                # Treat init/nav errors as fatal for this worker
                self.logger.error(self.caller, f"Fatal Error during WebDriver init/nav: {init_err}", exc_info=True)
                self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] WebDriver Init/Nav failed: {init_err}")
                self._cleanup_driver() # Attempt cleanup if driver was partially created
                self.finished.emit()
                return

            # --- 2. One-Time Face Upload --- #
            self.log_message.emit(f"[{worker_id_short}] Uploading face: {self.face.filename}...")
            try:
                # Use FACE_THUMBNAIL_XPATH for confirmation
                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH):
                    raise Exception(f"Face upload failed for {self.face.filename}") # Raise to stop worker
                self.log_message.emit(f"[{worker_id_short}] Face upload complete.")
            except Exception as face_upload_err:
                # Treat face upload errors as fatal
                self.logger.error(self.caller, f"Fatal Error during face upload: {face_upload_err}", exc_info=True)
                self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] Face Upload failed: {face_upload_err}")
                self._cleanup_driver()
                self.finished.emit()
                return

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
                    self.log_message.emit(f"  -> Attempt {attempt + 1}/{max_retries} for {source_image.filename}")

                    try:
                        # --- 3a. Upload Source Image (inside retry loop) --- #
                        self.log_message.emit(f"    -> Uploading source: {source_image.filename}...")
                        if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH):
                            raise Exception(f"Source upload failed for {source_image.filename} (Attempt {attempt + 1})")
                        self.log_message.emit(f"    -> Source upload complete.")

                        # --- 3b. Click Start Button (inside retry loop) --- #
                        self.log_message.emit(f"    -> Waiting for Start button...")
                        start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
                        start_button = WebDriverWait(self.driver, 60).until(
                            EC.element_to_be_clickable(start_button_locator)
                        )
                        self.log_message.emit(f"    -> Clicking Start button...")
                        start_button.click()
                        self.log_message.emit(f"    -> Start button clicked.")

                        # --- Check for and Handle 'Too many requests' popup ---
                        popup_handled = False
                        try:
                            self.log_message.emit(f"    -> Checking for 'Too many requests' popup...")
                            WebDriverWait(self.driver, 5).until(
                                EC.visibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
                            )
                            self.logger.warn(self.caller, "'Too many requests' popup detected.")
                            self.log_message.emit(f"    -> Popup detected. Dismissing...")
                            try:
                                ok_button = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, self.POPUP_OK_BUTTON_XPATH))
                                )
                                ok_button.click()
                                WebDriverWait(self.driver, 5).until(
                                    EC.invisibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
                                )
                                self.log_message.emit(f"    -> Popup dismissed.")
                                popup_handled = True
                            except Exception as popup_dismiss_err:
                                # If dismissing fails, treat it as a task error to trigger retry
                                raise Exception(f"Failed to dismiss 'Too many requests' popup: {popup_dismiss_err}")

                        except TimeoutException:
                            self.log_message.emit(f"    -> No popup detected.")
                            # No popup, proceed normally

                        # --- Verify State and Conditionally Re-upload/Wait/Click Start ---
                        needs_reupload = False
                        recovery_action_taken = popup_handled # Start with whether popup was handled
                        try:
                            self.log_message.emit(f"    -> Verifying image states...")
                            # Check Face Thumbnail
                            if not self._check_thumbnail_present(self.FACE_THUMBNAIL_XPATH):
                                self.log_message.emit("      -> Face thumbnail missing. Re-uploading...")
                                needs_reupload = True
                                if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH):
                                    raise Exception("Failed to re-upload face after state check")
                                self.log_message.emit("      -> Face re-upload successful.")
                                recovery_action_taken = True # Mark recovery action

                            # Check Source Thumbnail
                            if not self._check_thumbnail_present(self.SOURCE_THUMBNAIL_XPATH):
                                self.log_message.emit("      -> Source thumbnail missing. Re-uploading...")
                                needs_reupload = True
                                if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH):
                                    raise Exception("Failed to re-upload source after state check")
                                self.log_message.emit("      -> Source re-upload successful.")
                                recovery_action_taken = True # Mark recovery action

                            # --- Only re-wait and re-click if a recovery action occurred ---
                            if recovery_action_taken:
                                self.log_message.emit(f"    -> Recovery action performed, re-validating Start button...")
                                # Wait for Start button again (needed if popup was handled or even if not, ensures state)
                                self.log_message.emit(f"    -> Waiting for Start button to be clickable...")
                                start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
                                start_button_after_check = WebDriverWait(self.driver, 10).until(
                                    EC.element_to_be_clickable(start_button_locator)
                                )

                                # Conditional Wait (only if popup specifically was handled and no upload needed)
                                if popup_handled and not needs_reupload:
                                     self.log_message.emit("    -> Popup handled, no re-upload needed. Waiting 3 seconds...")
                                     time.sleep(3)
                                # Click Start (only if recovery happened)
                                start_button_after_check.click()
                                self.log_message.emit(f"    -> Start button re-clicked after recovery.")
                            else:
                                self.log_message.emit(f"    -> Initial state OK, no recovery needed.")

                        except Exception as state_check_err:
                            # If any check, re-upload, or final start click fails, raise to trigger outer retry
                            raise Exception(f"Error during state verification/recovery: {state_check_err}")

                        # --- 3c. Wait for Swap Completion (Robust Wait + Stall Detection) --- #
                        self.log_message.emit(f"    -> Waiting for swap completion (Attempt {attempt + 1})...")
                        
                        # --- Custom Polling Loop --- #
                        start_wait_time = time.time()
                        overall_timeout = 300 # seconds (5 minutes)
                        stall_timeout = 15 # seconds
                        last_progress_value = "-1" # Initialize to a value that won't match initially
                        last_progress_time = time.time()
                        completion_status = "TIMEOUT"

                        while time.time() - start_wait_time < overall_timeout:
                            # Check stop signal first
                            if self.stop_event.is_set():
                                self.log_message.emit(f"    -> Stop event detected during wait.")
                                completion_status = "STOPPED"
                                break

                            # Check for result image first
                            try:
                                result_elements = self.driver.find_elements(By.XPATH, self.RESULT_IMAGE_XPATH)
                                if result_elements and result_elements[0].is_displayed():
                                    src = result_elements[0].get_attribute('src')
                                    if src and src.startswith('http'):
                                        self.log_message.emit(f"    -> Result image appeared.")
                                        completion_status = "SUCCESS"
                                        break
                            except NoSuchElementException:
                                pass # Result not yet visible

                            # Check progress bar status
                            try:
                                progress_container = self.driver.find_element(By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH)
                                if not progress_container.is_displayed():
                                     self.log_message.emit(f"    -> Progress bar disappeared.")
                                     completion_status = "SUCCESS"
                                     break
                                else:
                                    # Progress bar is visible, check percentage
                                    try:
                                        progress_element = progress_container.find_element(By.XPATH, self.PROGRESS_PERCENTAGE_XPATH)
                                        current_progress = progress_element.text.strip()

                                        if current_progress != last_progress_value:
                                             self.log_message.emit(f"      -> Progress: {current_progress}%") # Log progress changes
                                             last_progress_value = current_progress
                                             last_progress_time = time.time()
                                        elif time.time() - last_progress_time > stall_timeout:
                                            self.logger.warn(self.caller, f"Progress stalled at {current_progress}% for > {stall_timeout}s.")
                                            self.log_message.emit(f"    -> Progress stalled at {current_progress}%. Triggering retry/fail.")
                                            completion_status = "STALLED"
                                            break
                                    except NoSuchElementException:
                                         # Couldn't find percentage text, maybe state changed?
                                         self.logger.warn(self.caller, "Could not find progress percentage text while progress bar visible.")
                                         # Assume it might have finished quickly, check again soon
                                         last_progress_time = time.time() # Reset stall timer
                            except NoSuchElementException:
                                # Progress container not found, assume finished
                                self.log_message.emit(f"    -> Progress container not found (likely finished).")
                                completion_status = "SUCCESS"
                                break

                            # Wait before next check
                            time.sleep(1)
                        # --- End of Custom Polling Loop --- #

                        # --- Handle Loop Outcome --- #
                        if completion_status == "SUCCESS":
                             self.log_message.emit(f"    -> Swap process completed successfully.")
                        elif completion_status == "STOPPED":
                             raise Exception("Stop event detected during wait") # Propagate stop signal
                        elif completion_status == "STALLED":
                             last_task_error = TimeoutException(f"Progress stalled on attempt {attempt + 1}")
                             # Need to trigger retry/failure logic from the outer loop
                             raise last_task_error
                        elif completion_status == "TIMEOUT": # Loop finished due to overall timeout
                             self.logger.warn(self.caller, f"Swap timed out after {overall_timeout}s (Attempt {attempt + 1})")
                             last_task_error = TimeoutException(f"Swap overall timeout on attempt {attempt + 1}")
                             # Need to trigger retry/failure logic from the outer loop
                             raise last_task_error

                        # --- 3d. Get Result & Save (Only if SUCCESS) --- #
                        self.log_message.emit(f"    -> Waiting for result image details...")
                        result_image_locator = (By.XPATH, self.RESULT_IMAGE_XPATH)
                        result_image_element = WebDriverWait(self.driver, 10).until(
                            EC.visibility_of_element_located(result_image_locator)
                        )
                        time.sleep(0.5) # Allow src attribute to potentially stabilize

                        result_url = result_image_element.get_attribute('src')

                        if result_url and result_url.startswith('http'):
                            self.logger.info(self.caller, f"Found result image URL: {result_url[:60]}...")
                            self.log_message.emit(f"    -> Fetching result image...")
                            response = requests.get(result_url, timeout=30)
                            response.raise_for_status()
                            webp_bytes = response.content

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
                            swap_successful = True # Mark success
                            break # Exit retry loop on success
                        else:
                            raise Exception(f"Result image URL not found or invalid: '{result_url}'")

                    except Exception as task_err:
                        # Catch errors within a single attempt
                        self.logger.error(self.caller, f"Error during attempt {attempt + 1}: {task_err}", exc_info=True)
                        last_task_error = task_err # Store the error

                        if attempt < max_retries - 1:
                            # Perform recovery actions before the next attempt
                            self.log_message.emit(f"  -> Error on attempt {attempt + 1}. Performing recovery for attempt {attempt + 2}...")
                            try:
                                # --- Full recovery before EVERY retry --- #
                                self.log_message.emit(f"      -> Clearing local storage...")
                                self.driver.execute_script("window.localStorage.clear();")
                                self.log_message.emit(f"      -> Clearing session storage...")
                                self.driver.execute_script("window.sessionStorage.clear();")
                                self.log_message.emit(f"      -> Clearing cookies...")
                                self.driver.delete_all_cookies()
                                self.log_message.emit(f"      -> Refreshing page...")
                                self.driver.refresh()
                                time.sleep(2)

                                # Check/recover image state
                                recovery_successful = self._recover_image_state(source_image)

                                if not recovery_successful:
                                    # Raise exception if recovery itself failed
                                    raise Exception("Recovery actions (clear storage/cookies/refresh/re-upload) failed.")

                                # --- Wait before next attempt --- #
                                self.log_message.emit(f"      -> Recovery complete. Waiting 3 seconds before attempt {attempt + 2}...")
                                time.sleep(3)
                                # Loop continues to next attempt

                            except Exception as reset_err:
                                self.logger.error(self.caller, f"Error during recovery actions: {reset_err}", exc_info=True)
                                self.log_message.emit(f"      -> [FATAL] Error during recovery: {reset_err}. Failing task.")
                                last_task_error = reset_err # Update error with the recovery error
                                break # Exit retry loop if recovery fails
                        else:
                            # Error on the final attempt (attempt 4)
                            self.log_message.emit(f"  -> Error on final attempt ({max_retries}). Error: {task_err}")
                            break # Exit retry loop, failure will be handled below

                # --- After Retry Loop --- #
                if not swap_successful:
                    # If loop finished without success, emit failure
                    error_msg = f"Failed to process {current_task.source_image.filename} after {max_retries} attempts. Last error: {last_task_error}"
                    self.logger.error(self.caller, error_msg, exc_info=True)
                    self.log_message.emit(f"[ERROR] [{worker_id_short}] {error_msg}")
                    self.task_failed.emit(current_task, str(last_task_error))
                    # Reset Pixnova state? Might need to navigate away/back or refresh?
                    # For now, just try the next source image.

                    # Attempt final reset before NEXT source image (outside retry loop)
                    try:
                        self.log_message.emit(f"  -> Attempting final reset after task failure...")
                        self.driver.refresh()
                        time.sleep(2)
                        self.log_message.emit(f"  -> Re-uploading face {self.face.filename} after failure...")
                        if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH):
                            self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] Failed to re-upload face after failure, stopping worker.")
                            break # Stop worker entirely if face upload fails here
                    except Exception as final_reset_err:
                        self.logger.error(self.caller, f"Error during final reset after task failure: {final_reset_err}")
                        self.log_message.emit(f"[WARN] [{worker_id_short}] Failed final reset, subsequent tasks might fail.")

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
            self.finished.emit() # Signal that the object has finished execution 

    def _upload_file_and_wait(self, input_xpath: str, file_path: str, thumbnail_xpath: str) -> bool:
        """Handles uploading a file and waiting for the thumbnail to appear."""
        worker_id_short = self._worker_id()
        if not self.driver:
            self.log_message.emit(f"[ERROR] [{worker_id_short}] Driver not available for upload.")
            return False
        try:
            file_name = Path(file_path).name
            self.log_message.emit(f"  -> Finding input for {file_name}...")
            upload_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )

            self.log_message.emit(f"  -> Uploading {file_name}...")
            upload_input.send_keys(file_path)
            time.sleep(0.5) # Brief pause after send_keys

            # --- Wait for Thumbnail --- #
            self.log_message.emit(f"  -> Waiting for {file_name} thumbnail to appear...")
            WebDriverWait(self.driver, 120).until( # Wait up to 2 mins for upload processing and thumbnail appearance
                EC.visibility_of_element_located((By.XPATH, thumbnail_xpath))
            )
            self.logger.info(self.caller, f"Thumbnail appeared for {file_name}.")
            self.log_message.emit(f"  -> Thumbnail loaded for {file_name}.")
            return True

        except Exception as e:
            # Log error and return False, let the main run() logic handle task failure
            self.logger.error(self.caller, f"Upload or thumbnail wait error for {file_name}: {e}", exc_info=True)
            self.log_message.emit(f"[ERROR] [{worker_id_short}] Upload/Thumbnail error for {file_name}: {e}")
            return False 