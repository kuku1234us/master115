# Face Reports Feature: Technical Specification and Implementation Plan

## 1. Introduction: Understanding Face Usage

As users leverage the AI face swap capabilities, a natural need arises to understand *how* their face assets are being used. Which faces are selected most often? Are there faces that are rarely or never used in the final, approved results? Answering these questions can help users curate their face libraries, identify popular looks, or troubleshoot why certain faces might not be yielding satisfactory results often.

To address this, we are introducing the **Face Reports** page. This new section within the application serves as a dedicated analytics dashboard focused specifically on the usage patterns of face images within the completed and approved swap workflow.

Our initial focus is the **Face Usage Report**, designed to provide a clear, visual answer to the question: "For a given person, how many times has each of their individual face images appeared in the final `FaceSwapped` directory?"

## 2. Integrating the Feature: Sidebar and Main Window

Before building the page itself, we need to make it accessible within the application's navigation structure.

1.  **Sidebar Configuration (`master115/resources/master115_config.yaml`):**
    *   We will add a new entry to the list under `sidebar.sections` where `title: "AI"`. This defines the new clickable item in the sidebar.
        ```yaml
        # Inside sidebar -> sections -> AI -> items:
        - id: "face_reports"
          title: "Face Reports"
          icon: "fa5s.chart-bar"  # Using a bar chart icon
          page: "FaceReportsPage" # Links to the new page class
        ```

2.  **Main Window Integration (`master115/ui/main_window.py`):**
    *   The `MainWindow` class needs to be aware of the new page.
    *   **Import:** Add `from .pages.facereports_page import FaceReportsPage` at the top.
    *   **Instantiation:** Inside the `initialize_pages` method, create an instance: `face_reports_widget = FaceReportsPage(self)`.
    *   **Adding to Stack:** Add the instance to the main content stack using the ID defined in the YAML: `self.add_page('face_reports', face_reports_widget)`.

## 3. Page Structure: `FaceReportsPage` (`ui/pages/facereports_page.py`)

This class acts as the top-level container for all reports related to face swapping.

*   **Purpose:** To provide a consistent entry point and structure for different types of face swap reports.
*   **Composition:**
    *   Inherits from `QWidget`.
    *   Its primary child is a `QTabWidget`. This allows us to organize different reports neatly into tabs, making the feature easily extensible in the future (e.g., adding tabs for "Swap Success Rate" or "Error Analysis").
*   **Initialization:**
    *   Creates the `QTabWidget`.
    *   Instantiates the `FaceUsageReport` component (detailed next).
    *   Adds the `FaceUsageReport` instance as the first tab in the `QTabWidget`, giving it the user-visible title "Face Usage".
    *   Sets the `QTabWidget` as its main layout element.

## 4. Core Component: `FaceUsageReport` (`ui/faceswap_components/face_usage_report.py`)

This component represents the actual content displayed within the "Face Usage" tab. It orchestrates the selection of a person and the display of their corresponding face usage data.

*   **Purpose:** To connect the person selection mechanism with the data visualization (histogram) and manage the data retrieval and processing needed for the report.
*   **Composition:**
    *   Inherits from `QWidget`.
    *   Uses a `QVBoxLayout` for its internal structure.
    *   Contains two primary child widgets:
        1.  An instance of `PersonBadgeCard` (see section 5.1) placed at the top.
        2.  An instance of `FaceHistogram` (see section 5.2) placed below the card.
*   **Functionality & Interaction:**
    *   **Initialization:** Creates and lays out its child widgets (`PersonBadgeCard`, `FaceHistogram`). Crucially, it connects its own slot method (e.g., `_on_person_selected`) to the `person_selected` signal emitted by the `PersonBadgeCard`.
    *   **Person Selection Handling (in `_on_person_selected` slot):**
        1.  Receives the `selected_person_name` (string) or `None` from the signal.
        2.  **If a name is received:**
            *   Constructs the path to the `<AI_ROOT>/FaceSwapped/` directory using `SettingsManager` to get the AI Root. Handles cases where the directory doesn't exist gracefully (e.g., logs a warning, tells histogram to clear).
            *   Iterates through all files within `FaceSwapped/`.
            *   **Filename Parsing:** For each file, it parses the filename. It assumes the standard naming convention: `"{Person Name} {Face Stem} {Source Stem}.jpg"`. It checks if the `{Person Name}` part matches the `selected_person_name`.
            *   **Usage Counting:** If the person name matches, it extracts the `{Face Stem}`. It maintains a dictionary (e.g., `usage_counts: Dict[str, int]`) to store the count for each unique face stem encountered for this person.
            *   **Face Path Retrieval:** After counting, it needs the *original* face image paths for the histogram's avatars. It iterates through the counted `face_stems` and constructs the expected path pattern (e.g., `<AI_ROOT>/Faces/{selected_person_name}/{face_stem}.*`) using `PeopleManager` or direct path manipulation to find the actual image file (handling different extensions like .jpg, .png). It stores these paths in a list, maintaining the same order as the counts.
            *   **Histogram Update:** Calls `self.face_histogram.set_data(face_image_paths, list(usage_counts.values()))`, passing the retrieved original face paths and the corresponding counts.
        3.  **If `None` is received (deselection):**
            *   Calls `self.face_histogram.set_data([], [])` to clear the histogram and display its placeholder text.

## 5. New UI Components (`ui/faceswap_components/`)

To build the `FaceUsageReport`, we need two significant supporting components.

### 5.1. `PersonBadgeCard` (`person_badge_card.py`)

*   **Purpose:** Provides a reusable UI element for displaying a grid of selectable person badges. This component is created by refactoring the grid logic previously embedded within `PeopleGrid` on the Face Dashboard page, promoting code reuse and separation of concerns.
*   **Composition:**
    *   Inherits from `QWidget`. Could potentially use a `BaseCard` internally for consistent styling, similar to how `PeopleGrid` was structured.
    *   Uses a `QGridLayout` (or potentially a `FlowLayout`) to arrange `PersonBadge` widgets.
*   **Responsibilities:**
    *   **Data Loading:** Fetches the list of all known persons using `PeopleManager.instance().get_persons()`.
    *   **Badge Creation:** For each person, creates a `PersonBadge` instance, providing the necessary data (name, path to first image for avatar).
    *   **Layout:** Arranges the badges within its grid, calculating columns dynamically based on available width.
    *   **Selection Management:**
        *   Implements **single selection** logic. When a badge is clicked:
            *   It deselects any currently selected badge (visually and internally).
            *   It selects the clicked badge.
            *   It emits the `person_selected(selected_person_name: str)` signal.
        *   If a selected badge is clicked again (or potentially if clicking empty space is implemented), it should deselect the badge and emit `person_selected(None)`.
    *   **Signal:** `person_selected = pyqtSignal(str | None)`

### 5.2. `FaceHistogram` (`face_histogram.py`)

*   **Purpose:** A specialized widget designed purely for visualizing the face usage count data as a bar chart with custom axis labels.
*   **Composition:**
    *   Inherits from `QWidget`.
    *   Internally, it might use:
        *   `QPainter` directly within its `paintEvent` for drawing bars, axes, and labels (simpler for basic charts).
        *   A third-party plotting library like `PyQtGraph` integrated as a child widget (more powerful for complex charts, zooming, etc., but adds a dependency). *Decision: Start with `QPainter` for simplicity.*
        *   A `QScrollArea` internally if horizontal scrolling is implemented manually with `QPainter`.
*   **Method:** `set_data(face_image_paths: List[str], counts: List[int])`
    *   Receives the data from `FaceUsageReport`.
    *   Clears any previously drawn chart elements.
    *   Stores the paths and counts.
    *   Triggers a repaint (`self.update()`).
    *   Calculates necessary dimensions and determines if scrolling is needed.
*   **Rendering (`paintEvent`):**
    *   **Placeholder:** If `counts` is empty, draws a placeholder text message (e.g., "Select a person above to view usage statistics") centered in the widget area.
    *   **Axes:** Draws a simple Y-axis with numerical labels based on the maximum value in `counts`. Draws a baseline for the X-axis.
    *   **Bars:** For each count in `counts`, draws a vertical bar whose height is proportional to the count.
    *   **X-Axis Labels:** Below each bar, draws the custom label:
        1.  Calls `make_round_pixmap` (imported helper function) using the corresponding `face_image_path` to generate a small circular avatar (e.g., 32x32). Handles potential errors if the image path is invalid (draws a placeholder avatar).
        2.  Extracts the face name (filename stem) from the `face_image_path`.
        3.  Draws the avatar.
        *   **Layout & Scrolling:** Calculates the total required width for all bars and labels. If this exceeds the widget's current width, it should ideally enable horizontal scrolling (e.g., by painting onto a larger internal surface managed by a `QScrollArea`, or adjusting the `paintEvent` logic to draw based on a scroll offset). *Initial implementation might omit scrolling if complex.*
*   **Error Handling:** Needs to gracefully handle cases where face image files provided in `face_image_paths` might be missing or unloadable when generating avatars (draw placeholders).

## 6. Implementation Plan

*Goal: Build the Face Reports page step-by-step, starting with UI structure and progressing to data handling and visualization.*

### Milestone 1: Setup, Page Structure, and `PersonBadgeCard` Refactor

*Focus: Get the new page integrated and display the selectable person badges.*

-   [x] **YAML:** Add "Face Reports" entry to `master115_config.yaml` under the AI sidebar section.
-   [x] **MainWindow:** Import `FaceReportsPage`, instantiate it in `initialize_pages`, add it to `content_stack`.
-   [x] **FaceReportsPage:** Create `facereports_page.py`. Implement the basic `QWidget` with a `QTabWidget`.
-   [x] **PersonBadgeCard Refactor:**
    -   [x] Create `person_badge_card.py`.
    -   [x] Define `PersonBadgeCard(QWidget)`.
    -   [x] Move the grid creation, person loading (`PeopleManager`), badge population, and dynamic column calculation logic from `PeopleGrid` (`ui/faceswap_components/people_grid.py`) into `PersonBadgeCard`.
    -   [x] Adapt the styling (e.g., using `BaseCard` internally or applying similar styles).
    -   [x] Implement the `person_selected = pyqtSignal(str | None)` signal.
    -   [x] Implement single-selection logic: when a badge is toggled ON, iterate through *other* badges and ensure they are toggled OFF. Emit the signal.
-   [x] **FaceUsageReport Skeleton:** Create `face_usage_report.py`. Implement `FaceUsageReport(QWidget)` with a `QVBoxLayout`.
-   [x] **Integration:** Instantiate `PersonBadgeCard` in `FaceUsageReport` and add it to the layout.
-   [x] **Tab Creation:** Instantiate `FaceUsageReport` in `FaceReportsPage` and add it as the "Face Usage" tab.
-   [x] **Testing:** Verify the "Face Reports" page appears, the "Face Usage" tab is present, and the `PersonBadgeCard` correctly loads and displays selectable person badges with single-selection behavior.

### Milestone 2: Data Gathering and Basic Histogram Placeholder

*Focus: Connect person selection to data processing and display basic histogram structure.*

-   [x] **FaceHistogram Skeleton:** Create `face_histogram.py`. Define `FaceHistogram(QWidget)` with a basic `paintEvent` and a `set_data` method.
-   [x] **FaceHistogram Placeholder:** Implement the `paintEvent` to draw the "Select a person..." message when `set_data` receives empty lists.
-   [x] **FaceUsageReport Layout:** Instantiate `FaceHistogram` in `FaceUsageReport` and add it below the `PersonBadgeCard`.
-   [x] **Signal Connection:** In `FaceUsageReport`, connect the `PersonBadgeCard.person_selected` signal to a new slot (e.g., `_on_person_selected`).
-   [x] **Data Gathering Logic:** Implement the core logic within `_on_person_selected`:
    -   [x] Get AI root and `FaceSwapped` path. Handle missing directory.
    -   [x] Scan files in `FaceSwapped`.
    -   [x] Implement filename parsing logic to extract `{Person Name}` and `{Face Stem}`.
    -   [x] Count face stem occurrences for the selected person.
    -   [x] Implement logic to find the original face image paths based on the counted stems and selected person name. Handle potential errors finding these paths.
-   [x] **Histogram Data Update:** In the `_on_person_selected` slot, after gathering data, call `self.face_histogram.set_data(face_paths, counts)`. Ensure it calls with empty lists when `person_selected(None)` is received.
-   [x] **FaceHistogram Basic Draw:** Modify `FaceHistogram.paintEvent` to draw simple rectangles (bars) based on the received `counts` when data is present (instead of the placeholder). Do not implement custom X-axis yet.
-   [x] **Testing:** Verify that selecting a person triggers logging (add temporary logs in `_on_person_selected` to show counts) and that the `FaceHistogram` updates from its placeholder to showing basic bars (heights corresponding to logged counts).

### Milestone 3: Histogram Visualization Refinement

*Focus: Implement the custom X-axis labels with avatars and names, and basic Y-axis.*

-   [ ] **Import Helper:** Import `make_round_pixmap` into `face_histogram.py`.
-   [ ] **FaceHistogram `paintEvent`:** Enhance the drawing logic:
    -   [ ] Calculate bar width and spacing based on the number of faces and widget width.
    -   [ ] Draw a simple Y-axis line with basic numerical labels (e.g., min, max count).
    -   [ ] For each bar/face:
        -   [ ] Call `make_round_pixmap` with the corresponding `face_image_path` to get the avatar `QPixmap`. Handle errors (use a placeholder pixmap if `make_round_pixmap` fails or the path is invalid).
        -   [ ] Extract the face name (stem) from the path.
        -   [ ] Draw the avatar below the X-axis baseline, centered under the bar position.
        -   [ ] Draw the face name text below the avatar.
-   [ ] **Layout Adjustments:** Ensure enough vertical space is allocated in `FaceHistogram` (and potentially `FaceUsageReport`) to accommodate the X-axis labels (avatars + text) below the bars. Adjust `paintEvent` coordinates accordingly.
-   [ ] **Testing:** Verify the histogram now displays bars with corresponding circular avatars and face names below them. Check that Y-axis scaling looks reasonable. Test with a person having multiple faces. Test error handling for missing face files (placeholder avatar should appear).

### Milestone 4: Scrolling and Final Touches

*Focus: Add horizontal scrolling to the histogram and polish the presentation.*

-   [ ] **Histogram Scrolling:**
    -   [ ] **Option A (Manual Paint):** Modify `FaceHistogram.paintEvent` to draw onto a potentially larger virtual area. Implement handling of a horizontal scrollbar (added to `FaceUsageReport` or within `FaceHistogram` itself) by offsetting the drawing coordinates in `paintEvent` based on the scrollbar's value. Update the scrollbar's range based on the calculated total width needed.
    -   [ ] **Option B (ScrollArea):** Place the `