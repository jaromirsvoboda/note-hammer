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
        export_delay: float = 3.0,
        max_books: Optional[int] = None
    ):
        self.device_id = device_id
        self.collection_name = collection_name
        self.export_delay = export_delay
        self.max_books = max_books
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
    
    def get_ui_text_elements(self) -> List[str]:
        """Get just text elements from UI (more efficient than full dump)"""
        ui_dump = self.get_ui_dump()
        import re
        text_pattern = r'text="([^"]+)"'
        return [text for text in re.findall(text_pattern, ui_dump) if text and len(text) > 2]

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
        # Use monkey command as it's more reliable across different device manufacturers
        self.run_adb_command([
            "shell", "monkey", 
            "-p", "com.amazon.kindle",
            "-c", "android.intent.category.LAUNCHER",
            "1"
        ])
        time.sleep(3)

    def navigate_to_collection(self) -> bool:
        """Navigate to the specified collection"""
        logging.info(f"Navigating to collection: {self.collection_name}")
        
        # Tap Library (usually bottom navigation)
        library_elements = self.find_elements_by_text("LIBRARY")
        if library_elements:
            self.tap(library_elements[0].x, library_elements[0].y)
        else:
            # Fallback: tap at known LIBRARY tab coordinates for Samsung devices
            logging.info("Using fallback coordinates for LIBRARY tab")
            self.tap(675, 2119)
        
        # Wait for Library to load
        time.sleep(3)
        logging.info("Library loaded, looking for collections")
        
        # Look for Collections or the collection name directly
        if self.wait_for_text("Collections"):
            logging.info("Found Collections, tapping it")
            collections_elements = self.find_elements_by_text("Collections")
            self.tap(collections_elements[0].x, collections_elements[0].y)
            time.sleep(2)
        else:
            logging.info("No Collections found, looking directly for collection name")
        
        # Find and tap the target collection
        logging.info(f"Looking for collection: {self.collection_name}")
        if not self.wait_for_text(self.collection_name):
            logging.error(f"Could not find collection: {self.collection_name}")
            
            # Debug: show what text elements we can find
            visible_text = self.get_ui_text_elements()
            logging.info(f"Available text elements: {visible_text[:10]}")  # Show first 10
            
            return False
            
        collection_elements = self.find_elements_by_text(self.collection_name)
        self.tap(collection_elements[0].x, collection_elements[0].y)
        
        return True

    def get_visible_books(self) -> List[UIElement]:
        """Get list of currently visible books on screen"""
        ui_dump = self.get_ui_dump()
        
        # Look for clickable book button elements (better than title text)
        import re
        # First try to find the clickable book buttons that contain the whole book
        button_pattern = r'content-desc="([^"]*book[^"]*)"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        matches = re.findall(button_pattern, ui_dump, re.IGNORECASE)
        
        logging.info(f"Book button pattern found {len(matches)} matches")
        
        # If no book buttons found, try title elements but get parent bounds
        if not matches:
            # Pattern that matches the actual XML structure we see
            book_pattern = r'text="([^"]+)"\s+resource-id="com\.amazon\.kindle:id/lib_book_row_title"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            title_matches = re.findall(book_pattern, ui_dump)
            logging.info(f"Title pattern found {len(title_matches)} matches")
            
            # For each title, find its parent button element
            for title, tx1, ty1, tx2, ty2 in title_matches:
                # Look for parent button that contains this title
                parent_pattern = rf'<node[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>.*?{re.escape(title[:30])}'
                parent_match = re.search(parent_pattern, ui_dump, re.DOTALL)
                if parent_match:
                    px1, py1, px2, py2 = parent_match.groups()
                    matches.append((title, px1, py1, px2, py2))
                    logging.info(f"Found parent button for: {title[:50]}")
                else:
                    # Fallback to title coordinates but expand the click area
                    tx1, ty1, tx2, ty2 = int(tx1), int(ty1), int(tx2), int(ty2)
                    # Expand left to cover the book cover area
                    expanded_x1 = max(0, tx1 - 200)  # Go left to cover book cover
                    expanded_y1 = ty1 - 50  # Go up a bit
                    expanded_y2 = ty2 + 100  # Go down to cover book area
                    matches.append((title, str(expanded_x1), str(expanded_y1), str(tx2), str(expanded_y2)))
                    logging.info(f"Using expanded coordinates for: {title[:50]}")
        
        # Alternative patterns as fallbacks
        if not matches:
            alt_pattern1 = r'text="([^"]+)"[^>]*resource-id="com\.amazon\.kindle:id/lib_book_row_title"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            matches = re.findall(alt_pattern1, ui_dump)
            logging.info(f"Alternative pattern 1 found {len(matches)} matches")
        
        # Debug: show relevant parts if no matches found
        if not matches:
            resource_pattern = r'resource-id="com\.amazon\.kindle:id/lib_book_row_title"'
            resource_matches = re.findall(resource_pattern, ui_dump)
            logging.info(f"Found {len(resource_matches)} lib_book_row_title elements")
            
            # Show sample book elements from UI
            book_sections = re.findall(r'<node[^>]*lib_book_row_title[^>]*>.*?</node>', ui_dump, re.DOTALL)
            if book_sections:
                logging.info("Sample book element from UI:")
                # Show first book element, truncated
                sample = book_sections[0][:400] + "..." if len(book_sections[0]) > 400 else book_sections[0]
                logging.info(sample)
                
            # Try to find clickable book buttons instead
            book_button_pattern = r'content-desc="([^"]*)" checkable="false"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            button_matches = re.findall(book_button_pattern, ui_dump)
            if button_matches:
                logging.info("Found clickable book buttons:")
                for desc, x1, y1, x2, y2 in button_matches[:3]:  # Show first 3
                    if any(keyword in desc.lower() for keyword in ['book', 'interview', 'mexico', 'kant']):
                        logging.info(f"  - {desc[:50]}... at ({x1},{y1})-({x2},{y2})")
                        center_x = (int(x1) + int(x2)) // 2
                        center_y = (int(y1) + int(y2)) // 2
                        matches.append((desc, str(center_x), str(center_y), str(center_x), str(center_y)))
        
        books = []
        for title, x1, y1, x2, y2 in matches:
            center_x = (int(x1) + int(x2)) // 2
            center_y = (int(y1) + int(y2)) // 2
            books.append(UIElement(center_x, center_y, title))
            logging.info(f"Found book: {title}")
        
        return books
    
    def get_all_books_in_collection(self) -> List[UIElement]:
        """Get list of all books in collection, with scrolling pagination"""
        time.sleep(2)  # Wait for collection to load
        
        # Debug: check what's visible in collection
        logging.info("Checking collection contents...")
        
        all_books = []
        seen_titles = set()
        scroll_attempts = 0
        max_scroll_attempts = 50  # Prevent infinite loops
        
        while scroll_attempts < max_scroll_attempts:
            # Get currently visible books
            visible_books = self.get_visible_books()
            
            # Add new books to our list
            new_books_found = False
            for book in visible_books:
                if book.text not in seen_titles:
                    all_books.append(book)
                    seen_titles.add(book.text)
                    new_books_found = True
                    
                    # Check if we've reached max_books limit
                    if self.max_books and len(all_books) >= self.max_books:
                        logging.info(f"Reached max_books limit of {self.max_books}")
                        return all_books[:self.max_books]
            
            # If no new books found, we've probably reached the end
            if not new_books_found:
                logging.info(f"No new books found after {scroll_attempts} scroll attempts")
                break
                
            # Scroll down to load more books
            logging.info(f"Found {len(all_books)} books so far, scrolling for more...")
            self.scroll_down_in_collection()
            scroll_attempts += 1
            time.sleep(1)  # Brief pause after scrolling
        
        logging.info(f"Found {len(all_books)} total books in collection")
        return all_books
    
    def scroll_down_in_collection(self):
        """Scroll down in the collection view"""
        # Scroll from middle of screen to load more books
        screen_height = 2340  # From UI dump bounds
        screen_width = 1080
        
        start_x = screen_width // 2
        start_y = int(screen_height * 0.7)  # Start from 70% down
        end_y = int(screen_height * 0.3)    # End at 30% down
        
        self.swipe(start_x, start_y, start_x, end_y, 500)

    def export_book_notes(self, book: UIElement) -> bool:
        """Export notes for a specific book"""
        logging.info(f"Exporting notes for: {book.text}")
        
        # Long press on book to open context menu
        logging.info(f"Long pressing book at ({book.x}, {book.y})")
        self.run_adb_command([
            "shell", "input", "swipe", 
            str(book.x), str(book.y), str(book.x), str(book.y), "1000"
        ])
        time.sleep(3)
        
        # Check what options appeared after long press
        visible_text = self.get_ui_text_elements()
        logging.info(f"Available options after long press: {[t for t in visible_text if len(t) < 50]}")
        
        # Also show relevant UI snippets with clickable elements
        ui_dump = self.get_ui_dump()
        import re
        clickable_elements = re.findall(r'<node[^>]*clickable="true"[^>]*text="([^"]+)"[^>]*>', ui_dump)
        if clickable_elements:
            logging.info(f"Clickable elements: {[t for t in clickable_elements if t and len(t) < 50]}")
        
        # Look for various possible note/highlight options
        note_options = ["Notes", "Highlights", "View Notes", "Notes & Highlights", "Export", "Share"]
        
        for option in note_options:
            if self.wait_for_text(option, timeout=2.0):
                logging.info(f"Found option: {option}")
                option_elements = self.find_elements_by_text(option)
                self.tap(option_elements[0].x, option_elements[0].y)
                time.sleep(2)
                return True
        
        # If no context menu appeared, try regular tap to open book
        logging.info("No context menu found, trying to open book directly")
        self.tap(book.x, book.y)
        time.sleep(3)
        
        # Check what's available in the opened book
        visible_text = self.get_ui_text_elements()
        logging.info(f"Options in opened book: {[t for t in visible_text if len(t) < 50]}")
        
        # Show clickable options in opened book
        ui_dump = self.get_ui_dump()
        clickable_elements = re.findall(r'<node[^>]*clickable="true"[^>]*text="([^"]+)"[^>]*>', ui_dump)
        if clickable_elements:
            logging.info(f"Clickable options in book: {[t for t in clickable_elements if t and len(t) < 50]}")
        
        logging.warning(f"Could not find notes export option for {book.text}")
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
        
        # Get books in collection (with pagination)
        books = self.get_all_books_in_collection()
        
        if self.max_books:
            logging.info(f"Found {len(books)} books in collection (limited to {self.max_books})")
        else:
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
    parser.add_argument("--max-books", type=int, help="Maximum number of books to export (for testing)")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    automator = AndroidKindleAutomator(
        device_id=args.device,
        collection_name=args.collection,
        export_delay=args.delay,
        max_books=args.max_books
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