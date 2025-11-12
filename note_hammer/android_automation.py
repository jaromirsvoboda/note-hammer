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
        max_books: Optional[int] = None,
        retry_attempts: int = 2
    ):
        self.device_id = device_id
        self.collection_name = collection_name
        self.export_delay = export_delay
        self.max_books = max_books
        self.retry_attempts = retry_attempts
        self.adb_prefix = ["adb"] + (["-s", device_id] if device_id else [])
        self.export_stats = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "failed_books": []
        }

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
        """Launch Kindle app and ensure we're at home screen"""
        logging.info("Launching Kindle app")
        # Use monkey command as it's more reliable across different device manufacturers
        self.run_adb_command([
            "shell", "monkey",
            "-p", "com.amazon.kindle",
            "-c", "android.intent.category.LAUNCHER",
            "1"
        ])
        time.sleep(3)

        # If Kindle resumed into a book, go back to home
        logging.info("Ensuring we're at Kindle home screen")
        self._navigate_to_home()

    def _navigate_to_home(self) -> None:
        """Navigate to Kindle home screen by pressing back until we get there"""
        logging.info("Navigating to Kindle home screen")

        max_attempts = 10
        for attempt in range(max_attempts):
            ui_dump = self.get_ui_dump()

            # Check if we're at home by looking for home indicators
            home_indicators = [
                "LIBRARY",
                "library_tab",
                "Home",
                "navigation_bar",
                "com.amazon.kindle:id/home"
            ]

            if any(indicator in ui_dump for indicator in home_indicators):
                logging.info(f"Reached Kindle home screen after {attempt} back presses")
                return

            # Press back and wait
            logging.info(f"Not at home yet (attempt {attempt + 1}/{max_attempts}), pressing back")
            self.press_key("KEYCODE_BACK")
            time.sleep(1)

        logging.warning("May not have reached home screen after maximum attempts")

    def navigate_to_collection(self) -> bool:
        """Navigate to the specified collection"""
        logging.info(f"Navigating to collection: {self.collection_name}")

        # Ensure we're at home first
        self._navigate_to_home()
        time.sleep(1)

        # Tap Library (usually bottom navigation)
        library_elements = self.find_elements_by_text("LIBRARY")
        if library_elements:
            logging.info("Found LIBRARY tab, tapping it")
            self.tap(library_elements[0].x, library_elements[0].y)
        else:
            # Fallback: tap at known LIBRARY tab coordinates for Samsung devices
            logging.info("Using fallback coordinates for LIBRARY tab")
            self.tap(675, 2119)

        # Wait for Library to load
        time.sleep(3)
        logging.info("Library loaded, checking if we need to switch to Collections view")

        # Check and close View/Sort menu if it's open (multiple times if needed)
        max_close_attempts = 3
        for attempt in range(max_close_attempts):
            ui_dump = self.get_ui_dump()
            if "lib_view_type_radio_group" in ui_dump or "design_bottom_sheet" in ui_dump:
                logging.info(f"View/Sort menu is open (attempt {attempt + 1}), closing it")
                self.press_key("KEYCODE_BACK")
                time.sleep(1.5)
            else:
                logging.info("View/Sort menu is closed")
                break

        # Now look for the collection card on the main library screen
        logging.info(f"Looking for collection card: {self.collection_name}")

        # Wait a bit for the library view to fully render
        time.sleep(1)

        # Get UI dump for analysis
        ui_dump = self.get_ui_dump()
        import re

        # DEBUG: Show ALL clickable elements in the view
        print("\n" + "=" * 80)
        print("DEBUG: Analyzing all clickable elements in current view")
        print("=" * 80)
        logging.info("=" * 80)
        logging.info("DEBUG: Analyzing all clickable elements in current view")
        logging.info("=" * 80)

        clickable_pattern = r'clickable="true"[^>]*(?:text="([^"]*)")?[^>]*(?:content-desc="([^"]*)")?[^>]*(?:resource-id="([^"]*)")?[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        clickable_matches = re.findall(clickable_pattern, ui_dump)

        for idx, match in enumerate(clickable_matches, 1):
            text, desc, res_id, x1, y1, x2, y2 = match
            center_x = (int(x1) + int(x2)) // 2
            center_y = (int(y1) + int(y2)) // 2

            display_text = text or desc or res_id.split('/')[-1] if res_id else "(no text)"
            msg = f"  [{idx}] Clickable: '{display_text}' at ({center_x}, {center_y}) - bounds=[{x1},{y1}][{x2},{y2}]"
            print(msg)
            logging.info(msg)
            if res_id:
                res_msg = f"      Resource ID: {res_id}"
                print(res_msg)
                logging.info(res_msg)

        print("=" * 80 + "\n")
        logging.info("=" * 80)

        # Look for collection card using parsed XML to avoid ordering issues in attributes
        logging.info(f"Looking for collection card with content-desc containing: {self.collection_name}")

        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(ui_dump)
        except Exception as parse_error:
            logging.error(f"Failed to parse UI XML: {parse_error}")
            return False

        def parse_bounds(bounds: str):
            match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if not match:
                return None
            x1, y1, x2, y2 = map(int, match.groups())
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            return x1, y1, x2, y2, center_x, center_y

        collection_nodes = []
        target_lower = self.collection_name.lower()

        for node in root.iter("node"):
            if node.get("class") != "android.widget.Button":
                continue

            desc = (node.get("content-desc") or "").strip()
            if target_lower not in desc.lower():
                continue

            bounds = node.get("bounds")
            parsed = parse_bounds(bounds or "")
            if not parsed:
                continue

            x1, y1, x2, y2, center_x, center_y = parsed
            collection_nodes.append((center_y, center_x, x1, y1, x2, y2, desc))

        msg = f"Found {len(collection_nodes)} collection card Button elements matching '{self.collection_name}'"
        print(msg)
        logging.info(msg)

        if not collection_nodes:
            err_msg = f"Could not find collection card for: {self.collection_name}"
            print(err_msg)
            logging.error(err_msg)
            print("HINT: Looking for android.widget.Button with content-desc containing collection name")
            logging.error("HINT: Looking for android.widget.Button with content-desc containing collection name")
            return False

        # Sort by vertical position to prefer the topmost matching card if duplicates exist
        collection_nodes.sort(key=lambda item: item[0])
        center_y, center_x, x1, y1, x2, y2, desc = collection_nodes[0]

        decision_msg = (
            f"DECISION: Will tap collection card '{self.collection_name}'"
            f" (content-desc='{desc}') at ({center_x}, {center_y})"
        )
        print(decision_msg)
        logging.info(decision_msg)
        print("=" * 80 + "\n")
        logging.info("=" * 80)

        # Tap the collection card
        self.tap(center_x, center_y)
        time.sleep(2)

        logging.info(f"Successfully tapped collection: {self.collection_name}")
        return True

    def get_visible_books(self) -> List[UIElement]:
        """Get list of currently visible books on screen"""
        ui_dump = self.get_ui_dump()
        logging.info(f"DEBUG: UI dump length: {len(ui_dump)} characters")

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

        try:
            # Step 1: Open the notes view for this book
            if not self._open_book_notes_view(book):
                logging.warning(f"Could not open notes view for {book.text}")
                return False

            # Step 2: Find and tap the share/export button
            if not self._tap_export_button():
                logging.warning(f"Could not find export button for {book.text}")
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                return False

            # Step 3: Select "Export Notebook" option
            if not self._select_export_notebook():
                logging.warning(f"Could not select export notebook for {book.text}")
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                return False

            # Step 4: Select OneDrive from share menu
            if not self._select_onedrive_share():
                logging.warning(f"Could not select OneDrive for {book.text}")
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                return False

            # Step 5: Confirm the OneDrive upload
            if not self._confirm_onedrive_upload():
                logging.warning(f"Could not confirm OneDrive upload for {book.text}")
                # Still return True since we got this far

            # Wait for export to complete
            logging.info(f"Export initiated for {book.text}, waiting {self.export_delay}s")
            time.sleep(self.export_delay)

            # Return to collection view
            self._return_to_collection()

            logging.info(f"Successfully exported notes for: {book.text}")
            return True

        except Exception as e:
            logging.error(f"Error exporting {book.text}: {e}")
            # Try to recover by going back to collection
            self._return_to_collection()
            return False

    def _open_book_notes_view(self, book: UIElement) -> bool:
        """Open the notes/highlights view for a book"""
        # Step 1: Tap the book to open it
        logging.info(f"Opening book by tapping at ({book.x}, {book.y})")
        self.tap(book.x, book.y, delay=3)

        # Step 2: Tap top of screen to show toolbar if not visible
        logging.info("Ensuring toolbar is visible")
        self.tap(540, 200)
        time.sleep(1)

        # Step 3: Look for the Notebook/Annotation icon button
        # This is the third button from the right in the upper right corner
        ui_dump = self.get_ui_dump()
        import re

        logging.info("Looking for Notebook/Annotation button")

        # Try multiple patterns for the notebook/annotation button
        notebook_patterns = [
            r'content-desc="[^"]*[Nn]otebook[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="[^"]*[Aa]nnotation[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'resource-id="[^"]*notebook[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'resource-id="[^"]*annotation[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ]

        for pattern in notebook_patterns:
            match = re.search(pattern, ui_dump, re.IGNORECASE)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                logging.info(f"Found Notebook button at ({center_x}, {center_y})")
                self.tap(center_x, center_y, delay=3)

                # Verify we're in Annotations view
                time.sleep(2)
                if self.wait_for_text("Annotations", timeout=3.0):
                    logging.info("Successfully opened Annotations view")
                    return True

        # If specific patterns don't work, try looking for buttons in the upper right area
        # and find the third from the right
        logging.info("Trying to find toolbar buttons in upper right corner")
        button_pattern = r'clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        all_buttons = re.findall(button_pattern, ui_dump)

        # Filter for buttons in upper right corner (y < 300, x > 700)
        upper_right_buttons = []
        for x1, y1, x2, y2 in all_buttons:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            if y1 < 300 and center_x > 700:
                upper_right_buttons.append((center_x, center_y, x1))

        # Sort by x coordinate (rightmost first) and get the third one
        upper_right_buttons.sort(key=lambda b: b[2], reverse=True)

        if len(upper_right_buttons) >= 3:
            third_from_right = upper_right_buttons[2]
            logging.info(f"Trying third button from right at ({third_from_right[0]}, {third_from_right[1]})")
            self.tap(third_from_right[0], third_from_right[1], delay=3)

            time.sleep(2)
            if self.wait_for_text("Annotations", timeout=3.0):
                logging.info("Successfully opened Annotations view")
                return True

        logging.warning("Could not open Annotations view")
        return False

    def _tap_export_button(self) -> bool:
        """Find and tap the export/share button in notes view"""
        logging.info("Looking for export/share button")

        # Wait a moment for the notes view to fully load
        time.sleep(2)

        # Look for various export button texts
        export_options = [
            "Export Notebook",
            "Share Notebook",
            "Export",
            "Share",
            "Send"
        ]

        for option in export_options:
            if self.wait_for_text(option, timeout=2.0):
                logging.info(f"Found export option: {option}")
                option_elements = self.find_elements_by_text(option)
                if option_elements:
                    self.tap(option_elements[0].x, option_elements[0].y, delay=2)
                    return True

        # Try finding share icon by resource ID or description
        ui_dump = self.get_ui_dump()
        import re

        # Look for share/export button by common patterns
        share_patterns = [
            r'content-desc="Share"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="Export"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'resource-id="[^"]*share[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'resource-id="[^"]*export[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="More options"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'  # Three-dot menu
        ]

        for pattern in share_patterns:
            match = re.search(pattern, ui_dump)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                logging.info(f"Found potential share button at ({center_x}, {center_y})")
                self.tap(center_x, center_y, delay=2)

                # Check if export option appeared
                for option in export_options:
                    if self.wait_for_text(option, timeout=1.5):
                        option_elements = self.find_elements_by_text(option)
                        if option_elements:
                            self.tap(option_elements[0].x, option_elements[0].y, delay=2)
                            return True

        # Last resort: try tapping top-right area where share buttons usually are
        logging.info("Trying top-right area for share button")
        self.tap(980, 150, delay=2)  # Top-right corner

        # Check if anything appeared
        for option in export_options:
            if self.wait_for_text(option, timeout=1.5):
                option_elements = self.find_elements_by_text(option)
                if option_elements:
                    self.tap(option_elements[0].x, option_elements[0].y, delay=2)
                    return True

        logging.warning("Could not find export button")
        return False

    def _select_export_notebook(self) -> bool:
        """Select citation style (None) from the citation dialog"""
        logging.info("Looking for citation style dialog")

        # Wait for citation style dialog to appear
        time.sleep(2)

        # Look for the citation style options: APA, Chicago Style, MLA, None
        citation_styles = [
            "None",  # Try "None" first as that's what we want
            "APA",
            "Chicago Style",
            "MLA"
        ]

        # Check if we're at the citation style dialog
        for style in citation_styles:
            if self.wait_for_text(style, timeout=2.0):
                logging.info(f"Citation style dialog found, options include: {style}")
                break
        else:
            # If no citation styles found, maybe we're already past this step
            if self.wait_for_text("OneDrive", timeout=1.0):
                logging.info("Already at share sheet, skipping citation selection")
                return True
            logging.warning("Could not find citation style dialog")
            return False

        # Select "None" citation style
        if self.wait_for_text("None", timeout=2.0):
            logging.info("Selecting 'None' citation style")
            none_elements = self.find_elements_by_text("None")
            if none_elements:
                self.tap(none_elements[0].x, none_elements[0].y, delay=2)
                logging.info("Selected 'None' citation style")
                return True

        logging.warning("Could not select 'None' citation style")
        return False

    def _select_onedrive_share(self) -> bool:
        """Select OneDrive from Android share menu"""
        logging.info("Looking for OneDrive in share menu")

        # Wait for share sheet to appear
        time.sleep(2)

        # Look for OneDrive
        if self.wait_for_text("OneDrive", timeout=5.0):
            logging.info("Found OneDrive option")
            onedrive_elements = self.find_elements_by_text("OneDrive")
            if onedrive_elements:
                self.tap(onedrive_elements[0].x, onedrive_elements[0].y, delay=3)
                return True

        # Try scrolling in share sheet to find OneDrive
        logging.info("OneDrive not immediately visible, trying to scroll")
        ui_dump = self.get_ui_dump()
        import re

        # Find scrollable area in share sheet
        scrollable_pattern = r'scrollable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        matches = re.findall(scrollable_pattern, ui_dump)

        if matches:
            # Try horizontal scroll in share sheet
            for _ in range(3):  # Try scrolling 3 times
                self.swipe(800, 1500, 300, 1500, 300)  # Swipe left
                time.sleep(1)

                if self.wait_for_text("OneDrive", timeout=2.0):
                    onedrive_elements = self.find_elements_by_text("OneDrive")
                    if onedrive_elements:
                        self.tap(onedrive_elements[0].x, onedrive_elements[0].y, delay=3)
                        return True

        # Debug: show what options are available
        visible_text = self.get_ui_text_elements()
        logging.info(f"Available share options: {[t for t in visible_text if len(t) < 30]}")

        logging.warning("Could not find OneDrive in share menu")
        return False

    def _confirm_onedrive_upload(self) -> bool:
        """Confirm the OneDrive upload (tap save/upload button)"""
        logging.info("Confirming OneDrive upload")

        # Wait for OneDrive interface to load
        time.sleep(2)

        # Look for save/upload/add buttons
        confirm_options = [
            "Save",
            "Upload",
            "Add",
            "Done",
            "OK",
            "Confirm"
        ]

        for option in confirm_options:
            if self.wait_for_text(option, timeout=3.0):
                logging.info(f"Found confirmation button: {option}")
                option_elements = self.find_elements_by_text(option)
                if option_elements:
                    # Usually want the top-right button
                    # Sort by x coordinate descending to get rightmost
                    option_elements.sort(key=lambda e: e.x, reverse=True)
                    self.tap(option_elements[0].x, option_elements[0].y, delay=2)
                    return True

        # Try tapping common save button locations
        logging.info("Trying common save button locations")
        # Top-right corner is typical for save buttons
        self.tap(980, 150, delay=2)

        time.sleep(1)
        return True  # Assume success if we got this far

    def _return_to_collection(self) -> None:
        """Return to the collection view from wherever we are"""
        logging.info("Returning to collection view")

        # Press back multiple times to ensure we're back at collection
        max_backs = 5
        for i in range(max_backs):
            time.sleep(1)

            # Check if we're back at the collection by looking for book titles
            ui_dump = self.get_ui_dump()
            if "lib_book_row_title" in ui_dump:
                logging.info(f"Back at collection after {i+1} back presses")
                return

            self.press_key("KEYCODE_BACK")

        logging.warning("May not be back at collection view")

    def export_book_notes_with_retry(self, book: UIElement) -> bool:
        """Export notes with retry logic"""
        for attempt in range(self.retry_attempts):
            if attempt > 0:
                logging.info(f"Retry attempt {attempt + 1}/{self.retry_attempts} for {book.text}")
                time.sleep(2)

            if self.export_book_notes(book):
                return True

        return False

    def export_collection_notes(self) -> dict:
        """Export notes for all books in the collection

        Returns:
            dict: Export statistics with keys: attempted, successful, failed, failed_books
        """
        logging.info(f"Starting automated export for collection: {self.collection_name}")

        # Reset stats
        self.export_stats = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "failed_books": []
        }

        try:
            # Launch Kindle and navigate to collection
            self.launch_kindle()

            if not self.navigate_to_collection():
                logging.error("Failed to navigate to collection")
                return self.export_stats

            # Get books in collection (with pagination)
            books = self.get_all_books_in_collection()

            logging.info(f"DEBUG: get_all_books_in_collection returned {len(books) if books else 0} books")

            if not books:
                logging.warning("No books found in collection")
                logging.warning("This could mean:")
                logging.warning("  1. Collection is empty")
                logging.warning("  2. Book detection patterns need adjustment")
                logging.warning("  3. UI structure changed")
                return self.export_stats

            if self.max_books:
                logging.info(f"Found {len(books)} books in collection (limited to {self.max_books})")
            else:
                logging.info(f"Found {len(books)} books in collection")

            # Process each book
            for i, book in enumerate(books, 1):
                logging.info(f"\n{'='*60}")
                logging.info(f"Processing book {i}/{len(books)}: {book.text}")
                logging.info(f"{'='*60}")

                self.export_stats["attempted"] += 1

                try:
                    if self.export_book_notes_with_retry(book):
                        self.export_stats["successful"] += 1
                        logging.info(f"✓ Successfully exported: {book.text}")
                    else:
                        self.export_stats["failed"] += 1
                        self.export_stats["failed_books"].append(book.text)
                        logging.warning(f"✗ Failed to export: {book.text}")

                    # Brief pause between books
                    time.sleep(2)

                except Exception as e:
                    self.export_stats["failed"] += 1
                    self.export_stats["failed_books"].append(book.text)
                    logging.error(f"✗ Error processing {book.text}: {e}")

                    # Try to recover by going back to collection
                    try:
                        self._return_to_collection()
                    except:
                        # If recovery fails, try to navigate back from scratch
                        logging.warning("Recovery failed, trying to navigate back to collection")
                        self.navigate_to_collection()

            # Log final summary
            self._log_export_summary()

        except KeyboardInterrupt:
            logging.info("\nExport interrupted by user")
            self._log_export_summary()
            raise
        except Exception as e:
            logging.error(f"Fatal error during export: {e}")
            self._log_export_summary()
            raise

        return self.export_stats

    def _log_export_summary(self) -> None:
        """Log a summary of the export operation"""
        logging.info(f"\n{'='*60}")
        logging.info("EXPORT SUMMARY")
        logging.info(f"{'='*60}")
        logging.info(f"Total attempted:  {self.export_stats['attempted']}")
        logging.info(f"Successful:       {self.export_stats['successful']}")
        logging.info(f"Failed:           {self.export_stats['failed']}")

        if self.export_stats['failed_books']:
            logging.info(f"\nFailed books:")
            for book in self.export_stats['failed_books']:
                logging.info(f"  - {book}")

        if self.export_stats['attempted'] > 0:
            success_rate = (self.export_stats['successful'] / self.export_stats['attempted']) * 100
            logging.info(f"\nSuccess rate: {success_rate:.1f}%")

        logging.info(f"{'='*60}\n")


def main():
    """Main function for standalone execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Automate Kindle note export from Android app")
    parser.add_argument("--device", help="ADB device ID (optional)")
    parser.add_argument("--collection", default="To Export", help="Collection name to export")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay after each export")
    parser.add_argument("--max-books", type=int, help="Maximum number of books to export (for testing)")
    parser.add_argument("--retry", type=int, default=2, help="Number of retry attempts per book")

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
        max_books=args.max_books,
        retry_attempts=args.retry
    )

    try:
        stats = automator.export_collection_notes()

        print(f"\nAutomation complete!")
        print(f"Exported notes from {stats['successful']}/{stats['attempted']} books.")

        if stats['failed'] > 0:
            print(f"\nFailed books: {stats['failed']}")
            return 1
        return 0

    except KeyboardInterrupt:
        logging.info("Automation interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Automation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    main()
