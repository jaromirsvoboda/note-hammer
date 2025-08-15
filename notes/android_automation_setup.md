# Android Kindle Automation Setup Guide

This guide will help you set up automated note extraction from your Android Kindle app's "To Export" collection.

## Prerequisites

### 1. Android Device Setup
1. **Enable Developer Options**:
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times
   - Developer options will appear in Settings

2. **Enable USB Debugging**:
   - Go to Settings → Developer Options
   - Turn on "USB Debugging"
   - Connect your phone to computer via USB
   - Accept the debugging prompt on your phone

3. **Install ADB** (Android Debug Bridge):
   - **Windows**: Download Android SDK Platform Tools
   - **Mac**: `brew install android-platform-tools`
   - **Linux**: `sudo apt install adb` or `sudo pacman -S android-tools`

### 2. Test ADB Connection
```bash
# Check if device is connected
adb devices

# Should show something like:
# List of devices attached
# ABC123XYZ    device
```

### 3. OneDrive Setup
- Ensure OneDrive app is installed and logged in on your Android device
- Note the local path where OneDrive syncs files on your computer

## Usage

### Complete Automation (Recommended)
```bash
note-hammer automate_android \
    --collection "To Export" \
    --onedrive-path "/path/to/onedrive/kindle/notes" \
    --output-path "./markdown_notes" \
    --export-delay 5.0
```

### Android-Only Automation
If you prefer to process files separately:
```bash
# Step 1: Export from Android
python -m note_hammer.android_automation --collection "To Export" --delay 5.0

# Step 2: Process exported files later
note-hammer extract_kindle -i "/path/to/onedrive/kindle" -o "./notes"
```

## Command Options

- `--device`: Specify device ID if multiple Android devices connected
- `--collection`: Name of Kindle collection (default: "To Export")
- `--export-delay`: Seconds to wait after each export (default: 3.0)
- `--onedrive-path`: Path to OneDrive folder where Kindle exports are saved
- `--output-path`: Where final markdown files will be saved
- `--skip-confirmation`: Skip safety prompts

## Troubleshooting

### Common Issues

**1. "No devices found"**
- Check USB cable connection
- Ensure USB debugging is enabled
- Try running `adb kill-server && adb start-server`

**2. "Device unauthorized"**
- Check your phone for debugging authorization prompt
- Accept the prompt and check "Always allow from this computer"

**3. "Could not find collection"**
- Ensure the collection name matches exactly (case-sensitive)
- Check that books exist in the collection
- Try opening Kindle app manually first

**4. "Automation gets stuck"**
- The script may need tuning for your device's UI
- Check the logs for where it stopped
- You may need to adjust coordinates or element detection

### UI Customization

The automation script finds UI elements by text matching. If your Kindle app uses different language or has different UI elements, you may need to modify:

1. Collection navigation text in `navigate_to_collection()`
2. Notes/sharing button text in `export_book_notes()`
3. OneDrive sharing option text

### Performance Tips

- Use `--export-delay 5.0` or higher for slower devices
- Close other apps to reduce interference
- Keep phone plugged in during long automation runs
- Test with 1-2 books first before running on entire collection

## Security Notes

- This automation requires USB debugging, which can be a security risk
- Only connect to trusted computers
- Disable USB debugging when not needed
- The script only interacts with the Kindle app and sharing functions

## Example Workflow

1. **Prepare**: Add books to "To Export" collection in Kindle app
2. **Connect**: Plug phone into computer with USB debugging enabled
3. **Run**: Execute the automation command
4. **Wait**: Let the script work through all books (may take 5-10 minutes)
5. **Review**: Check the generated markdown files in your output directory

The automation will:
- Open Kindle app
- Navigate to your collection
- For each book: open → view notes → share to OneDrive
- Wait for OneDrive sync
- Process all exported HTML files into markdown
- Generate clean markdown files ready for use in Obsidian or other tools