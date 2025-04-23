import json
import threading
import shutil
from pathlib import Path
from typing import List, Dict, Set, Optional, Any

from PyQt6.QtCore import QObject, pyqtSignal
from qt_base_app.models import Logger, SettingsManager, SettingType

# Constants
PENDING_REVIEW_FILENAME = "PendingReview.json"

class ReviewManager(QObject):
    """
    Manages the state of face swap results pending user review,
    persisting the data in PendingReview.json within the AI Root Directory.
    Implemented as a thread-safe singleton.
    """
    # Signal emitted when a new item is successfully added and ready for review
    # Payload is the dictionary representing the added item
    review_item_added = pyqtSignal(dict)

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
                                all(k in item for k in ['original_source_path', 'completed_source_path', 'result_image_paths'])
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

    # --- Public API --- #

    def add_pending_review(self, original_source_path: Path, result_paths: Set[str]):
        """
        Moves the completed source file, adds the entry to the pending review list,
        saves the list, and emits a signal.
        """
        with self._lock:
            # --- Calculate Paths --- #
            ai_root_path = self._get_ai_root_path() # Get validated AI Root path
            if not ai_root_path:
                self.logger.error(self.caller, f"Cannot add pending review for {original_source_path.name}, AI Root path not found.")
                return # Cannot proceed

            completed_dir = ai_root_path / "SourceImages" / "Completed"
            completed_path = completed_dir / original_source_path.name
            # ---------------------- #

            # Use string paths for consistency and JSON compatibility
            original_path_str = str(original_source_path.resolve())
            completed_path_str = str(completed_path.resolve()) # Use calculated path
            result_paths_list = sorted([str(Path(p).resolve()) for p in result_paths])

            # --- Move File First --- #
            try:
                completed_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(self.caller, f"Moving completed source '{original_source_path.name}' to Completed/ folder.")
                shutil.move(str(original_source_path), str(completed_path))
                self.logger.info(self.caller, f"Successfully moved {original_source_path.name} to {completed_path}")
            except OSError as e:
                err_msg = f"Error moving {original_source_path.name} to Completed/: {e}"
                self.logger.error(self.caller, err_msg, exc_info=True)
                # Do not add to JSON or emit signal if move fails
                return
            except Exception as e:
                err_msg = f"Unexpected error moving {original_source_path.name}: {e}"
                self.logger.error(self.caller, err_msg, exc_info=True)
                # Do not add to JSON or emit signal if move fails
                return
            # ----------------------- #

            # Check for duplicates based on original_source_path
            if any(item.get('original_source_path') == original_path_str for item in self._pending_reviews):
                self.logger.warn(self.caller, f"Attempted to add duplicate entry for {original_source_path.name}. Ignoring.")
                return

            new_entry = {
                'original_source_path': original_path_str,
                'completed_source_path': completed_path_str,
                'result_image_paths': result_paths_list
            }
            
            self._pending_reviews.append(new_entry)
            self.logger.info(self.caller, f"Added entry for {original_source_path.name} to pending reviews.")
            self._save_data()
            # Emit signal *after* successful move and save
            self.review_item_added.emit(new_entry)

    def remove_pending_review(self, original_source_path_str: str) -> bool:
        """
        Removes a pending review item identified by its original source path string.

        Args:
            original_source_path_str (str): The original path string of the source image to remove.

        Returns:
            bool: True if an item was found and removed, False otherwise.
        """
        removed = False
        with self._lock:
            initial_count = len(self._pending_reviews)
            self._pending_reviews = [
                item for item in self._pending_reviews 
                if item.get('original_source_path') != original_source_path_str
            ]
            if len(self._pending_reviews) < initial_count:
                self.logger.info(self.caller, f"Removed entry for {Path(original_source_path_str).name} from pending reviews.")
                self._save_data()
                removed = True
            else:
                 self.logger.warn(self.caller, f"Attempted to remove non-existent entry for {Path(original_source_path_str).name}.")
        return removed

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Returns a copy of the list of items pending review."""
        with self._lock:
            # Return a deep copy if complex nested objects were stored,
            # but for list of dicts with strings/lists, list[:] is usually sufficient
            # For safety, especially if structure evolves, use copy.deepcopy
            # import copy
            # return copy.deepcopy(self._pending_reviews) 
            return list(self._pending_reviews) # Return a shallow copy

    def clear_all_pending_reviews(self):
        """Removes all items from the pending review list and saves."""
        with self._lock:
            if self._pending_reviews:
                self.logger.info(self.caller, f"Clearing all {len(self._pending_reviews)} pending review items.")
                self._pending_reviews = []
                self._save_data()
            else:
                self.logger.info(self.caller, "Clear all requested, but no items were pending review.") 