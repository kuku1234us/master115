#!/usr/bin/env python
"""
Entry point script to run the Music Player application.
"""
import sys
import os

from qt_base_app.app import create_application, run_application
from music_player.ui.dashboard import MusicPlayerDashboard

def main():
    """Main entry point for the Music Player application."""
    # Create application with MusicPlayerDashboard as the main window
    app, window = create_application(
        window_class=MusicPlayerDashboard,
        # Application configuration
        config_path="music_player/resources/music_player_config.yaml",
        # Icon paths to try in order of preference (ICO first for Windows)
        icon_paths=[
            "music_player/resources/play.ico",
            "music_player/resources/play.png"
        ],
        # Font configuration
        fonts_dir="fonts",
        font_mappings={
            "Geist-Regular.ttf": "default",
            "GeistMono-Regular.ttf": "monospace",
            "ICARubrikBlack.ttf": "title"
        }
    )
    
    # Run the application
    return run_application(app, window)

if __name__ == "__main__":
    sys.exit(main()) 