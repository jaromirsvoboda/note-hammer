import uiautomator2 as u2
import time
import logging
from datetime import datetime
import sys
import subprocess
from typing import Optional
import json
from pathlib import Path
from contextlib import contextmanager

class DeviceConnectionError(Exception):
    """Custom exception for device connection issues."""
    pass

class KindleUIError(Exception):
    """Custom exception for Kindle UI navigation issues."""
    pass

class KindleHighlightExporter:
    def __init__(self, device_serial: Optional[str] = None, export_dir: str = "exported_highlights"):
        """
        Initialize the Kindle Highlight Exporter.

        Args:
            device_serial: Optional specific device to connect to
            export_dir: Directory to save exported highlights
        """
        # Set up logging
        self._setup_logging()

        # Set up export directory
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        # Set up debug directory
        self.debug_dir = Path("ui_dumps")
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Connect to device
        self.device = self._connect_device(device_serial)

        # Initialize state
        self.processed_documents = set()
        self.current_collection = None

        # Load configuration
        self.config = self._load_config()

    def _setup_logging(self):
        """Set up logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"kindle_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self) -> dict:
        """Load configuration from config.json if it exists."""
        config_file = Path("config.json")
        default_config = {
            "kindle_package": "com.amazon.kindle",
            "wait_times": {
                "app_launch": 3,
                "navigation": 1,
                "highlight_export": 2
            },
            "retry_attempts": 3,
            "ui_elements": {
                "library": ["Library", "书库", "Bibliothèque"],  # Multiple languages
                "home": ["Home", "主页", "Accueil"],
                "back": ["Back", "返回", "Retour"]
            }
        }

        if config_file.exists():
            try:
                with config_file.open() as f:
                    return {**default_config, **json.load(f)}
            except json.JSONDecodeError:
                self.logger.warning("Invalid config.json, using defaults")
                return default_config
        return default_config

    @contextmanager
    def wait_for_ui(self, timeout=5.0):
        """Context manager for UI operations with timeout."""
        try:
            self.device.implicitly_wait(timeout)
            yield
        finally:
            self.device.implicitly_wait(0.0)

    def _check_adb_installed(self) -> bool:
        """Check if ADB is installed and accessible."""
        try:
            subprocess.run(['adb', 'version'],
                         capture_output=True,
                         text=True,
                         check=True)
            return True
        except FileNotFoundError:
            self.logger.error("ADB not found in PATH. Please ensure Android Platform Tools are installed.")
            return False
        except subprocess.CalledProcessError:
            self.logger.error("Error running ADB. Please check your Android Platform Tools installation.")
            return False

    def _get_connected_devices(self) -> list:
        """Get list of connected Android devices."""
        try:
            result = subprocess.run(['adb', 'devices'],
                                  capture_output=True,
                                  text=True,
                                  check=True)

            lines = result.stdout.strip().split('\n')[1:]
            devices = [line.split('\t')[0] for line in lines if '\tdevice' in line]

            return devices
        except Exception as e:
            self.logger.error(f"Error getting device list: {e}")
            return []

    def _connect_device(self, device_serial: Optional[str] = None) -> u2.Device:
        """Connect to Android device with improved error handling and guidance."""
        if not self._check_adb_installed():
            raise DeviceConnectionError("""
ADB not found. Please:
1. Download Android Platform Tools from: https://developer.android.com/tools/releases/platform-tools
2. Add the platform-tools folder to your system PATH
3. Restart your terminal/IDE
""")

        devices = self._get_connected_devices()

        if not devices:
            usb_debug_ok, debug_message = self._verify_usb_debugging()
            guidance = """
No Android device detected. Please:

1. Enable USB debugging on your Android device:
   - Go to Settings > About phone
   - Tap Build number 7 times to enable Developer options
   - Go to Settings > System > Developer options
   - Enable USB debugging

2. Connect your device via USB
   - Use a good quality USB cable
   - Try different USB ports
   - Make sure your device is unlocked

3. Accept the USB debugging prompt on your device
   - Look for a popup on your Android device
   - Check "Always allow from this computer"
   - Tap "Allow"

Current status: {debug_message}
"""
            raise DeviceConnectionError(guidance.format(debug_message=debug_message))

        if device_serial and device_serial not in devices:
            raise DeviceConnectionError(f"Specified device {device_serial} not found. Available devices: {devices}")

        target_device = device_serial or devices[0]

        try:
            device = u2.connect(target_device)
            self.logger.info(f"Successfully connected to device: {target_device}")
            return device
        except Exception as e:
            raise DeviceConnectionError(f"Failed to connect to device {target_device}: {e}")

    def find_and_click(self, *text_options, **selector_kwargs):
        """Find and click a UI element with multiple selector attempts."""
        # Try exact text matches first
        for text in text_options:
            try:
                element = self.device(text=text)
                if element.exists:
                    element.click()
                    time.sleep(0.5)
                    return True
            except Exception:
                continue

        # Try other selectors
        selectors = []

        for text in text_options:
            selectors.extend([
                {'text': text},
                {'textContains': text},
                {'description': text},
                {'descriptionContains': text}
            ])

        if 'resourceId' in selector_kwargs:
            selectors.append({'resourceId': selector_kwargs['resourceId']})

        for selector in selectors:
            try:
                element = self.device(**selector)
                if element.exists:
                    element.click()
                    time.sleep(0.5)
                    return True
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")
                continue

        return False

    def is_in_book_view(self):
        """Check if currently in a book view."""
        # Multiple ways to detect if we're in a book
        return any([
            self.device(resourceId="com.amazon.kindle:id/reader_toolbar_button").exists,
            self.device(resourceId="com.amazon.kindle:id/reading_view").exists,
            self.device(resourceId="com.amazon.kindle:id/mini_shopping_button").exists
        ])

    def return_to_home(self):
        """Return to Kindle home screen from any state."""
        max_attempts = 3
        for _ in range(max_attempts):
            # If in a book view
            if self.is_in_book_view():
                # Try to find and click the back button or navigation menu
                if not (self.find_and_click("Back to Library", "返回图书馆", resourceId="com.amazon.kindle:id/reader_toolbar_button") or
                        self.device.press("back")):
                    continue
                time.sleep(1)

            # Check if we're on the home screen using multiple methods
            # Method 1: Check for "Home" text in various languages
            for home_text in self.config["ui_elements"]["home"]:
                if self.device(text=home_text).exists:
                    return True

            # Method 2: Check for common home screen UI elements
            home_indicators = [
                self.device(resourceId="com.amazon.kindle:id/home_fragment").exists,
                self.device(resourceId="com.amazon.kindle:id/library_button").exists,
                self.device(resourceId="com.amazon.kindle:id/tab_layout").exists,
                self.device(description="Library").exists,
                self.device(description="Home").exists,
            ]
            if any(home_indicators):
                self.logger.info("Detected home screen via UI elements")
                return True

            # If not in book view and not on home screen, try pressing back
            self.device.press("back")
            time.sleep(0.5)

        # If we couldn't confirm home screen but also not in book view, assume we're on home
        if not self.is_in_book_view():
            self.logger.warning("Could not confirm home screen, but not in book view - assuming home")
            return True

        return False

    def start_kindle_app(self):
        """Launch Kindle app and ensure we're at the home screen."""
        try:
            # Check if screen is locked before starting
            self.ensure_screen_unlocked()

            # Start the app
            self.device.app_start(self.config["kindle_package"])
            time.sleep(self.config["wait_times"]["app_launch"])

            # Check again in case the screen locked during app launch
            self.ensure_screen_unlocked()

            # Ensure we're at the home screen
            if not self.return_to_home():
                raise KindleUIError("Failed to navigate to Kindle home screen")

            self.logger.info("Kindle app started and ready")
        except Exception as e:
            self.logger.error(f"Failed to start Kindle app: {e}")
            raise

    def cleanup(self):
        """Clean up resources and close connections."""
        try:
            if hasattr(self, 'device') and self.device:
                # Stop the Kindle app
                try:
                    self.device.app_stop(self.config["kindle_package"])
                except Exception as e:
                    self.logger.warning(f"Failed to stop Kindle app during cleanup: {e}")

                self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def is_screen_locked(self) -> bool:
        """Check if the device screen is locked."""
        try:
            # Check screen state
            info = self.device.info
            screen_on = info.get('screenOn', False)

            # If screen is off, it's definitely locked
            if not screen_on:
                return True

            # Check for lock screen indicators
            lock_indicators = [
                self.device(resourceId="com.android.systemui:id/lock_icon").exists,
                self.device(resourceId="com.android.systemui:id/keyguard_indication_area").exists,
                self.device(text="Swipe up to unlock").exists,
                self.device(description="Unlock").exists,
            ]

            return any(lock_indicators)
        except Exception as e:
            self.logger.warning(f"Error checking screen lock state: {e}")
            return False

    def ensure_screen_unlocked(self):
        """Ensure the device screen is unlocked, or raise an error with instructions."""
        if self.is_screen_locked():
            raise DeviceConnectionError("""
Device screen is locked. Please:
1. Unlock your device
2. Keep the screen on during the export process
3. Run the script again

Tip: You can adjust your device's screen timeout in Settings > Display > Screen timeout
to prevent it from locking during the export.
""")

    def dump_ui_hierarchy(self) -> Optional[str]:
        """Dump the current UI hierarchy to a file for debugging."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = self.debug_dir / f"ui_hierarchy_{timestamp}.xml"

            # Get UI hierarchy
            xml = self.device.dump_hierarchy()

            # Save to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(xml)

            self.logger.info(f"UI hierarchy dumped to {filename}")
            return str(filename)
        except Exception as e:
            self.logger.error(f"Failed to dump UI hierarchy: {e}")
            return None

    def take_debug_screenshot(self, prefix: str = "screenshot") -> Optional[str]:
        """Take a screenshot and save it to the debug directory."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = self.debug_dir / f"{prefix}_{timestamp}.png"
            self.device.screenshot(str(filename))
            self.logger.info(f"Debug screenshot saved to {filename}")
            return str(filename)
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")
            return None

    def navigate_to_collection(self, collection_name: str):
        """Navigate to the specified collection."""
        try:
            # Ensure we're starting from the home screen
            if not self.return_to_home():
                raise KindleUIError("Failed to return to home screen")

            # Check if we're already on the Library tab
            library_tab = self.device(resourceId="com.amazon.kindle:id/library_tab")
            if library_tab.exists:
                # Check if already selected
                if library_tab.info.get("selected", False) or "selected" in library_tab.info.get("content-desc", "").lower():
                    self.logger.info("Already on Library tab")
                    library_found = True
                else:
                    # Click the Library tab
                    library_tab.click()
                    time.sleep(self.config["wait_times"]["navigation"])
                    library_found = True
                    self.logger.info("Clicked Library tab")
            else:
                library_found = False

                # Try to find Library tab using multiple methods
                # Method 1: Try direct "Library" text in multiple languages
                for library_text in self.config["ui_elements"]["library"]:
                    if self.find_and_click(library_text):
                        library_found = True
                        break

                # Method 2: Try bottom navigation
                if not library_found and self.device(resourceId="com.amazon.kindle:id/bottom_navigation").exists:
                    tabs = self.device(resourceId="com.amazon.kindle:id/bottom_navigation").child()
                    for tab in tabs:
                        if any(lib_text.lower() in tab.info.get("content-desc", "").lower()
                              for lib_text in self.config["ui_elements"]["library"]):
                            tab.click()
                            library_found = True
                            break

                # Method 3: Try hamburger menu
                if not library_found and self.device(description="Menu").exists:
                    self.device(description="Menu").click()
                    time.sleep(0.5)
                    for library_text in self.config["ui_elements"]["library"]:
                        if self.find_and_click(library_text):
                            library_found = True
                            break

                if not library_found:
                    raise KindleUIError("Could not find Library navigation element")

                time.sleep(self.config["wait_times"]["navigation"])

            # Find Collections view - Try multiple methods
            collections_found = False

            # Method 1: Try sort/view options button (the button on the right)
            sort_button = self.device(resourceId="com.amazon.kindle:id/sort_filter")
            if sort_button.exists:
                self.logger.info("Found sort/view options button, clicking it")
                sort_button.click()
                time.sleep(1.0)

                # Take screenshot to see what options appear
                self.take_debug_screenshot("sort_options_menu")
                self.dump_ui_hierarchy()

                # Look for Collections option
                if self.find_and_click("Collections", "收藏夹", "collections"):
                    collections_found = True
                    self.logger.info("Found and clicked Collections in sort/view menu")
                else:
                    self.logger.warning("Collections not found in sort/view menu, trying back")
                    self.device.press("back")
                    time.sleep(0.5)

            # Method 2: Try filter button (the icon with sliders on the left)
            if not collections_found:
                filter_button = self.device(resourceId="com.amazon.kindle:id/refine_menu_button_container")
                if filter_button.exists:
                    self.logger.info("Found filter button, clicking it")
                    filter_button.click()
                    time.sleep(1.0)

                    # Take screenshot to see what's in the filter menu
                    self.take_debug_screenshot("filter_menu")
                    self.dump_ui_hierarchy()

                    # Look for Collections option in the filter menu
                    if self.find_and_click("Collections", "收藏夹", "collections"):
                        collections_found = True
                        self.logger.info("Found and clicked Collections in filter menu")
                    else:
                        self.logger.warning("Collections not found in filter menu, trying back")
                        self.device.press("back")
                        time.sleep(0.5)

            # Method 3: Direct "Collections" text (if it's visible on main screen)
            if not collections_found and self.find_and_click("Collections", "收藏夹", "collections"):
                collections_found = True
                self.logger.info("Found Collections as direct text")

            # Method 4: Try the "More" tab at the bottom
            if not collections_found:
                more_tab = self.device(resourceId="com.amazon.kindle:id/more_tab")
                if more_tab.exists:
                    self.logger.info("Trying More tab")
                    more_tab.click()
                    time.sleep(1.0)

                    # Take screenshot
                    self.take_debug_screenshot("more_tab")
                    self.dump_ui_hierarchy()

                    # Look for Collections
                    if self.find_and_click("Collections", "收藏夹", "collections"):
                        collections_found = True
                        self.logger.info("Found Collections in More tab")
                    else:
                        # Go back to library
                        library_tab = self.device(resourceId="com.amazon.kindle:id/library_tab")
                        if library_tab.exists:
                            library_tab.click()
                            time.sleep(0.5)

            if not collections_found:
                # Take debug screenshots before failing
                self.take_debug_screenshot("no_collections_found")
                self.dump_ui_hierarchy()
                raise KindleUIError("Could not find Collections option. Please check the debug screenshots in ui_dumps/ folder.")

            time.sleep(self.config["wait_times"]["navigation"])

            # Find the specific collection
            collection_found = False
            max_scrolls = 5
            scroll_count = 0

            while scroll_count < max_scrolls and not collection_found:
                # Method 1: Try to find by collection_title text
                collection_title = self.device(resourceId="com.amazon.kindle:id/collection_title", text=collection_name)
                if collection_title.exists:
                    # Get the parent button by finding a button that contains this title
                    parent_button = self.device(className="android.widget.Button", descriptionContains=collection_name)
                    if parent_button.exists:
                        parent_button.click()
                        collection_found = True
                        self.logger.info(f"Clicked on collection '{collection_name}' via parent button")
                        break
                    else:
                        # Try clicking on the title itself and hope it bubbles up
                        collection_title.click()
                        collection_found = True
                        self.logger.info(f"Clicked on collection '{collection_name}' via title")
                        break

                # Method 2: Try generic find_and_click
                if not collection_found and self.find_and_click(collection_name):
                    collection_found = True
                    self.logger.info(f"Found collection '{collection_name}' via find_and_click")
                    break

                # Scroll down to find more collections
                self.device.swipe_ext("up", scale=0.8)
                scroll_count += 1
                time.sleep(0.5)
                self.logger.info(f"Scrolled {scroll_count}/{max_scrolls} times looking for '{collection_name}'")

            if not collection_found:
                # Take debug screenshots before failing
                self.take_debug_screenshot("collection_not_found")
                self.dump_ui_hierarchy()
                raise KindleUIError(f"Collection '{collection_name}' not found after {max_scrolls} scrolls")

            time.sleep(self.config["wait_times"]["navigation"])

            self.current_collection = collection_name
            self.logger.info(f"Successfully navigated to collection: {collection_name}")

        except Exception as e:
            self.logger.error(f"Failed to navigate to collection: {e}")
            # Take a screenshot for debugging
            self.take_debug_screenshot("navigation_error")
            raise

    # ... [Previous export_document_highlights, process_documents, and other methods remain the same] ...

def main():
    try:
        # Initialize exporter
        exporter = KindleHighlightExporter()

        # Start Kindle app and ensure we're at the home screen
        exporter.start_kindle_app()

        try:
            # Navigate to collection
            collection_name = "YourCollectionName"  # Replace with your collection name
            exporter.navigate_to_collection(collection_name)
        except (KindleUIError, Exception) as e:
            print("\nError navigating Kindle UI:")
            print(e)
            print("\nDumping UI hierarchy for debugging...")
            hierarchy_file = exporter.dump_ui_hierarchy()
            if hierarchy_file:
                print(f"UI hierarchy dumped to {hierarchy_file}")
            print("\nTaking screenshot for debugging...")
            screenshot_file = exporter.take_debug_screenshot("error")
            if screenshot_file:
                print(f"Screenshot saved to {screenshot_file}")
            sys.exit(1)

        # Process all documents
        processed_count, failed_documents = exporter.process_documents()

        # Log summary
        print("\nExport Summary:")
        print(f"Processed {processed_count} documents")
        if failed_documents:
            print("\nFailed documents:")
            for doc in failed_documents:
                print(f"- {doc}")

    except DeviceConnectionError as e:
        print("\nDevice Connection Error:")
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logging.exception("Unexpected error occurred")
        sys.exit(1)
    finally:
        # Cleanup
        if 'exporter' in locals():
            exporter.cleanup()

if __name__ == "__main__":
    main()
