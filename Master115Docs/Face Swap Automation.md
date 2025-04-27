# Introduction

# AI Face Swap Automation Specification

## 1. Overview

This document outlines the design and implementation plan for an AI-powered face swap automation feature within the Master115 application. The goal is to automate the process of swapping specific faces onto a series of source images using an external service (like Pixnova) and provide a user interface for managing the process and reviewing the results.

## 2. Configuration and Setup

### 2.1. Preferences

-   **AI Root Directory:** A new setting will be added to the application's Preferences page (`PreferencesPage`).
    -   **Label:** "AI Root Directory"
    -   **Functionality:** Allows the user to select the main working directory for the automation process using a directory selection dialog.
    -   **Storage:** The selected path will be stored persistently in the application's settings.
    -   **Default:** No default. The user must set this before using the AI features. Validation should ensure the path is set and exists before starting automation.

### 2.2. Directory Structure

The automation process relies on a specific directory structure within the selected "AI Root Directory":

```
<AI Root Directory>/
│
├── Faces/                  # Contains faces to swap IN
│   ├── <Person1_Name>/     # Subfolder for each person (e.g., "Dandan")
│   │   ├── face1.jpg       # Face images (no spaces in names)
│   │   ├── face2.png
│   │   └── ...
│   ├── <Person2_Name>/
│   │   └── ...
│   └── ...
│
├── SourceImages/           # Contains source images to swap ONTO
│   ├── image1.gif          # Source images (processed one by one)
│   ├── image2.jpeg
│   │   └── ...
│   └── Completed/          # Processed source images are moved here
│       └── <original_filename>
│
├── FaceSwapped/            # Final approved output images (flat structure)
│   └── <Person_Name> <Face_Filename> <Source_Filename>.jpg # Naming convention
│
└── Temp/                   # Temporary storage for results awaiting review
    └── <Person_Name> <Face_Filename> <Source_Filename>.jpg # Same naming convention
```

-   **Naming Constraints:** Folder names under `Faces/` and image filenames within these folders must not contain spaces. Source image filenames can contain spaces.

## 3. User Interface (UI)

All new top-level pages will reside in `./master115/ui/pages`. Supporting UI components will be in `./master115/ui/faceswap_components`.

### 3.1. Sidebar Navigation

-   A new top-level section labeled "AI" will be added to the main application sidebar.
-   Under "AI", two sub-items will be added:
    -   "Face Dashboard"
    -   "Face Review"

### 3.2. Face Dashboard Page (`./master115/ui/pages/face_dashboard_page.py`)

This page provides controls and status monitoring for the automation process.

-   **Layout:** Likely a `QVBoxLayout` or similar, containing the Person Picker, Control Buttons, and Status Log.

-   **Person Picker Card:**
    -   **Container:** A distinct visual card (e.g., `QFrame` with styling) that resizes to fit its content.
    -   **Content:** Displays multiple `PersonBadge` components, likely arranged in a flow layout (`FlowLayout` or similar custom widget) to wrap badges as needed.
    -   **Initialization:** When the page is first displayed, it scans the `<AI Root Directory>/Faces/` folder.
        -   For each subfolder found (representing a person), it creates a `PersonBadge`.
        -   The data (person name, path to first face image, toggle state) is cached in memory for the lifetime of the page view.
    -   **PersonBadge Component (`./master115/ui/faceswap_components/person_badge.py`):**
        -   **Appearance:** Shows a small, circular avatar (thumbnail) of the *first* face image found in the person's `Faces/` subfolder. Displays the person's name (derived from the folder name) below or next to the avatar.
        -   **Interaction:** Acts as a toggle button. Clicking it toggles its state between "selected" (will be processed) and "deselected" (will be skipped).
        -   **State Indication:** Clearly indicates the selected/deselected state (e.g., background color change, border, checkmark overlay).
        -   **Data:** Stores the person's name and the list of face image paths associated with them.
        -   **Layout & Design:** The avatar and name label are arranged horizontally. Visual feedback indicates its state (selected/deselected) by changing the background color and border. The widget has a fixed height and minimum width for uniformity.
        -   **Progress Overlay (During Automation):**
            -   **Appearance:** When the automation process is running, and this specific person was selected for processing, a text overlay appears on the badge (e.g., centered or near the name).
            -   **Content:** The overlay displays progress in the format "X/Y", where:
                -   `Y` is the total number of face images (and thus, worker threads) associated with this person for the current run.
                -   `X` is the number of those worker threads that have completed their processing for all source images.
            -   **Visibility:** The overlay is only visible while the automation is active and only on badges corresponding to selected persons. It disappears once the process finishes or is stopped/killed.
        -   **Interaction:** A simple click toggles the selected state. It needs to store its current state (selected/deselected). The progress overlay does not affect clickability.

-   **Control Buttons:**
    -   **Layout:** Arranged horizontally (`QHBoxLayout`).
    -   **Start/Stop Button:**
        -   **Appearance:** An icon-only button (no text label). Uses a "Play" icon (▶️) initially. When automation is running, it changes to a "Stop" icon (⏹️).
        -   **Functionality (Start):**
            -   Validates that the "AI Root Directory" is set and valid.
            -   Validates that at least one `PersonBadge` is selected.
            -   Initiates the automation process (see Section 4).
            -   Changes icon to "Stop".
            -   Disables the "Start" functionality while running.
        -   **Functionality (Stop):**
            -   Initiates a graceful shutdown sequence:
                -   Signals all active worker threads to stop processing *new* tasks.
                -   Allows currently running swaps to complete.
                -   Waits for all worker threads to finish and clean up (e.g., close browser instances).
                -   Once all threads are stopped, changes icon back to "Play".
                -   Re-enables the "Start" functionality.
    -   **Kill Button:**
        -   **Appearance:** An icon-only button (e.g., Skull 💀 or similar "force stop" icon). Positioned next to the Start/Stop button.
        -   **Functionality:**
            -   Immediately terminates all active worker threads forcefully (e.g., `thread.terminate()` if possible, or equivalent OS-level process kill if necessary). *Caution: This may leave resources (like browser instances) orphaned.*
            -   Resets the UI state (Start/Stop button to "Play").
            -   Should be used only if the graceful "Stop" fails.

-   **Status Log Area:**
    -   **Widget:** A scrollable text area (`QTextEdit` or a custom list widget).
    -   **Content:** Displays timestamped log messages from the automation process.
    -   **Formatting:**
        -   When processing for a *source image* begins: Insert a log entry with a small thumbnail (e.g., 50x50 pixels, possibly loaded and scaled asynchronously) of the source image and the text "Starting processing for `<source_image_name>`...".
        -   When processing for a specific *face* on that source image begins: Insert an indented log entry, e.g., "  - Swapping `<person_name>` (`<face_filename>`) onto `<source_image_name>`..." (no thumbnail needed here).
        -   Completion/Error Logs: Log success or failure messages for each swap, including the output path for temporary results.
        -   General Status: Log messages for starting, stopping, killing the process, errors finding directories, etc.
    -   **Auto-Scroll:** Should automatically scroll to the bottom as new logs are added.

### 3.3. Face Review Page (`./master115/ui/pages/face_review_page.py`)

This page allows the user to approve or reject the generated face swap results.

-   **Layout:** Main area showing the Result Review Queue. A popup dialog is used for detailed review.

-   **Result Review Queue:**
    -   **Widget:** A `QListWidget` or `QGridView` displaying thumbnails.
    -   **Initialization/Update:** Scans the `<AI Root Directory>/Temp/` folder for result image files (e.g., `.jpg`). It parses filenames (expected format: `<Person_Name> <Face_Stem> <Source_Stem>.jpg`) to group results. Files are grouped based on the unique combination of `<Person_Name>` and `<Source_Stem>`. This scan happens when the page is shown or refreshed.
    -   **Display Item:** For each unique `(<Person_Name>, <Source_Stem>)` group found, creates a list/grid item:
        -   **Thumbnail:** Displays a 100x100 thumbnail of the *first* result image found for that group (e.g., one of the `Temp/<Person_Name> <Some_Face_Stem> <Source_Stem>.jpg` files). Thumbnails should be loaded asynchronously.
        -   **Label (Optional):** Could display `<Person_Name>` / `<Source_Stem>`.
        -   **Data:** Stores the associated `person_name`, `source_stem`, and the list of all result file paths (`result_image_paths`) found in `Temp/` belonging to this group.
    -   **Interaction:** Clicking a thumbnail opens the Review Popup Panel for that group, passing the stored data (person name, source stem, result image paths).

-   **Review Popup Panel (Non-Modal Dialog):**
    -   **Trigger:** Displayed when a thumbnail in the Result Review Queue is clicked. It's non-modal, managed by the `FaceReviewPage`.
    -   **Resizable:** The dialog should be resizable by the user, and its geometry is saved/restored.
    -   **Content:**
        -   **Title:** Displays "Reviewing: `<Person_Name>` / `<Source_Stem>`".
        -   **Image Display Area:** Shows all generated result images for the selected group (obtained from the `result_image_paths` list) side-by-side in a horizontally scrollable area. Images are scaled appropriately to fit vertically while maintaining aspect ratio.
        -   **Labeling:** Each displayed result image has:
            -   A small, semi-transparent circular overlay (e.g., top-left corner) containing a single digit (1, 2, 3,... corresponding to its order in the visible list).
            -   A semi-transparent overlay near the bottom-center containing the original face's avatar (circular thumbnail loaded once) and the face filename stem (e.g., "01", "02").
        -   **Selection State:** When an image is "checked" (approved) via hotkey or click:
            -   The top-left digit overlay changes appearance (e.g., green background).
            -   Internally track the approval state for each image. Default state is "unchecked".
    -   **Hotkeys (Dialog must have focus):**
        -   **Up Arrow / Page Up:** Signals the `FaceReviewPage` to navigate to the *previous* item in the Result Review Queue. The `FaceReviewPage` updates the *existing* popup dialog with the new item's data. Wraps around if at the top.
        -   **Down Arrow / Page Down:** Signals the `FaceReviewPage` to navigate to the *next* item in the Result Review Queue. The `FaceReviewPage` updates the *existing* popup dialog with the new item's data. Wraps around if at the bottom.
        -   **0-9:** Toggles the "checked" state of the *currently visible* image corresponding to the digit (1-9, 0 potentially for the 10th if needed, based on the dynamic numbering after using '-'). Updates the visual checkmark overlay.
        -   **- (Minus key):**
            -   Finds all *visible* images that are currently "checked".
            -   Unchecks (deselects) each of these found images.
            -   Hides these images from the dialog view.
            -   Re-numbers the overlays of the remaining visible images sequentially (1, 2, 3,...).
        -   **Enter Key:**
            -   Finds all *visible* images that are currently "unchecked" (not approved).
            -   Hides these images from the dialog view.
            -   Unchecks (deselects) any remaining visible images (which must have been approved).
            -   Re-numbers the overlays of the remaining visible images sequentially (1, 2, 3,...).
        -   **+ (Plus key):**
            -   Identifies all *currently loaded* (visible or hidden by '-' or Enter) images that are "checked" (`approved_paths`) and those that are "unchecked" (`unapproved_paths`).
            -   Emits a `review_processed` signal containing the `person_name`, `source_stem`, `approved_paths` list, and `unapproved_paths` list.
            -   The `FaceReviewPage` receives this signal and calls `ReviewManager.process_review_decision(approved_paths, unapproved_paths)` to handle file operations (moving approved to `FaceSwapped/`, deleting unapproved from `Temp/`).
            -   After the `ReviewManager` call returns successfully, the `FaceReviewPage` removes the corresponding item from its `QListWidget` and attempts to navigate to the next available item in the list (updating the dialog with the new item or closing it if the list becomes empty).

## 4. UI Components

This section details the reusable custom UI components that will be created in the `./master115/ui/faceswap_components/` directory to build the Face Dashboard and Face Review pages. Adhering to good design principles, breaking the UI down into smaller, manageable components makes the code easier to understand, maintain, and test.

### 4.1. PersonBadge (`./master115/ui/faceswap_components/person_badge.py`)

-   **Purpose:** This component acts as a visual representation and interactive toggle for each person identified in the `<AI Root Directory>/Faces/` directory. It allows users to easily select which people's faces they want to use in the upcoming automation batch.
-   **Composition:**
    -   It will likely inherit from `QWidget` or `QFrame` to serve as a container.
    -   A `QVBoxLayout` could arrange the elements vertically.
    -   A `QHBoxLayout` is used to arrange the avatar and name label horizontally.
    -   A `QLabel` will be used to display the person's name (derived from the folder name). Clarity and readability are key here.
    -   Another `QLabel` will display the circular avatar thumbnail. Using a `QLabel` is convenient for setting pixmaps (`QPixmap`). We'll need logic to load the *first* image found in the person's folder, scale it appropriately (e.g., 64x64 pixels), and potentially mask it to appear circular for aesthetic consistency. Asynchronous loading might be considered if directory scanning is slow, but initial implementation can be synchronous.
    -   A text overlay is drawn directly onto the badge using `paintEvent` when the automation process is active for this person.
-   **Layout & Design:** The avatar should be prominently displayed, with the name label positioned clearly below or beside it. Crucially, visual feedback must indicate its state (selected/deselected). This could be implemented by changing the background color, drawing a border, or overlaying a checkmark icon on the avatar when selected. The widget should have a fixed or constrained size to ensure uniformity in the Person Picker Card.
-   **Interaction:** A simple click toggles the selected state. It needs to store its current state (selected/deselected) and the associated data (person's name, list of face file paths).

### 4.2. ReviewQueueItem (`./master115/ui/faceswap_components/review_queue_item.py`)

-   **Purpose:** This component represents a single entry in the "Result Review Queue" on the `FaceReviewPage`. Each item corresponds to a specific Person/Source Image pair for which face swap results have been generated and saved in the `Temp/` directory, awaiting review. It primarily acts as a clickable thumbnail to trigger the detailed review popup.
-   **Composition:**
    -   This could be implemented as a custom `QWidget` designed to be used with `QListWidget::setItemWidget` or as part of a custom `QStyledItemDelegate` if using `QListView` or `QGridView`. Using `setItemWidget` with a `QWidget` is often simpler initially.
    -   The core element is a `QLabel` to display the thumbnail (e.g., 100x100 pixels) of the *first* generated result image for the group. Asynchronous loading is highly recommended here, as there could be many items, and loading images synchronously would block the UI. A placeholder icon or background should be shown while loading.
    -   Optionally, another `QLabel` could display text information like `<Person_Name>` and `<Source_Filename>` below or overlaid on the thumbnail, though the primary interaction is visual.
-   **Layout & Design:** The thumbnail should be the main focus. If text labels are included, they should be concise and not obstruct the image significantly. The overall size should be consistent for grid/list alignment.
-   **Interaction:** Clicking anywhere on this widget should signal the `FaceReviewPage` to open the `ReviewPopupDialog` for the corresponding group of results. It needs to store the associated data required by the popup: Person Name, Source Filename, and the list of all result image file paths in `Temp/` for this group.

### 4.3. ReviewPopupDialog (`./master115/ui/faceswap_components/review_popup_dialog.py`)

-   **Purpose:** This is a modal dialog window that provides a focused environment for the user to review all the generated face swap images for a single Person/Source Image pair. It allows the user to approve individual results before they are moved to the final `FaceSwapped` directory.
-   **Composition:**
    -   Inherits from `QDialog`. Setting it as modal (`setModal(True)`) ensures the user interacts with it before returning to the main review queue.
    -   A `QVBoxLayout` can manage the overall structure: Title, Image Display Area, potentially action buttons (though hotkeys are the primary interaction method specified).
    -   A `QLabel` at the top displays the title, e.g., "Reviewing: `<Person_Name>` on `<Source_Filename>`".
    -   The central area will contain the `ResultImageDisplayArea` (see 4.4) housed within a `QScrollArea` to handle cases where there are more images than fit horizontally. The `QScrollArea` is essential for managing potentially numerous results without cluttering the dialog.
-   **Layout & Design:** The dialog should be resizable (`setSizeGripEnabled(True)`). The layout should prioritize the `ResultImageDisplayArea`, making the images large enough for clear inspection.
-   **Interaction:** The dialog itself primarily hosts the `ResultImageDisplayArea`. It needs to capture keyboard events (specifically Up/Down arrows, PageUp/PageDown, 0-9 digits, '+') to handle navigation and approval logic as defined in section 3.3. It will interact with the `FaceReviewPage` to signal closure, approval actions, and navigation requests (next/previous item).

### 4.4. ResultImageDisplay (`./master115/ui/faceswap_components/result_image_display.py`)

-   **Purpose:** This widget is responsible for displaying a *single* generated face swap result image within the `ReviewPopupDialog`. Its key responsibilities include showing the image, overlaying the identifying digit, overlaying the approval checkmark when toggled, and handling the toggle interaction itself (via hotkeys managed by the parent dialog).
-   **Composition:**
    -   Likely inherits from `QWidget` or potentially `QLabel`.
    -   A `QLabel` can be used to display the actual result image (`QPixmap`). It should scale the pixmap while preserving the aspect ratio to fit the allocated space.
    -   Overlays (digit and checkmark) require careful implementation. Options:
        1.  **Custom Painting:** Subclass `QLabel` or `QWidget` and override the `paintEvent`. Draw the base image, then draw the semi-transparent circle and digit/checkmark on top. This offers the most control.
        2.  **Layered Widgets:** Use stacked `QLabel`s within the main `QWidget`. One for the image, one positioned absolutely in the corner for the digit overlay, and another for the checkmark overlay. Visibility of the overlay labels would be toggled. This might be simpler but potentially less performant or flexible.
-   **Layout & Design:** The image should fill the widget bounds (respecting aspect ratio). Overlays must be clearly visible but not completely obscure the underlying image corner. Semi-transparency is specified. The digit overlay (e.g., small circle, top-left) should be present always. The checkmark overlay (e.g., larger green circle with a white checkmark) appears only when the image is selected/approved.
-   **Interaction:** While the hotkey (0-9) is captured by the parent `ReviewPopupDialog`, this widget needs methods to:
    -   Set the image path to display.
    -   Set the digit to overlay (1-9, 0).
    -   Toggle the approved state (show/hide checkmark overlay).
    -   Report its current approved state back to the dialog when the '+' key is processed.
    -   It needs to store its associated result file path and its current approval state.

### 4.5. PeopleGrid (`./master115/ui/faceswap_components/people_grid.py`)

-   **Purpose:** This component serves as the main container for displaying all available persons found by the `PeopleManager`. It presents a grid of `PersonBadge` widgets, allowing the user to visually identify and select which persons' faces should be included in the face swap process. Think of it as the central hub for choosing your actors.
-   **Composition:**
    -   Inherits from `QWidget` and uses a `QGridLayout` as its main layout.
    -   It utilizes a `BaseCard` component (`PersonPickerCard`) internally to provide a consistent styled container for the grid of badges. This ensures it visually integrates with other card-based elements in the application.
    -   Within the `BaseCard`, another `QGridLayout` (`person_grid_layout`) is used to arrange the `PersonBadge` widgets dynamically.
-   **Data Loading & Display:**
    -   Crucially, `PeopleGrid` does not scan the filesystem itself. It relies entirely on the `PeopleManager` singleton to get the list of `PersonData` objects. This separation of concerns keeps the UI component focused on presentation.
    -   The `load_persons` method is responsible for fetching data from `PeopleManager` (optionally forcing a rescan) and populating the grid. It first clears any existing badges, then retrieves the person list.
    -   For each `PersonData`, it creates a `PersonBadge` instance, providing the person's name and the path to their first face image (obtained via `PeopleManager.get_first_image_path`). This first image is used for the badge's avatar.
    -   The badges are arranged in a grid, calculating the number of columns based on the available width to create a responsive layout.
    -   If no persons are found (or the AI Root Directory is not configured), it displays an informative message within the `BaseCard` instead of the grid.
    -   Loading is typically triggered when the widget is first shown (`showEvent`), but only if the grid is currently empty, to avoid unnecessary reloads on simple tab switches. A `refresh_persons` method allows forcing a rescan and reload.
-   **Interaction & Signals:**
    -   It connects to the `toggled` signal of each `PersonBadge` it creates.
    -   When any badge's selection state changes, the `_on_badge_toggled` slot triggers the emission of the `PeopleGrid`'s own `selection_changed` signal. This signal carries a list of the currently selected person names. The `FaceDashboardPage` listens to this signal to know which persons to process when the "Start" button is clicked.
    -   The `get_selected_person_names` method provides a convenient way for parent widgets (like `FaceDashboardPage`) to retrieve the current selection.
    -   A `set_enabled` method allows disabling/enabling interaction with the entire grid (including all badges and the container card), typically used when the automation process is running.

## 5. Automation Process Logic

The core automation logic triggered by the "Start" button on the Face Dashboard.

### 5.1. People Manager (`./master115/models/people_manager.py`)

-   **Purpose:** The `PeopleManager` serves as a centralized, singleton service responsible for discovering and managing information about the "people" available for face swapping. Its primary role is to abstract the complexities of filesystem scanning and caching away from the UI components like `PeopleGrid`. Think of it as the librarian for your face assets. Using a singleton pattern (`PeopleManager.instance()`) ensures that all parts of the application access the same, consistent person data and cache.

### 5.2. Review Manager (`./master115/models/review_manager.py`): Discovering and Processing Reviews

**Purpose and Rationale:**

The `ReviewManager` is a singleton service responsible for handling the *results* of the face swap process that require user review. Its core responsibilities have shifted away from maintaining a persistent state file (`PendingReview.json`).

-   **Discovering Reviewable Items:** Its primary dynamic function is to scan the `<AI Root Directory>/Temp/` directory. It parses the filenames of the result images found there (e.g., `.jpg`) to identify unique groups of results belonging to the same original source image (based on `<Person_Name>` and `<Source_Stem>` parsed from the filename). This scanning provides the `FaceReviewPage` with the list of items currently awaiting review.
-   **Processing Review Decisions:** Its other main function is to execute the user's decision from the review popup. Based on the lists of approved and unapproved file paths provided by the UI, it performs the necessary file operations: moving approved files from `Temp/` to the final `FaceSwapped/` directory and deleting unapproved files from `Temp/`.

**Key Methods:**

-   **`scan_temp_for_review_items() -> List[Dict]`:**
    -   Scans the `Temp/` directory for result images (e.g., `.jpg`).
    -   Parses filenames (e.g., `<Person_Name> <Face_Stem> <Source_Stem>.jpg`).
    -   Groups results by the unique `(<Person_Name>, <Source_Stem>)` combination.
    -   Returns a list of dictionaries, each containing `person_name`, `source_stem`, and `result_image_paths` (a list of full paths to the files in `Temp/` for that group), typically sorted for consistent UI presentation.
-   **`process_review_decision(approved_paths: List[str], unapproved_paths: List[str]) -> bool`:**
    -   Takes two lists of full file paths (originating from the `Temp/` directory).
    -   Ensures the `FaceSwapped/` directory exists.
    -   Moves files listed in `approved_paths` to the `FaceSwapped/` directory. Includes safety checks to ensure paths are within `Temp/`.
    -   Deletes files listed in `unapproved_paths` from the `Temp/` directory. Includes safety checks.
    -   Includes error handling for file operations.
    -   Returns `True` if operations were attempted, `False` on critical setup errors (like invalid AI Root or inability to create `FaceSwapped/`).

**Removed Functionality:**

-   The manager no longer maintains an internal list (`_pending_reviews`) or reads/writes a `PendingReview.json` file. State is determined purely by the contents of the `Temp/` directory.
-   Methods like `add_pending_review`, `add_person_source_review`, `mark_source_completed_and_move`, `get_pending_reviews`, `get_review_details`, `clear_all_pending_reviews` have been removed as they related to the old JSON-based state management.
-   Signals like `review_item_added` have been removed.

### 5.3. Initialization

1.  Read the "AI Root Directory" from preferences. Validate its existence.
2.  Identify selected persons from the `PersonBadge` toggles on the Dashboard. Validate at least one is selected.
3.  Scan `<AI Root Directory>/Faces/` to get the full list of face files for each selected person. Store this mapping (Person Name -> List of Face File Paths).
4.  Scan `<AI Root Directory>/SourceImages/` (excluding the `Completed/` subdirectory) to get the list of source image files to process.

### 5.4. WebDriver Setup

-   **Manager:** Use `webdriver-manager` for Python.
-   **Target Browser:** Google Chrome (system installation, *not* 115chrome).
-   **Driver Path:** Configure `webdriver-manager` to download/manage the `chromedriver.exe` specifically in `D:\\projects\\googlechrome_driver`. This ensures isolation from any drivers used by 115chrome.
-   **Instantiation:** Each worker thread (see below) will manage its own WebDriver instance.

### 5.5. Worker Threads

-   **Concurrency:** To avoid blocking the UI and potentially speed up processing, the core face swap operations will run in separate threads (`QThread`).
-   **Strategy:** Determine the best threading strategy. Options:
    -   **Option A (Per Face-Task):** Create a pool of worker threads. Iterate through source images. For each source image, iterate through selected persons. For each person, iterate through their face files. Create a task `(source_image_path, person_name, face_image_path)` and submit it to the thread pool. Each thread handles one swap task. *Might lead to many short-lived browser instances.*
    -   **Option B (Per Person/Face):** Create one persistent worker thread *per selected face file*. Each thread gets its own dedicated Chrome instance managed via WebDriver. These threads loop through the available `SourceImages`. When a thread finishes swapping its specific face onto a source image, it saves the result to `Temp/` and looks for the next source image. *Potentially more efficient use of browser instances.*
    -   **Decision:** **Option B seems more robust and efficient.** Each thread manages one browser instance for the duration of the automation run (or until stopped).

-   **Worker Thread Logic (Option B):**
    1.  **Initialization:** Takes the `person_name` and `face_image_path` it's responsible for. Gets the list of `source_image_paths` to process. Initializes its WebDriver instance (using the specified driver path, Chrome binary, no user profile). Logs its startup. **Crucially, navigate to the face swap service (e.g., Pixnova) and perform the one-time upload of the assigned `face_image_path`. Handle potential errors during this initial upload.**
    2.  **Loop:** Iterates through the `source_image_paths`.
    3.  **Check Stop Signal:** Before starting a swap, check if the main thread has signaled a graceful stop. If so, break the loop and proceed to cleanup.
    4.  **Face Swap (Per Source Image):**
        -   **(Face image is assumed to be already uploaded and selected in the browser instance)**
        -   Automate the UI interactions for the *current* source image:
            -   Upload the current `source_image_path`. **(Do NOT re-upload the face image)**.
            -   Initiate the swap.
            -   Wait for completion (handle timeouts and errors).
            -   Download the result image (likely involves finding the download link/button and potentially handling browser download mechanisms or intercepting network requests if possible, though direct download is preferred).
        -   **Result Handling:**
            -   The downloaded file (assume it's WEBP or similar) needs to be saved as JPG. *Initial thought: Use the existing PixnovaPage download/save logic? No, that's UI-based. The worker thread needs direct saving.*
            -   **Revised Saving (Fetch WebP, Convert to JPG):** 
                -   **Clarification:** The final, highest-quality result generated by Pixnova is the `.webp` image displayed in the preview area. Its URL is found in the `src` attribute of the result `<img>` tag. The "Download" button on the Pixnova page likely performs a server-side conversion of this same `.webp` image to JPG for user convenience/compatibility, but does not access a different or higher-quality source.
                -   **Our Process:** The worker thread will:
                    1.  Obtain the `.webp` image URL from the result preview's `<img>` tag `src` attribute.
                    2.  Fetch the raw `.webp` image **bytes** using `requests`.
                    3.  Use `Pillow` within the thread to:
                        -   Open the fetched `.webp` image data from bytes.
                -   Open the downloaded image data/file.
                        -   Convert to 'RGB' mode (necessary for saving as standard JPEG).
                -   Construct the output filename: `<AI Root Directory>/Temp/<Person_Name> <Face_Filename> <Source_Filename>.jpg`.
                        -   Save as JPEG to the `Temp/` directory with appropriate quality (e.g., 75%). This conversion is done locally primarily for broader compatibility with systems/apps that may not natively support `.webp`.
                -   Log success/failure to the main UI's Status Log Area (using thread-safe signals).
            -   If the swap fails, log the error.
    5.  **Post-Swap (Source Image):** *Coordination needed.* A mechanism is required to know when *all* assigned faces have been processed for a *single* source image. Only then should that source image be moved.
        -   **Coordination Idea:** A central manager object (thread-safe) could track `(source_image, person, face)` tasks. When a worker completes a task, it notifies the manager. The manager checks if all tasks for a given `source_image` are done. If so, it moves the `source_image` file from `SourceImages/` to `SourceImages/Completed/` and logs this action.
    6.  **Cleanup:** After the loop (normal completion or graceful stop), the worker thread must:
        -   Close its WebDriver browser instance (`driver.quit()`).
        -   Log its shutdown.
        -   Emit a finished signal to the main thread.

### 5.6. Graceful Stop and Kill

-   **Graceful Stop:**
    -   The main thread sets a flag (e.g., `threading.Event`) that all worker threads periodically check.
    -   When the flag is set, workers finish their *current* swap task but do not start processing the next source image. They proceed to cleanup.
    -   The main thread waits for all worker `finished` signals before resetting the UI (Start/Stop button).
-   **Kill:**
    -   The main thread attempts to forcefully terminate each worker thread/process. The exact method depends on how threads/processes are managed (`QThread.terminate()`, `multiprocessing.Process.terminate()`, etc.).
    -   Resource cleanup (like browser processes) is not guaranteed. Log a warning about potential orphaned processes.
    -   Reset the UI immediately.

## 6. Multithreading Architecture

To ensure the main application remains responsive during potentially lengthy operations like **browser initialization** and the **face swap process itself**, and to maximize processing efficiency (especially when dealing with external web services like Pixnova), we employ a multithreaded approach. This section details the design and interaction of the key components involved: `FaceSwapManager` and `FaceSwapWorker`.

### 6.1. Design Rationale: One Worker per Face

A crucial design decision was how to parallelize the work. We considered creating a new task for every single combination of (source image, face image) but opted for a more persistent strategy:

*   **Strategy:** Create **one dedicated worker object (`FaceSwapWorker`) for each selected *face* image.**
*   **Operation:** Each worker is responsible for taking its assigned face and processing it against the *entire list* of source images sequentially.
*   **Benefits:**
    *   **Efficiency:** This significantly reduces redundant operations. For web services like Pixnova, the face image typically needs to be uploaded only *once* per session. By keeping a worker (and its associated browser instance) alive for the duration of the process, we upload each selected face just once at the beginning. The worker then only needs to upload the different source images one by one.
    *   **Resource Management:** While it creates multiple browser instances (one per worker/face), it avoids the rapid creation and destruction of browser instances that a per-task approach might entail.
    *   **Throttling Mitigation:** Having multiple independent browser sessions (one per worker) inherently distributes the load on the external service, making it less likely to hit throttling limits compared to funneling all requests through a single session.

### 6.2. Core Components

The multithreading system revolves around two main classes:

1.  **`FaceSwapManager` (`./master115/models/faceswap_manager.py`):** The central coordinator and orchestra conductor.
2.  **`FaceSwapWorker` (`./master115/models/face_swap_worker.py`):** The actual workhorse performing the automation tasks for a single face.

Here's a conceptual overview:

```ascii
+-----------------------+       Calls       +-------------------+      Creates & Manages     +-----------------+     Runs Task      +-----------------+
| FaceDashboardPage (UI)| ----------------> |  FaceSwapManager  | -------------------------> |    QThread      | ---------------> | FaceSwapWorker  |
| (QWidget)             |   start_process() |    (QObject)      |      (Qt Thread Pool)    |   moveToThread()  |    (QObject)     |
+-----------------------+   stop_process()  +-------------------+                            +-----------------+                    +-----------------+
        ^                     kill_process()          |                                              |      Signals finished()         |       ^ Signals log_message,
        | Signals process_*                           | Signals log_message, process_*               |      Signals quit(), wait()     |       | task_complete, etc.
        +---------------------------------------------+                                              +---------------------------------+       |
                                                                                                                 (Manager interacts with Thread)        (Worker interacts with Manager via signals)
```

### 6.3. `FaceSwapWorker`: The Task Executor (`QObject`)

*   **Role:** Executes the face swap process for *one specific face image* across all provided source images.
*   **Inheritance:** Crucially, `FaceSwapWorker` inherits from `QObject`, **not** `QThread`. This adheres to Qt's recommended threading pattern where the worker logic is separate from the thread execution context itself.
*   **Execution:** An instance of `FaceSwapWorker` is created by the `FaceSwapManager` and then moved to a separate `QThread` instance using `worker.moveToThread(thread)`. The worker's `run()` method is connected to the `thread.started` signal, so the work begins only when the dedicated thread starts its event loop.
*   **Responsibilities:**
    *   Receive the `PersonData`, `FaceData` (for its assigned face), the full list of `SourceImageData`, the output directory path, and a shared `threading.Event` for graceful stops.
    *   (In Milestone 4) Initialize and manage its own Selenium WebDriver instance.
    *   (In Milestone 4) Perform the one-time upload of its assigned face image.
    *   Iterate through the source image list.
    *   For each source image:
        *   Check the `stop_event`.
        *   (In Milestone 4) Perform the source image upload, trigger the swap, download the result, and save it to the temporary directory.
        *   (Currently) Simulate the process and create a dummy output file.
    *   Emit signals (`log_message`, `task_complete`, `task_failed`) to report progress and results back to the `FaceSwapManager`.
    *   Emit the `finished` signal *once* after processing all source images (or stopping early).
    *   (In Milestone 4) Ensure its WebDriver instance is properly closed (`driver.quit()`) in a `finally` block within `run()`.

### 6.4. `FaceSwapManager`: The Coordinator (`QObject`)

*   **Role:** Manages the entire face swap automation lifecycle, acting as the bridge between the UI (`FaceDashboardPage`) and the worker objects.
*   **Instantiation:** Created by `FaceDashboardPage`, with the page set as its parent (`parent=self`) to ensure proper Qt object lifetime management.
*   **Responsibilities:**
    *   **Initialization (`start_process`):**
        *   Validates input (AI Root dir, selected persons).
        *   Retrieves necessary data (source images, full person/face data) using `PeopleManager`.
        *   Creates a `threading.Event` (`_stop_event`) shared by all workers for graceful shutdown.
        *   For *each* selected face, creates a `FaceSwapWorker` instance and a dedicated `QThread`.
        *   Moves the worker to the thread.
        *   Sets up signal/slot connections:
            *   `thread.started -> worker.run`
            *   `worker.log_message -> manager.log_message` (forwards to UI)
            *   `worker.task_complete -> manager._on_task_complete` (logs success)
            *   `worker.task_failed -> manager._on_task_failed` (logs failure)
            *   `worker.finished -> manager._on_worker_finished` (tracks completion count)
            *   `worker.finished -> thread.quit` (requests thread loop termination)
            *   `thread.finished -> worker.deleteLater` (schedules worker cleanup)
        *   Stores references to the workers and threads (`_workers`, `_worker_threads`).
        *   Starts all the created threads.
        *   Updates internal state (`_is_running`, `_active_worker_count`).
        *   Emits `process_started` signal to the UI.
    *   **Graceful Stop (`stop_process`):**
        *   Sets the shared `_stop_event`. Workers check this event before processing each new source image.
    *   **Force Kill (`kill_process`):**
        *   Iterates through running threads, calling `terminate()` followed by `wait()` (as a last resort).
        *   Immediately cleans up internal state and emits `process_killed`. *Caution: `terminate()` can leave resources dangling.*
    *   **Completion Handling (`_on_worker_finished`):**
        *   Decrements the `_active_worker_count`.
        *   When the count reaches zero (all workers have emitted `finished`):
            *   Logs that all workers are done.
            *   **Crucially, enters the correct thread shutdown sequence to prevent race conditions:**
                *   **Problem:** Initially, `thread.finished.connect(thread.deleteLater)` was connected when starting threads. This caused a race condition: the last thread's `finished` signal could schedule its deletion *before* the manager's shutdown loop (`_on_worker_finished`) could safely interact with it (call `quit()` or `wait()`), leading to a `RuntimeError: wrapped C/C++ object of type QThread has been deleted`.
                *   **Solution:** Remove the automatic `thread.deleteLater` connection during thread startup. The manager must explicitly control thread cleanup in the shutdown sequence.
                *   **Correct Sequence:**
                    1.  **Request Quit:** Iterate through all known `_worker_threads` and call `t.quit()` on each. This politely asks the thread's event loop to exit *after* processing any pending events. It's safe to call `quit()` even if the thread isn't running.
                    2.  **Wait for Termination:** Iterate through all `_worker_threads` again and call `t.wait()` on each. This *blocks* the manager's execution (specifically, the main thread where the manager likely lives) until the target thread has actually finished its `run()` method and its event loop has terminated. Using `wait()` *after* `quit()` ensures the thread has fully stopped processing. A timeout should be used with `wait()` to prevent indefinite blocking if a thread hangs.
                    3.  **Schedule Deletion:** *After* `wait()` confirms the thread has terminated (or timed out), call `t.deleteLater()` on the thread object. This safely schedules the C++ object for deletion by Qt's event loop when control returns to it, preventing the `RuntimeError`.
            *   Logs final status ("All tasks completed" or "Process stopped gracefully").
            *   Calls `_cleanup_after_stop`.
            *   Emits `process_finished` signal to the UI.
    *   **Cleanup (`_cleanup_after_stop`):**
        *   Resets internal state flags and clears the lists holding worker/thread references.

## 7. Error Handling

-   **Directory/File Errors:** Handle cases where directories (`AI Root`, `Faces`, `SourceImages`, etc.) don't exist or files are missing/unreadable. Log errors clearly.
-   **WebDriver Errors:** Handle `WebDriverException` during browser launch, navigation, element interaction, or download. Log errors. The worker might retry once or twice before giving up on a specific swap.
-   **Face Swap Service Errors:** The service itself might return errors or time out. Log these.
-   **Image Processing Errors:** Handle errors during image saving with Pillow (invalid data, disk full, permissions). Log errors.
-   **Threading Errors:** Handle potential deadlocks or race conditions (use thread-safe data structures and signaling).

## 8. Logging

-   Use the application's standard `Logger` singleton.
-   Log key events: Automation start/stop/kill, directory scanning results, worker thread start/stop, individual swap start/success/failure, file movements (source to Completed, temp to FaceSwapped), errors encountered.
-   Ensure log messages from worker threads are safely passed to the main thread for display in the Status Log Area (use Qt Signals).

## 9. Implementation Plan

This section outlines the detailed steps required to implement the AI Face Swap Automation feature. It is organized into milestones, prioritizing the visibility of UI elements before fully implementing their underlying logic. Use the checkboxes to track progress.

### Milestone 1: Setup and Basic Dashboard UI

*Goal: Set up project dependencies, configure the AI root directory preference, and display the basic layout of the Face Dashboard page, including placeholder person badges.*

- [x] **Dependencies:** Add `Pillow` and `webdriver-manager` to `pyproject.toml` and run `poetry lock` and `poetry install`.
- [x] **Preferences UI:** Add an "AI Root Directory" setting to the `PreferencesPage` UI.
    - [x] Add a `QLabel` for "AI Root Directory".
    - [x] Add a `QLineEdit` to display the path.
    - [x] Add a `QPushButton` ("Browse...") to open a `QFileDialog.getExistingDirectory` dialog.
- [x] **Preferences Logic:** Implement saving the selected path to application settings (`QSettings`) when changed.
- [x] **Preferences Logic:** Implement loading the saved path into the `QLineEdit` when the `PreferencesPage` is shown.
- [x] **Preferences Validation:** Add logic to validate that the path is set and the directory exists when saving preferences. Display an error message if invalid.
- [x] **Sidebar Navigation:** Add the new "AI" top-level section to the main sidebar.
- [x] **Sidebar Navigation:** Add "Face Dashboard" and "Face Review" `QAction` or equivalent items under the "AI" section.
- [x] **Page Skeletons:** Create empty `QWidget` subclasses `FaceDashboardPage` in `./master115/ui/pages/face_dashboard_page.py` and `FaceReviewPage` in `./master115/ui/pages/face_review_page.py`.
- [x] **Page Navigation:** Connect the sidebar actions to display the corresponding (currently empty) page widget in the main application area.
- [x] **Dashboard Layout:** Define the main layout for `FaceDashboardPage` (e.g., `QVBoxLayout`).
- [x] **PersonBadge Component:** Create the `PersonBadge` widget skeleton in `./master115/ui/faceswap_components/person_badge.py` (e.g., inheriting `QFrame`).
- [x] **PersonBadge UI:** Inside `PersonBadge`, add a `QLabel` for the avatar (set a placeholder background color/icon) and a `QLabel` for the person's name. Arrange them (e.g., `QVBoxLayout`). Apply basic size constraints.
- [x] **Dashboard Person Picker:** Add a `QFrame` to `FaceDashboardPage` layout to act as the "Person Picker Card". Apply styling (e.g., border, background) to make it visually distinct.
- [x] **Dashboard Flow Layout:** Implement or integrate a `FlowLayout` manager to arrange badges within the Person Picker Card. (If `FlowLayout` is complex, use `QGridLayout` as a temporary measure).
- [x] **Dashboard Person Scanning:** Implement logic in `FaceDashboardPage` (e.g., in `showEvent` or a dedicated method) to scan the subdirectories within the configured `<AI Root Directory>/Faces/`. Handle cases where the root directory isn't set or doesn't exist.
- [x] **Dashboard Badge Population:** For each person directory found, create an instance of `PersonBadge`, set its name label, and add it to the `FlowLayout` inside the Person Picker Card. Clear previous badges before populating.
- [x] **PersonBadge Avatar Loading:** Enhance `PersonBadge` to load the *first* image file found in the person's directory path (passed during instantiation or via a method). Scale the image (`QPixmap.scaled`), apply circular masking (optional, can use `QBitmap` mask), and set it on the avatar `QLabel`. Handle errors gracefully (e.g., no images found, invalid image file).
- [x] **PersonBadge Toggle State:** Add internal state (e.g., `self.is_selected = False`) to `PersonBadge`.
- [x] **PersonBadge Interaction:** Implement `mousePressEvent` in `PersonBadge` to toggle the `is_selected` state and trigger a visual update.
- [x] **PersonBadge Visual State:** Implement a method in `PersonBadge` (e.g., `update_visuals`) that changes the widget's appearance based on `is_selected` (e.g., set stylesheet for background color/border).
- [x] **Dashboard Controls Layout:** Add a `QHBoxLayout` to `FaceDashboardPage` for control buttons.
- [x] **Dashboard Buttons:** Add `QPushButton` instances for Start/Stop (use temporary text "Start") and Kill (use temporary text "Kill") to the controls layout.
- [x] **Dashboard Status Log:** Add a `QTextEdit` widget to `FaceDashboardPage`. Set it to read-only and ensure it's scrollable.

### Milestone 2: Basic Automation Workflow & Review Page UI

*Goal: Implement a minimal end-to-end workflow: clicking "Start" triggers a simulated swap for one face/source, saves a dummy result, and the Review Page shows a placeholder thumbnail for this result.*

- [x] **Review Page Layout:** Define the main layout for `FaceReviewPage` (e.g., `QVBoxLayout`).
- [x] **Review Queue Widget:** Add a `QListWidget` (or `QGridView`) to `FaceReviewPage` to serve as the "Result Review Queue".
- [x] **ReviewQueueItem Component:** Create the `ReviewQueueItem` widget skeleton in `./master115/ui/faceswap_components/review_queue_item.py` (e.g., inheriting `QWidget`).
- [x] **ReviewQueueItem UI:** Inside `ReviewQueueItem`, add a `QLabel` for the thumbnail (set a placeholder background color/icon). Apply basic size constraints (e.g., 100x100 pixels).
- [x] **Core Data Structures:** Define necessary data classes (e.g., using `@dataclass`) to hold information about persons, faces, source images, and swap tasks.
- [x] **WebDriver Setup Logic:** Implement a utility function or class method to initialize and configure `webdriver-manager` to use Chrome from the system installation and manage `chromedriver.exe` within `D:\\projects\\googlechrome_driver`.
- [x] **Worker Thread Skeleton:** Create the `FaceSwapWorker` class inheriting `QThread` in a suitable location (e.g., `./master115/models/face_swap_worker.py`). Define necessary signals (e.g., `log_message(str)`, `task_complete(str)`, `task_failed(str, str)`, `finished()`).
- [x] **Worker Initialization:** Implement `FaceSwapWorker.__init__` to accept `person_name`, `face_image_path`, `source_image_paths` (list), and potentially a reference to a shared stop event/flag. Store these.
- [x] **Dashboard Start Logic (Basic):**
    - [x] In `FaceDashboardPage`, implement the "Start" button click handler.
    - [x] Get the AI Root Directory path from settings.
    - [x] Identify *one* selected `PersonBadge` and get its face path list.
    - [x] Find *one* source image file in `<AI Root Directory>/SourceImages/`.
    - [x] **Temporarily:** Log the intent to process this single face/source pair to the Status Log.
    - [x] **(Defer Threading):** Do not create/start the worker thread yet.
- [x] **Dashboard Stop/Kill Logic (Placeholders):** Implement click handlers for "Stop" and "Kill" buttons that simply log the action to the Status Log.
- [x] **Worker Run Logic (Simulation):**
    - [x] Implement the `FaceSwapWorker.run` method.
    - [x] **Simulate WebDriver:** Log messages like "Initializing WebDriver...", "Navigating to service...", "Uploading face image...", "Uploading source image...", "Performing swap...", "Downloading result...".
    - [x] **Simulate Result:** Use `pathlib` or `os` to create an empty dummy file in `<AI Root Directory>/Temp/` with the correct naming convention: `<Person_Name> <Face_Filename> <Source_Filename>.jpg`.
    - [x] **Simulate Cleanup:** Log "Closing WebDriver...".
    - [x] Emit appropriate signals (`log_message`, `task_complete` or `task_failed`, `finished`).
- [x] **Dashboard-Worker Connection:** *(Now handled via FaceSwapManager)*
    - [x] Modify the "Start" button handler: Create *one* instance of `FaceSwapWorker` with the test data. Connect its signals (`log_message`, `task_complete`, `task_failed`, `finished`) to slots/methods in `FaceDashboardPage` that update the Status Log.
    - [x] Start the worker thread (`worker.start()`).
- [x] **Dashboard Stop Logic (Basic):** Modify the "Stop" button handler to set a shared stop flag/event that the (currently simulated) worker should check (though it won't act on it yet). Log the signal was sent. *(Now calls manager.stop_process())*
- [x] **Review Page Scanning:** Implement logic in `FaceReviewPage` (e.g., in `showEvent` or a refresh method) to scan the `<AI Root Directory>/Temp/` directory.
- [x] **Review Page Grouping:** Process the list of files found in `Temp/` and group them by the `(Person_Name, Source_Filename)` part of the filename. Store this grouping (e.g., in a dictionary `{(person, source): [list_of_temp_files]}`).
- [x] **Review Page Population:** Clear the `QListWidget`. For each group found:
    - [x] Create a `QListWidgetItem`.
    - [x] Create an instance of `ReviewQueueItem`.
    - [x] **(Defer Thumbnail):** Set the `ReviewQueueItem`'s placeholder view. *(Note: Implemented synchronous loading)*
    - [x] Store the group data (person, source, list of temp files) within the `QListWidgetItem` (e.g., using `setData`). *(Note: Data stored in item widget)*
    - [x] Add the item to the `QListWidget` and set the `ReviewQueueItem` as its widget (`setItemWidget`).
- [x] **ReviewQueueItem Thumbnail Loading:** Enhance `ReviewQueueItem` to accept the list of result file paths for its group. Load the *first* image file from the list, scale it (`QPixmap.scaled`), and display it in the thumbnail `QLabel`. *(Note: Displays thumbnail; async loading is a potential future optimization)*

### Milestone 3: Review Popup Implementation and Interaction

*Goal: Enable clicking a thumbnail on the Review Page to open a functional popup dialog showing all results for that group, allowing selection via hotkeys, and implementing the approval/rejection logic.*

- [x] **Review Popup Dialog Skeleton:** Create `ReviewPopupDialog` class inheriting `QDialog` in `./master115/ui/faceswap_components/review_popup_dialog.py`. Configure it to be modal and resizable.
- [x] **Review Popup Layout:** Add a `QVBoxLayout`. Add a `QLabel` at the top for the title.
- [x] **Result Image Display Skeleton:** Create `ResultImageDisplay` class inheriting `QWidget` in `./master115/ui/faceswap_components/result_image_display.py`.
- [x] **Result Image Display UI:** Add a `QLabel` to `ResultImageDisplay` for the image (placeholder). Plan for overlay elements.
- [x] **Review Popup Scroll Area:** Add a `QScrollArea` to `ReviewPopupDialog`'s layout. Set its widgetResizable property to `True`. Create a container `QWidget` inside the scroll area with a `QHBoxLayout`.
- [x] **Review Page Click Interaction:** Connect the `itemClicked` signal of the `QListWidget` on `FaceReviewPage` to a slot/method.
- [x] **Review Page Popup Trigger:** In the `itemClicked` handler:
    - [x] Retrieve the stored group data (person, source, list of temp files) from the clicked `QListWidgetItem`.
    - [x] Create an instance of `ReviewPopupDialog`, passing this data.
    - [x] Show the dialog (`dialog.exec_()`).
- [x] **Review Popup Population Logic:**
    - [x] In `ReviewPopupDialog.__init__` (or a setup method), receive the group data.
    - [x] Set the dialog title `QLabel` text (e.g., "Reviewing: `<Person_Name>` on `<Source_Filename>`").
    - [x] Clear any existing widgets from the scroll area's `QHBoxLayout`.
    - [x] For each result file path in the received list (keeping track of index 0-N):
        - [x] Create an instance of `ResultImageDisplay`.
        - [x] Pass the image path and the index (0-N) to the `ResultImageDisplay` instance.
        - [x] Add the `ResultImageDisplay` instance to the `QHBoxLayout`.
- [x] **Result Image Display Loading:** Implement logic in `ResultImageDisplay` to load and display the image from the provided path in its `QLabel`, scaling appropriately (preserve aspect ratio).
- [x] **Result Image Display Overlays UI:** Implement the visual overlays within `ResultImageDisplay`.
    - [x] **Digit:** Draw the index + 1 (1-N) in a semi-transparent circle in a corner (e.g., top-left) using custom `paintEvent` or layered `QLabel`s.
    - [x] **Checkmark:** Prepare the checkmark overlay (e.g., semi-transparent green circle with a white checkmark) but keep it hidden initially.
- [x] **Result Image Display State:** Add state tracking (`self.is_approved = False`) and the result file path to `ResultImageDisplay`.
- [x] **Result Image Display Toggle:** Add a method (e.g., `toggle_approval`) to `ResultImageDisplay` that flips `self.is_approved` and shows/hides the checkmark overlay.
- [x] **Review Popup Hotkey Capture:** Override `keyPressEvent` in `ReviewPopupDialog`.
- [x] **Review Popup 0-9 Hotkey:** In `keyPressEvent`, if the key is a digit 1-9 (or 0 for 10th):
    - [x] Calculate the corresponding index (key - 1).
    - [x] Get the `ResultImageDisplay` widget at that index from the layout.
    - [x] If it exists, call its `toggle_approval()` method.
- [x] **Review Popup '-' Hotkey:** In `keyPressEvent`, if the key is '-':
    - [x] Finds all *visible* images that are currently "checked".
    - [x] Unchecks (deselects) each of these found images.
    - [x] Hides these images from the dialog view.
    - [x] Re-numbers the overlays of the remaining visible images sequentially (1, 2, 3,...).
- [x] **Review Popup '+' Hotkey:** In `keyPressEvent`, if the key is '+':
    - [x] Identifies all *currently visible* images that are "checked".
    - [x] Moves each checked image file from `<AI Root Directory>/Temp/` to `<AI Root Directory>/FaceSwapped/`.
    - [x] Deletes all *currently visible* images that are "unchecked" for this group from `<AI Root Directory>/Temp/`. (Note: Previously hidden images are not affected by this action).
    - [x] Removes the corresponding thumbnail item from the Result Review Queue UI.
    - [x] Closes the current popup.
    - [x] Automatically selects the *next* item in the Result Review Queue (if any) and opens its Review Popup. If it was the last item, simply closes the popup.
- [x] **Review Page Refresh:** Connect the `review_completed` signal from the dialog to the method on `FaceReviewPage` that scans `Temp/` and repopulates the `QListWidget`.
- [x] **Review Page Item Removal:** Implement logic in `FaceReviewPage` to remove a specific `QListWidgetItem` (and its associated widget) when notified by the popup (or potentially by `ReviewManager` if it emits an `item_removed` signal).
- [x] **Review Popup Navigation Hotkeys (Basic):** Implement Up/Down/PgUp/PgDn hotkey handling in `keyPressEvent`:
    - [x] Signal the `FaceReviewPage` to select the previous/next item.
    - [x] Emit signals (e.g., `navigate_previous`, `navigate_next`) from the dialog.
- [x] **Review Page Navigation Logic:** Connect the navigation signals. Implement methods on `FaceReviewPage` to:
    - [x] Get the current selection index in the `QListWidget`.
    - [x] Calculate the previous/next index (handle wrapping).
    - [x] Set the current index of the `QListWidget`.
    - [x] Trigger the logic to show the `ReviewPopupDialog` for the new index.

### Milestone 4: Full Automation Logic, Scaling, and Refinement

*Goal: Implement the complete, multi-threaded automation process using the actual face swap service, handle coordination, enable full start/stop/kill functionality, and refine logging and error handling.*

- [ ] **Task Manager:** Implement a thread-safe central manager class (e.g., using `threading.Lock` or `queue.Queue`) to track the status of all `(source_image, person_name, face_image)` swap tasks. *(Partially done - manager coordinates workers but lacks specific source completion tracking)*
- [x] **Dashboard Start Logic (Full):**
    - [x] Modify the "Start" handler to get *all* selected `PersonBadge` data (person -> list of face paths). *(Done in `FaceSwapManager.start_process`)*
    - [x] Get *all* source image paths from `<AI Root Directory>/SourceImages/` (excluding `Completed/`).
    - [x] **Task Completion Handling (`_on_task_complete`):**
        -   Slot connected to worker `task_complete`.
        -   Logs success message.
        -   Updates internal progress trackers (`_person_source_progress`) for the specific face/source combination. Adds the `output_path` to the results set for that person/source.
        -   Checks if the person has completed all their faces for this source image.
        -   If a person completes a source, updates the overall source completion tracker (`_source_overall_completion`).
        -   Checks if *all* selected persons have completed this source image (`_source_overall_completion` matches `_current_run_selected_persons`).
        -   **If a source image is fully completed by all selected people:**
            -   If the "Move Source File" setting for the current run is enabled, it *directly* attempts to move the original source image file from `<AI Root Directory>/SourceImages/` to `<AI Root Directory>/SourceImages/Completed/`. Handles potential errors during the move.
            -   Removes the completed source path from the internal progress trackers.
            -   **Note:** It does *not* interact with `ReviewManager` at this stage. `ReviewManager` discovers completed items later by scanning the `Temp/` directory when the user navigates to the Face Review page.
    -   **Task Failure Handling (`_on_task_failed`):**
        -   Slot connected to worker `task_failed`.
        -   Logs failure message.
        -   Updates internal progress trackers (`_person_source_progress`) for the specific face/source combination.
        -   Checks if the person has completed all their faces for this source image.
        -   If a person completes a source, updates the overall source completion tracker (`_source_overall_completion`).
        -   Checks if *all* selected persons have completed this source image (`_source_overall_completion` matches `_current_run_selected_persons`).
        -   **If a source image is fully completed by all selected people:**
            -   If the "Move Source File" setting for the current run is enabled, it *directly* attempts to move the original source image file from `<AI Root Directory>/SourceImages/` to `<AI Root Directory>/SourceImages/Completed/`. Handles potential errors during the move.
            -   Removes the completed source path from the internal progress trackers.
            -   **Note:** It does *not* interact with `ReviewManager` at this stage. `ReviewManager` discovers completed items later by scanning the `Temp/` directory when the user navigates to the Face Review page.
    -   **Task Completion Handling (`_on_task_complete`):**
        -   Slot connected to worker `task_complete`.
        -   Logs success message.
        -   Updates internal progress trackers (`_person_source_progress`) for the specific face/source combination. Adds the `output_path` to the results set for that person/source.
        -   Checks if the person has completed all their faces for this source image.
        -   If a person completes a source, updates the overall source completion tracker (`_source_overall_completion`).
        -   Checks if *all* selected persons have completed this source image (`_source_overall_completion` matches `_current_run_selected_persons`).
        -   **If a source image is fully completed by all selected people:**
            -   If the "Move Source File" setting for the current run is enabled, it *directly* attempts to move the original source image file from `<AI Root Directory>/SourceImages/` to `<AI Root Directory>/SourceImages/Completed/`. Handles potential errors during the move.
            -   Removes the completed source path from the internal progress trackers.
            -   **Note:** It does *not* interact with `ReviewManager` at this stage. `ReviewManager` discovers completed items later by scanning the `Temp/` directory when the user navigates to the Face Review page.
    -   **Task Failure Handling (`_on_task_failed`):**
        -   Slot connected to worker `task_failed`.
        -   Logs failure message.
        -   Updates internal progress trackers (`_person_source_progress`) for the specific face/source combination.
        -   Checks if the person has completed all their faces for this source image.
        -   If a person completes a source, updates the overall source completion tracker (`_source_overall_completion`).
        -   Checks if *all* selected persons have completed this source image (`_source_overall_completion` matches `_current_run_selected_persons`).
        -   **If a source image is fully completed by all selected people:**
            -   If the "Move Source File" setting for the current run is enabled, it *directly* attempts to move the original source image file from `<AI Root Directory>/SourceImages/` to `<AI Root Directory>/SourceImages/Completed/`. Handles potential errors during the move.
            -   Removes the completed source path from the internal progress trackers.
            -   **Note:** It does *not* interact with `ReviewManager` at this stage. `ReviewManager` discovers completed items later by scanning the `Temp/` directory when the user navigates to the Face Review page.