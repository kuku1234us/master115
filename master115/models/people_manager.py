import os
import json
from pathlib import Path
from typing import List, Dict, Optional, TypedDict
from qt_base_app.models import SettingsManager, Logger, SettingType
from .face_swap_models import PersonData, FaceData

# REMOVED Hardcoded fallbacks for AI_ROOT_DIR_KEY and DEFAULT_AI_ROOT_DIR
# They are now managed by SettingsManager

VALID_IMAGE_EXTENSIONS = ["*.jpg", "*.png", "*.jpeg", "*.gif"]

class PeopleManager:
    """Manages the discovery and retrieval of person data from the AI Root Directory."""
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if PeopleManager._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            self.settings = SettingsManager.instance()
            self.logger = Logger.instance()
            self.caller = "PeopleManager"
            self._persons_cache: Optional[List[PersonData]] = None # Cache results
            PeopleManager._instance = self

    def _get_ai_root(self) -> Optional[Path]:
        """Gets and validates the AI Root Directory path from settings."""
        # Use the key and default defined in SettingsManager
        ai_root_raw = self.settings.get(
            SettingsManager.AI_ROOT_DIR_KEY, 
            # SettingsManager.get now uses its internal default, 
            # so we might not need to specify it here, but being explicit is safer.
            default=SettingsManager.DEFAULT_AI_ROOT_DIR, 
            setting_type=SettingType.PATH
        )
        
        if not ai_root_raw: # Should only happen if default is also None/empty
            self.logger.warn(self.caller, "AI Root Directory not set in preferences and no valid default found.")
            return None
        
        # SettingsManager already returns a Path object if setting_type=SettingType.PATH
        ai_root_path = ai_root_raw 
        
        if not ai_root_path.is_dir():
            self.logger.warn(self.caller, f"AI Root Directory path is not a valid directory: {ai_root_path}")
            # Optionally, attempt to create it?
            # try:
            #     ai_root_path.mkdir(parents=True, exist_ok=True)
            #     self.logger.info(self.caller, f"Created AI Root Directory: {ai_root_path}")
            # except OSError as e:
            #     self.logger.error(self.caller, f"Failed to create AI Root Directory {ai_root_path}: {e}")
            #     return None
            return None # For now, just warn and fail if it doesn't exist
            
        return ai_root_path

    def get_persons(self, force_rescan: bool = False) -> List[PersonData]:
        """
        Scans the AI Root/Faces directory and returns a list of PersonData objects.
        Uses a cache unless force_rescan is True.
        """
        if not force_rescan and self._persons_cache is not None:
            self.logger.debug(self.caller, "Returning cached person data.")
            return self._persons_cache

        self.logger.info(self.caller, "Scanning for persons...")
        self._persons_cache = [] # Clear cache before scan

        ai_root_path = self._get_ai_root()
        if not ai_root_path:
            return [] # Return empty list if root dir is invalid

        faces_dir = ai_root_path / "Faces"

        if not faces_dir.is_dir():
            self.logger.warn(self.caller, f"Faces directory not found or not a directory: {faces_dir}")
            # Optionally, create it?
            # try:
            #     faces_dir.mkdir(parents=True, exist_ok=True)
            #     self.logger.info(self.caller, f"Created Faces directory: {faces_dir}")
            # except OSError as e:
            #     self.logger.error(self.caller, f"Failed to create Faces directory {faces_dir}: {e}")
            #     return []
            return [] # For now, fail if not found

        persons_found_data: List[PersonData] = []
        try:
            for item in faces_dir.iterdir():
                if item.is_dir():
                    person_name = item.name
                    face_data_list: List[FaceData] = []
                    first_image_path: Optional[Path] = None # Track the first image for the badge

                    # Scan for face images within the person's directory
                    for img_ext in VALID_IMAGE_EXTENSIONS:
                        for face_path in item.glob(img_ext):
                            if face_path.is_file():
                                face_data_list.append(FaceData(path=face_path))
                                if first_image_path is None:
                                    first_image_path = face_path.resolve()

                    if not face_data_list:
                        self.logger.warn(self.caller, f"No face images found for person: {person_name} in {item}")
                        # Optionally skip, or add person with empty faces list
                        # Adding with empty faces for now, UI can decide how to handle
                        
                    person_data = PersonData(
                        name=person_name, 
                        directory_path=item, 
                        faces=face_data_list
                        # We might add first_image_path here if needed frequently, 
                        # but PersonBadge currently only needs it once at creation.
                    )
                    persons_found_data.append(person_data)
        
        except OSError as e:
            self.logger.error(self.caller, f"Error scanning Faces directory {faces_dir}: {e}")
            return [] # Return empty on error

        self.logger.info(self.caller, f"Found {len(persons_found_data)} persons.")
        self._persons_cache = sorted(persons_found_data, key=lambda x: x.name) # Cache sorted list
        return self._persons_cache

    def get_person_data_by_names(self, names: List[str]) -> List[PersonData]:
        """Retrieves full PersonData for a list of person names from the cache."""
        if self._persons_cache is None:
            self.get_persons() # Ensure cache is populated

        if self._persons_cache is None: # Check again if scan failed
             return []

        # Create a dictionary for quick lookup
        cache_dict = {person.name: person for person in self._persons_cache}
        
        result = [cache_dict[name] for name in names if name in cache_dict]
        
        if len(result) != len(names):
            self.logger.warn(self.caller, f"Could not find data for all requested names. Requested: {names}, Found: {[p.name for p in result]}")
            
        return result

    def invalidate_cache(self):
        """Clears the internal cache, forcing a rescan on the next get_persons call."""
        self.logger.debug(self.caller, "Invalidating person cache.")
        self._persons_cache = None
        
    def get_first_image_path(self, person_name: str) -> Optional[str]:
        """Helper to get the first image path for a specific person, used by the badge."""
        if self._persons_cache is None:
            self.get_persons()
            
        if self._persons_cache is None:
             return None

        for person in self._persons_cache:
            if person.name == person_name:
                if person.faces:
                    return str(person.faces[0].path.resolve())
                else:
                    self.logger.warn(self.caller, f"Person '{person_name}' found but has no face images listed.")
                    return None
        
        self.logger.warn(self.caller, f"Person '{person_name}' not found in cache.")
        return None
        
    def find_face_image_path(self, person_name: str, face_stem: str) -> Optional[str]:
        """Finds the full path to an original face image given the person and stem.
        
        Searches for common image extensions (.jpg, .png, .jpeg, .webp).
        
        Args:
            person_name: The name of the person.
            face_stem: The filename stem of the face image (e.g., '01', 'profile').
            
        Returns:
            The full path to the image file if found, otherwise None.
        """
        ai_root = self._get_ai_root()
        if not ai_root:
            return None
        
        person_dir = Path(ai_root) / "Faces" / person_name
        if not person_dir.is_dir():
            self.logger.warn(self.caller, f"Person directory not found: {person_dir}")
            return None
        
        supported_extensions = [".jpg", ".png", ".jpeg", ".webp"]
        
        for ext in supported_extensions:
            potential_path = person_dir / f"{face_stem}{ext}"
            if potential_path.is_file():
                self.logger.debug(self.caller, f"Found face image: {potential_path}")
                return str(potential_path)
        
        self.logger.warn(self.caller, f"Could not find image for stem '{face_stem}' in {person_dir}")
        return None

# Example usage (optional, for testing)
if __name__ == '__main__':
    # This requires the app's QSettings to be initialized, might not run standalone easily
    # For basic testing, you might mock SettingsManager or set a fixed path
    
    # Mock SettingsManager for basic testing
    class MockSettingsManager:
        AI_ROOT_DIR_KEY = 'ai/root_dir' # Define the key for the mock
        DEFAULT_AI_ROOT_DIR = "D:/AIRoot/Test" # Define the default for the mock
        
        def get(self, key, default=None, setting_type=None):
            if key == self.AI_ROOT_DIR_KEY:
                # --- !!! IMPORTANT: Set this to your actual test AI Root path !!! ---
                test_path_str = self.DEFAULT_AI_ROOT_DIR 
                if setting_type == SettingType.PATH:
                    return Path(test_path_str)
                return test_path_str
            return default
        
        def instance(self):
            # Ensure the mock instance has the necessary class attributes if accessed that way
            # setattr(self, 'AI_ROOT_DIR_KEY', 'ai/root_dir')
            # setattr(self, 'DEFAULT_AI_ROOT_DIR', "D:/AIRoot/Test")
            return self 
    
    # Temporarily replace SettingsManager instance for test
    original_settings = SettingsManager._instance
    mock_settings_instance = MockSettingsManager()
    SettingsManager._instance = mock_settings_instance
    # Add class attributes directly to the mock instance if needed by the code under test
    # setattr(SettingsManager, 'AI_ROOT_DIR_KEY', mock_settings_instance.AI_ROOT_DIR_KEY)
    # setattr(SettingsManager, 'DEFAULT_AI_ROOT_DIR', mock_settings_instance.DEFAULT_AI_ROOT_DIR)
    
    # Mock Logger
    class MockLogger:
        def info(self, *args): print("INFO:", *args)
        def warn(self, *args): print("WARN:", *args)
        def error(self, *args): print("ERROR:", *args)
        def debug(self, *args): print("DEBUG:", *args)
        def instance(self): return self
        
    original_logger = Logger._instance
    Logger._instance = MockLogger()

    print("--- Testing PeopleManager ---")
    # Access the singleton instance (which should be our mock now)
    manager = PeopleManager.instance() 
    
    # Ensure test directory structure exists:
    # D:/AIRoot/Test/Faces/PersonA/faceA1.jpg
    # D:/AIRoot/Test/Faces/PersonB/faceB1.png, faceB2.jpg
    # D:/AIRoot/Test/Faces/PersonC/ (empty)
    
    all_people = manager.get_persons(force_rescan=True)
    print(f"\nFound Persons ({len(all_people)}):")
    for p in all_people:
        print(f"  - {p.name} (Faces: {len(p.faces)})")
        for f in p.faces:
            print(f"    - {f.filename}")
            
    print("\nGetting data for PersonA and PersonB:")
    selected_data = manager.get_person_data_by_names(["PersonA", "PersonB", "MissingPerson"])
    for p in selected_data:
        print(f"  - Retrieved: {p.name}")
        
    print("\nGetting first image path for PersonB:")
    img_path = manager.get_first_image_path("PersonB")
    print(f"  - Path: {img_path}")
    
    print("\nGetting first image path for PersonC (no faces):")
    img_path = manager.get_first_image_path("PersonC")
    print(f"  - Path: {img_path}")

    print("\n--- Test Complete ---")
    
    # Restore original instances if needed
    SettingsManager._instance = original_settings
    Logger._instance = original_logger 