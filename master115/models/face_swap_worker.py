# ./master115/models/face_swap_worker.py
import time
import threading
from pathlib import Path
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal

# Import models (now from the same directory)
from .face_swap_models import PersonData, FaceData, SourceImageData, SwapTaskData
from qt_base_app.models import Logger

class FaceSwapWorker(QObject):
    """
    Worker object to handle the face swapping process for a single face
    across multiple source images using WebDriver.
    """
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

    def run(self):
        """The main execution method for the worker object."""
        self.logger.info(self.caller, f"Worker started for face '{self.face.filename}'.")
        self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Started.")

        try:
            # --- WebDriver Initialization (Simulation for Milestone 2) --- #
            self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Initializing WebDriver (Simulated)...")
            time.sleep(0.5) # Simulate init time
            self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Navigating to service (Simulated)...")
            time.sleep(0.2)
            self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Uploading face image '{self.face.filename}' (Simulated)...")
            time.sleep(0.3)
            # ---------------------------------------------------------- #

            # --- Process Source Images --- #
            for source_image in self.source_images:
                # Check for stop signal before starting next task
                if self.stop_event.is_set():
                    self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Stop signal received. Aborting remaining tasks.")
                    break # Exit the loop

                self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Processing source: {source_image.filename}")

                # Create SwapTaskData for this specific operation
                current_task = SwapTaskData(
                    person=self.person,
                    face=self.face,
                    source_image=source_image,
                    output_dir=self.temp_output_dir
                )

                try:
                    # --- Simulate Swap Task --- # 
                    self.log_message.emit(f"  -> Uploading source '{source_image.filename}' (Simulated)...")
                    time.sleep(0.2)
                    self.log_message.emit(f"  -> Performing swap (Simulated)...")
                    time.sleep(1.0) # Simulate swap time
                    self.log_message.emit(f"  -> Downloading result (Simulated)...")
                    time.sleep(0.3)

                    # --- Simulate Result File Creation --- #
                    output_filename = f"{self.person.name} {self.face.filename} {source_image.filename}.jpg"
                    output_path = self.temp_output_dir / output_filename
                    
                    # Create an empty dummy file
                    output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure Temp dir exists
                    output_path.touch() # Create the file
                    self.logger.debug(self.caller, f"Created dummy result file: {output_path}")
                    # ---------------------------------- #

                    self.log_message.emit(f"  -> Swap complete for {current_task.source_image.filename}. Result: {output_filename}")
                    self.task_complete.emit(current_task, str(output_path))

                except Exception as e:
                    error_msg = f"Error processing {current_task.source_image.filename}: {e}"
                    self.logger.error(self.caller, error_msg)
                    self.log_message.emit(f"[ERROR] [Worker {self.person.name}/{self.face.filename}] {error_msg}")
                    self.task_failed.emit(current_task, str(e))
                    # Decide if we continue to the next source image or stop the worker on error
                    # For now, let's continue

            # --- End of Loop --- #

        except Exception as e:
            # Catch errors during WebDriver init or other general issues
            init_error_msg = f"Worker failed during initialization or general processing: {e}"
            self.logger.error(self.caller, init_error_msg)
            self.log_message.emit(f"[FATAL ERROR] [Worker {self.person.name}/{self.face.filename}] {init_error_msg}")
            # We might want a different signal for fatal worker errors

        finally:
            # --- WebDriver Cleanup (Simulation) --- #
            self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Cleaning up (Simulated WebDriver quit)...")
            time.sleep(0.1)
            self.driver = None # Clear the placeholder
            # -------------------------------------- #

            self.logger.info(self.caller, "Worker finished.")
            self.log_message.emit(f"[Worker {self.person.name}/{self.face.filename}] Finished.")
            self.finished.emit() # Signal that the object has finished execution 