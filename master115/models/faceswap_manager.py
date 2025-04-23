import threading
from pathlib import Path
from typing import List, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

from .face_swap_models import PersonData, FaceData, SourceImageData, SwapTaskData
from .face_swap_worker import FaceSwapWorker
from .people_manager import PeopleManager
from qt_base_app.models import Logger, SettingsManager, SettingType

VALID_IMAGE_EXTENSIONS = ["*.jpg", "*.png", "*.jpeg", "*.gif"]

class FaceSwapManager(QObject):
    """
    Manages the face swap automation pipeline, including worker creation,
    lifecycle, and communication with the UI.
    """

    # --- Signals --- #
    # General log messages for the UI status log
    log_message = pyqtSignal(str)
    # Signals process state changes for UI updates (e.g., button states)
    process_started = pyqtSignal()
    process_finished = pyqtSignal() # Emitted on normal completion or graceful stop
    process_killed = pyqtSignal() # Emitted after a forceful kill
    # Optional: Signal for individual task updates if needed by UI beyond logging
    # task_update = pyqtSignal(str) # Example: could carry simple status strings

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = "FaceSwapManager"
        self.settings = SettingsManager.instance()
        self.people_manager = PeopleManager.instance()

        self._is_running = False
        self._workers: List[FaceSwapWorker] = []
        self._worker_threads: List[QThread] = []
        self._active_worker_count = 0
        self._stop_event: Optional[threading.Event] = None

    def is_running(self) -> bool:
        """Returns True if the automation process is currently active."""
        return self._is_running

    # --- Public Methods --- #

    def start_process(self, selected_person_names: List[str]):
        """Starts the face swap automation process."""
        # --- Logic moved from FaceDashboardPage._handle_start_request --- #
        self.logger.info(self.caller, f"Start process requested for: {selected_person_names}")
        if self._is_running:
            self.logger.warn(self.caller, "Start requested but process is already running.")
            self.log_message.emit("Warning: Automation process is already running.")
            return

        # 1. Validate AI Root Dir
        ai_root_path = self.people_manager._get_ai_root()
        if not ai_root_path:
            self.log_message.emit("Error: AI Root Directory is not set or invalid. Please check Preferences.")
            self.logger.error(self.caller, "AI Root Directory invalid or not set.")
            return

        # 2. Get All Source Images
        all_source_images = self._get_all_source_images(ai_root_path) # Use internal method
        if not all_source_images:
            # _get_all_source_images already emits a warning
            self.logger.error(self.caller, "No source images found.")
            return

        # 3. Get Selected Persons and Their Full Data
        if not selected_person_names:
             self.log_message.emit("Error: No persons selected. Please select persons from the grid.")
             self.logger.error(self.caller, "No persons selected.")
             return
             
        selected_persons_data = self.people_manager.get_person_data_by_names(selected_person_names)
        valid_selected_persons = [p for p in selected_persons_data if p.faces]
        
        if not valid_selected_persons:
            self.log_message.emit("Error: Selected persons have no face images found in their directories. Check Faces folders.")
            self.logger.error(self.caller, "Selected persons have no face images.")
            return
            
        if len(valid_selected_persons) < len(selected_persons_data):
             missing_faces_names = [p.name for p in selected_persons_data if not p.faces]
             self.log_message.emit(f"Warning: Skipping selected persons with no faces: {', '.join(missing_faces_names)}")
             self.logger.warn(self.caller, f"Skipping selected persons with no faces: {missing_faces_names}")

        # 4. Prepare for Workers
        temp_output_dir = ai_root_path / "Temp"
        try:
            temp_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            err_msg = f"Error creating temporary output directory: {e}"
            self.log_message.emit(f"Error: {err_msg}")
            self.logger.error(self.caller, f"Could not create Temp directory: {temp_output_dir}. Error: {e}")
            return

        # Clear previous run artifacts if any
        self._workers.clear()
        self._worker_threads.clear()
        self._active_worker_count = 0
        self._stop_event = threading.Event()

        self.logger.info(self.caller, f"Preparing to start workers. Persons: {len(valid_selected_persons)}, Sources: {len(all_source_images)}")
        total_workers_to_start = sum(len(person.faces) for person in valid_selected_persons)
        self.log_message.emit(f"Starting automation... Found {len(all_source_images)} source images.")
        self.log_message.emit(f"Processing faces for {len(valid_selected_persons)} selected persons. Total workers: {total_workers_to_start}")

        # 5. Create and Start Workers
        for person in valid_selected_persons:
            for face in person.faces:
                worker = FaceSwapWorker(
                    person=person,
                    face=face,
                    source_images=all_source_images,
                    temp_output_dir=temp_output_dir,
                    stop_event=self._stop_event
                )
                thread = QThread()
                worker.moveToThread(thread)

                # Connect signals to internal slots
                worker.log_message.connect(self.log_message) # Forward log messages directly
                worker.task_complete.connect(self._on_task_complete)
                worker.task_failed.connect(self._on_task_failed)
                worker.finished.connect(self._on_worker_finished) # Connect worker finished
                thread.started.connect(worker.run)

                # Setup cleanup connections
                worker.finished.connect(thread.quit)
                # Delete worker when thread finishes cleanly
                thread.finished.connect(worker.deleteLater)

                self._workers.append(worker)
                self._worker_threads.append(thread)

                thread.start()
                self._active_worker_count += 1
                self.logger.debug(self.caller, f"Started worker thread for {person.name} - {face.filename}")

        if self._active_worker_count > 0:
            self._is_running = True
            self.process_started.emit() # Signal UI that process has started
            self.logger.info(self.caller, f"Successfully started {self._active_worker_count} worker threads.")
            self.log_message.emit(f"Automation process running with {self._active_worker_count} workers.")
        else:
            self.log_message.emit("Warning: No worker threads were started. Check configuration or face images.")
            self.logger.warning(self.caller, "No worker threads were started.")
            # No UI state to reset here, UI will handle based on signals
        # --- End of moved logic ---

    def stop_process(self):
        """Requests a graceful stop of the automation process."""
        # --- Logic moved from FaceDashboardPage._handle_stop_request --- #
        self.logger.info(self.caller, "Stop process requested.")
        if self._is_running and self._stop_event:
            if not self._stop_event.is_set(): # Prevent multiple signals
                self.log_message.emit("Stop requested. Signaling workers to stop after current task...")
                self._stop_event.set() # Signal all workers
                # UI will handle disabling button via process_started/finished signals
            else:
                self.logger.info(self.caller, "Stop already signaled.")
                self.log_message.emit("Stop already signaled. Waiting for workers to finish...")
        elif not self._is_running:
            self.logger.warn(self.caller, "Stop requested but no process is running.")
            self.log_message.emit("Stop requested, but no process is running.")
        else: # _is_running is true but _stop_event is None (should not happen)
             self.logger.error(self.caller, "Stop requested but stop_event is missing while running!")
             self.log_message.emit("[MANAGER ERROR] Cannot stop process, internal state inconsistent.")
        # --- End of moved logic ---

    def kill_process(self):
        """Force-terminate threads (rarely needed now)."""
        if not self._is_running:
            self.log_message.emit("Kill requested, but nothing is running.")
            self.logger.info(self.caller, "Kill requested, but no process is running.") # Added log
            return

        self.log_message.emit("Force-killing all threads...")
        self.logger.warning(self.caller, "Force kill requested.")

        killed_count = 0
        for t in self._worker_threads:
            if t.isRunning():
                try:
                    t.terminate()        # brutal - last resort
                    t.wait() # Wait for termination confirmation
                    killed_count += 1
                except Exception as e:
                     self.logger.error(self.caller, f"Error terminating/waiting on thread {t}: {e}")
        self.logger.warning(self.caller, f"Issued terminate+wait for {killed_count} running threads.")

        # Cleanup state and signal UI immediately after attempting termination
        self._cleanup_after_stop()
        self.process_killed.emit()

    # --- Internal Logic & Slots --- #

    def _get_all_source_images(self, ai_root_dir: Path) -> List[SourceImageData]:
        """Scans the SourceImages directory (excluding Completed)."""
        # --- Logic moved from FaceDashboardPage --- #
        source_dir = ai_root_dir / "SourceImages"
        completed_dir = source_dir / "Completed"
        source_images = []

        if not source_dir.is_dir():
            self.logger.warn(self.caller, f"SourceImages directory not found: {source_dir}")
            self.log_message.emit(f"Warning: SourceImages directory not found: {source_dir}") # Signal UI
            return []

        self.logger.info(self.caller, f"Scanning for source images in: {source_dir}")
        try:
            for ext in VALID_IMAGE_EXTENSIONS:
                for img_path in source_dir.glob(ext):
                    # Skip if it's inside the Completed subdirectory
                    if completed_dir.is_dir() and completed_dir in img_path.parents:
                        continue
                    if img_path.is_file():
                        source_images.append(SourceImageData(path=img_path))
        except OSError as e:
            err_msg = f"Error scanning SourceImages directory {source_dir}: {e}"
            self.logger.error(self.caller, err_msg)
            self.log_message.emit(f"Error: {err_msg}") # Signal UI
            return []

        self.logger.info(self.caller, f"Found {len(source_images)} source images.")
        if not source_images:
             self.log_message.emit("Warning: No source images found in SourceImages directory (excluding Completed/).")
        return source_images
        # --- End of moved logic ---

    @pyqtSlot(SwapTaskData, str)
    def _on_task_complete(self, task: SwapTaskData, output_path: str):
        """Handles completion of a single task from a worker."""
        # --- Logic moved from FaceDashboardPage --- #
        try:
            source_name = task.source_image.filename if task.source_image else "Unknown Source"
            person_name = task.person.name if task.person else "Unknown Person"
            face_name = task.face.filename if task.face else "Unknown Face"
            msg = f"Swap complete for {person_name}/{face_name} on {source_name}. -> Temp/{Path(output_path).name}"
            # Signal the concise message to the UI log
            self.log_message.emit(f"✅ SUCCESS: {msg}")
            self.logger.info(self.caller, msg) # Log internally too
        except Exception as e:
            self.logger.error(self.caller, f"Error processing task_complete signal: {e}")
            self.log_message.emit("[MANAGER ERROR] Error logging task completion details.")
        # --- End of moved logic ---

    @pyqtSlot(SwapTaskData, str)
    def _on_task_failed(self, task: SwapTaskData, error: str):
        """Handles failure of a single task from a worker."""
        # --- Logic moved from FaceDashboardPage --- #
        try:
            source_name = task.source_image.filename if task.source_image else "Unknown Source"
            person_name = task.person.name if task.person else "Unknown Person"
            face_name = task.face.filename if task.face else "Unknown Face"
            detailed_msg = f"Swap failed for '{person_name}/{face_name}' on '{source_name}'. Error: {error}"
            # Signal the concise message to the UI log
            self.log_message.emit(f"❌ FAILED: {detailed_msg}")
            self.logger.error(self.caller, detailed_msg) # Log detailed error internally
        except Exception as e:
            self.logger.error(self.caller, f"Error processing task_failed signal: {e}")
            self.log_message.emit("[MANAGER ERROR] Error logging task failure details.")
        # --- End of moved logic ---

    @pyqtSlot()
    def _on_worker_finished(self):
        """Invoked each time a worker emits `finished()`."""
        if not self._is_running:
            # Safety check: Should not happen if logic is correct
            self.logger.debug(self.caller, "_on_worker_finished called while not running. Ignoring.")
            return

        self._active_worker_count -= 1
        self.logger.debug(self.caller, f"Worker finished. Remaining active: {self._active_worker_count}")

        if self._active_worker_count <= 0:
            self.logger.info(self.caller, "All worker objects finished; shutting down threads.")

            # ---- FIX: Implement correct Quit -> Wait -> DeleteLater sequence ----
            # 1) Tell every thread to quit its event-loop
            self.logger.debug(self.caller, "Requesting all threads to quit...")
            for thread in self._worker_threads:
                if thread.isRunning():
                    thread.quit()             # Ask the event loop to exit

            # 2) Wait until *all* have actually terminated
            self.logger.debug(self.caller, "Waiting for all threads to terminate...")
            for thread in self._worker_threads:
                if thread.isRunning():
                    if not thread.wait(5000): # Wait up to 5 seconds
                        self.logger.warn(self.caller, f"Thread {thread} did not finish within the timeout after quit signal.")
                    # else: # Debug log if needed
                    #     self.logger.debug(self.caller, f"Thread {thread} finished cleanly after wait.")

                # Optional: Destroy automatically after waiting
                # Ensure deleteLater is called even if wait timed out or thread was already finished
                thread.deleteLater()
            # -------------------------------------------------------------------- #

            self.logger.info(self.caller, "All QThreads have terminated cleanly.")

            # Log final status and cleanup state *after* threads are done
            final_message = "Process stopped gracefully." if self._stop_event and self._stop_event.is_set() else "All tasks completed."
            self.log_message.emit(final_message)

            self._cleanup_after_stop()
            self.process_finished.emit()

        # If workers > 0, just return (no cleanup yet)

    def _cleanup_after_stop(self):
        """Cleans up internal state after process stops or is killed."""
        self._is_running = False
        self._workers.clear()
        self._worker_threads.clear() # Should be empty if using deleteLater correctly
        self._active_worker_count = 0
        self._stop_event = None
        self.logger.info(self.caller, "Manager internal state reset.") 