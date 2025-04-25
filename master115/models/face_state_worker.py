import time
import threading
import io
from pathlib import Path
from typing import List, Optional, Tuple, Any # Added Tuple, Any
from enum import Enum, auto # Added Enum

# --- Selenium Imports --- #
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement # Added WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    StaleElementReferenceException, ElementClickInterceptedException # Added ElementClickInterceptedException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Other Imports --- #
import requests
from PIL import Image

# --- Local Imports --- #
from PyQt6.QtCore import QObject, pyqtSignal

# Import models
from .face_swap_models import PersonData, FaceData, SourceImageData, SwapTaskData
from .webdriver_utils import initialize_chrome_driver
from qt_base_app.models import Logger

# --- Define Enums for State/Results --- #
class SwapResult(Enum):
    SUCCESS = auto()
    FAILED = auto()
    TIMEOUT = auto()
    TOO_MANY_REQUESTS = auto()
    STOP_REQUESTED = auto()

class UploadResult(Enum):
    SUCCESS = auto()
    FAILED_TIMEOUT = auto()
    FAILED_STUCK_SPINNER = auto() # If we add spinner check back later
    FAILED_OTHER = auto()
    STOP_REQUESTED = auto()
# -------------------------------------- #

class FaceStateWorker(QObject):
    """
    Worker object using a state machine approach to handle the face swapping process
    for a single face across multiple source images using WebDriver.
    """
    # --- Constants (Copied from FaceSwapWorker) --- #
    PIXNOVA_URL = "https://pixnova.ai/ai-face-swap/#playground"
    PANE_1_SELECTOR = "//div[@id='pane-1']"
    SOURCE_INPUT_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']//input[@type='file']"
    FACE_INPUT_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']//input[@type='file']"
    SOURCE_BUTTON_LOADING_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    FACE_BUTTON_LOADING_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']//button[contains(@class, 'el-button') and contains(@class, 'is-loading')]"
    START_SWAP_BUTTON_XPATH = (
        f"{PANE_1_SELECTOR}"
        "//button[.//span[normalize-space()='Start face swapping']]")
    PROGRESS_BAR_CONTAINER_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'operate-container')]//div[contains(@class, 'loading-container')]"
    RESULT_IMAGE_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'result-container')]//img[contains(@class, 'el-image__inner') and @src]"
    SOURCE_THUMBNAIL_XPATH = f"{PANE_1_SELECTOR}//div[@id='sourceImage']/preceding-sibling::span[contains(@class,'el-avatar')]/img[@src]"
    FACE_THUMBNAIL_XPATH = f"{PANE_1_SELECTOR}//div[@id='faceImage']/preceding-sibling::span[contains(@class,'el-avatar')]/img[@src]"
    POPUP_TITLE_XPATH = "//h2[@id='swal2-title' and contains(text(), 'Too many requests')]"
    POPUP_OK_BUTTON_XPATH = "//div[contains(@class, 'swal2-popup')]//button[contains(@class, 'swal2-confirm') and contains(text(), 'Ok, got it!')]"
    PROGRESS_PERCENTAGE_XPATH = f"{PANE_1_SELECTOR}//div[contains(@class, 'loading-container')]//p/span[contains(@class, 'fs-3')]"
    # -------------------------------------------- #

    # --- Signals (Copied from FaceSwapWorker) --- #
    log_message = pyqtSignal(str)
    task_complete = pyqtSignal(SwapTaskData, str)
    task_failed = pyqtSignal(SwapTaskData, str)
    finished = pyqtSignal()
    # ------------------------------------------- #

    def __init__(self,
                 person: PersonData,
                 face: FaceData,
                 source_images: List[SourceImageData],
                 temp_output_dir: Path,
                 stop_event: threading.Event,
                 run_headless: bool,
                 parent=None):
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = f"FaceStateWorker-{person.name}-{Path(face.filename).stem}" # Unique caller ID

        self.person = person
        self.face = face
        self.source_images = source_images or [] # Ensure it's a list
        self.temp_output_dir = temp_output_dir
        self.stop_event = stop_event
        self.run_headless = run_headless

        self.driver: Optional[WebDriver] = None
        self._need_refresh: bool = False
        self._source_image_index: int = 0

    # --- Core Run Method --- #

    def run(self):
        """Main execution logic using a state machine approach."""
        worker_id = self._worker_id()
        self._log("info", "[run][start]", f"Worker started.")

        try:
            # --- Initial Setup --- #
            self.driver = self._create_browser()
            if self.driver is None: # Should not happen with _create_browser loop, but safety check
                self._log("error", "[run][init_fail]", "Failed to create browser.")
                return # Cannot proceed

            if not self._guarantee_pixnova():
                 self._log("error", "[run][init_fail]", "Failed to navigate to Pixnova initially.")
                 return # Cannot proceed
            # ------------------- #

            self._need_refresh = False # Start clean

            while self._source_image_index < len(self.source_images):
                if self.stop_event.is_set():
                    self._log("info", "[run][stop_signal]", "Stop signal detected.")
                    break

                current_source_image = self.source_images[self._source_image_index]
                task_id = f"Task ({current_source_image.filename})" # Identifier for logs

                self._log("info", "[run][next_task]", f"{task_id} Starting processing.")

                try:
                    # --- State Check & Recovery --- #
                    if self._need_refresh:
                        self._log("info", "[run][refresh_needed]", f"{task_id} Refresh needed, attempting recovery.")
                        if not self._guarantee_fresh_pixnova():
                             self._log("warn", "[run][recovery_fail]", f"{task_id} Failed to guarantee fresh pixnova, attempting browser restart.")
                             if not self._kill_and_restart_browser():
                                 self._log("error", "[run][recovery_fail]", f"{task_id} Critical failure: Cannot restart browser.")
                                 break # Exit main loop if browser cannot be restarted
                        self._need_refresh = False # Reset flag after successful recovery/restart
                    # ------------------------------ #

                    if self.stop_event.is_set(): break

                    # --- Ensure Face Image Uploaded --- #
                    face_present = self._check_face_image_presence()
                    if not face_present:
                        self._log("info", "[run][face_check]", f"{task_id} Face image not present, ensuring upload.")
                        if not self._guarantee_face_upload():
                            self._log("warn", "[run][face_upload_fail]", f"{task_id} Failed to guarantee face upload, requesting refresh.")
                            self._need_refresh = True
                            continue # Skip to next iteration to trigger refresh
                    # ---------------------------------- #

                    if self.stop_event.is_set(): break

                    # --- Ensure Source Image Uploaded --- #
                    source_upload_result = self._guarantee_source_upload(current_source_image)
                    if source_upload_result != UploadResult.SUCCESS:
                        self._log("warn", "[run][source_upload_fail]", f"{task_id} Failed to guarantee source upload ({source_upload_result.name}), requesting refresh.")
                        self._need_refresh = True
                        continue # Skip to next iteration to trigger refresh
                    # ------------------------------------ #

                    if self.stop_event.is_set(): break

                    # --- Check Start Button --- #
                    start_button_state = self._get_start_button_state()
                    if start_button_state != "ENABLED":
                        self._log("warn", "[run][start_button_check]", f"{task_id} Start button not ready (State: {start_button_state}), requesting refresh.")
                        self._need_refresh = True
                        time.sleep(3) # Brief pause before refresh
                        continue # Skip to next iteration to trigger refresh
                    # ------------------------ #

                    if self.stop_event.is_set(): break

                    # --- Perform Face Swap --- #
                    self._log("info", "[run][start_swap]", f"{task_id} Starting face swap process.")
                    swap_result = self._start_faceswap(current_source_image)
                    # ------------------------- #

                    # --- Handle Swap Result --- #
                    if swap_result == SwapResult.SUCCESS:
                        # Assuming _start_faceswap calls _save_swap_result on success
                        self._log("info", "[run][swap_success]", f"{task_id} Face swap successful.")
                        # task_complete signal is emitted within _save_swap_result now
                        # Only increment index on full success
                        self._source_image_index += 1 
                        if self._source_image_index < len(self.source_images):
                            self._log("info", "[run][next_image]", f"Moving to next source image index {self._source_image_index}.")
                        else:
                            self._log("info", "[run][all_done]", f"All source images processed.")
                    elif swap_result == SwapResult.STOP_REQUESTED:
                        self._log("info", "[run][stop_signal]", f"{task_id} Stop requested during swap process.")
                        break # Exit the main loop
                    else: # FAILED, TIMEOUT, TOO_MANY_REQUESTS (after retry)
                        self._log("warn", "[run][swap_fail]", f"{task_id} Face swap failed or timed out ({swap_result.name}), requesting refresh.")
                        # Emit task_failed signal here for specific task failure
                        fail_task_data = SwapTaskData(self.person, self.face, current_source_image, self.temp_output_dir)
                        self.task_failed.emit(fail_task_data, f"Swap process failed with state: {swap_result.name}")
                        self._need_refresh = True
                        # Continue to next iteration to trigger refresh
                    # -------------------------- #
                
                # --- Granular Exception Handling for the Task Loop --- #
                except TimeoutException as e_timeout:
                    # Log TimeoutExceptions specifically as debug
                    self._log("debug", "[run][task_timeout]", f"{task_id} TimeoutException encountered: {e_timeout}")
                    self._need_refresh = True # Assume refresh is needed after timeout
                except (NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e_selenium:
                     # Log common Selenium interaction issues as warnings
                    self._log("warn", "[run][task_selenium_error]", f"{task_id} Selenium interaction error: {type(e_selenium).__name__} - {e_selenium}")
                    self._need_refresh = True # Assume refresh is needed
                except Exception as e_main_loop:
                    # Catch other unexpected errors within a single source image loop
                    self._log("error", "[run][task_exception]", f"{task_id} Unexpected error: {e_main_loop}", exc_info=True)
                    # Emit failure signal
                    fail_task_data = SwapTaskData(self.person, self.face, current_source_image, self.temp_output_dir)
                    self.task_failed.emit(fail_task_data, f"Unexpected error: {e_main_loop}")
                    self._need_refresh = True # Request refresh on next iteration
                # --- End Granular Exception Handling --- #
                # Loop continues to next iteration if continue wasn't hit earlier or error occurred

            # --- End of main while loop --- #
            self._log("info", "[run][exit_loop]", "Exited main processing loop.")

        except Exception as e_outer:
            # Catch errors during initial setup or very unexpected issues
            self._log("error", "[run][outer_exception]", f"Outer exception caught: {e_outer}", exc_info=True)

        finally:
            # --- Cleanup --- #
            self._log("info", "[run][cleanup]", "Performing final cleanup.")
            self._cleanup_driver()
            self._log("info", "[run][finished]", "Worker finished execution.")
            self.finished.emit()
            # --------------- #

    # --- Browser Management --- #

    def _create_browser(self) -> Optional[WebDriver]:
        """Creates and returns a WebDriver instance, retrying indefinitely until success or stop."""
        attempt = 1
        while True:
            if self.stop_event.is_set(): # Check at loop start
                 self._log("info", "[_create_browser][stop_signal]", "Stop requested during browser creation.")
                 return None
            step_id = f"[create_browser][attempt_{attempt}]"
            try:
                self._log("info", step_id, "Attempting to initialize WebDriver.")
                driver = initialize_chrome_driver(headless=self.run_headless)
                if driver:
                    self._log("info", step_id, "WebDriver initialized successfully.")
                    return driver
                else:
                    # initialize_chrome_driver handles its own errors, returning None is failure
                    self._log("warn", step_id, "initialize_chrome_driver returned None.")
            except WebDriverException as e:
                self._log("warn", step_id, f"WebDriverException during creation: {e}")
            except Exception as e:
                 self._log("error", step_id, f"Unexpected error during creation: {e}", exc_info=True)

            # If initialization failed, wait and retry
            self._log("info", step_id, "Waiting 5 seconds before retry...")
            if self.stop_event.wait(5): # Wait with check
                self._log("info", "[_create_browser][stop_signal]", "Stop requested while waiting for retry.")
                return None
            attempt += 1

    def _guarantee_pixnova(self) -> bool:
        """Ensures the current driver is navigated to the Pixnova URL, retrying indefinitely."""
        if not self.driver:
            self._log("error", "[_guarantee_pixnova]", "Driver is None, cannot navigate.")
            return False

        attempt = 1
        while True:
            if self.stop_event.is_set(): # Check at loop start
                 self._log("info", "[_guarantee_pixnova][stop_signal]", "Stop requested during navigation.")
                 return False
            step_id = f"[_guarantee_pixnova][attempt_{attempt}]"
            try:
                current_url = ""
                try:
                    current_url = self.driver.current_url
                except Exception: # Handle cases where driver might crash getting URL
                    pass
                
                if self.PIXNOVA_URL in current_url:
                    self._log("info", step_id, "Already on Pixnova URL.")
                    return True

                self._log("info", step_id, f"Navigating to {self.PIXNOVA_URL}")
                self.driver.get(self.PIXNOVA_URL)
                # Basic check after navigation (e.g., wait for title or a key element)
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, self.PANE_1_SELECTOR))
                )
                self._log("info", step_id, "Navigation successful.")
                return True
            except TimeoutException:
                self._log("warn", step_id, "TimeoutException waiting for element after navigation.")
            except WebDriverException as e:
                self._log("warn", step_id, f"WebDriverException during navigation: {e}")
            except Exception as e:
                 self._log("error", step_id, f"Unexpected error during navigation: {e}", exc_info=True)

            # If navigation failed, wait and retry
            self._log("info", step_id, "Waiting 5 seconds before retry...")
            if self.stop_event.wait(5): # Wait with check
                self._log("info", "[_guarantee_pixnova][stop_signal]", "Stop requested while waiting for retry.")
                return False
            attempt += 1

    def _guarantee_fresh_pixnova(self) -> bool:
        """Clears storage/cookies and guarantees navigation to Pixnova."""
        step_id = "[_guarantee_fresh_pixnova]"
        if not self.driver:
            self._log("error", step_id, "Driver is None, cannot refresh.")
            return False
            
        if self.stop_event.is_set(): return False # Check before action

        try:
            self._log("info", step_id, "Clearing local storage...")
            self.driver.execute_script("window.localStorage.clear();")
            self._log("info", step_id, "Clearing session storage...")
            self.driver.execute_script("window.sessionStorage.clear();")
            self._log("info", step_id, "Clearing cookies...")
            self.driver.delete_all_cookies()
            self._log("info", step_id, "Refreshing page...")
            self.driver.refresh()
            # Wait briefly after refresh
            time.sleep(2)
        except WebDriverException as e:
            self._log("warn", step_id, f"WebDriverException during clear/refresh: {e}")
            # Continue to guarantee navigation anyway
        except Exception as e:
            self._log("error", step_id, f"Unexpected error during clear/refresh: {e}", exc_info=True)
            # Continue to guarantee navigation anyway

        if self.stop_event.is_set(): return False # Check after potentially long action
        return self._guarantee_pixnova()

    def _kill_and_restart_browser(self) -> bool:
        """Forcefully closes the current browser and attempts to create/navigate a new one."""
        step_id = "[_kill_and_restart_browser]"
        self._log("warn", step_id, "Attempting to kill and restart browser.")
        self._cleanup_driver() # Attempt graceful quit first

        # --- Force Kill (Placeholder - OS specific if needed) ---
        # If self.driver.quit() fails reliably, OS-level process kill might be needed
        # For now, rely on self.driver = None and _create_browser
        # ------------------------------------------------------- #

        self.driver = self._create_browser()
        if self.driver is None:
            self._log("error", step_id, "Failed to create new browser after kill.")
            return False

        if self.stop_event.is_set(): return False # Check after potentially long action
        if not self._guarantee_pixnova():
             self._log("error", step_id, "Failed to navigate to Pixnova after restarting browser.")
             return False

        self._log("info", step_id, "Browser successfully restarted and navigated.")
        return True

    # --- Upload Logic --- #

    def _check_face_image_presence(self) -> bool:
        """Checks if the face thumbnail seems present."""
        step_id = "[_check_face_image_presence]"
        if not self.driver: return False
        if self.stop_event.is_set(): return False # Quick check
        try:
            # Using simplified check: exists in DOM and has valid src
            elements = self.driver.find_elements(By.XPATH, self.FACE_THUMBNAIL_XPATH)
            if elements:
                src = elements[0].get_attribute('src')
                if src and (src.startswith('blob:') or src.startswith('http:')):
                    self._log("debug", step_id, "Face thumbnail found with valid src.")
                    return True
        except Exception as e:
            self._log("warn", step_id, f"Error checking face presence: {e}")
        self._log("debug", step_id, "Face thumbnail not found or src invalid.")
        return False

    def _guarantee_face_upload(self) -> bool:
        """Ensures the face image is uploaded, retrying with page refresh on failure."""
        if not self.driver: return False
        attempt = 1
        while True:
            if self.stop_event.is_set(): # Check at loop start
                 self._log("info", "[_guarantee_face_upload][stop_signal]", "Stop requested.")
                 return False
            step_id = f"[_guarantee_face_upload][attempt_{attempt}]"
            try:
                self._log("info", step_id, f"Attempting to upload face: {self.face.filename}")
                upload_result = self._upload_file_basic_wait(
                    self.FACE_INPUT_XPATH,
                    str(self.face.path),
                    self.FACE_THUMBNAIL_XPATH
                )

                if upload_result == UploadResult.SUCCESS:
                    self._log("info", step_id, "Face upload successful.")
                    return True
                elif upload_result == UploadResult.STOP_REQUESTED:
                     self._log("info", step_id, "Stop requested during face upload wait.")
                     return False
                else: # FAILED_TIMEOUT or FAILED_OTHER
                    self._log("warn", step_id, f"Face upload failed ({upload_result.name}). Refreshing page.")
                    self.driver.refresh()
                    time.sleep(3) # Wait after refresh
            except WebDriverException as e:
                 self._log("warn", step_id, f"WebDriverException during face upload attempt: {e}")
                 # Potentially try refresh or browser restart? For now, just retry loop.
                 time.sleep(5)
            except Exception as e:
                self._log("error", step_id, f"Unexpected error during face upload attempt: {e}", exc_info=True)
                time.sleep(5) # Wait before retry on unexpected error

            attempt += 1

    def _guarantee_source_upload(self, source_image: SourceImageData) -> UploadResult:
        """Ensures the source image is uploaded. Returns status."""
        if not self.driver: return UploadResult.FAILED_OTHER
        attempt = 1
        while True: # Limit attempts? For now, retry indefinitely like other guarantees
            if self.stop_event.is_set(): # Check at loop start
                self._log("info", "[_guarantee_source_upload][stop_signal]", "Stop requested.")
                return UploadResult.STOP_REQUESTED
            step_id = f"[_guarantee_source_upload][attempt_{attempt}]"
            try:
                self._log("info", step_id, f"Attempting to upload source: {source_image.filename}")
                upload_result = self._upload_file_basic_wait(
                    self.SOURCE_INPUT_XPATH,
                    str(source_image.path),
                    self.SOURCE_THUMBNAIL_XPATH
                )

                if upload_result == UploadResult.SUCCESS:
                    self._log("info", step_id, "Source upload successful.")
                    return UploadResult.SUCCESS
                elif upload_result == UploadResult.STOP_REQUESTED:
                     self._log("info", step_id, "Stop requested during source upload wait.")
                     return UploadResult.STOP_REQUESTED
                else: # FAILED_TIMEOUT or FAILED_OTHER
                    self._log("warn", step_id, f"Source upload failed ({upload_result.name}). Returning failure.")
                    # Per pseudo-code/clarification: If upload fails, let main loop handle refresh.
                    return upload_result # Return the specific failure type
                    
                    # --- Removed complex checks after failure --- #
                    # # If simple upload wait failed, check button/spinner state
                    # # Note: Spinner check might be less reliable now
                    # is_spinner = self._is_element_visible(self.SOURCE_BUTTON_LOADING_XPATH)
                    # if is_spinner:
                    #     self._log("warn", step_id, "Source upload failed and spinner is visible. Assuming stuck.")
                    #     return UploadResult.FAILED_STUCK_SPINNER # Indicate stuck state

                    # # Check button state (maybe redundant if spinner check works)
                    # # source_button_state = self._get_source_upload_button_state()
                    # # if source_button_state != "ENABLED":
                    # #     self._log("warn", step_id, f"Source upload failed and button is not enabled ({source_button_state}). Assuming stuck.")
                    # #     return UploadResult.FAILED_OTHER # Stuck

                    # # If not obviously stuck, wait and retry upload attempt
                    # self._log("info", step_id, "Source upload failed, but not obviously stuck. Retrying upload.")
                    # time.sleep(3)
                    # --- End Removed complex checks --- #

            except WebDriverException as e:
                 self._log("warn", step_id, f"WebDriverException during source upload attempt: {e}")
                 time.sleep(5) # Wait before retry
            except Exception as e:
                self._log("error", step_id, f"Unexpected error during source upload attempt: {e}", exc_info=True)
                time.sleep(5) # Wait before retry

            attempt += 1

    def _upload_file_basic_wait(self, input_xpath: str, file_path: str, thumbnail_xpath: str) -> UploadResult:
        """Uploads file and waits for thumbnail existence with valid src using hard timeout."""
        step_id = "[_upload_file_basic_wait]"
        file_name = Path(file_path).name
        hard_timeout = 180 # seconds (3 minutes) - Reduced from old worker
        if not self.driver: return UploadResult.FAILED_OTHER

        try:
            self._log("debug", step_id, f"Finding input element for {file_name}")
            upload_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )

            self._log("debug", step_id, f"Sending file path: {file_path}")
            upload_input.send_keys(file_path)
            # No sleep here unless needed

            self._log("debug", step_id, f"Waiting for thumbnail: {thumbnail_xpath} (max {hard_timeout}s)")
            start_time = time.time()
            while time.time() - start_time < hard_timeout:
                if self.stop_event.is_set(): return UploadResult.STOP_REQUESTED # Check inside loop
                # Use simplified check: exists in DOM & valid src
                try:
                    elements = self.driver.find_elements(By.XPATH, thumbnail_xpath)
                    if elements:
                        src = elements[0].get_attribute('src')
                        if src and (src.startswith('blob:') or src.startswith('http:')):
                            self._log("info", step_id, f"Thumbnail found with valid src for {file_name}.")
                            return UploadResult.SUCCESS
                except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
                    pass # Ignore errors during polling, loop will continue
                if self.stop_event.is_set(): return UploadResult.STOP_REQUESTED # Check before sleep
                time.sleep(0.5) # Poll interval

            # If loop finishes, hard timeout was reached
            self._log("warn", step_id, f"Hard timeout ({hard_timeout}s) reached waiting for {file_name} thumbnail.")
            return UploadResult.FAILED_TIMEOUT

        except FileNotFoundError:
             self._log("error", step_id, f"File not found for upload: {file_path}")
             return UploadResult.FAILED_OTHER
        except (WebDriverException, TimeoutException) as e:
            self._log("warn", step_id, f"WebDriver/TimeoutException during upload/wait for {file_name}: {e}")
            return UploadResult.FAILED_OTHER
        except Exception as e:
            self._log("error", step_id, f"Unexpected error during upload/wait for {file_name}: {e}", exc_info=True)
            return UploadResult.FAILED_OTHER

    # --- Face Swap Execution --- #

    def _get_start_button_state(self) -> str:
        """Checks the state of the start button. Returns 'ENABLED', 'DISABLED', or 'NOT_FOUND'."""
        step_id = "[_get_start_button_state]"
        if not self.driver: return "NOT_FOUND"
        try:
            button = WebDriverWait(self.driver, 5).until( # Short wait for presence
                 EC.presence_of_element_located((By.XPATH, self.START_SWAP_BUTTON_XPATH))
            )
            # Check is_enabled() AFTER finding it
            if button.is_enabled():
                self._log("debug", step_id, "Start button found and enabled.")
                return "ENABLED"
            else:
                self._log("debug", step_id, "Start button found but disabled.")
                return "DISABLED"
        except TimeoutException:
            self._log("debug", step_id, "Start button not found within timeout.")
            return "NOT_FOUND"
        except Exception as e:
            self._log("warn", step_id, f"Error checking start button state: {e}")
            return "NOT_FOUND" # Treat other errors as not found/ready

    def _click_start_button(self) -> bool:
        """Attempts to click the start button."""
        step_id = "[_click_start_button]"
        if not self.driver: return False
        try:
            # Ensure it's clickable before clicking
            button = WebDriverWait(self.driver, 5).until(
                 EC.element_to_be_clickable((By.XPATH, self.START_SWAP_BUTTON_XPATH))
            )
            self._log("info", step_id, "Clicking start button.")
            button.click()
            return True
        except TimeoutException:
             self._log("warn", step_id, "Timeout waiting for start button to be clickable.")
             return False
        except ElementClickInterceptedException:
             self._log("warn", step_id, "Start button click intercepted (likely by overlay/popup).")
             # Could check for popup here again if needed
             return False
        except Exception as e:
            self._log("error", step_id, f"Error clicking start button: {e}", exc_info=True)
            return False

    def _start_faceswap(self, source_image: SourceImageData) -> SwapResult:
        """Attempts to start the swap process and waits for the result."""
        step_id = f"[_start_faceswap][{source_image.filename}]"
        if not self.driver: return SwapResult.FAILED

        # Double check button state before proceeding
        button_state = self._get_start_button_state()
        if button_state != "ENABLED":
            self._log("warn", step_id, f"Start button not enabled ({button_state}) before swap attempt.")
            return SwapResult.FAILED

        # --- Get Previous Result State --- #
        previous_result_src = self._search_result_image()
        # --------------------------------- #

        self._log("info", step_id, "Attempting first click on start button.")
        first_click_ok = self._click_start_button()
        
        # --- Handle First Click Outcome --- #
        if not first_click_ok:
            self._log("warn", step_id, "First click failed.")
            # Check for popup immediately after failed click
            if self._search_too_many_requests_popup(dismiss=True):
                self._log("info", step_id, "Popup dismissed after first click failed. Attempting second click.")
                time.sleep(3) # Wait after dismissal
                second_click_ok = self._click_start_button()
                if not second_click_ok:
                    self._log("warn", step_id, "Second click failed after popup dismissal.")
                    # Failure Case 1: Too many requests even after dismissal/retry
                    return SwapResult.TOO_MANY_REQUESTS 
                # If second click OK, proceed to wait below
                self._log("info", step_id, "Second click successful after popup dismissal.")
            else:
                # First click failed, no obvious popup
                self._log("warn", step_id, "First click failed, no popup detected.")
                # Failure Case 2: General click failure
                return SwapResult.FAILED 
        # --------------------------------- #
        
        # If first click was successful OR second click after popup was successful:
        self._log("info", step_id, "Start button clicked successfully, awaiting result.")
        time.sleep(1) # Brief pause after click

        # --- Wait for Result --- #
        swap_result = self._await_face_swap_result(previous_result_src)
        # ----------------------- #

        # --- Handle TOO_MANY_REQUESTS during wait --- #
        if swap_result == SwapResult.TOO_MANY_REQUESTS:
            self._log("warn", step_id, "Received TOO_MANY_REQUESTS during await phase.")
            # Try to dismiss if it reappeared
            if self._search_too_many_requests_popup(dismiss=True): 
                self._log("info", step_id, "Popup dismissed during await phase. Attempting final click.")
                time.sleep(3) # Wait after dismissal
                final_click_ok = self._click_start_button()
                if not final_click_ok:
                    self._log("error", step_id, "Final click failed after TOO_MANY_REQUESTS during await.")
                    # Failure Case 3: Cannot recover from popup during wait
                    return SwapResult.FAILED 
                
                # If final click succeeded, wait again
                self._log("info", step_id, "Final click succeeded, awaiting result again.")
                time.sleep(1)
                swap_result = self._await_face_swap_result(previous_result_src) # Wait again
            else:
                self._log("warn", step_id, "TOO_MANY_REQUESTS reported by await, but popup not found for recovery click.")
                # Failure Case 4: Inconsistent state
                return SwapResult.FAILED 
        # ------------------------------------------ #

        # Return final result after all checks/retries
        self._log("info", step_id, f"Final swap result: {swap_result.name}")
        return swap_result

    def _await_face_swap_result(self, previous_result_src: Optional[str]) -> SwapResult:
        """Waits for the swap result, checking progress, popups, and timeouts."""
        step_id = "[_await_face_swap_result]"
        if not self.driver: return SwapResult.FAILED

        prev_progress_percentage = -1
        time_percentage_update = time.time()
        start_time = time.time()
        progress_found_ever = False # Track if % ever appeared
        
        # Reduced timeouts compared to pseudo-code, adjust as needed
        MAX_TIMEOUT_NO_PROGRESS = 60 # Max wait if NO progress % ever appears (1 min)
        MAX_PERCENTAGE_STALL = 30 # Max wait if progress % STALLS (30 sec)
        OVERALL_TIMEOUT = 300 # Absolute max wait (5 min)

        while time.time() - start_time < OVERALL_TIMEOUT:
            if self.stop_event.is_set(): return SwapResult.STOP_REQUESTED # Check inside loop
            try:
                # 1. Check for New Result Image
                current_result_src = self._search_result_image()
                if current_result_src and current_result_src != previous_result_src:
                    self._log("info", step_id, "New result image detected.")
                    if self._save_swap_result(current_result_src):
                         return SwapResult.SUCCESS
                    else:
                         self._log("error", step_id, "Failed to save the detected result image.")
                         return SwapResult.FAILED # Treat save failure as critical

                # 2. Check for Popup (non-dismissing check first)
                if self._search_too_many_requests_popup(dismiss=False):
                    self._log("warn", step_id, "'Too Many Requests' popup appeared during wait.")
                    # Return status to let _start_faceswap handle dismissal and retry click
                    return SwapResult.TOO_MANY_REQUESTS 

                # 3. Check for Progress Percentage Update / Stall
                progress_percent = self._search_progress_percentage()
                
                if progress_percent is not None: # Progress % element found
                    progress_found_ever = True # Mark that we saw progress at least once
                    if progress_percent != prev_progress_percentage:
                        self._log("debug", step_id, f"Progress updated: {progress_percent}%")
                        prev_progress_percentage = progress_percent
                        time_percentage_update = time.time() # Reset stall timer
                    elif time.time() - time_percentage_update > MAX_PERCENTAGE_STALL:
                         # Progress found previously, but hasn't changed for too long
                         self._log("warn", step_id, f"Progress stalled at {progress_percent}% for > {MAX_PERCENTAGE_STALL}s.")
                         return SwapResult.TIMEOUT # Timeout due to stall
                
                elif not progress_found_ever and (time.time() - start_time > MAX_TIMEOUT_NO_PROGRESS):
                     # Progress % has NEVER appeared, and waited long enough
                     self._log("warn", step_id, f"No progress percentage found after {MAX_TIMEOUT_NO_PROGRESS}s.")
                     return SwapResult.TIMEOUT # Timeout due to no progress indication

                # 4. Brief pause before next check
                time.sleep(1)

            except TimeoutException as e_timeout:
                # Log TimeoutExceptions from internal waits as debug
                self._log("debug", step_id, f"TimeoutException during wait loop check: {e_timeout}")
                # Allow loop to continue, rely on overall timeout or stall detection
            except (NoSuchElementException, StaleElementReferenceException) as e_selenium:
                 # Log common Selenium errors during checks as warnings, continue loop
                 self._log("warn", step_id, f"Selenium check error during wait loop: {type(e_selenium).__name__}")
                 time.sleep(1) # Pause longer after error
            except WebDriverException as e:
                # Log other WebDriver errors but continue loop if possible
                self._log("warn", step_id, f"WebDriverException during wait loop: {e}")
                time.sleep(1) # Pause longer after error
            except Exception as e:
                 self._log("error", step_id, f"Unexpected error during wait loop: {e}", exc_info=True)
                 return SwapResult.FAILED # Exit on unexpected errors

        # If loop finishes, overall timeout was reached
        self._log("warn", step_id, f"Overall timeout ({OVERALL_TIMEOUT}s) reached.")
        return SwapResult.TIMEOUT

    # --- Helper Functions for State Checking / Interaction --- #

    def _search_result_image(self) -> Optional[str]:
        """Tries to find the result image and returns its src if valid, else None."""
        if not self.driver: return None
        try:
            elements = self.driver.find_elements(By.XPATH, self.RESULT_IMAGE_XPATH)
            if elements and elements[0].is_displayed():
                src = elements[0].get_attribute('src')
                if src and src.startswith('http'): # Result image should have http src
                    return src
        except (NoSuchElementException, StaleElementReferenceException):
            pass # Element not present or stale
        except Exception as e:
             self._log("warn", "[_search_result_image]", f"Error finding result image: {e}")
        return None

    def _search_too_many_requests_popup(self, dismiss: bool = False) -> bool:
        """Checks for the 'Too Many Requests' popup and optionally dismisses it."""
        if not self.driver: return False
        step_id = "[_search_too_many_requests_popup]"
        try:
            title = WebDriverWait(self.driver, 0.5).until( # Very short wait
                EC.visibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
            )
            if title:
                self._log("warn", step_id, "Popup detected.")
                if dismiss:
                    self._log("info", step_id, "Dismissing popup.")
                    try:
                        ok_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, self.POPUP_OK_BUTTON_XPATH))
                        )
                        ok_button.click()
                        WebDriverWait(self.driver, 5).until(
                             EC.invisibility_of_element_located((By.XPATH, self.POPUP_TITLE_XPATH))
                        )
                        self._log("info", step_id, "Popup dismissed.")
                    except Exception as e_dismiss:
                        self._log("error", step_id, f"Failed to dismiss popup: {e_dismiss}")
                        # Still return True as popup WAS detected
                return True
        except TimeoutException:
            pass # Popup not visible within the short wait
        except Exception as e:
            self._log("warn", step_id, f"Error checking for popup: {e}")
        return False

    def _search_progress_percentage(self) -> Optional[int]:
        """Tries to find and parse the progress percentage. Returns int or None."""
        if not self.driver: return None
        try:
            # Check if progress bar container is visible first
            container = self.driver.find_element(By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH)
            if not container.is_displayed():
                return None # Container gone, no progress to report

            # Find percentage element within container
            percentage_element = container.find_element(By.XPATH, self.PROGRESS_PERCENTAGE_XPATH)
            text = percentage_element.text.strip().replace('%','')
            return int(text)
        except (NoSuchElementException, StaleElementReferenceException):
            return None # Element not found or stale
        except (ValueError, TypeError):
            return None # Cannot parse text to int
        except Exception as e:
             self._log("warn", "[_search_progress_percentage]", f"Error finding progress percentage: {e}")
             return None

    def _is_element_visible(self, xpath: str) -> bool:
         """Checks if an element exists and is displayed."""
         if not self.driver: return False
         try:
             element = self.driver.find_element(By.XPATH, xpath)
             return element.is_displayed()
         except (NoSuchElementException, StaleElementReferenceException):
             return False
         except Exception:
             return False # Treat other errors as not visible

    # --- Result Handling --- #

    def _save_swap_result(self, result_url: str) -> bool:
        """Fetches the result image and saves it."""
        step_id = "[_save_swap_result]"
        # Need the current source image to create task data and filename
        if self._source_image_index >= len(self.source_images):
             self._log("error", step_id, "Source image index out of bounds, cannot save.")
             return False
        current_source_image = self.source_images[self._source_image_index]
        task_id = f"Task ({current_source_image.filename})"

        try:
            self._log("info", step_id, f"{task_id} Fetching result image from URL...")
            response = requests.get(result_url, timeout=30)
            response.raise_for_status()
            webp_bytes = response.content

            self._log("info", step_id, f"{task_id} Saving result as JPG...")
            face_stem = Path(self.face.filename).stem
            source_stem = Path(current_source_image.filename).stem
            output_filename = f"{self.person.name} {face_stem} {source_stem}.jpg"
            output_path = self.temp_output_dir / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            image_stream = io.BytesIO(webp_bytes)
            img = Image.open(image_stream)
            if img.mode == 'RGBA': img = img.convert('RGB')
            img.save(str(output_path), "JPEG", quality=75)

            self._log("info", step_id, f"{task_id} Saved result to {output_path}")

            # --- Emit task_complete signal --- #
            task_data = SwapTaskData(
                 person=self.person,
                 face=self.face,
                 source_image=current_source_image,
                 output_dir=self.temp_output_dir
            )
            self.task_complete.emit(task_data, str(output_path))
            # --------------------------------- #
            return True

        except requests.exceptions.RequestException as e:
             self._log("error", step_id, f"{task_id} Error fetching result image URL {result_url}: {e}")
             return False
        except (IOError, OSError, Image.Error) as e:
             self._log("error", step_id, f"{task_id} Error saving/converting image to {output_path}: {e}")
             return False
        except Exception as e:
             self._log("error", step_id, f"{task_id} Unexpected error saving result: {e}", exc_info=True)
             return False

    # --- Utility Methods --- #

    def _cleanup_driver(self):
        """Safely quits the WebDriver instance if running in headless mode."""
        step_id = "[_cleanup_driver]"
        if self.driver:
            if self.run_headless:
                self._log("info", step_id, "Quitting WebDriver instance (headless mode).")
                try:
                    self.driver.quit()
                except Exception as e:
                    self._log("error", step_id, f"Error quitting WebDriver: {e}")
                finally:
                    self.driver = None # Ensure reference is cleared even if quit fails
            else:
                 self._log("info", step_id, "Skipping WebDriver quit() for manual inspection (visible mode).")
                 # Keep driver reference for inspection, but it won't be reused.
                 # No need to set self.driver = None here if we want external inspection
        else:
            self._log("debug", step_id, "No WebDriver instance to clean up.")

    def _worker_id(self) -> str:
        """Helper for shorter log messages."""
        face_filename_no_ext = Path(self.face.filename).stem
        return f"{self.person.name}/{face_filename_no_ext}"

    def _log(self, level: str, step_id: str, message: str, exc_info=False):
        """Helper for consistent logging."""
        log_prefix = f"[{self._worker_id()}]{step_id}"
        full_message = f"{log_prefix} {message}"

        # Log using self.logger
        log_func = getattr(self.logger, level, self.logger.info)
        log_func(self.caller, full_message, exc_info=exc_info)

        # Emit signal for UI
        # Add level prefix to UI message for clarity?
        ui_prefix_map = {
            "debug": "[DEBUG]", "info": "[INFO]", "warn": "[WARN]", "error": "[ERROR]"
        }
        ui_prefix = ui_prefix_map.get(level, "[INFO]")
        self.log_message.emit(f"{ui_prefix} {full_message}")
