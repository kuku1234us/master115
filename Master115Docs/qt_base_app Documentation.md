# Introduction

The `qt_base_app` framework provides a foundational structure for building desktop applications using PyQt6. Its primary goal is to offer a reusable toolkit that simplifies common application development tasks, such as configuration management, theming, persistent settings, logging, and establishing a standard window layout. By handling these boilerplate aspects, the framework allows developers to focus more on the unique features and logic of their specific application.

This document serves as a guide for understanding the architecture, components, and usage patterns of the `qt_base_app` framework. It is geared towards developers who will be building applications on top of this base, providing explanations and examples to facilitate rapid development.

## Architecture and Structure

The framework is organized into several key directories, each responsible for a distinct aspect of the application's base functionality:

*   `/qt_base_app`
    *   `app.py`: The main application setup script. Contains functions to initialize the Qt application instance (`QApplication`), configure styling (like dark title bars on Windows), load custom fonts, and create the main application window.
    *   `/components`: Contains reusable UI components that are not specific to a particular application but provide common UI patterns. Example: `SidebarWidget`.
    *   `/config`: (Potentially) Holds default or base configuration files for the framework itself, although application-specific configuration is typically external.
    *   `/models`: Contains non-UI logic, data management, and utility classes. Examples: `SettingsManager`, `ThemeManager`, `ResourceLocator`, `Logger`.
    *   `/theme`: Handles visual styling. Contains the theme configuration (`theme.yaml`) and the `ThemeManager` class responsible for loading and providing theme properties (colors, fonts, dimensions, stylesheets).
    *   `/window`: Contains base window implementations. `BaseWindow` provides a standard layout with a sidebar and a central content area.

This modular structure promotes separation of concerns, making the framework easier to understand, maintain, and extend.

## Core Components and Helpers

### 1. Models (`qt_base_app/models/`)

This directory houses the backbone services and data handling classes.

*   **`SettingsManager` (`settings_manager.py`)**
    *   **Purpose:** Provides a centralized, singleton interface for managing application settings.
    *   **Functionality:** It cleverly combines two types of settings:
        *   **Persistent Settings (Registry/QSettings):** Uses PyQt6's `QSettings` to store user-specific settings that should persist between application runs (e.g., window size, volume, last-used directories). On Windows, this typically maps to the Registry; on other OSes, it uses appropriate native methods. Accessed via `SettingsManager.instance().get(...)` and `SettingsManager.instance().set(...)`.
        *   **Static Configuration (YAML):** Loads a main application configuration file (specified during application startup, e.g., `music_player_config.yaml`) into memory. This YAML file defines the application's structure, initial settings, sidebar layout, AI parameters, logging configuration, etc. Accessed via `SettingsManager.instance().get_yaml_config(...)`.
    *   **Key Methods:**
        *   `instance()`: Accesses the singleton instance.
        *   `load_yaml_config(path)`: Loads the specified YAML file.
        *   `get_yaml_config(key_path, default)`: Retrieves values from the loaded YAML using dot notation (e.g., `'app.title'`).
        *   `get(key, default, type)`: Retrieves a persistent setting (from Registry/QSettings).
        *   `set(key, value, type)`: Stores a persistent setting.
    *   **Why Separate?** This distinction is important. YAML configuration is typically for defining the application's static structure and default behaviors, read once at startup. Persistent settings are for user preferences and state that change during runtime and need to be saved.
    *   **Usage Example:**
        ```python
        from qt_base_app.models import SettingsManager, SettingType
        from pathlib import Path

        # Get the instance
        settings = SettingsManager.instance()

        # --- YAML Config Access ---
        # Assuming YAML has: app: { title: "MyApp" }
        app_title = settings.get_yaml_config('app.title', 'Default Title')
        print(f"App Title from YAML: {app_title}")

        # Assuming YAML has: ai: { groq: { model_name: "llama-x" } }
        model = settings.get_yaml_config('ai.groq.model_name', 'default-model')
        print(f"AI Model: {model}")

        # --- Persistent Settings (Registry/QSettings) Access ---

        # Set a persistent value (e.g., player volume)
        settings.set('player/volume', 85, SettingType.INT)

        # Get a persistent value (provide default and type)
        volume = settings.get('player/volume', 100, SettingType.INT)
        print(f"Player Volume: {volume}")

        # Get a path setting
        last_dir = settings.get('user/last_browse_dir', Path.home(), SettingType.PATH)
        print(f"Last browsed directory: {last_dir}")

        # Save changes to persistent storage
        settings.sync()
        ```

*   **`Logger` (`logger.py`)**
    *   **Purpose:** Provides a singleton logging service for the entire application.
    *   **Functionality:** Uses Python's standard `logging` module. It configures itself based on the `logging` section within the application's YAML configuration (read via `SettingsManager.get_yaml_config`). It supports logging to both the console and a file.
    *   **Configuration (via YAML):**
        *   `logging.level`: Sets the minimum severity level (DEBUG, INFO, WARNING, etc.).
        *   `logging.log_to_file`: Enables/disables file logging.
        *   `logging.log_to_console`: Enables/disables console output.
        *   `logging.clear_on_startup`: If true, the log file is overwritten on each launch.
        *   `app.title` (from YAML): Used to name the log file (e.g., `Music Player.log`).
    *   **Log File Location:** Detects if running as a script (logs to project root) or a bundled executable (logs to executable's directory).
    *   **Usage Example:**
        ```python
        from qt_base_app.models import Logger

        # Get the instance (usually done once in main window/app)
        logger = Logger.instance()

        # Log messages at different levels
        logger.debug("Starting data processing.")
        logger.info("User logged in successfully.")
        logger.warning("Network connection is slow.")

        try:
            result = 10 / 0
        except ZeroDivisionError as e:
            # Log error with exception traceback
            logger.error(f"Calculation failed: {e}", exc_info=True)
            # Alternative using exception helper
            # logger.exception("Calculation failed during processing:")

        logger.critical("System database is unreachable!")
        ```

*   **`ResourceLocator` (`resource_locator.py`)**
    *   **Purpose:** Provides a reliable way to find resource files (like images, configuration files, fonts) regardless of whether the application is running from source code or as a bundled executable (e.g., created with PyInstaller).
    *   **Functionality:** When running bundled, PyInstaller sets a `sys._MEIPASS` attribute pointing to a temporary directory where resources are extracted. When running from source, it typically uses the directory of the main script or the current working directory.
    *   **Usage Example:**
        ```python
        from qt_base_app.models import ResourceLocator
        from PyQt6.QtGui import QPixmap
        import os

        # Get path for an image located in 'resources/images/logo.png'
        # relative to the project root or executable location.
        logo_path_relative = os.path.join("resources", "images", "logo.png")
        logo_path_absolute = ResourceLocator.get_path(logo_path_relative)

        if os.path.exists(logo_path_absolute):
            pixmap = QPixmap(logo_path_absolute)
            # Use the pixmap
        else:
            print(f"Error: Resource not found at {logo_path_absolute}")

        # Get path for a config file
        config_path = ResourceLocator.get_path("config/default_settings.yaml")
        # Use the config_path to open the file
        ```

### 2. Theme (`qt_base_app/theme/`)

Handles the visual appearance of the application.

*   **`theme.yaml`:** Defines the core theme properties: colors (primary, secondary, background levels, text levels, etc.), typography (font families, sizes, weights for different text types), dimensions (sidebar width, header height), and base stylesheets for specific components.
*   **`ThemeManager` (`theme_manager.py`)**
    *   **Purpose:** A singleton service that loads `theme.yaml` and provides convenient access to theme properties.
    *   **Functionality:** Uses `ResourceLocator` to find `theme.yaml`. Provides methods like `get_color()`, `get_dimension()`, `get_typography()`, `get_stylesheet()` to retrieve theme values.
    *   **Usage Example:**
        ```python
        from qt_base_app.theme import ThemeManager
        from PyQt6.QtWidgets import QLabel, QPushButton

        # Get the instance
        theme = ThemeManager.instance()

        # Apply colors
        label = QLabel("Important Info")
        primary_color = theme.get_color('text', 'primary') # Gets colors.text.primary
        label.setStyleSheet(f"color: {primary_color};")

        button = QPushButton("Submit")
        button_bg = theme.get_color('primary') # Gets colors.primary
        button_text = theme.get_color('text', 'primary')
        button.setStyleSheet(f"background-color: {button_bg}; color: {button_text}; border-radius: 4px;")

        # Apply dimensions
        sidebar_width = theme.get_dimension('sidebar', 'expanded_width')
        # Use sidebar_width to set widget width

        # Apply typography
        title_label = QLabel("Application Title")
        title_font_info = theme.get_typography('title') # Gets typography.title
        # Apply font family, size, weight using QFont or stylesheet
        title_label.setStyleSheet(f"font-size: {title_font_info['size']}px; font-weight: {title_font_info['weight']}; ...")
        ```

### 3. Window (`qt_base_app/window/`)

Provides the main application window structure.

*   **`BaseWindow` (`base_window.py`)**
    *   **Purpose:** A `QMainWindow` subclass providing a standard layout featuring a collapsible sidebar (`SidebarWidget`) on the left and a central content area (a `QStackedWidget` managed by the `BaseWindow`).
    *   **Functionality:**
        *   Loads the main application configuration YAML during initialization and makes it available via `self.config` and also loads it into `SettingsManager` for global access.
        *   Sets up the window title and initial size based on the configuration.
        *   Creates the `SidebarWidget` and connects its `item_clicked` signal.
        *   Creates the main content area, including a header (`QWidget`) with a sidebar toggle button and a page title (`QLabel`).
        *   Uses a `QStackedWidget` (`self.content_stack`) to manage different application pages.
        *   Provides methods like `add_page(page_id, widget)` and `show_page(page_id)` for managing the content stack.
        *   Handles basic theme application to the window background.
    *   **Extensibility:** Designed to be subclassed by specific application windows (like `MusicPlayerDashboard`). Subclasses typically override `_assemble_layout()` if they need a different core layout and implement `initialize_pages()` (or similar) to create and add their specific page widgets using `add_page()`.
    *   **Usage Patterns:**
        *   **Direct Instantiation:** If the standard sidebar-content layout is sufficient and you don't need complex custom widgets directly in the main window structure, you can potentially instantiate `BaseWindow` directly in your `run_myapp.py`. You would need a way to configure which pages load initially, perhaps by modifying `create_application` or passing page info via `**window_kwargs`. This is generally less common for full applications.
        *   **Subclassing (Recommended):** The typical approach is to create a new class that inherits from `BaseWindow` (like `MusicPlayerDashboard` or `MainWindow` in the tutorial). This allows you:
            *   To override `_assemble_layout()` if you need a different core structure (e.g., adding a player panel at the bottom).
            *   To implement `initialize_pages()` (or a similar method) to create instances of your specific application page widgets and add them using `self.add_page()`.
            *   To connect signals between pages or other application-specific components.
            *   To add custom methods and properties specific to your main application window.

### 4. Components (`qt_base_app/components/`)

Contains reusable UI widgets.

*   **`SidebarWidget` (`sidebar.py`)**
    *   **Purpose:** Implements the collapsible sidebar navigation menu.
    *   **Functionality:**
        *   Reads its structure (sections, items, icons, page links) from the application configuration YAML file (`sidebar` section).
        *   Creates `MenuItem` buttons for navigation.
        *   Handles expand/collapse animations.
        *   Saves/restores its expanded/collapsed state using `SettingsManager`.
        *   Emits an `item_clicked(item_id, page_class_name)` signal when an item is selected.

### 5. Application Setup (`qt_base_app/app.py`)

This module ties everything together during application startup.

*   **`create_application(...)` Function:**
    *   Creates the `QApplication` instance.
    *   Initializes the `ThemeManager` singleton.
    *   Applies platform-specific setup (like dark title bars on Windows).
    *   Loads custom fonts using `ResourceLocator`.
    *   Applies basic application-wide styles.
    *   Instantiates the main window class (e.g., `MusicPlayerDashboard`, which subclasses `BaseWindow`), passing the path to the application configuration YAML.
    *   Sets the application icon.
    *   Returns the `app` and `window` instances.
*   **`run_application(app, window)` Function:**
    *   Shows the main window (`window.show()`).
    *   Starts the Qt event loop (`app.exec()`).

## Tutorial: Creating a New Application

Let's walk through creating a simple new application, "MyApp", using the `qt_base_app` framework.

**1. Project Structure:**

It's recommended to keep your application code separate from the framework code. Place the `qt_base_app` folder alongside your application's main folder.

```
/MyProjectRoot
├── /myapp                 <-- Your Application Code
│   ├── /ui
│   │   ├── __init__.py
│   │   ├── pages
│   │   │   └── __init__.py
│   │   │   └── home_page.py
│   │   └── main_window.py
│   ├── /resources         <-- Store app-specific resources here
│   │   ├── myapp_config.yaml  <-- YOUR App Config
│   │   └── rocket.png       <-- Example icon
│   └── __init__.py
├── /qt_base_app           <-- The Framework Code
│   ├── /components
│   ├── /models
│   ├── /theme
│   │   └── theme.yaml     <-- Default Framework Theme
│   ├── /window
│   └── app.py
├── run_myapp.py           <-- Your Application Entry Point
```

**2. Create Configuration (`myapp/resources/myapp_config.yaml`):**

This file defines *your* application's specifics. The `create_application` function will load this.

```yaml
# myapp/resources/myapp_config.yaml
app:
  title: "MyApp"
  icon: "fa5s.rocket"
  icon_path: "myapp/resources/rocket.png"
  window:
    width: 900
    height: 650
    min_width: 600
    min_height: 400

logging:
  level: "INFO"
  log_to_file: True
  log_to_console: True
  clear_on_startup: True

sidebar:
  title: "MyApp Menu"
  icon: "fa5s.compass"
  sections:
    - title: "Main"
      items:
        - id: "home"
          title: "Home"
          icon: "fa5s.home"
          page: "HomePage" # Name corresponds to your page class
    - title: "Help"
      items:
        - id: "about"
          title: "About"
          icon: "fa5s.info-circle"
          page: "AboutPage"
```

**3. Create Pages (`myapp/ui/pages/`):**

Create your page widgets (e.g., `home_page.py` as shown previously). Use `ThemeManager` for styling.

**(Example `home_page.py` - shown before)**

**4. Create the Main Window (`myapp/ui/main_window.py`):**

Subclass `BaseWindow`. This is where you instantiate and add your pages.

**(Example `main_window.py` - shown before)**

**5. Create the Entry Point (`run_myapp.py`):**

This script sets everything up.

```python
#!/usr/bin/env python
# run_myapp.py
import sys
import os

# Add project root to path if necessary, depending on how you run it
# e.g., if run from MyProjectRoot:
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from qt_base_app.app import create_application, run_application
from myapp.ui.main_window import MainWindow

def main():
    # --- Pass the path to YOUR config file --- 
    app_config_path = os.path.join("myapp", "resources", "myapp_config.yaml")

    app, window = create_application(
        window_class=MainWindow,
        config_path=app_config_path, # Pass the correct path here
        icon_paths=[
            # Relative paths are resolved by ResourceLocator
            os.path.join("myapp", "resources", "rocket.ico"),
            os.path.join("myapp", "resources", "rocket.png")
        ],
        # Optional Font config
        # fonts_dir=os.path.join("myapp", "resources", "fonts"),
    )
    return run_application(app, window)

if __name__ == "__main__":
    sys.exit(main())
```

**6. Run:**

Execute `python run_myapp.py` from the `/MyProjectRoot` directory. The `create_application` function will:
*   Receive `myapp/resources/myapp_config.yaml` as the `config_path`.
*   Instantiate `MainWindow` (your subclass of `BaseWindow`).
*   `MainWindow`'s `__init__` calls `BaseWindow`'s `__init__`.
*   `BaseWindow` uses `ResourceLocator` to find the *absolute path* to `myapp_config.yaml` and loads it into `self.config`.
*   `BaseWindow` then calls `SettingsManager.instance().load_yaml_config()` with that absolute path, making the YAML data globally accessible.
*   `MainWindow` then continues its `__init__` (initializing the logger, which reads from `SettingsManager`) and `initialize_pages` (creating page instances and adding them using `add_page`).
*   The application starts.

This tutorial demonstrates how the `qt_base_app`