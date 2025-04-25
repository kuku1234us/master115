import json
import threading
import shutil
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from datetime import datetime # Needed for backup timestamp

from PyQt6.QtCore import QObject, pyqtSignal
from qt_base_app.models import Logger, SettingsManager, SettingType

# Constants
PENDING_REVIEW_FILENAME = "PendingReview.json"
# Define expected keys for the new JSON structure
JSON_REQUIRED_KEYS = ['person_name', 'original_source_path', 'result_image_paths']

class ReviewManager(QObject):
    """
    Manages the state of face swap results pending user review,
    persisting the data in PendingReview.json within the AI Root Directory.
    Implemented as a thread-safe singleton.
    """
    # Signal emitted when a new item is successfully added and ready for review
    # Payload is the dictionary representing the added item
    review_item_added = pyqtSignal(dict)
    # Signal emitted when an item is successfully processed and removed
    # Payload: person_name (str), original_source_path_str (str)
    review_item_removed = pyqtSignal(str, str)

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        """Gets the singleton instance of the ReviewManager."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Private constructor for the singleton."""
        if ReviewManager._instance is not None:
            raise Exception("This class is a singleton! Use ReviewManager.instance()")
        
        super().__init__()
        self.logger = Logger.instance()
        self.settings = SettingsManager.instance()
        self.caller = "ReviewManager"
        
        self._pending_reviews: List[Dict[str, Any]] = []
        self._json_path: Optional[Path] = None
        self._load_data() # Load data on initialization

    def _get_ai_root_path(self) -> Optional[Path]:
        """Gets the configured AI Root directory path from settings and validates it."""
        ai_root_raw = self.settings.get(SettingsManager.AI_ROOT_DIR_KEY, SettingsManager.DEFAULT_AI_ROOT_DIR, SettingType.PATH)
        if not ai_root_raw:
            self.logger.error(self.caller, "AI Root Directory is not set in settings.")
            return None
        ai_root_path = Path(ai_root_raw)
        if not ai_root_path.is_dir():
            self.logger.error(self.caller, f"Configured AI Root Directory is not a valid directory: {ai_root_path}")
            return None
        return ai_root_path

    def _get_json_path(self) -> Optional[Path]:
        """Determines the path to PendingReview.json based on settings."""
        if self._json_path: # Cache path after first lookup
            return self._json_path
            
        ai_root_path = self._get_ai_root_path()
        if not ai_root_path:
            self.logger.error(self.caller, f"Cannot locate {PENDING_REVIEW_FILENAME}, AI Root Directory is not set.")
            return None
            
        self._json_path = ai_root_path / PENDING_REVIEW_FILENAME
        return self._json_path

    def _load_data(self):
        """Loads pending review data from the JSON file. Assumes lock is held."""
        json_path = self._get_json_path()
        if not json_path:
            self._pending_reviews = [] # Reset if path is invalid
            return

        try:
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip(): # Avoid error on empty file
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, list):
                            # Basic validation of list items (check for required keys)
                            self._pending_reviews = [
                                item for item in loaded_data
                                if isinstance(item, dict) and
                                all(k in item for k in JSON_REQUIRED_KEYS)
                            ]
                            if len(self._pending_reviews) != len(loaded_data):
                                self.logger.warn(self.caller, f"Loaded {len(self._pending_reviews)} valid items from {json_path.name}, ignored some invalid entries.")
                        else:
                            self.logger.warn(self.caller, f"{json_path.name} does not contain a list. Resetting.")
                            self._pending_reviews = []
                    else:
                         self._pending_reviews = [] # Treat empty file as empty list
                self.logger.info(self.caller, f"Loaded {len(self._pending_reviews)} items from {json_path.name}")
            else:
                 self.logger.info(self.caller, f"{json_path.name} not found, starting fresh.")
                 self._pending_reviews = []
        except json.JSONDecodeError:
            self.logger.error(self.caller, f"Error decoding JSON from {json_path.name}. File might be corrupt. Backing up and resetting.", exc_info=True)
            self._backup_corrupt_json(json_path)
            self._pending_reviews = [] # Reset
        except Exception as e:
            self.logger.error(self.caller, f"Error reading {json_path.name}: {e}", exc_info=True)
            self._pending_reviews = [] # Reset on generic read error

    def _save_data(self):
        """Saves the current pending review data to the JSON file. Assumes lock is held."""
        json_path = self._get_json_path()
        if not json_path:
            self.logger.error(self.caller, "Cannot save pending reviews, JSON path is invalid.")
            return

        try:
            # Ensure parent directory exists (should be AI Root, but check anyway)
            json_path.parent.mkdir(parents=True, exist_ok=True) 
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self._pending_reviews, f, indent=4) # Pretty print
            self.logger.debug(self.caller, f"Successfully saved {len(self._pending_reviews)} items to {json_path.name}")
        except Exception as e:
            self.logger.error(self.caller, f"Error writing to {json_path.name}: {e}", exc_info=True)
            # Optionally emit a signal or raise an error if saving is critical

    def _backup_corrupt_json(self, json_path: Path):
        """Creates a timestamped backup of a potentially corrupt JSON file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = json_path.with_suffix(f".json.corrupt_{timestamp}")
            if json_path.exists(): # Check again before copying
                shutil.copy2(json_path, backup_path)
                self.logger.info(self.caller, f"Created backup of corrupt file at {backup_path}")
        except Exception as backup_err:
            self.logger.error(self.caller, f"Could not create backup of corrupt JSON: {backup_err}")

    def _find_review_item_index(self, person_name: str, original_source_path_str: str) -> int:
        """Finds the index of a specific pending review item. Returns -1 if not found."""
        # Assumes lock is already held by the caller
        for index, item in enumerate(self._pending_reviews):
            if item.get('person_name') == person_name and item.get('original_source_path') == original_source_path_str:
                return index
        return -1 # Not found

    # --- Public API --- #

    def add_pending_review(self, original_source_path: Path, result_paths: Set[str]):
        """
        DEPRECATED: Use add_person_source_review instead.

        Moves the completed source file, adds the entry to the pending review list,
        saves the list, and emits a signal.
        """
        self.logger.warn(self.caller, "DEPRECATED method add_pending_review called. Please update calling code.")
        # This method is no longer suitable for the per-person review logic.
        # We might keep it for future use cases or remove it entirely.
        # For now, just log a warning.
        pass # Avoid any operations

    def add_person_source_review(self, person_name: str, original_source_path: Path, result_paths: Set[str]):
        """
        Adds a (Person, Source) pair to the pending review list, saves the JSON,
        and emits the review_item_added signal.
        This method does NOT move the source file.
        """
        with self._lock:
            original_path_str = str(original_source_path.resolve())
            result_paths_list = sorted([str(Path(p).resolve()) for p in result_paths])

            # Use helper to check for duplicates
            existing_index = self._find_review_item_index(person_name, original_path_str)
            if existing_index != -1:
                self.logger.warn(self.caller, f"Attempted to add duplicate review entry for {person_name} / {original_source_path.name}. Ignoring.")
                return

            new_entry = {
                'person_name': person_name,
                'original_source_path': original_path_str,
                'result_image_paths': result_paths_list,
                'completed_source_path': None # Initialize as None, will be set later
            }

            self._pending_reviews.append(new_entry)
            self.logger.info(self.caller, f"Added review entry for {person_name} / {original_source_path.name} to pending reviews.")
            self._save_data()
            # Emit signal *after* successful save
            self.review_item_added.emit(new_entry)

    def mark_source_completed_and_move(self, original_source_path: Path):
        """
        Moves the source file to the Completed directory and updates the
        'completed_source_path' field for all related entries in the JSON.
        """
        with self._lock:
            ai_root_path = self._get_ai_root_path()
            if not ai_root_path:
                self.logger.error(self.caller, f"Cannot mark source completed for {original_source_path.name}, AI Root path not found.")
                return

            completed_dir = ai_root_path / "SourceImages" / "Completed"
            completed_path = completed_dir / original_source_path.name

            original_path_str = str(original_source_path.resolve())
            completed_path_str = str(completed_path.resolve())

            # 1. Move the file
            try:
                completed_dir.mkdir(parents=True, exist_ok=True)
                # Check if file still exists before moving (maybe already moved?)
                if original_source_path.exists():
                    self.logger.info(self.caller, f"Moving completed source '{original_source_path.name}' to Completed/ folder (Overall completion).")
                    shutil.move(str(original_source_path), str(completed_path))
                    self.logger.info(self.caller, f"Successfully moved {original_source_path.name} to {completed_path}")
                else:
                    self.logger.warn(self.caller, f"Source file {original_source_path.name} not found for final move, perhaps already moved or deleted?")
            except OSError as e:
                err_msg = f"Error moving {original_source_path.name} to Completed/ during finalization: {e}"
                self.logger.error(self.caller, err_msg, exc_info=True)
                # Continue to update JSON even if move failed?
                # For now, we'll still try to update JSON, assuming the move *should* have happened.
            except Exception as e:
                err_msg = f"Unexpected error moving {original_source_path.name} during finalization: {e}"
                self.logger.error(self.caller, err_msg, exc_info=True)
                # Continue?

            # 2. Update JSON entries
            updated_count = 0
            for item in self._pending_reviews:
                if item.get('original_source_path') == original_path_str:
                    if item.get('completed_source_path') != completed_path_str:
                        item['completed_source_path'] = completed_path_str
                        updated_count += 1

            if updated_count > 0:
                self.logger.info(self.caller, f"Updated 'completed_source_path' for {updated_count} review entries related to {original_source_path.name}.")
                self._save_data()
            else:
                 self.logger.info(self.caller, f"No pending review entries found or needed update for completed source: {original_source_path.name}")

    def remove_pending_review(self, original_source_path_str: str) -> bool:
        """
        DEPRECATED: Use process_review_decision instead.

        Removes a pending review item identified by its original source path string.

        Args:
            original_source_path_str (str): The original path string of the source image to remove.

        Returns:
            bool: True if an item was found and removed, False otherwise.
        """
        removed = False
        with self._lock:
            # This method is ambiguous now, as multiple items might share the same original_source_path.
            # We need person_name to uniquely identify.
            self.logger.warn(self.caller, f"DEPRECATED method remove_pending_review called for {original_source_path_str}. No action taken. Use process_review_decision.")
            # initial_count = len(self._pending_reviews)
            # self._pending_reviews = [
            #     item for item in self._pending_reviews
            #     if item.get('original_source_path') != original_source_path_str
            # ]
            # if len(self._pending_reviews) < initial_count:
            #     self.logger.info(self.caller, f"Removed entry for {Path(original_source_path_str).name} from pending reviews.")
            #     self._save_data()
            #     removed = True
            # else:
            #      self.logger.warn(self.caller, f"Attempted to remove non-existent entry for {Path(original_source_path_str).name}.")
        return removed

    def process_review_decision(self, person_name: str, original_source_path_str: str, approved_paths: List[str], unapproved_paths: List[str]):
        """
        Processes the user's review decision for a specific item:
        - Moves approved files from Temp to FaceSwapped.
        - Deletes unapproved files from Temp.
        - Removes the item from the pending review list and JSON.
        - Emits review_item_removed on success.
        """
        with self._lock:
            # 1. Get AI Root and target directories
            ai_root_path = self._get_ai_root_path()
            if not ai_root_path:
                self.logger.error(self.caller, f"Cannot process review decision for {original_source_path_str}: AI Root path invalid.")
                return
            face_swapped_dir = ai_root_path / "FaceSwapped"
            temp_dir = ai_root_path / "Temp"

            # Ensure FaceSwapped directory exists
            try:
                face_swapped_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.logger.error(self.caller, f"Could not ensure FaceSwapped directory {face_swapped_dir} exists: {e}")
                return # Cannot proceed if destination doesn't exist

            file_op_errors = 0
            processed_item_name = Path(original_source_path_str).name

            # 2. Perform file moves for approved files
            for src_path_str in approved_paths:
                try:
                    src_path = Path(src_path_str)
                    # Safety check: ensure source is in Temp
                    if not temp_dir in src_path.parents:
                         self.logger.warn(self.caller, f"Skipping approved move, file not in Temp: {src_path}")
                         continue
                    dest_path = face_swapped_dir / src_path.name
                    self.logger.info(self.caller, f"Moving approved file for {processed_item_name}: {src_path.name} -> {face_swapped_dir.name}/")
                    shutil.move(str(src_path), str(dest_path))
                except (IOError, OSError, shutil.Error) as e:
                    self.logger.error(self.caller, f"Error moving approved file {src_path}: {e}")
                    file_op_errors += 1

            # 3. Perform file deletions for unapproved files
            for src_path_str in unapproved_paths:
                try:
                    src_path = Path(src_path_str)
                    # Safety check: ensure source is in Temp
                    if not temp_dir in src_path.parents:
                         self.logger.warn(self.caller, f"Skipping unapproved delete, file not in Temp: {src_path}")
                         continue
                    if src_path.is_file(): # Check if it still exists (might have been moved if approved) - unlikely but safe
                        self.logger.info(self.caller, f"Deleting unapproved file for {processed_item_name}: {src_path.name}")
                        src_path.unlink()
                    else:
                         self.logger.warn(self.caller, f"Tried to delete unapproved file, but it was not found: {src_path}")
                except (IOError, OSError) as e:
                    self.logger.error(self.caller, f"Error deleting unapproved file {src_path}: {e}")
                    file_op_errors += 1

            # 4. Remove the item from pending reviews and save JSON
            # Use helper to find the index
            item_index_to_remove = self._find_review_item_index(person_name, original_source_path_str)
            item_removed = False

            if item_index_to_remove != -1:
                try:
                    removed_item_data = self._pending_reviews.pop(item_index_to_remove)
                    self.logger.info(self.caller, f"Removed entry for {processed_item_name} from pending reviews list.")
                    self._save_data()
                    item_removed = True
                except IndexError:
                     # Should not happen if index is valid, but handle defensively
                     self.logger.error(self.caller, f"IndexError removing item at index {item_index_to_remove}. List length: {len(self._pending_reviews)}")
            else:
                 self.logger.warn(self.caller, f"Tried to remove entry for {processed_item_name}, but it was not found in list.")

            # 5. Emit signal if item was successfully removed from list
            if item_removed:
                # Emit with person_name as well
                self.review_item_removed.emit(person_name, original_source_path_str)
                if file_op_errors > 0:
                     self.logger.warn(self.caller, f"Review processing complete for {processed_item_name} with {file_op_errors} file errors. Item removed from queue.")
                else:
                     self.logger.info(self.caller, f"Review processing complete for {processed_item_name}. Item removed from queue.")
            else:
                 # This case might indicate a logic error or race condition if the item *should* have been there
                 self.logger.error(self.caller, f"Review decision processed for {processed_item_name}, but item was not found in the list for removal! File ops completed with {file_op_errors} errors.")

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Returns a copy of the list of items pending review."""
        with self._lock:
            # Return a deep copy if complex nested objects were stored,
            # but for list of dicts with strings/lists, list[:] is usually sufficient
            # For safety, especially if structure evolves, use copy.deepcopy
            # import copy
            # return copy.deepcopy(self._pending_reviews) 
            return list(self._pending_reviews) # Return a shallow copy

    def get_review_details(self, person_name: str, original_source_path_str: str) -> Optional[Dict[str, Any]]:
        """Finds and returns the full dictionary for a specific pending review item."""
        with self._lock:
            # Use helper to find index
            item_index = self._find_review_item_index(person_name, original_source_path_str)
            if item_index != -1:
                try:
                    # Return a copy to prevent external modification
                    return dict(self._pending_reviews[item_index])
                except IndexError:
                    # Should not happen if index is valid
                    self.logger.error(self.caller, f"IndexError getting details at index {item_index}. List length: {len(self._pending_reviews)}")
                    return None
            else:
                # Item not found
                self.logger.warn(self.caller, f"Could not find review details for {person_name}/{Path(original_source_path_str).name}")
                return None

    def clear_all_pending_reviews(self):
        """Removes all items from the pending review list and saves."""
        with self._lock:
            if self._pending_reviews:
                self.logger.info(self.caller, f"Clearing all {len(self._pending_reviews)} pending review items.")
                self._pending_reviews = []
                self._save_data()
            else:
                self.logger.info(self.caller, "Clear all requested, but no items were pending review.") 