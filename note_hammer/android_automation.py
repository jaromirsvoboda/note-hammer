"""
Android Kindle App Automation for Note Export
Automates the process of exporting notes from all books in a specific collection
"""
import time
import logging
import subprocess
import json
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class UIElement:
    """Represents a UI element with coordinates and properties"""
    x: int
    y: int
    text: str = ""
    resource_id: str = ""
    class_name: str = ""


class AndroidKindleAutomator:
    def __init__(
        self,
        device_id: Optional[str] = None,
        collection_name: str = "To Export",
        export_delay: float = 3.0
    ):
        self.device_id = device_id
        self.collection_name = collection_name
        self.export_delay = export_delay
        self.adb_prefix = ["adb"] + (["-s", device_id] if device_id else [])
        
    def run_adb_command(self, command: List[str]) -> str:
        """Execute ADB command and return output"""
        full_command = self.adb_prefix + command
        try:
            result = subprocess.run(
                full_command, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"ADB command failed: {' '.join(full_command)}")
            logging.error(f"Error: {e.stderr}")
            raise

    def tap(self, x: int, y: int, delay: float = 1.0) -> None:
        """Tap at coordinates and wait"""
        self.run_adb_command(["shell", "input", "tap", str(x), str(y)])
        time.sleep(delay)
        logging.info(f"Tapped at ({x}, {y})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        """Swipe from one point to another"""
        self.run_adb_command([
            "shell", "input", "swipe", 
            str(x1), str(y1), str(x2), str(y2), str(duration)
        ])
        time.sleep(1)
        logging.info(f"Swiped from ({x1}, {y1}) to ({x2}, {y2})")

    def type_text(self, text: str) -> None:
        """Type text (escape special characters)"""
        escaped_text = text.replace(" ", "%s").replace("'", "\\'")
        self.run_adb_command(["shell", "input", "text", escaped_text])
        time.sleep(0.5)

    def press_key(self, key: str) -> None:
        """Press a key (KEYCODE_BACK, KEYCODE_HOME, etc.)"""
        self.run_adb_command(["shell", "input", "keyevent", key])
        time.sleep(1)

    def get_ui_dump(self) -> str:
        """Get current UI hierarchy"""
        self.run_adb_command(["shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
        return self.run_adb_command(["shell", "cat", "/sdcard/ui_dump.xml"])

    def find_elements_by_text(self, text: str) -> List[UIElement]:
        """Find UI elements containing specific text"""
        ui_dump = self.get_ui_dump()
        # Simple XML parsing for text attributes
        import re
        pattern = rf'text="[^"]*{re.escape(text)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        matches = re.findall(pattern, ui_dump)
        
        elements = []
        for match in matches:
            x1, y1, x2, y2 = map(int, match)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            elements.append(UIElement(center_x, center_y, text))
        
        return elements

    def wait_for_text(self, text: str, timeout: float = 10.0) -> bool:
        """Wait for text to appear on screen"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            elements = self.find_elements_by_text(text)
            if elements:
                return True
            time.sleep(1)
        return False

    def launch_kindle(self) -> None:
        """Launch Kindle app"""
        logging.info("Launching Kindle app")
        self.run_adb_command([
            "shell", "am", "start", 
            "-n", "com.amazon.kindle/.routing.LauncherActivity"
        ])
        time.sleep(3)

    def navigate_to_collection(self) -> bool:
        """Navigate to the specified collection"""
        logging.info(f"Navigating to collection: {self.collection_name}")
        
        # Tap Library (usually bottom navigation)
        library_elements = self.find_elements_by_text("Library")
        if not library_elements:
            logging.error("Could not find Library button")
            return False
        
        self.tap(library_elements[0].x, library_elements[0].y)
        
        # Look for Collections or the collection name directly
        if self.wait_for_text("Collections"):
            collections_elements = self.find_elements_by_text("Collections")
            self.tap(collections_elements[0].x, collections_elements[0].y)
        
        # Find and tap the target collection
        if not self.wait_for_text(self.collection_name):
            logging.error(f"Could not find collection: {self.collection_name}")
            return False
            
        collection_elements = self.find_elements_by_text(self.collection_name)
        self.tap(collection_elements[0].x, collection_elements[0].y)
        
        return True

    def get_books_in_collection(self) -> List[UIElement]:
        """Get list of books in the current collection view"""
        time.sleep(2)  # Wait for collection to load
        ui_dump = self.get_ui_dump()
        
        # Look for book titles or cover images
        # This is a simplified approach - you may need to adjust based on actual UI
        import re
        book_pattern = r'class="[^"]*"[^>]*text="([^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        matches = re.findall(book_pattern, ui_dump)
        
        books = []
        for title, x1, y1, x2, y2 in matches:
            if title and len(title) > 5:  # Filter out UI elements
                center_x = (int(x1) + int(x2)) // 2
                center_y = (int(y1) + int(y2)) // 2
                books.append(UIElement(center_x, center_y, title))
        
        return books

    def export_book_notes(self, book: UIElement) -> bool:
        """Export notes for a specific book"""
        logging.info(f"Exporting notes for: {book.text}")
        
        # Long press on book to open context menu
        self.run_adb_command([
            "shell", "input", "swipe", 
            str(book.x), str(book.y), str(book.x), str(book.y), "1000"
        ])
        time.sleep(2)
        
        # Look for "View Notes & Highlights" or similar option
        if self.wait_for_text("Notes"):
            notes_elements = self.find_elements_by_text("Notes")
            self.tap(notes_elements[0].x, notes_elements[0].y)
        else:
            # Alternative: tap book normally then look for notes option
            self.tap(book.x, book.y)
            time.sleep(2)
            
            # Look for notes/highlights menu option
            if not self.wait_for_text("Notes"):
                logging.warning(f"Could not find notes option for {book.text}")
                self.press_key("KEYCODE_BACK")
                return False
        
        # Wait for notes view to load
        time.sleep(2)
        
        # Look for share/export button (usually three dots or share icon)
        share_elements = self.find_elements_by_text("Share") or self.find_elements_by_text("⋮")
        if not share_elements:
            logging.warning(f"Could not find share option for {book.text}")
            self.press_key("KEYCODE_BACK")
            return False
        
        self.tap(share_elements[0].x, share_elements[0].y)
        time.sleep(1)
        
        # Look for OneDrive in share menu
        if self.wait_for_text("OneDrive"):
            onedrive_elements = self.find_elements_by_text("OneDrive")
            self.tap(onedrive_elements[0].x, onedrive_elements[0].y)
            
            # Wait for OneDrive to process
            time.sleep(self.export_delay)
            
            # Navigate back to collection
            self.press_key("KEYCODE_BACK")
            self.press_key("KEYCODE_BACK")
            
            logging.info(f"Successfully exported notes for {book.text}")
            return True
        else:
            logging.warning(f"Could not find OneDrive option for {book.text}")
            self.press_key("KEYCODE_BACK")
            return False

    def export_collection_notes(self) -> int:
        """Export notes for all books in the collection"""
        logging.info(f"Starting automated export for collection: {self.collection_name}")
        
        # Launch Kindle and navigate to collection
        self.launch_kindle()
        
        if not self.navigate_to_collection():
            logging.error("Failed to navigate to collection")
            return 0
        
        # Get books in collection
        books = self.get_books_in_collection()
        logging.info(f"Found {len(books)} books in collection")
        
        successful_exports = 0
        for i, book in enumerate(books, 1):
            logging.info(f"Processing book {i}/{len(books)}: {book.text}")
            
            try:
                if self.export_book_notes(book):
                    successful_exports += 1
                else:
                    logging.warning(f"Failed to export notes for: {book.text}")
                
                # Brief pause between books
                time.sleep(2)
                
            except Exception as e:
                logging.error(f"Error processing {book.text}: {e}")
                # Try to recover by going back to collection
                self.press_key("KEYCODE_BACK")
                self.press_key("KEYCODE_BACK")
                time.sleep(2)
        
        logging.info(f"Export complete. Successfully exported {successful_exports}/{len(books)} books")
        return successful_exports


def main():
    """Main function for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automate Kindle note export from Android app")
    parser.add_argument("--device", help="ADB device ID (optional)")
    parser.add_argument("--collection", default="To Export", help="Collection name to export")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay after each export")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    automator = AndroidKindleAutomator(
        device_id=args.device,
        collection_name=args.collection,
        export_delay=args.delay
    )
    
    try:
        successful_exports = automator.export_collection_notes()
        print(f"Automation complete. Exported notes from {successful_exports} books.")
        
    except KeyboardInterrupt:
        logging.info("Automation interrupted by user")
    except Exception as e:
        logging.error(f"Automation failed: {e}")


if __name__ == "__main__":
    main()