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
            self.log_message.emit(f"[{self._worker_id()}] Cleaning up WebDriver...")
            try:
                self.driver.quit()
                self.logger.info(self.caller, "WebDriver quit successfully.")
            except Exception as e:
                self.logger.error(self.caller, f"Error quitting WebDriver: {e}")
            finally:
                self.driver = None

    def _worker_id(self) -> str:
        """Helper for shorter log messages."""
        # Extract filename without extension for brevity
        face_filename_no_ext = Path(self.face.filename).stem 
        return f"{self.person.name}/{face_filename_no_ext}"

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

                try:
                    # --- 3a. Upload Source Image --- #
                    self.log_message.emit(f"  -> Uploading source: {source_image.filename}...")
                    # Use SOURCE_THUMBNAIL_XPATH for confirmation
                    if not self._upload_file_and_wait(self.SOURCE_INPUT_XPATH, str(source_image.path), self.SOURCE_THUMBNAIL_XPATH):
                        raise Exception(f"Source upload failed for {source_image.filename}")
                    self.log_message.emit(f"  -> Source upload complete.")

                    # --- 3b. Click Start Button --- #
                    self.log_message.emit(f"  -> Waiting for Start button...")
                    start_button_locator = (By.XPATH, self.START_SWAP_BUTTON_XPATH)
                    start_button = WebDriverWait(self.driver, 60).until(
                        EC.element_to_be_clickable(start_button_locator)
                    )
                    self.log_message.emit(f"  -> Clicking Start button...")
                    start_button.click()
                    self.log_message.emit(f"  -> Start button clicked.")

                    # --- 3c. Wait for Swap Completion (Progress Bar) --- #
                    self.log_message.emit(f"  -> Waiting for swap process to start...")
                    progress_locator = (By.XPATH, self.PROGRESS_BAR_CONTAINER_XPATH)
                    WebDriverWait(self.driver, 30).until(
                        EC.visibility_of_element_located(progress_locator)
                    )
                    self.log_message.emit(f"  -> Swapping in progress (waiting for finish)...")
                    WebDriverWait(self.driver, 300).until( # 5 min timeout
                        EC.invisibility_of_element_located(progress_locator)
                    )
                    self.log_message.emit(f"  -> Swap process likely complete.")

                    # --- 3d. Get Result & Save --- #
                    self.log_message.emit(f"  -> Waiting for result image...")
                    result_image_locator = (By.XPATH, self.RESULT_IMAGE_XPATH)
                    result_image_element = WebDriverWait(self.driver, 30).until(
                         EC.visibility_of_element_located(result_image_locator)
                    )
                    time.sleep(0.5) # Allow src attribute to potentially stabilize

                    result_url = result_image_element.get_attribute('src')

                    if result_url and result_url.startswith('http'): # Basic validation
                        self.logger.info(self.caller, f"Found result image URL: {result_url[:60]}...")
                        self.log_message.emit(f"  -> Fetching result image...")
                        try:
                            response = requests.get(result_url, timeout=30)
                            response.raise_for_status()
                            webp_bytes = response.content

                            self.log_message.emit(f"  -> Saving result as JPG...")
                            # Use stem to remove extensions from components
                            face_stem = Path(self.face.filename).stem
                            source_stem = Path(source_image.filename).stem
                            output_filename = f"{self.person.name} {face_stem} {source_stem}.jpg"
                            output_path = self.temp_output_dir / output_filename
                            output_path.parent.mkdir(parents=True, exist_ok=True)

                            # Use Pillow to convert and save
                            image_stream = io.BytesIO(webp_bytes)
                            img = Image.open(image_stream)
                            if img.mode == 'RGBA': img = img.convert('RGB')
                            img.save(str(output_path), "JPEG", quality=75) # Save with 75% quality
                            
                            self.logger.info(self.caller, f"Saved result to {output_path}")
                            self.task_complete.emit(current_task, str(output_path))

                        except requests.exceptions.RequestException as req_err:
                            raise Exception(f"Failed to download result image: {req_err}")
                        except Exception as img_err:
                            raise Exception(f"Failed to process/save image: {img_err}")
                    else:
                        raise Exception(f"Result image URL not found or invalid: '{result_url}'")

                except Exception as task_err:
                    # Log and signal failure for this specific task, then continue
                    error_msg = f"Error processing {current_task.source_image.filename}: {task_err}"
                    self.logger.error(self.caller, error_msg, exc_info=True)
                    self.log_message.emit(f"[ERROR] [{worker_id_short}] {error_msg}")
                    self.task_failed.emit(current_task, str(task_err))
                    # Reset Pixnova state? Might need to navigate away/back or refresh?
                    # For now, just try the next source image.
                    time.sleep(1) # Small pause before next attempt
                    try: # Attempt a page refresh to reset state before next image
                         self.log_message.emit(f"  -> Refreshing page after error...")
                         if self.driver: self.driver.refresh()
                         time.sleep(2) # Wait for refresh
                         # Re-upload face after refresh!
                         self.log_message.emit(f"[{worker_id_short}] Re-uploading face: {self.face.filename} after error...")
                         # Use FACE_THUMBNAIL_XPATH for confirmation
                         if not self._upload_file_and_wait(self.FACE_INPUT_XPATH, str(self.face.path), self.FACE_THUMBNAIL_XPATH):
                             self.log_message.emit(f"[FATAL ERROR] [{worker_id_short}] Failed to re-upload face after error, stopping worker.")
                             break # Stop processing further images if face re-upload fails
                    except Exception as refresh_err:
                         self.logger.error(self.caller, f"Error refreshing page after task error: {refresh_err}")
                         self.log_message.emit(f"[ERROR] [{worker_id_short}] Failed to refresh page after error, attempting next image anyway.")

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