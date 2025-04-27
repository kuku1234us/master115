import threading
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

from .face_swap_models import PersonData, FaceData, SourceImageData, SwapTaskData
from .face_state_worker import FaceStateWorker
from .people_manager import PeopleManager
from .review_manager import ReviewManager
from qt_base_app.models import Logger, SettingsManager, SettingType

VALID_IMAGE_EXTENSIONS = ["*.jpg", "*.png", "*.jpeg", "*.gif"]
MAX_CONCURRENT_WORKERS = 6 # Limit simultaneous browser instances

class FaceSwapManager(QObject):
    """
    Manages the face swap automation pipeline, including worker creation,
    lifecycle, communication with the UI, and tracking completion status.
    """

    # --- Signals --- #
    # General log messages for the UI status log
    log_message = pyqtSignal(str)
    # Signals process state changes for UI updates (e.g., button states)
    process_started = pyqtSignal(dict) # Emits {person_name: total_workers}
    process_finished = pyqtSignal() # Emitted on normal completion or graceful stop
    process_killed = pyqtSignal() # Emitted after a forceful kill
    # Signal for individual person progress updates
    person_progress_updated = pyqtSignal(str, int, int) # person_name, completed, total

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = Logger.instance()
        self.caller = "FaceSwapManager"
        self.settings = SettingsManager.instance()
        self.people_manager = PeopleManager.instance()

        self._is_running = False
        self._workers: List[FaceStateWorker] = []
        self._worker_threads: List[QThread] = []
        self._active_worker_count = 0
        self._stop_event: Optional[threading.Event] = None
        # --- Add lists for pending workers --- #
        self._pending_workers: List[FaceStateWorker] = []
        self._pending_threads: List[QThread] = []
        # ----------------------------------- #
        # --- Active Worker ID Tracking --- #
        self._active_worker_ids: Dict[str, FaceStateWorker] = {} # Map worker_id -> worker instance
        # ------------------------------- #
        
        # --- Worker Progress Tracking --- #
        self._person_worker_totals: Dict[str, int] = {}
        self._person_completed_workers: Dict[str, int] = {}
        # -------------------------------- #

        # --- NEW Progress Tracking Structures --- #
        self._progress_lock = threading.Lock()
        # Tracks completion per (source, person) pair
        # {source_path: {person_name: {'total_faces': int, 'completed_faces': set(), 'result_paths': set()}}}
        self._person_source_progress: Dict[Path, Dict[str, Dict[str, Set[str] | int]]] = {}
        # Tracks which persons have completed ALL their faces for a given source
        # {source_path: set_of_completed_person_names}
        self._source_overall_completion: Dict[Path, Set[str]] = {}
        # Store the set of initially selected persons for this run (needed for overall check)
        self._current_run_selected_persons: Set[str] = set()
        # ---------------------------------------- #

        # --- Store current run's headless setting --- #
        self._current_run_headless: bool = True # Default if not set by start_process
        # --- Store current run's move source setting --- #
        self._current_run_move_source: bool = True # Default if not set by start_process
        # ---------------------------------------- #

    def is_running(self) -> bool:
        """Returns True if the automation process is currently active."""
        return self._is_running

    # --- Public Methods --- #

    def get_active_worker_ids_for_person(self, person_name: str) -> List[str]:
        """Returns a list of active worker IDs for a given person name."""
        # Worker IDs are in the format 'PersonName-FaceStem'
        ids = []
        with self._progress_lock: # Use the same lock for accessing active workers
            for worker_id in self._active_worker_ids.keys():
                # Check if the worker ID starts with the requested person's name and a hyphen
                if worker_id.startswith(f"{person_name}-"):
                    ids.append(worker_id)
        return sorted(ids) # Return sorted for consistent menu order

    def start_process(self, selected_person_names: List[str], run_headless: bool = True, move_source_file: bool = True):
        """Starts the face swap automation process."""
        # --- Logic moved from FaceDashboardPage._handle_start_request --- #
        self.logger.info(self.caller, f"Start process requested for: {selected_person_names}, Headless: {run_headless}, Move Source: {move_source_file}")
        # Store the settings for this run
        self._current_run_headless = run_headless
        self._current_run_move_source = move_source_file
        
        if self._is_running:
            self.logger.warn(self.caller, "Start requested but process is already running.")
            self.log_message.emit("Warning: Automation process is already running.")
            return

        # 1. Validate AI Root Dir
        # Get AI Root Dir directly from SettingsManager (it will be validated)
        ai_root_path = self.settings.get(
            SettingsManager.AI_ROOT_DIR_KEY, 
            None, # Default to None if setting missing or invalid
            SettingType.PATH
        )
        # Check if the returned path is valid (SettingsManager returns None if invalid)
        if not ai_root_path:
            self.log_message.emit("Error: AI Root Directory is not set or is invalid. Please check Preferences.")
            # Logger messages are already handled by SettingsManager if invalid
            self.logger.error(self.caller, "AI Root Directory not set or invalid.")
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
             
        # --- Calculate total faces to process for tracking --- #
        all_selected_faces = set()
        for person in valid_selected_persons:
            for face in person.faces:
                all_selected_faces.add(face.filename) # Use filename as unique identifier
        total_faces_to_process = len(all_selected_faces)
        if total_faces_to_process == 0:
             self.log_message.emit("Error: No valid face files found for any selected person.")
             self.logger.error(self.caller, "Calculated 0 total faces to process.")
             return
        # --------------------------------------------------- #

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
        # --- Clear pending lists as well --- #
        self._pending_workers.clear()
        self._pending_threads.clear()
        # --- Clear active worker IDs --- #
        self._active_worker_ids.clear()
        # ------------------------------- #
        
        # --- Initialize NEW progress tracking --- #
        with self._progress_lock:
            self._person_source_progress.clear()
            self._source_overall_completion.clear()
            # Store the names of persons we are actually processing
            self._current_run_selected_persons = {p.name for p in valid_selected_persons}

            for src_img in all_source_images:
                source_path = src_img.path
                self._person_source_progress[source_path] = {}
                self._source_overall_completion[source_path] = set() # Initialize empty set for overall completion

                for person in valid_selected_persons:
                    person_faces_count = len(person.faces)
                    if person_faces_count > 0: # Only track persons with faces for this source
                        self._person_source_progress[source_path][person.name] = {
                            'total_faces': person_faces_count,
                            'completed_faces': set(), # Store completed face filenames for this person/source
                            'result_paths': set()     # Store paths generated for this person/source
                        }
                    # --- Store Worker Totals --- #
                    if person.faces: # Only store if person has faces
                        self._person_worker_totals[person.name] = len(person.faces)
                        self._person_completed_workers[person.name] = 0 # Initialize completed count
                    # ------------------------- #

        self.logger.info(self.caller, f"Preparing to start workers. Persons: {len(valid_selected_persons)}, Sources: {len(all_source_images)}")
        total_workers_to_start = sum(len(person.faces) for person in valid_selected_persons)
        self.log_message.emit(f"Starting automation... Found {len(all_source_images)} source images.")
        self.log_message.emit(f"Processing faces for {len(valid_selected_persons)} selected persons ({total_faces_to_process} unique faces). Total workers: {total_workers_to_start}")
        self.log_message.emit(f"Concurrency limit set to {MAX_CONCURRENT_WORKERS} workers.")

        # 5. Create Workers and Threads (but don't start all yet)
        for person in valid_selected_persons:
            for face in person.faces:
                # Create worker - DO NOT MOVE TO THREAD YET
                worker = FaceStateWorker(
                    person=person,
                    face=face,
                    source_images=all_source_images,
                    temp_output_dir=temp_output_dir,
                    stop_event=self._stop_event,
                    run_headless=self._current_run_headless # Pass headless value
                )
                thread = QThread() # Create thread

                # Add to pending lists
                self._pending_workers.append(worker)
                self._pending_threads.append(thread)

        # 6. Start the initial batch of workers
        self._is_running = True
        self._start_pending_workers() # Call helper to start up to the limit

        # Check if any workers actually started
        if self._active_worker_count > 0:
            # Emit totals when starting
            self.process_started[dict].emit(dict(self._person_worker_totals))
            self.logger.info(self.caller, f"Successfully started initial {self._active_worker_count} worker threads.")
            self.log_message.emit(f"Automation process running with {self._active_worker_count} active workers (limit {MAX_CONCURRENT_WORKERS}).")
        else:
            # This case might happen if _start_pending_workers fails immediately, though unlikely
            self.log_message.emit("Error: Failed to start any initial worker threads.")
            self.logger.error(self.caller, "Failed to start initial workers.")
            self._cleanup_after_stop()
            self._is_running = False # Ensure state is correct
        # --- End of modified start logic ---

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
                    is_in_completed = False
                    try:
                        # Check if completed_dir is an ancestor of img_path
                         if completed_dir.is_dir() and completed_dir.resolve() in img_path.resolve().parents:
                              is_in_completed = True
                    except Exception as e:
                        self.logger.warn(self.caller, f"Error checking if path {img_path} is in {completed_dir}: {e}")

                    if is_in_completed:
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
            source_path = task.source_image.path
            face_filename = task.face.filename # Identifier for the face
            person_name = task.person.name 

            # Log simple success message first
            msg = f"Swap complete for {person_name}/{face_filename} on {task.source_image.filename}. -> Temp/{Path(output_path).name}"
            self.log_message.emit(f"✅ SUCCESS: {msg}")
            self.logger.info(self.caller, msg) # Log internally too
            
            # --- Update Progress & Check for Source Completion --- #
            with self._progress_lock:
                # Check if source and person are tracked
                if source_path in self._person_source_progress and person_name in self._person_source_progress[source_path]:
                    person_progress = self._person_source_progress[source_path][person_name]
                    person_progress['completed_faces'].add(face_filename)
                    person_progress['result_paths'].add(output_path)

                    total_person_faces = person_progress['total_faces']
                    completed_person_faces = len(person_progress['completed_faces'])

                    self.logger.debug(self.caller, f"Progress for {person_name} on {source_path.name}: {completed_person_faces}/{total_person_faces} faces done.")

                    # --- Check 1: Person completed for this source ---
                    if completed_person_faces >= total_person_faces:
                        self.logger.info(self.caller, f"All {total_person_faces} faces for {person_name} completed on source: {source_path.name}. Adding to review.")
                        # Add this person/source pair to review (will NOT move file)
                        ReviewManager.instance().add_person_source_review(
                            person_name=person_name,
                            original_source_path=source_path,
                            result_paths=person_progress['result_paths'] # Pass only this person's results
                        )

                        # Update overall source completion tracker
                        if source_path in self._source_overall_completion:
                            self._source_overall_completion[source_path].add(person_name)
                        else:
                            # Should not happen if initialized correctly, but handle defensively
                             self.logger.warn(self.caller, f"Source path {source_path.name} not found in overall completion tracker while updating for {person_name}.")
                             self._source_overall_completion[source_path] = {person_name}

                        # --- Check 2: Source completed for ALL selected persons ---
                        completed_persons_for_source = self._source_overall_completion[source_path]
                        if completed_persons_for_source == self._current_run_selected_persons:
                            log_msg_suffix = "Moving source file." if self._current_run_move_source else "Skipping source file move (toggle disabled)."
                            self.logger.info(self.caller, f"Source {source_path.name} is now complete for ALL selected persons ({len(self._current_run_selected_persons)}). {log_msg_suffix}")
                            
                            # Conditionally move the source file based on the setting for this run
                            if self._current_run_move_source:
                                ReviewManager.instance().mark_source_completed_and_move(
                                    original_source_path=source_path
                                )
                            # --- Remove completed source from tracking immediately --- #
                            if source_path in self._person_source_progress:
                                del self._person_source_progress[source_path]
                                self.logger.debug(self.caller, f"Removed {source_path.name} from active person progress tracker.")
                            if source_path in self._source_overall_completion:
                                del self._source_overall_completion[source_path]
                                self.logger.debug(self.caller, f"Removed {source_path.name} from overall completion tracker.")
                            # --------------------------------------------------------- #

                else:
                    self.logger.warn(self.caller, f"Received task_complete for untracked source/person: {source_path.name} / {person_name}")

            # --- End of Progress Update --- #

        except Exception as e:
            self.logger.error(self.caller, f"Error processing task_complete signal: {e}", exc_info=True)
            self.log_message.emit("[MANAGER ERROR] Error logging task completion details.")
        # --- End of moved logic ---
        
    def _handle_source_completion(self, source_path: Path, completed_data: dict):
        """
        Moves the source file and updates the pending review JSON.
        MUST be called within the _progress_lock.
        """
        self.logger.debug(self.caller, f"Handling completion for: {source_path.name}")
        ai_root_path = self.people_manager._get_ai_root()
        if not ai_root_path:
            self.logger.error(self.caller, "Cannot handle source completion, AI Root path not found.")
            self.log_message.emit(f"[ERROR] Failed to move {source_path.name}: AI Root directory not set.")
            return # Cannot proceed

        try:
            # --- Add to Pending Review Manager --- #
            ReviewManager.instance().add_pending_review(
                original_source_path=source_path,
                result_paths=completed_data['result_paths']
            )
            # --------------------------------------- #

            # Remove from in-memory tracker *only after successful move and JSON update*
            if source_path in self._person_source_progress:
                del self._person_source_progress[source_path]
                self.logger.debug(self.caller, f"Removed {source_path.name} from active progress tracking.")

        except Exception as e:
            # Log errors specifically from ReviewManager call or dict removal
            err_msg = f"Unexpected error during source completion handling (ReviewManager call or dict removal) for {source_path.name}: {e}"
            self.logger.error(self.caller, err_msg, exc_info=True)
            self.log_message.emit(f"[ERROR] {err_msg}")

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
            
            # Note: We are currently NOT decrementing the 'total_faces' or modifying
            # the completion check based on failures. A source image will only be moved
            # if ALL originally scheduled faces for it complete successfully.
            
        except Exception as e:
            self.logger.error(self.caller, f"Error processing task_failed signal: {e}", exc_info=True)
            self.log_message.emit("[MANAGER ERROR] Error logging task failure details.")
        # --- End of moved logic ---

    @pyqtSlot()
    def _on_any_worker_finished(self):
        """Invoked each time a worker emits `finished()`. Handles overall count and process end."""
        if not self._is_running:
            # Safety check: Should not happen if logic is correct
            self.logger.debug(self.caller, "_on_any_worker_finished called while not running. Ignoring.")
            return

        self._active_worker_count -= 1
        self.logger.debug(self.caller, f"Worker finished. Remaining active: {self._active_worker_count}")

        # --- Attempt to start next worker --- #
        if self._is_running and not (self._stop_event and self._stop_event.is_set()):
             self._start_pending_workers()
        # ---------------------------------- #

        if self._active_worker_count <= 0 and self._is_running:
            # Check if all pending workers have been processed
            # Use the lock here just to be safe when checking pending list
            with self._progress_lock:
                 all_pending_started = not self._pending_workers
                 stop_requested = self._stop_event and self._stop_event.is_set()
                 
            # Either all workers started OR stop was requested and all active workers finished
            if all_pending_started or stop_requested:
                self.logger.info(self.caller, "All worker objects finished; shutting down threads.")

                # ---- FIX: Implement correct Quit -> Wait -> DeleteLater sequence ----
                # 1) Tell every thread to quit its event-loop
                self.logger.debug(self.caller, "Requesting all threads to quit...")
                for thread in self._worker_threads:
                    thread.quit()             # Ask the event loop to exit

                # 2) Wait until *all* have actually terminated
                self.logger.debug(self.caller, "Waiting for all threads to terminate...")
                all_terminated = True # Flag to track if all waited successfully
                for thread in self._worker_threads:
                    if not thread.wait(5000): # Wait up to 5 seconds
                        self.logger.warn(self.caller, f"Thread {thread} did not finish within the timeout after quit signal.")
                        all_terminated = False
                    else: # Debug log if needed
                        self.logger.debug(self.caller, f"Thread {thread} finished cleanly after wait.")
                    # Schedule for deletion regardless of clean termination within wait
                    thread.deleteLater()
                # -------------------------------------------------------------------- #

                if all_terminated:
                    self.logger.info(self.caller, "All QThreads have terminated cleanly.")
                else:
                     self.logger.warn(self.caller, "Some QThreads did not terminate cleanly within the timeout.")


                # Log final status and cleanup state *after* threads are done
                final_message = "Process stopped gracefully." if stop_requested else "All tasks completed."
                # Check if any tasks are still pending (shouldn't be if count is 0, but safety check)
                with self._progress_lock:
                    remaining_tasks = len(self._person_source_progress)
                if remaining_tasks > 0 and not stop_requested:
                     final_message += f" (Warning: {remaining_tasks} source images did not fully complete)."
                     self.logger.warn(self.caller, f"Process finished, but {remaining_tasks} source images remain in progress tracker.")

                self.log_message.emit(final_message)
                
                self._cleanup_after_stop()
                self.process_finished.emit()

        # If workers > 0, just return (no cleanup yet)

    @pyqtSlot(str)
    def _on_specific_worker_finished(self, person_name: str):
        """Slot connected to the worker's finished(person_name) signal."""
        sender_worker = self.sender()
        worker_id = None
        # Find the worker_id associated with the sender
        with self._progress_lock: # Protect access to _active_worker_ids
            for w_id, worker in self._active_worker_ids.items():
                if worker is sender_worker:
                    worker_id = w_id
                    break
            # Remove the worker ID if found
            if worker_id and worker_id in self._active_worker_ids:
                del self._active_worker_ids[worker_id]
                self.logger.debug(self.caller, f"Removed finished worker ID: {worker_id}")
            else:
                 self.logger.warn(self.caller, f"Finished worker (Person: {person_name}, Sender: {sender_worker}) not found in active IDs.")

        with self._progress_lock: # Separate lock context for clarity
            if person_name in self._person_completed_workers:
                self._person_completed_workers[person_name] += 1
                completed = self._person_completed_workers[person_name]
                total = self._person_worker_totals.get(person_name, 0) # Get total, default 0
                self.logger.debug(self.caller, f"Worker finished for {person_name}. Progress: {completed}/{total}")
                # Emit progress update signal
                self.person_progress_updated.emit(person_name, completed, total)
            else:
                 self.logger.warn(self.caller, f"Received worker finished signal for untracked/already cleared person: {person_name}")
        # Note: Do not call _on_any_worker_finished here, it's connected separately

    def _cleanup_after_stop(self):
        """Resets internal state after the process has fully stopped."""
        self.logger.info(self.caller, "Cleaning up manager state.")
        self._is_running = False
        self._workers.clear()
        self._worker_threads.clear()
        self._pending_workers.clear()
        self._pending_threads.clear()
        self._active_worker_ids.clear() # Clear active worker IDs
        self._active_worker_count = 0
        self._stop_event = None
        # Reset progress tracking
        with self._progress_lock:
            self._person_worker_totals.clear()
            self._person_completed_workers.clear()
            self._person_source_progress.clear()
            self._source_overall_completion.clear()
            self._current_run_selected_persons.clear()

    def _update_pending_review_json(self, original_path: Path, completed_path: Path, result_paths: Set[str]):
        """
        Reads, updates, and writes the PendingReview.json file.
        MUST be called within the _progress_lock.
        """
        # Implementation of this method is not provided in the original file or the code block
        # This method should be implemented to read, update, and write the PendingReview.json file
        # based on the original_path, completed_path, and result_paths
        pass 

    # --- New Helper Method --- #
    def _start_pending_workers(self):
        """Starts workers from the pending list up to the concurrency limit."""
        with self._progress_lock: # Protect access to worker lists and count
            while self._active_worker_count < MAX_CONCURRENT_WORKERS and self._pending_workers:
                worker = self._pending_workers.pop(0)
                thread = self._pending_threads.pop(0)

                worker_id = worker._worker_id() # Get the ID for tracking

                # Move worker to thread **before** connecting signals that rely on thread context
                worker.moveToThread(thread)

                # Connect signals
                worker.log_message.connect(self.log_message)
                worker.task_complete.connect(self._on_task_complete)
                worker.task_failed.connect(self._on_task_failed)
                # Connect to the specific finished signal that includes person_name
                worker.finished.connect(self._on_specific_worker_finished)
                # Connect generic finished for thread cleanup and overall count
                worker.finished.connect(self._on_any_worker_finished)
                worker.finished.connect(thread.quit)
                # Schedule deletion of worker
                thread.finished.connect(worker.deleteLater)
                # Start worker's run method when thread starts
                thread.started.connect(worker.run)

                # Store references
                self._workers.append(worker)
                self._worker_threads.append(thread)
                self._active_worker_ids[worker_id] = worker # Add to active dict
                self._active_worker_count += 1

                thread.start() # Start the thread
    # ------------------------ # 