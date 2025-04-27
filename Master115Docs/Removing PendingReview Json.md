# Migration Plan: Removing PendingReview.json (V3 - Stem-Based)

## Goal

Remove the reliance on `PendingReview.json` for managing face swap review state. Instead, dynamically determine reviewable items by parsing the contents of the `<AIRoot>/Temp` directory, using the source image *stem* as the primary identifier.

## Assumptions

1.  Filenames in the `Temp` directory follow the pattern: `{PersonName} {FaceStem} {SourceStem}.jpg`.
2.  `PersonName` and `FaceStem` are single tokens (no spaces). `{SourceStem}` is the remaining part of the filename before the `.jpg` extension and represents the original source image's stem.
3.  The core review logic (grouping results, processing decisions) only requires the `SourceStem` to identify the set of results belonging to one original source image.
4.  The UI (`ReviewQueueItem`) uses a *result* image (one of the files from `Temp`) for its thumbnail display.

## Revised Steps

1.  **Modify `ReviewManager` - Core Logic & Parsing:**
    *   **Remove JSON State:** Delete internal methods related to loading, saving, and backing up `PendingReview.json` (`_load_data`, `_save_data`, `_backup_corrupt_json`, `_get_json_path`). Remove the `_pending_reviews` list attribute.
    *   **Create `scan_temp_for_review_items()` Method:**
        *   This method becomes the primary way to get reviewable items.
        *   Get the `<AIRoot>/Temp` path. Handle cases where it doesn't exist.
        *   List all files ending in `.jpg` within the `Temp` directory.
        *   **Parse Filenames:** For each `.jpg` file:
            *   Remove the `.jpg` extension to get the full stem.
            *   Split the full stem by space.
            *   Token 0 = `PersonName`.
            *   Token 1 = `FaceStem`.
            *   Join remaining tokens (Token 2 onwards) to get `SourceStem`.
            *   Log warnings/errors and skip files that don't have at least 3 parts after splitting.
        *   **Group Results:** Group the *full paths* of the `.jpg` result files by the parsed `SourceStem`. A `defaultdict(lambda: {'person_name': None, 'result_image_paths': []})` keyed by `SourceStem` is suitable. Store the `PersonName` within the group's dictionary (verify it's consistent if multiple files map to the same stem).
        *   **Return Structure:** Return a list of dictionaries, where each dictionary represents one source stem needing review:
            ```python
            [
                {
                    'person_name': str,         # Person name parsed from files
                    'source_stem': str,         # Source stem used for grouping
                    'result_image_paths': List[str] # List of *full paths* to results in Temp/
                },
                # ... more items
            ]
            ```
    *   **Update `process_review_decision` Signature & Logic:**
        *   Change the method signature to: `process_review_decision(self, approved_paths: List[str], unapproved_paths: List[str]) -> bool`.
        *   Remove all logic related to finding/removing items from any internal state list.
        *   Keep only the file operations: Moving approved files (from `approved_paths` list, which are full paths in `Temp`) to `FaceSwapped`, and deleting unapproved files (from `unapproved_paths` list, also full paths in `Temp`). Perform safety checks to ensure paths are within `Temp` before operating.
        *   Return `True` if file operations were attempted (regardless of individual file success/failure), `False` only on critical setup errors (like invalid AI Root).

2.  **Modify `ReviewManager` - Remove Unused API & Signals:**
    *   Delete the following methods: `add_pending_review`, `add_person_source_review`, `mark_source_completed_and_move`, `get_review_details`, `clear_all_pending_reviews`, `_find_review_item_index`.
    *   Delete the `review_item_added` signal.

3.  **Modify `FaceReviewPage` - Adapt Data Loading & Handling:**
    *   **Update `_load_review_items`:**
        *   Call the new `ReviewManager.scan_temp_for_review_items()`.
        *   Iterate through the list of dictionaries returned.
        *   Extract `person_name`, `source_stem`, and `result_image_paths`.
        *   Store `person_name`, `source_stem`, and the `result_image_paths` list in the `QListWidgetItem` using `setData` roles for later retrieval.
        *   Update the `ReviewQueueItem` widget's constructor or a dedicated method (e.g., `setData`) to accept `person_name`, `source_stem`, and `result_image_paths`. The widget should display `person_name / source_stem` textually and use the first path from `result_image_paths` to load its thumbnail.
    *   **Update `_handle_review_processed`:**
        *   Modify the slot to receive `person_name`, `source_stem`, `approved_paths`, `unapproved_paths` from the dialog's signal.
        *   Call `ReviewManager.process_review_decision(approved_paths, unapproved_paths)`.
        *   On return (assume `True` unless critical error), simply call `_load_review_items()` again to refresh the list based on the (now changed) contents of the `Temp` folder.
        *   Delete the `_remove_review_item_widget` method.
    *   **Remove Signal Connection:** Delete the connection to the `review_item_added` signal.
    *   **Update `_get_data_for_item`:** Modify this helper to retrieve `person_name`, `source_stem`, and `result_image_paths` directly from the `QListWidgetItem`'s `setData` roles. Return these as a tuple or dictionary.
    *   **Update `_display_review_item`:** Retrieve data using `_get_data_for_item`. Update the `ReviewPopupDialog` constructor call to pass `person_name`, `source_stem`, and `result_image_paths`.

4.  **Modify `FaceSwapManager` - Simplify Completion Logic:**
    *   **Remove `ReviewManager` Calls:** In `_on_task_complete`, remove the calls to `ReviewManager.add_person_source_review()` and `ReviewManager.mark_source_completed_and_move()`.
    *   **Direct Source File Move:** Within `_on_task_complete`, when the condition `completed_persons_for_source == self._current_run_selected_persons` is met:
        *   Check if `self._current_run_move_source` is `True`.
        *   If `True`, directly perform the `shutil.move` operation to move the original source file from `SourceImages/` to `SourceImages/Completed/`. The original source path is available as the key in the `_person_source_progress` dictionary. Include necessary directory creation (`mkdir`) and error handling (`try...except OSError`).
        *   Log the outcome of the move attempt.
        *   Keep the existing logic that removes the `source_path` from the internal `_person_source_progress` and `_source_overall_completion` trackers.

5.  **Modify `ReviewPopupDialog` - Adapt to Stem:**
    *   **Update `__init__`:** Change the `original_source_path: str` parameter to `source_stem: str`. Store `self.source_stem = source_stem`. Remove storage/use of `original_source_path`.
    *   **Update Title:** Change `_update_display_data` to set the window title using `self.person_name` and `self.source_stem` (e.g., `f"Review: {self.person_name} / {self.source_stem}"`).
    *   **Update Signal:** Change the `review_processed` signal definition to `pyqtSignal(str, str, list, list)` (emitting person_name, source_stem, approved_paths, unapproved_paths).
    *   **Update Emit:** Change `_handle_plus_key` to emit `self.review_processed.emit(self.person_name, self.source_stem, approved_paths, unapproved_paths)`.

6.  **Testing:**
    *   Run face swaps; confirm `.jpg` files appear in `Temp` with the correct naming convention.
    *   Open the Review page. Verify items are listed based on unique `source_stem` values found in `Temp`. Check that the displayed text (`person_name / source_stem`) and thumbnail (from a result image) are correct.
    *   Open the review popup. Verify the title shows `person_name / source_stem` and the correct result images are displayed.
    *   Use approve/reject keys ('1'-'9', '-', Enter) and confirm UI updates correctly within the popup.
    *   Use the '+' key to finalize. Verify approved images move from `Temp` to `FaceSwapped`, unapproved are deleted from `Temp`.
    *   Verify the item disappears from the Review page list after processing.
    *   If 'Move Source File' was enabled for the swap, verify the *original* source image file (which `FaceSwapManager` tracks) is moved from `SourceImages/` to `SourceImages/Completed/` *after all people finish processing it*.
    *   Test edge cases: Empty `Temp` folder, invalid filenames in `Temp` (should be ignored), restarting the app with files still in `Temp`.
