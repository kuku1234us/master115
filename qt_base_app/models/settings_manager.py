"""
Settings manager module for handling application settings.

This module provides a robust and reusable settings management system that can be used
across different applications. It wraps QSettings to provide:
- Type safety and validation
- Default values
- Hierarchical settings organization
- Support for complex data types
- Settings migration capabilities
- Singleton pattern for global access
"""

from typing import Any, Dict, List, Optional, Union, TypeVar, Type
from enum import Enum
import json
import yaml
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QSettings

T = TypeVar('T')

class SettingType(Enum):
    """Enumeration of supported setting types"""
    STRING = str
    INT = int
    FLOAT = float
    BOOL = bool
    LIST = list
    DICT = dict
    DATETIME = datetime
    PATH = Path

class SettingsManager:
    """
    A singleton class to manage application settings with type safety and validation.
    
    Features:
    - Type-safe settings storage and retrieval
    - Hierarchical organization with namespaces
    - Default values
    - Complex data type support (lists, dicts, datetime, paths)
    - Settings validation
    - Automatic type conversion
    - Settings migration from legacy QSettings
    
    Example usage:
        settings = SettingsManager.instance()
        
        # Store settings
        settings.set('player/volume', 75, SettingType.INT)
        settings.set('preferences/playlists_dir', Path('/music/playlists'), SettingType.PATH)
        
        # Retrieve settings
        volume = settings.get('player/volume', 100, SettingType.INT)
        playlists_dir = settings.get('preferences/playlists_dir', Path.home(), SettingType.PATH)
    """
    
    _instance = None
    
    @classmethod
    def instance(cls) -> 'SettingsManager':
        """Get the singleton instance of SettingsManager"""
        if cls._instance is None:
            cls._instance = cls('MusicPlayer', 'App')
            cls._instance._migrate_legacy_settings()
        return cls._instance
    
    def __init__(self, organization: str, application: str):
        """
        Initialize the settings manager.
        
        Args:
            organization: Organization name
            application: Application name
        """
        if SettingsManager._instance is not None:
            raise RuntimeError("Use SettingsManager.instance() to get the settings manager")
            
        self._settings = QSettings(organization, application)
        
        # --- Add storage for loaded YAML config --- 
        self._yaml_config: Dict[str, Any] = {} 
        # -------------------------------------------
        
        self._type_converters = {
            SettingType.STRING: str,
            SettingType.INT: int,
            SettingType.FLOAT: float,
            SettingType.BOOL: bool,
            SettingType.LIST: self._convert_list,
            SettingType.DICT: self._convert_dict,
            SettingType.DATETIME: self._convert_datetime,
            SettingType.PATH: Path
        }
        
        # Define keys consistently
        SettingsManager.AI_ROOT_DIR_KEY = 'ai/root_dir'
        SettingsManager.DEFAULT_AI_ROOT_DIR = str(Path.home() / "AIRoot") # Default to User's Home/AIRoot
        # --- Add Face Swap Specific Keys ---
        SettingsManager.AI_FACE_SWAP_MOVE_SOURCE_KEY = 'ai/faceswap/move_source_to_completed'
        SettingsManager.AI_FACE_SWAP_RUN_HEADLESS_KEY = 'ai/faceswap/run_headless'
        # ---------------------------------

        # Default settings (for registry/QSettings) - AI defaults removed previously
        self._defaults = {
            'player/volume': (100, SettingType.INT),
            'preferences/seek_interval': (3, SettingType.INT),
            'preferences/playlists_dir': (str(Path.home()), SettingType.PATH),
            'ui/sidebar/expanded': (True, SettingType.BOOL),
            'recent/files': ([], SettingType.LIST),
            'recent/playlists': ([], SettingType.LIST),
            # --- Add AI Root Default ---
            SettingsManager.AI_ROOT_DIR_KEY: (SettingsManager.DEFAULT_AI_ROOT_DIR, SettingType.PATH),
            # --- Add Face Swap Defaults ---
            SettingsManager.AI_FACE_SWAP_MOVE_SOURCE_KEY: (True, SettingType.BOOL), # Default to moving files
            SettingsManager.AI_FACE_SWAP_RUN_HEADLESS_KEY: (True, SettingType.BOOL),  # Default to running headless
            # --------------------------
        }
        
        # Initialize QSettings with defaults if not set
        for key, (default_value, setting_type) in self._defaults.items():
            if not self.contains(key):
                # Use the internal method to set QSettings values
                self._set_qsetting(key, default_value, self._get_setting_type_enum(setting_type))
    
    def _migrate_legacy_settings(self):
        """Migrate settings from legacy QSettings to new format"""
        # logger = Logger.instance() # Logger removed, print simple message for now
        # Legacy settings locations
        legacy_player = QSettings('MusicPlayer', 'Player')
        legacy_prefs = QSettings('MusicPlayer', 'Preferences')
        
        # Migration mappings (old_key, old_settings, new_key, setting_type)
        migrations = [
            # Player settings
            ('player/volume', legacy_player, 'player/volume', SettingType.INT),
            
            # Preference settings
            ('seek_interval', legacy_prefs, 'preferences/seek_interval', SettingType.INT),
            ('playlists_dir', legacy_prefs, 'preferences/playlists_dir', SettingType.PATH),
            ('sidebar_expanded', legacy_prefs, 'ui/sidebar/expanded', SettingType.BOOL)
        ]
        
        # Perform migrations
        for old_key, old_settings, new_key, setting_type in migrations:
            if old_settings.contains(old_key):
                value = old_settings.value(old_key)
                if value is not None:
                    try:
                        self.set(new_key, value, setting_type)
                        old_settings.remove(old_key)
                    except (ValueError, TypeError) as e:
                        # print(f"Error migrating setting {old_key}: {e}") # Replaced logger with simple print
                        pass # Silently ignore migration errors for now
        
        # Sync changes
        legacy_player.sync()
        legacy_prefs.sync()
        self.sync()

    def set_defaults(self, defaults: Dict[str, tuple]):
        """
        Set default values for QSettings.
        """
        self._defaults.update(defaults)
        for key, (default_value, setting_type) in defaults.items():
            if not self.contains(key):
                self.set(key, default_value, setting_type)
                
    def reset_to_defaults(self):
        """
        Reset all QSettings to their default values.
        """
        for key, (default_value, setting_type) in self._defaults.items():
            self.set(key, default_value, setting_type)
            
    def _get_setting_type_enum(self, setting_type: Union[SettingType, Type]) -> Optional[SettingType]:
        """Helper to get the SettingType enum from various inputs."""
        if isinstance(setting_type, SettingType):
            return setting_type
        try:
            return SettingType(setting_type)
        except ValueError:
            return None
            
    def get_setting_type(self, key: str) -> Optional[SettingType]:
        """Get the type of a QSetting by its key"""
        return self._get_setting_type_enum(self._defaults.get(key, (None, None))[1])

    # Renamed 'set' to '_set_qsetting' to avoid conflict and clarify purpose
    def _set_qsetting(self, key: str, value: Any, setting_type: Optional[SettingType] = None) -> None:
        """
        Internal method to set a QSettings value with type validation.
        """
        if setting_type:
            if isinstance(setting_type, SettingType):
                converter = self._type_converters[setting_type]
            else:
                converter = setting_type
                
            try:
                value = converter(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid value type for {key}. Expected {setting_type}, got {type(value)}") from e
        
        # Special handling for complex types
        if isinstance(value, (list, dict, datetime, Path)):
            value = self._serialize_value(value)
            
        # Special handling for boolean values to ensure consistent storage
        if isinstance(value, bool):
            value = 1 if value else 0
            
        self._settings.setValue(key, value)
        
    # Add a public 'set' method that calls the internal one
    def set(self, key: str, value: Any, setting_type: Optional[Union[SettingType, Type]] = None) -> None:
        """
        Set a persistent setting value (in QSettings/Registry) with type validation.
        
        Args:
            key: The setting key (can be hierarchical, e.g., 'app/window/size')
            value: The value to store
            setting_type: Optional type validation (SettingType enum or Python type)
        """
        st_enum = self._get_setting_type_enum(setting_type)
        self._set_qsetting(key, value, st_enum)

    # Renamed 'get' to '_get_qsetting' to avoid conflict and clarify purpose
    def _get_qsetting(self, key: str, default: Any = None, setting_type: Optional[SettingType] = None) -> Any:
        """
        Internal method to get a QSettings value with type conversion.
        """
        value = self._settings.value(key, default)
        
        if value is None:
            return default
        
        # Special handling for boolean values from QSettings
        if setting_type == SettingType.BOOL or setting_type == bool:
            # QSettings sometimes stores booleans as strings, handle both cases
            if isinstance(value, str):
                # Case-insensitive comparison for string representations
                return value.lower() in ('true', '1', 'yes', 'y', 'on')
            else:
                # Otherwise, convert to bool directly
                return bool(value)
            
        if setting_type:
            # --- Path Validation Logic --- #
            if setting_type == SettingType.PATH:
                try:
                    path_obj = Path(value) # Convert first
                    if not path_obj.exists():
                        # Use Logger if available, otherwise print
                        msg = f"Path setting '{key}' does not exist: {path_obj}"
                        try:
                            Logger.instance().warning(self.__class__.__name__, msg)
                        except Exception:
                            print(f"[SettingsManager WARNING] {msg}")
                        return None # Indicate invalid path
                    if not path_obj.is_dir():
                        msg = f"Path setting '{key}' is not a directory: {path_obj}"
                        try:
                            Logger.instance().warning(self.__class__.__name__, msg)
                        except Exception:
                            print(f"[SettingsManager WARNING] {msg}")
                        return None # Indicate invalid path
                    # Path is valid, return the Path object
                    return path_obj 
                except Exception as e:
                    # Handle potential errors during Path() conversion itself
                    msg = f"Error converting path setting '{key}': {e}"
                    try:
                        Logger.instance().warning(self.__class__.__name__, msg)
                    except Exception:
                        print(f"[SettingsManager WARNING] {msg}")
                    return None # Indicate invalid path
            # --- End Path Validation --- #

            # --- Other Type Conversions --- #
            converter: Optional[callable] = None
            if isinstance(setting_type, SettingType):
                # Handle other complex types needing deserialization first
                if isinstance(value, str) and setting_type in [SettingType.LIST, SettingType.DICT, SettingType.DATETIME]:
                    try:
                        value = self._deserialize_value(value, setting_type)
                    except (json.JSONDecodeError, ValueError) as e:
                        msg = f"Error deserializing setting '{key}' for type {setting_type}: {e}"
                        try:
                            Logger.instance().warning(self.__class__.__name__, msg)
                        except Exception:
                            print(f"[SettingsManager WARNING] {msg}")
                        return default # Return default on deserialization error
                # Get the final converter
                converter = self._type_converters.get(setting_type)
            elif callable(setting_type):
                converter = setting_type
                
            if converter:
                try:
                    return converter(value)
                except (ValueError, TypeError) as e:
                    msg = f"Error converting setting '{key}' to type {setting_type}: {e}"
                    try:
                        Logger.instance().warning(self.__class__.__name__, msg)
                    except Exception:
                        print(f"[SettingsManager WARNING] {msg}")
                    return default # Return default on final conversion error
            else:
                # Should not happen if setting_type is valid
                msg = f"Invalid setting_type provided for key '{key}': {setting_type}"
                try:
                    Logger.instance().error(self.__class__.__name__, msg)
                except Exception:
                    print(f"[SettingsManager ERROR] {msg}")
                return default
            # --- End Other Type Conversions --- #
                
        # If no setting_type specified, return raw value from QSettings
        return value
        
    # Add a public 'get' method that calls the internal one
    def get(self, key: str, default: Any = None, setting_type: Optional[Union[SettingType, Type]] = None) -> Any:
        """
        Get a persistent setting value (from QSettings/Registry) with type conversion.
        
        Args:
            key: The setting key
            default: Default value if setting doesn't exist
            setting_type: Optional type to convert the value to
            
        Returns:
            The setting value converted to the specified type, or the default value
        """
        st_enum = self._get_setting_type_enum(setting_type)
        return self._get_qsetting(key, default, st_enum)

    def remove(self, key: str) -> None:
        """Remove a setting"""
        self._settings.remove(key)
    
    def clear(self) -> None:
        """Clear all settings"""
        self._settings.clear()
    
    def contains(self, key: str) -> bool:
        """Check if a setting exists"""
        return self._settings.contains(key)
    
    def all_keys(self) -> List[str]:
        """Get all setting keys"""
        return self._settings.allKeys()
    
    def begin_group(self, prefix: str) -> None:
        """Begin a settings group"""
        self._settings.beginGroup(prefix)
    
    def end_group(self) -> None:
        """End the current settings group"""
        self._settings.endGroup()
    
    def sync(self) -> None:
        """Sync settings to storage"""
        self._settings.sync()
        
    def _serialize_value(self, value: Any) -> str:
        """Serialize complex types to string"""
        if isinstance(value, (list, dict)):
            return json.dumps(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Path):
            return str(value)
        return value
        
    def _deserialize_value(self, value: str, setting_type: SettingType) -> Any:
        """Deserialize string to complex type"""
        if setting_type == SettingType.LIST:
            return json.loads(value)
        elif setting_type == SettingType.DICT:
            return json.loads(value)
        elif setting_type == SettingType.DATETIME:
            return datetime.fromisoformat(value)
        elif setting_type == SettingType.PATH:
            return Path(value)
        return value
    
    def _convert_list(self, value: Union[str, list]) -> list:
        """Convert value to list"""
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
    
    def _convert_dict(self, value: Union[str, dict]) -> dict:
        """Convert value to dict"""
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)
    
    def _convert_datetime(self, value: Union[str, datetime]) -> datetime:
        """Convert value to datetime"""
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    # --- Add methods for YAML config loading and access --- 
    def load_yaml_config(self, config_path: Union[str, Path]):
        """Loads configuration from a YAML file into the manager."""
        # logger = Logger.instance()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._yaml_config = yaml.safe_load(f) or {}
                # logger.info(f"Successfully loaded YAML config from: {config_path}")
        except FileNotFoundError:
            # logger.warning(f"YAML config file not found at {config_path}. Using empty config.")
            self._yaml_config = {}
        except yaml.YAMLError as e:
            # logger.error(f"Error parsing YAML config file {config_path}: {e}")
            self._yaml_config = {}
        except Exception as e:
            # logger.error(f"Error loading YAML config {config_path}: {e}")
            self._yaml_config = {}
            
    def get_yaml_config(self, key_path: str, default: Any = None) -> Any:
        """
        Retrieves a value from the loaded YAML configuration using a dot-separated key path.
        
        Args:
            key_path: Dot-separated path (e.g., 'app.window.width', 'ai.groq.model_name').
            default: Default value to return if the key path is not found.
            
        Returns:
            The value found at the key path, or the default value.
        """
        # logger = Logger.instance()
        try:
            keys = key_path.split('.')
            value = self._yaml_config
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    # Tried to access a key on a non-dict item
                    return default 
            return value
        except KeyError:
            # Key not found at some level
            return default
        except Exception as e:
            # logger.error(f"Error accessing YAML config key '{key_path}': {e}")
            return default
    # -------------------------------------------------------- 