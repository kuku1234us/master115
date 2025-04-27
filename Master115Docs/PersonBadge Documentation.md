# PersonBadge Component Documentation

## Introduction: What is a PersonBadge?

Imagine you have a collection of digital actors, each represented by a folder containing images of their face. In our AI Face Swap system, we need a way to visually represent these actors and allow the user to easily select which ones they want to use for a batch of face swaps. This is precisely the role of the `PersonBadge` component (`./master115/ui/faceswap_components/person_badge.py`).

Think of each `PersonBadge` as a small, interactive card representing one person identified by the system (based on the subfolders found in the `<AI Root Directory>/Faces/` directory). It serves two primary functions:

1.  **Visual Identification:** It shows you *who* the person is by displaying their name and a small avatar derived from one of their face images.
2.  **Selection Control:** It acts as a toggle button, allowing you to include or exclude this person from the next automation run with a simple click.

These badges are typically displayed together within the `PeopleGrid` component on the `FaceDashboardPage`, providing a user-friendly interface for managing the participants in the face swap process.

## Visual Anatomy

A `PersonBadge` is designed for clarity and efficient use of space. Its key visual elements are arranged horizontally:

*   **Circular Avatar:** On the left side, a small, circular thumbnail image (currently 32x32 pixels) provides a quick visual cue. This avatar is generated from the *first* valid image file found within that person's specific folder under `<AI Root Directory>/Faces/`. If no image is found or an image fails to load, a placeholder graphic or color is displayed instead.
*   **Name Label:** To the right of the avatar, the person's name is displayed as text. This name is directly derived from the name of the subfolder within the `Faces` directory (e.g., a folder named "Dandan" results in a badge labeled "Dandan").
*   **Background & Border:** The entire badge has a background color and border that changes depending on its selection state, providing clear visual feedback.

## Interaction: Toggling Selection

The primary way to interact with a `PersonBadge` is by clicking on it. Each click toggles its selection state:

*   **Deselected State (Default):** The badge has a standard background color (e.g., dark grey). Clicking it transitions it to the selected state.
*   **Selected State:** The badge changes its appearance (e.g., different background color like dark green, potentially a more prominent border) to clearly indicate it's chosen. Clicking it again transitions it back to the deselected state.

When the state changes, the badge emits a `toggled` signal, informing its parent container (the `PeopleGrid`) about the change, including the person's name and their new selection status (True for selected, False for deselected). This allows the application to keep track of which people are intended for the next automation run.

## The Progress Overlay: Monitoring Active Workers

While the face swap automation process is running, the `PersonBadge` gains an additional visual element for *selected* participants: a progress overlay.

*   **Purpose:** This overlay provides real-time feedback on the progress of the tasks associated *specifically with that person*. Since the system creates one worker thread for each face image belonging to a selected person, this overlay shows how many of those workers have completed their entire assigned workload (swapping their specific face onto *all* source images).
*   **Appearance:** When the automation starts, a text overlay appears on the badge (typically positioned near the name label, possibly with a semi-transparent background for readability). This overlay only appears on badges that were *selected* when the process was initiated.
*   **Format:** The text displays progress in the format `X/Y`.
    *   `Y`: Represents the **total number of face images** found for this person at the start of the run. This corresponds to the total number of worker threads created for this person.
    *   `X`: Represents the **number of those worker threads that have finished** their work completely.
*   **Example:** An overlay showing `4/9` means that for this specific person, 9 face images were found and 9 corresponding worker threads were started. So far, 4 of those threads have finished processing all source images.
*   **Updates:** As worker threads complete their tasks, the `FaceSwapManager` signals these completions. The `PeopleGrid` receives these signals and instructs the relevant `PersonBadge` to update the value of `X` in its overlay text.
*   **Visibility:** The overlay is *only* visible during an active automation run and *only* on the badges of people selected for that run. Once the automation process finishes (either completes normally, is stopped gracefully, or is killed), the overlay disappears from all badges.

This overlay provides valuable insight into the progress per person, especially in runs involving multiple people with varying numbers of face images.

## Interaction During Automation: Log Filtering

Normally, clicking a `PersonBadge` toggles its selection state. However, when the face swap automation process is *actively running*, clicking a badge serves a different purpose: **filtering the status log**. This allows you to focus on the messages generated by the specific worker threads associated with that person.

Here's how it works:

1.  **Clicking the Badge:** When you click on a `PersonBadge` while the automation is running, it will *not* toggle its selection state. Instead, it signals the `FaceDashboardPage` to display a context menu.
2.  **Context Menu:** A small menu appears near your cursor. This menu lists the unique identifiers (Worker IDs) for all the worker threads currently active for the person represented by the clicked badge. Each worker ID typically follows the format `PersonName-FaceFilenameStem` (e.g., `Dandan-face1`, `David-003`).
3.  **Selecting a Worker ID:** Clicking on one of the Worker IDs in the context menu activates a filter on the main **Status Log Area** on the `FaceDashboardPage`.
4.  **Filtered Log View:** The Status Log Area immediately updates to show *only* the log messages generated by the specific worker thread you selected. This is extremely useful for diagnosing issues or monitoring the detailed progress of a particular face swap operation.
5.  **Cancel Filter Button:** While a log filter is active, a small overlay button appears on the Status Log Area itself (typically in a corner). This button displays an icon indicating "cancel" or "return" (like an undo arrow).
6.  **Cancelling the Filter:** Clicking this overlay button removes the active filter. The Status Log Area reverts to displaying *all* messages from the current run, and the cancel filter button disappears.

This feature provides a powerful way to drill down into the details of the automation process without being overwhelmed by logs from potentially numerous concurrent workers.

## Implementation Notes

The `PersonBadge` is implemented as a custom `QWidget`. It uses a `QHBoxLayout` to arrange the avatar (`QLabel`) and name (`QLabel`). The circular avatar is achieved by loading the source `QPixmap`, scaling and cropping it appropriately, and then using `QPainter` with a circular clip path (`QPainterPath.addEllipse`) to render it onto a transparent target `QPixmap` which is then set on the avatar `QLabel`. Selection state visuals are handled by applying different stylesheets to the main `QWidget`. The progress overlay is also drawn using `QPainter` directly within the `paintEvent` method of the `PersonBadge` widget itself when progress text is provided.
