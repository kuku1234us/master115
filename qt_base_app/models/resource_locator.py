# qt_base_app/models/resource_locator.py
import sys
import os

from .logger import Logger

class ResourceLocator:
    """
    Provides a reliable way to locate resource files both when running
    from source and when running as a bundled application (PyInstaller).
    """

    @staticmethod
    def get_path(relative_path: str) -> str:
        """
        Get the absolute path to a resource file.

        Args:
            relative_path: The path to the resource relative to the
                           application root (source) or the bundle root (_MEIPASS).

        Returns:
            The absolute path to the resource.
        """
        logger = Logger.instance()
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            # This is the base path when running as a bundled app
            base_path = sys._MEIPASS
            logger.debug("ResourceLocator", f"Running bundled, _MEIPASS: {base_path}")
        except AttributeError:
            # _MEIPASS attribute not found, running from source.
            # Use the directory of the main script (sys.argv[0]) as the base.
            # This assumes resources are relative to where the app starts.
            base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
            # Fallback if sys.argv[0] is not reliable (e.g., interactive session)
            if not os.path.isdir(base_path):
                 base_path = os.path.abspath(".") # Use current working directory as last resort

            logger.debug("ResourceLocator", f"Running from source, base_path: {base_path}")


        # Ensure base_path exists
        if not os.path.isdir(base_path):
             logger.warning("ResourceLocator", f"Determined base_path does not exist: {base_path}")
             # Return the relative path hoping the system can find it? Or raise error?
             # Let's return the joined path anyway for now.
             # raise FileNotFoundError(f"Could not determine a valid base path for resources.")


        # Important: Use os.path.normpath to handle potential mixed slashes
        resource_abs_path = os.path.normpath(os.path.join(base_path, relative_path))
        logger.debug("ResourceLocator", f"Resolved '{relative_path}' to: {resource_abs_path}")

        return resource_abs_path
