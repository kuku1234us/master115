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
    -   **Initialization/Update:** Scans the `<AI Root Directory>/Temp/` folder. Groups files by `(<Person_Name>, <Source_Filename>)`.
    -   **Display Item:** For each group, creates a list/grid item:
        -   **Thumbnail:** Displays a 100x100 thumbnail of the *first* result image found for that group (e.g., `Temp/<Person_Name> <First_Face_Filename> <Source_Filename>.jpg`). Thumbnails should be loaded asynchronously.
        -   **Label (Optional):** Could display `<Person_Name>` and `<Source_Filename>`.
        -   **Data:** Stores the associated Person Name, Source Filename, and the list of all result file paths in `Temp/` for this group.
    -   **Interaction:** Clicking a thumbnail opens the Review Popup Panel for that group.

-   **Review Popup Panel (Modal Dialog):**
    -   **Trigger:** Displayed when a thumbnail in the Result Review Queue is clicked.
    -   **Resizable:** The dialog should be resizable by the user.
    -   **Content:**
        -   **Title:** Displays "Reviewing: `<Person_Name>` on `<Source_Filename>`".
        -   **Image Display Area:** Shows all generated result images for the selected group (`Temp/<Person_Name> <Face_Filename> <Source_Filename>.jpg`) side-by-side. Images should be scaled appropriately to fit while maintaining aspect ratio. A horizontal scrollbar might be needed if there are many images.
        -   **Labeling:** Each displayed result image has a small, semi-transparent circular overlay (e.g., top-left corner) containing a single digit (1, 2, 3,... corresponding to the face file used).
        -   **Selection State:** When an image is "checked" (approved) via hotkey:
            -   Display a second overlay: a semi-transparent (50% opacity) green circle containing a white checkmark (✓).
            -   Internally track the approval state for each image. Default state is "unchecked".
    -   **Hotkeys (Dialog must have focus):**
        -   **Up Arrow / Page Up:** Closes the current popup, selects the *previous* item in the Result Review Queue, and opens the Review Popup for that previous item. Wraps around if at the top.
        -   **Down Arrow / Page Down:** Closes the current popup, selects the *next* item in the Result Review Queue, and opens the Review Popup for that next item. Wraps around if at the bottom.
        -   **0-9:** Toggles the "checked" state of the corresponding labeled image (1-9, 0 potentially for the 10th if needed). Updates the visual checkmark overlay.
        -   **+ (Plus key):**
            -   Identifies all "checked" images in the current view.
            -   Moves each checked image file from `<AI Root Directory>/Temp/` to `<AI Root Directory>/FaceSwapped/`.
            -   Deletes all "unchecked" image files for this group from `<AI Root Directory>/Temp/`.
            -   Removes the corresponding thumbnail item from the Result Review Queue UI.
            -   Closes the current popup.
            -   Automatically selects the *next* item in the Result Review Queue (if any) and opens its Review Popup. If it was the last item, simply closes the popup.

## 4. UI Components

This section details the reusable custom UI components that will be created in the `./master115/ui/faceswap_components/` directory to build the Face Dashboard and Face Review pages. Adhering to good design principles, breaking the UI down into smaller, manageable components makes the code easier to understand, maintain, and test.

### 4.1. PersonBadge (`./master115/ui/faceswap_components/person_badge.py`)

-   **Purpose:** This component acts as a visual representation and interactive toggle for each person identified in the `<AI Root Directory>/Faces/` directory. It allows users to easily select which people's faces they want to use in the upcoming automation batch.
-   **Composition:**
    -   It will likely inherit from `QWidget` or `QFrame` to serve as a container.
    -   A `QVBoxLayout` could arrange the elements vertically.
    -   A `QLabel` will be used to display the person's name (derived from the folder name). Clarity and readability are key here.
    -   Another `QLabel` will display the circular avatar thumbnail. Using a `QLabel` is convenient for setting pixmaps (`QPixmap`). We'll need logic to load the *first* image found in the person's folder, scale it appropriately (e.g., 64x64 pixels), and potentially mask it to appear circular for aesthetic consistency. Asynchronous loading might be considered if directory scanning is slow, but initial implementation can be synchronous.
    -   The entire widget should function like a button, specifically a toggle button. We could achieve this by overriding mouse press events on the main widget or embedding a transparent `QPushButton`.
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

### 5.2. Review Manager (`./master115/models/review_manager.py`): Bridging Completion and Review

**Purpose and Rationale:**

As the `FaceSwapManager` completes processing all selected faces for a particular source image, we reach a critical transition point. The raw processing is done, but the results haven't been approved by the user yet. We need a reliable way to:

1.  **Persist State:** Remember which source images are fully processed and which generated temporary files belong to them, even if the application restarts.
2.  **Manage Files:** Move the original source image out of the input queue (`SourceImages/`) and into a holding area (`SourceImages/Completed/`) to prevent it from being processed again.
3.  **Notify UI:** Inform the `FaceReviewPage` that new results are available for inspection.

While the `FaceSwapManager` *could* handle these tasks, it would tightly couple the swap orchestration logic with state persistence and file system management specific to the review process. Similarly, having the `FaceReviewPage` manage the state file directly would burden the UI component with non-UI responsibilities.

Therefore, we introduce the `ReviewManager` as a dedicated, centralized service (implemented as a singleton) to handle this specific responsibility. It acts as the single source of truth for the "pending review" state, decoupling the `FaceSwapManager` (which only *reports* completion) from the `FaceReviewPage` (which *consumes* the pending review list). This adheres to the principle of Separation of Concerns, making the system easier to understand, test, and maintain.

**Core Responsibilities:**

The `ReviewManager` is solely responsible for the lifecycle of items awaiting user review:

1.  **Receiving Completion Notification:** It exposes the `add_pending_review` method, which the `FaceSwapManager` calls when it determines all faces have been successfully processed for a given source image.
2.  **Moving Completed Source Files:** Upon receiving a notification via `add_pending_review`, the `ReviewManager` takes ownership of moving the original source image file from its location in `<AI Root Directory>/SourceImages/` to the `<AI Root Directory>/SourceImages/Completed/` subdirectory. This ensures the source file is archived correctly *before* its state is recorded.
3.  **Maintaining `PendingReview.json`:** It manages the `PendingReview.json` file located in the AI Root Directory. This file stores a list of all source images that have been fully processed and are awaiting review. The `ReviewManager` handles reading this file on startup, adding new entries when `add_pending_review` is called (after a successful file move), removing entries when the `FaceReviewPage` signals completion (via `remove_pending_review`), and writing changes back to the file persistently. It includes error handling for file I/O and potential JSON corruption (creating backups if needed).
4.  **Notifying the UI:** After successfully moving the source file and updating the JSON, it emits the `review_item_added(dict)` signal. This signal carries the dictionary representing the newly added review item, allowing the `FaceReviewPage` to update its display dynamically without needing to constantly poll or rescan.

**Process Flow:**

The interaction sequence involving the `ReviewManager` is as follows:

1.  `FaceSwapManager`'s `_on_task_complete` slot receives a `task_complete` signal from a `FaceSwapWorker`.
2.  It updates its internal progress tracker (`_source_image_progress`) for the specific source image associated with the task.
3.  It checks if the number of completed faces for that source image now equals the total number expected.
4.  If the source image is fully processed, `FaceSwapManager` calls `_handle_source_completion`.
5.  Inside `_handle_source_completion`, `FaceSwapManager` calls `ReviewManager.instance().add_pending_review(original_source_path, result_paths)`.
6.  `ReviewManager`'s `add_pending_review` method:
    *   Calculates the destination path in the `Completed/` folder.
    *   Attempts to move the `original_source_path` file to the `completed_path`.
    *   If the move succeeds:
        *   Creates a dictionary containing the original path, completed path, and the list of result image paths.
        *   Adds this dictionary to its internal list (`_pending_reviews`).
        *   Saves the updated list to `PendingReview.json`.
        *   Emits the `review_item_added` signal with the newly created dictionary as the payload.
    *   If the move fails, it logs an error and takes no further action for that item.
7.  `FaceReviewPage`, having connected to the `review_item_added` signal during its initialization, receives the signal in its `_on_review_item_added` slot.
8.  The slot parses the received dictionary and adds a corresponding `ReviewQueueItem` widget to its `QListWidget`, making the newly completed item visible to the user for review.

**`PendingReview.json` Format:**

The `PendingReview.json` file stores a JSON list (array). Each element in the list is an object (dictionary) representing one source image group that is pending review. The structure of each object is:

```json
[
  {
    "original_source_path": "D:\\AIRoot\\SourceImages\\source_image1.jpg",
    "completed_source_path": "D:\\AIRoot\\SourceImages\\Completed\\source_image1.jpg",
    "result_image_paths": [
      "D:\\AIRoot\\Temp\\PersonA Face1 source_image1.jpg",
      "D:\\AIRoot\\Temp\\PersonB Face2 source_image1.jpg"
    ]
  },
  {
    "original_source_path": "D:\\AIRoot\\SourceImages\\another_source.png",
    "completed_source_path": "D:\\AIRoot\\SourceImages\\Completed\\another_source.png",
    "result_image_paths": [
       "D:\\AIRoot\\Temp\\PersonA Face1 another_source.jpg",
       "D:\\AIRoot\\Temp\\PersonB Face2 another_source.jpg"
    ]
  }
]
```

*   `original_source_path`: The absolute path (as a string) to the source image *before* it was moved. This serves as a unique identifier for the review item.
*   `completed_source_path`: The absolute path (as a string) to the source image *after* it was moved to the `Completed/` directory.
*   `result_image_paths`: A list containing the absolute paths (as strings) to all the generated face swap images stored in the `Temp/` directory for this specific source image.

**Thread Safety:**

Since the `task_complete` signal from `FaceSwapWorker` instances might arrive from different threads, and the UI updates triggered by `review_item_added` happen on the main GUI thread, the `ReviewManager` uses a `threading.Lock` (`_lock`) to protect all access to its internal `_pending_reviews` list and the read/write operations on the `PendingReview.json` file. This prevents race conditions and ensures data integrity. Qt's signal/slot mechanism handles the cross-thread communication safely for the `review_item_added` signal.

### 5.2. Initialization

1.  Read the "AI Root Directory" from preferences. Validate its existence.
2.  Identify selected persons from the `PersonBadge` toggles on the Dashboard. Validate at least one is selected.
3.  Scan `<AI Root Directory>/Faces/` to get the full list of face files for each selected person. Store this mapping (Person Name -> List of Face File Paths).
4.  Scan `<AI Root Directory>/SourceImages/` (excluding the `Completed/` subdirectory) to get the list of source image files to process.

### 5.3. WebDriver Setup

-   **Manager:** Use `webdriver-manager` for Python.
-   **Target Browser:** Google Chrome (system installation, *not* 115chrome).
-   **Driver Path:** Configure `webdriver-manager` to download/manage the `chromedriver.exe` specifically in `D:\\projects\\googlechrome_driver`. This ensures isolation from any drivers used by 115chrome.
-   **Instantiation:** Each worker thread (see below) will manage its own WebDriver instance.

### 5.4. Worker Threads

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

### 5.5. Graceful Stop and Kill

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
            *   **Crucially, enters the two-loop shutdown sequence:**
                1.  Iterate through all `_worker_threads` and call `t.quit()` on each running thread. This politely asks the thread's event loop to exit *after* processing any pending events (like the `worker.finished` signal).
                2.  Iterate through all `_worker_threads` again and call `t.wait()` on each running thread. This *blocks* the manager's execution until the target thread has actually finished its `run()` method and terminated. Using `wait()` *after* `quit()` ensures we don't deadlock.
                3.  Call `t.deleteLater()` on each thread after waiting to schedule it for safe deletion by Qt's event loop.
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
- [x] **Review Popup '+' Hotkey:** In `keyPressEvent`, if the key is '+':
    - [x] Identifies all "checked" images in the current view.
    - [x] Moves each checked image file from `<AI Root Directory>/Temp/` to `<AI Root Directory>/FaceSwapped/` (create `FaceSwapped/` if needed). Handle potential file errors.
    - [x] Deletes all "unchecked" image files for this group from `<AI Root Directory>/Temp/`.
    - [x] Signal the `ReviewManager` to remove the entry for the just-reviewed item (using its `original_source_path`).
    - [x] Signal the `FaceReviewPage` to remove the corresponding visual item from the main queue list.
    - [x] Attempt to find the *next* available review item in the `FaceReviewPage`'s list.
    - [x] If a next item is found:
        - [x] Clear the current content of the popup (title, displayed images).
        - [x] Load and display the data (title, result images) for the *next* review item within the *same* popup window.
    - [x] If no next item is found:
        - [x] Close the dialog (`self.accept()` or `self.done(QDialog.Accepted)`).
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
    - [x] Get *all* source image paths from `<AI Root Directory>/SourceImages/` (excluding `Completed/`). *(Done in `FaceSwapManager._get_all_source_images`)*
    - [ ] Initialize the central task manager with all pending tasks. *(Partially done - manager exists, but detailed task tracking for source completion is missing)*
    - [x] Create a shared stop event (`threading.Event`). *(Done in `FaceSwapManager.start_process`)*
    - [x] For each selected face file across all selected persons:
        - [x] Create a `FaceSwapWorker` instance, passing its assigned `person_name`, `face_image_path`, the *full list* of source image paths, and the shared stop event. *(Done in `FaceSwapManager.start_process`)*
        - [x] Connect worker signals to the dashboard/manager as needed. *(Done in `FaceSwapManager.start_process`)*
        - [x] Start the worker thread. *(Done in `FaceSwapManager.start_process`)*
    - [x] Update UI state (buttons, icons). *(Done via `process_started`/`process_finished` signals)*
- [x] **Worker Run Logic (Actual):**
    - [x] Replace simulation logic in `FaceSwapWorker.run` with actual WebDriver automation:
        - [x] Initialize WebDriver instance using the configured setup (`initialize_chrome_driver`).
        - [x] Navigate to the face swap service (Pixnova URL).
        - [x] Perform the *one-time* upload of the worker's assigned `face_image_path`. Handle WebDriver waits and potential errors. *(Done, uses thumbnail check)*
        - [x] Loop through the `source_image_paths` list.
        - [x] **Check Stop Event:** Before processing each source image, check the shared `stop_event.is_set()`. If set, break the loop.
        - [x] Upload the *current* `source_image_path`. *(Done, uses thumbnail check)*
        - [x] Initiate the swap via WebDriver interactions. *(Done, clicks start button)*
        - [x] Wait for the result `<img>` tag to be visible. Handle timeouts and errors. *(Done)*
        - [x] Get the `.webp` image URL from the `src` attribute. *(Done)*
        - [x] If URL found, use `requests` to fetch the `.webp` image bytes. *(Done)*
        - [x] Use `Pillow` to open the `.webp` image bytes, convert to RGB, and save as JPG to `<AI Root Directory>/Temp/` with the correct naming convention (e.g., 75% quality). Handle image processing/saving errors. *(Done, including filename fix)*
        - [x] Emit `task_complete` or `task_failed` signal with relevant info... *(Done)*
        - [x] **Notify Manager:** After successful save, notify the central task manager... *(Worker emits `task_complete` signal, received by `FaceSwapManager`)*
    - [x] **Worker Cleanup:** Ensure `driver.quit()` is called in a `finally` block within the `run` method... *(Done)*
    - [x] Emit `finished` signal when the `run` method exits. *(Done)*
- [ ] **Task Manager Logic:** *(Responsibilities now split between FaceSwapManager and ReviewManager)*
    - [x] Implement the method to receive notifications from workers. *(`FaceSwapManager._on_task_complete` exists)*
    - [x] Track completed tasks for each source image. *(Done in `FaceSwapManager._source_image_progress`)*
    - [x] When all faces for a given source image are reported as complete, move the original `source_image` file from `SourceImages/` to `SourceImages/Completed/` and log this action. *(Done by `ReviewManager.add_pending_review` after notification from `FaceSwapManager`)*