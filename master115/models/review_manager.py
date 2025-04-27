import json
import threading
import shutil
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from datetime import datetime # Needed for backup timestamp
from collections import defaultdict # Import defaultdict

from PyQt6.QtCore import QObject, pyqtSignal
from qt_base_app.models import Logger, SettingsManager, SettingType

# Constants
# PENDING_REVIEW_FILENAME = "PendingReview.json" # Removed
# Define expected keys for the new JSON structure
# JSON_REQUIRED_KEYS = ['person_name', 'original_source_path', 'result_image_paths'] # Removed

class ReviewManager(QObject):
    """
    Manages the discovery of face swap results pending user review by scanning
    the Temp directory.
    Implemented as a thread-safe singleton.
    """
    # Signal emitted when a new item is successfully added and ready for review
    # review_item_added = pyqtSignal(dict) # Removed

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        """Gets the singleton instance of the ReviewManager."""
        # Lock is still useful if multiple threads might scan/process simultaneously
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
        
        # self._pending_reviews: List[Dict[str, Any]] = [] # Removed
        # self._json_path: Optional[Path] = None # Removed
        # self._load_data() # Removed - data is now scanned dynamically

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

    # --- Removed JSON handling methods --- #
    # def _get_json_path(self) -> Optional[Path]: ...
    # def _load_data(self): ...
    # def _save_data(self): ...
    # def _backup_corrupt_json(self, json_path: Path): ...
    # def _find_review_item_index(self, person_name: str, original_source_path_str: str) -> int: ...
    # --- ----------------------------- --- #

    # --- Removed deprecated/unused API methods --- #
    # def add_pending_review(self, original_source_path: Path, result_paths: Set[str]): ...
    # def add_person_source_review(self, person_name: str, original_source_path: Path, result_paths: Set[str]): ...
    # def mark_source_completed_and_move(self, original_source_path: Path): ...
    # def remove_pending_review(self, original_source_path_str: str) -> bool: ...
    # def get_pending_reviews(self) -> List[Dict[str, Any]]: ...
    # def get_review_details(self, person_name: str, original_source_path_str: str) -> Optional[Dict[str, Any]]: ...
    # def clear_all_pending_reviews(self): ...
    # --- ----------------------------------- --- #

    # --- Public API --- #

    def scan_temp_for_review_items(self) -> List[Dict[str, Any]]:
        """Scans the Temp directory, parses filenames, and returns review items grouped by (person, source stem)."""
        with self._lock:
            ai_root_path = self._get_ai_root_path()
            if not ai_root_path:
                return [] # Cannot scan without AI Root

            temp_dir = ai_root_path / "Temp"
            if not temp_dir.is_dir():
                self.logger.debug(self.caller, f"Temp directory not found: {temp_dir}. No items to review.")
                return []

            # Group results by (person_name, source_stem) tuple
            # Structure: { (person_name, source_stem): List[str] } # Store list of result paths
            grouped_results = defaultdict(list)
            file_count = 0
            parse_errors = 0

            try:
                for temp_file in temp_dir.glob('*.jpg'): # Only look for .jpg files
                    if not temp_file.is_file():
                        continue
                    file_count += 1
                    
                    full_stem = temp_file.stem
                    parts = full_stem.split(' ')

                    if len(parts) < 3:
                        self.logger.warn(self.caller, f"Skipping file in Temp dir with unexpected name format (less than 3 parts): {temp_file.name}")
                        parse_errors += 1
                        continue
                    
                    person_name = parts[0]
                    # face_stem = parts[1] # We don't use this for grouping
                    source_stem = " ".join(parts[2:]) # Join remaining parts for source stem
                    
                    # Store the full path to the result file
                    result_path_str = str(temp_file.resolve())
                    
                    # Use tuple (person_name, source_stem) as the key
                    group_key = (person_name, source_stem)
                    grouped_results[group_key].append(result_path_str)

            except OSError as e:
                self.logger.error(self.caller, f"Error scanning Temp directory {temp_dir}: {e}")
                return [] # Return empty on scanning error

            self.logger.debug(self.caller, f"Scanned {file_count} .jpg files in Temp. Found {len(grouped_results)} unique (person, source_stem) groups. Encountered {parse_errors} parse errors.")

            # Convert the tuple-keyed dictionary into the list format expected by the UI
            review_items = []
            # Iterate through items, unpacking the tuple key
            for (person_name, source_stem), result_paths in grouped_results.items():
                if result_paths: # Only add if there are actually result paths
                    review_items.append({
                        'person_name': person_name,
                        'source_stem': source_stem,
                        'result_image_paths': sorted(result_paths) # Sort paths for consistency
                    })
                # No need for the 'else' logging from previous version, as the key guarantees person_name exists

            # Sort the final list (e.g., by person name then source stem for consistent UI order)
            return sorted(review_items, key=lambda x: (x['person_name'], x['source_stem']))

    def process_review_decision(self, approved_paths: List[str], unapproved_paths: List[str]) -> bool:
        """
        Processes the user's review decision:
        - Moves approved files from Temp to FaceSwapped.
        - Deletes unapproved files from Temp.
        Returns True if file operations were attempted, False on critical setup error.
        """
        with self._lock:
            # 1. Get AI Root and target directories
            ai_root_path = self._get_ai_root_path()
            if not ai_root_path:
                self.logger.error(self.caller, f"Cannot process review decision: AI Root path invalid.")
                return False # Critical setup error
                
            face_swapped_dir = ai_root_path / "FaceSwapped"
            temp_dir = ai_root_path / "Temp"

            # Ensure FaceSwapped directory exists
            try:
                face_swapped_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.logger.error(self.caller, f"Could not ensure FaceSwapped directory {face_swapped_dir} exists: {e}")
                return False # Cannot proceed if destination doesn't exist

            file_op_errors = 0
            # Extract a representative name for logging, if possible
            log_item_name = Path(approved_paths[0]).name if approved_paths else (Path(unapproved_paths[0]).name if unapproved_paths else "unknown item")
            log_item_name = " ".join(log_item_name.split(' ')[2:]) # Get the source stem part for logging

            # 2. Perform file moves for approved files
            for src_path_str in approved_paths:
                try:
                    src_path = Path(src_path_str).resolve() # Ensure we have absolute path
                    # Safety check: ensure source is in Temp
                    if not str(temp_dir.resolve()) in str(src_path.parent):
                         self.logger.warn(self.caller, f"Skipping approved move, file not in Temp dir '{temp_dir}': {src_path}")
                         continue
                    dest_path = face_swapped_dir / src_path.name
                    self.logger.info(self.caller, f"Moving approved file for {log_item_name}: {src_path.name} -> {face_swapped_dir.name}/")
                    shutil.move(str(src_path), str(dest_path))
                except (IOError, OSError, shutil.Error) as e:
                    self.logger.error(self.caller, f"Error moving approved file {src_path}: {e}")
                    file_op_errors += 1
                except Exception as e:
                     self.logger.error(self.caller, f"Unexpected error moving approved file {src_path_str}: {e}", exc_info=True)
                     file_op_errors += 1

            # 3. Perform file deletions for unapproved files
            for src_path_str in unapproved_paths:
                try:
                    src_path = Path(src_path_str).resolve()
                    # Safety check: ensure source is in Temp
                    if not str(temp_dir.resolve()) in str(src_path.parent):
                         self.logger.warn(self.caller, f"Skipping unapproved delete, file not in Temp dir '{temp_dir}': {src_path}")
                         continue
                    if src_path.is_file(): # Check if it still exists
                        self.logger.info(self.caller, f"Deleting unapproved file for {log_item_name}: {src_path.name}")
                        src_path.unlink()
                    else:
                         self.logger.warn(self.caller, f"Tried to delete unapproved file, but it was not found: {src_path}")
                except (IOError, OSError) as e:
                    self.logger.error(self.caller, f"Error deleting unapproved file {src_path}: {e}")
                    file_op_errors += 1
                except Exception as e:
                     self.logger.error(self.caller, f"Unexpected error deleting unapproved file {src_path_str}: {e}", exc_info=True)
                     file_op_errors += 1
            
            # 4. Log completion status (No state removal needed)
            if file_op_errors > 0:
                self.logger.warn(self.caller, f"Review file processing complete for source stem '{log_item_name}' with {file_op_errors} errors.")
            else:
                self.logger.info(self.caller, f"Review file processing complete for source stem '{log_item_name}'.")

            # Return True because file operations were attempted
            return True 