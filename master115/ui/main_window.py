from qt_base_app.window import BaseWindow
from qt_base_app.models import Logger, SettingsManager # Import SettingsManager
from .pages import HomePage, SearchPage, PreferencesPage # Import pages

class MainWindow(BaseWindow):
    def __init__(self, config_path: str, **kwargs):
        # BaseWindow loads the config, sets up logger based on it
        super().__init__(config_path=config_path, **kwargs)

        # Logger is now configured, we can use it
        self.logger = Logger.instance()
        self.logger.info("main_window", f"Main window initialized with config: {config_path}")

        # --- Application-specific setup --- #
        # (Add any custom widgets, connections, or logic here)
        self.initialize_pages()
        self.logger.info("main_window", "Application pages initialized.")

        # Get the SettingsManager singleton instance
        settings_manager = SettingsManager.instance()

        # Show the initial page specified in config or a default
        # Use the settings_manager instance to get persistent settings
        initial_page = settings_manager.get('window/initial_page', 'home')
        self.show_page(initial_page)


    def initialize_pages(self):
        """Create instances of all pages and add them to the content stack."""
        # Instantiate pages
        home_widget = HomePage(self)       # Pass self as parent
        search_widget = SearchPage(self)
        prefs_widget = PreferencesPage(self)

        # Add pages to the stack using the IDs from the YAML config
        self.add_page('home', home_widget)
        self.add_page('search', search_widget)
        self.add_page('preferences', prefs_widget)

    # Add other application-specific methods below if needed
    # def custom_method(self):
    #     pass 