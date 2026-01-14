# Debug Screenshots Guide

The Android automation script now supports detailed screenshot debugging to help troubleshoot navigation issues.

## How to Use

Run the script with the `--debug-screenshots` flag:

```bash
python -m note_hammer.android_automation --debug-screenshots --max-books 1
```

## What It Does

The script will:
1. Create a timestamped directory like `debug_screenshots/session_20260111_143052/`
2. Take numbered screenshots at every major step
3. Save the UI dump XML alongside each screenshot

## Screenshot Sequence Example

For a typical book export, you'll get screenshots like:

```
001_BEFORE_-_About_to_tap_book.png                      # Before opening book
002_AFTER_-_Tapped_book_(should_be_in_book_view).png   # After opening book
003_AFTER_-_Tapped_top_to_show_toolbar.png             # After showing toolbar
004_BEFORE_-_About_to_tap_Notebook_button.png          # Before opening annotations
005_AFTER_-_Tapped_Notebook_button_(should_show_annotations).png
006_SUCCESS_-_In_Annotations_view.png                   # Successfully in annotations
007_Looking_for_export/share_button.png                 # Looking for export
008_BEFORE_-_About_to_tap_Export_Notebook.png          # Before tapping export
009_AFTER_-_Tapped_Export_Notebook.png                  # After tapping export
010_Looking_for_citation_style_dialog.png               # Citation dialog
011_BEFORE_-_About_to_select_None_citation.png
012_AFTER_-_Selected_None_citation.png
013_BEFORE_-_About_to_click_EXPORT_button.png
014_AFTER_-_Clicked_EXPORT_button_(should_show_share_menu).png
015_Looking_for_OneDrive_in_share_menu.png              # Share sheet
016_BEFORE_-_About_to_tap_OneDrive.png
017_AFTER_-_Tapped_OneDrive_(should_open_OneDrive).png
018_Looking_for_OneDrive_save/upload_button.png         # OneDrive screen
019_BEFORE_-_About_to_tap_Save_button.png
020_AFTER_-_Tapped_Save_button_(upload_should_complete).png
```

## Debugging Workflow

1. **Run with debug mode**: Use `--debug-screenshots --max-books 1` to test on just one book
2. **Review screenshots**: Open the timestamped folder and look at the numbered screenshots
3. **Find the problem**: Look for the screenshot where things go wrong
   - Example: "Screenshot 014 shows the share menu but screenshot 015 shows the wrong screen"
4. **Check the XML**: Open the corresponding `.xml` file to see the UI structure
5. **Report issue**: You can then say "Screenshot 014 is correct, but on 015 you clicked the wrong button"

## Example Usage

```bash
# Test on 1 book with debug screenshots
python -m note_hammer.android_automation --debug-screenshots --max-books 1 --collection "To Export"

# Use custom screenshot directory
python -m note_hammer.android_automation --debug-screenshots --screenshot-dir "my_debug_session"

# Full run with debug mode (will generate many screenshots)
python -m note_hammer.android_automation --debug-screenshots
```

## Tips

- Each session creates a new timestamped folder, so old screenshots aren't overwritten
- Screenshots are saved as PNG files
- UI dumps are saved as XML files with the same name
- The counter ensures screenshots are in chronological order
- Annotation in filename describes what's happening at that moment
