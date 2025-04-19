#!/usr/bin/env python
"""
Entry point script to run the Movie Python application.
"""
import sys
import os

# If running from the project root, this might not be necessary,
# but it ensures the modules can be found if run from elsewhere.
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from qt_base_app.app import create_application, run_application
from master115.ui.main_window import MainWindow # Import our new MainWindow

def main():
    """Main entry point for the Movie Python application."""
    # Create application with MainWindow as the main window
    app, window = create_application(
        window_class=MainWindow, # Use our subclass
        # Application configuration
        config_path="master115/resources/master115_config.yaml",
        # Icon paths (provide paths to .ico/.png)
        icon_paths=[
            "master115/resources/master115.ico", # Used for .exe and potentially taskbar
            "master115/resources/master115.png"
        ],
        # Font configuration (optional, copy from music player example if needed)
        # fonts_dir="fonts",
        # font_mappings={
        #     "Geist-Regular.ttf": "default",
        #     "GeistMono-Regular.ttf": "monospace",
        # }
    )

    # Run the application
    return run_application(app, window)

if __name__ == "__main__":
    sys.exit(main()) 