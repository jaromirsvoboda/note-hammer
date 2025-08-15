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

            # Check if we're on the home screen
            for home_text in self.config["ui_elements"]["home"]:
                if self.device(text=home_text).exists:
                    return True

            # If not in book view and not on home screen, try pressing back
            self.device.press("back")
            time.sleep(0.5)

        return False

    def start_kindle_app(self):
        """Launch Kindle app and ensure we're at the home screen."""
        try:
            # Start the app
            self.device.app_start(self.config["kindle_package"])
            time.sleep(self.config["wait_times"]["app_launch"])
            
            # Ensure we're at the home screen
            if not self.return_to_home():
                raise KindleUIError("Failed to navigate to Kindle home screen")
            
            self.logger.info("Kindle app started and ready")
        except Exception as e:
            self.logger.error(f"Failed to start Kindle app: {e}")
            raise

    def navigate_to_collection(self, collection_name: str):
        """Navigate to the specified collection."""
        try:
            # Ensure we're starting from the home screen
            if not self.return_to_home():
                raise KindleUIError("Failed to return to home screen")

            # Try to find Library tab using multiple methods
            library_found = False
            
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

            # Find Collections view
            collections_found = False
            
            # Method 1: Direct "Collections" text
            if self.find_and_click("Collections", "收藏夹", "Collections"):
                collections_found = True
            
            # Method 2: Try filter/sort button
            if not collections_found and self.device(resourceId="com.amazon.kindle:id/filter_sort_button").exists:
                self.device(resourceId="com.amazon.kindle:id/filter_sort_button").click()
                time.sleep(0.5)
                if self.find_and_click("Collections", "收藏夹", "Collections"):
                    collections_found = True

            if not collections_found:
                raise KindleUIError("Could not find Collections option")

            time.sleep(self.config["wait_times"]["navigation"])

            # Find the specific collection
            collection_found = False
            max_scrolls = 5
            scroll_count = 0
            
            while scroll_count < max_scrolls and not collection_found:
                if self.find_and_click(collection_name):
                    collection_found = True
                    break
                    
                self.device.swipe_ext("up", scale=0.8)
                scroll_count += 1
                time.sleep(0.5)

            if not collection_found:
                raise KindleUIError(f"Collection '{collection_name}' not found after {max_scrolls} scrolls")

            time.sleep(self.config["wait_times"]["navigation"])
            
            self.current_collection = collection_name
            self.logger.info(f"Successfully navigated to collection: {collection_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to collection: {e}")
            # Take a screenshot for debugging
            screenshot_path = f"debug_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.device.screenshot(screenshot_path)
            self.logger.info(f"Debug screenshot saved to {screenshot_path}")
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
            screenshot_file = f"error_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            exporter.device.screenshot(screenshot_file)
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