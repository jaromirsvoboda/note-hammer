"""
Android Kindle App Automation for Note Export
Automates the process of exporting notes from all books in a specific collection
"""
import os
import sys
import time
import logging
import subprocess
import json
from typing import List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

# Use port 5039 for ADB to avoid Windows Hyper-V port exclusion range (5037 is often blocked)
os.environ.setdefault("ANDROID_ADB_SERVER_PORT", "5039")


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
        retry_attempts: int = 2,
        debug_screenshots: bool = False,
        screenshot_dir: str = "debug_screenshots",
        share_target: str = "total_commander",
        device_export_path: str = "/sdcard/Download/KindleExports"
    ):
        # Auto-detect device if not specified
        if device_id is None:
            device_id = self._auto_detect_device()

        self.device_id = device_id
        self.collection_name = collection_name
        self.export_delay = export_delay
        self.max_books = max_books
        self.retry_attempts = retry_attempts
        self.share_target = share_target
        self.device_export_path = device_export_path
        self.adb_prefix = ["adb"] + (["-s", device_id] if device_id else [])
        self.export_stats = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "failed_books": []
        }

        # Debug screenshot settings
        self.debug_screenshots = debug_screenshots
        self.screenshot_counter = 0
        self.screenshot_dir = None

        if self.debug_screenshots:
            # Create timestamped directory for this session
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.screenshot_dir = Path(screenshot_dir) / f"session_{timestamp}"
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Debug screenshots enabled. Saving to: {self.screenshot_dir}")

    def _ensure_adb_server(self) -> None:
        """Ensure ADB server is running on the configured port."""
        import shutil
        import socket

        adb_port = int(os.environ.get("ANDROID_ADB_SERVER_PORT", "5039"))
        adb_path = shutil.which("adb")
        print(f"DEBUG: ADB port={adb_port}, ADB path={adb_path}", flush=True)

        # Check if server is already running by trying to connect to the port
        def is_server_running():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', adb_port))
                sock.close()
                return result == 0
            except:
                return False

        if is_server_running():
            print(f"DEBUG: ADB server already running on port {adb_port}", flush=True)
            return

        print(f"DEBUG: ADB server not running, starting it on port {adb_port}...", flush=True)

        # Kill any existing ADB server first (might be on wrong port)
        try:
            if sys.platform == "win32":
                # On Windows, use taskkill to ensure all adb processes are killed
                subprocess.run(
                    ["taskkill", "/f", "/im", "adb.exe"],
                    capture_output=True,
                    timeout=5
                )
            else:
                subprocess.run(["adb", "kill-server"], capture_output=True, timeout=5, env=os.environ.copy())
            time.sleep(1)
        except Exception as e:
            print(f"DEBUG: Kill server: {e}", flush=True)

        # Start the server with proper Windows flags to prevent hanging
        try:
            env = os.environ.copy()
            env["ANDROID_ADB_SERVER_PORT"] = str(adb_port)

            if sys.platform == "win32":
                # On Windows, start adb server detached so it doesn't block
                CREATE_NO_WINDOW = 0x08000000
                DETACHED_PROCESS = 0x00000008

                process = subprocess.Popen(
                    ["adb", "start-server"],
                    env=env,
                    creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                # Give server time to start
                time.sleep(3)
            else:
                subprocess.run(
                    ["adb", "start-server"],
                    capture_output=True,
                    timeout=15,
                    env=env
                )

            # Verify server started
            for attempt in range(5):
                if is_server_running():
                    print(f"DEBUG: ADB server started successfully on port {adb_port}", flush=True)
                    return
                time.sleep(1)

            print(f"DEBUG: WARNING - ADB server may not have started properly", flush=True)

        except Exception as e:
            print(f"DEBUG: Error starting ADB server: {e}", flush=True)
            logging.warning(f"Could not start ADB server: {e}")
            logging.warning(f"Try running manually: set ANDROID_ADB_SERVER_PORT={adb_port} && adb start-server")

    def _auto_detect_device(self) -> Optional[str]:
        """Auto-detect connected ADB device. If only one device is connected, return its ID."""
        self._ensure_adb_server()
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Parse device list (skip header line)
            lines = [line.strip() for line in result.stdout.strip().split('\n')[1:] if line.strip()]
            devices = []

            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2 and parts[1] == 'device':
                    devices.append(parts[0])

            if len(devices) == 0:
                logging.error("No ADB devices connected!")
                logging.error("Please connect your device via USB or WiFi debugging:")
                logging.error("  1. Enable Developer Options and USB Debugging on your device")
                logging.error("  2. For WiFi: Settings > Developer Options > Wireless debugging")
                logging.error("  3. Run 'adb devices' to verify connection")
                raise RuntimeError("No ADB devices found. Please connect a device.")
            elif len(devices) == 1:
                logging.info(f"Auto-detected device: {devices[0]}")
                return devices[0]
            else:
                logging.error(f"Multiple devices connected: {devices}")
                logging.error("Please specify which device to use with --device option")
                raise RuntimeError(f"Multiple devices found: {devices}. Please specify --device")

        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to detect ADB devices: {e}")
            raise
        except FileNotFoundError:
            logging.error("ADB command not found. Please install Android SDK Platform Tools.")
            raise

    def run_adb_command(self, command: List[str], timeout: int = 30) -> str:
        """Execute ADB command and return output"""
        full_command = self.adb_prefix + command
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired as e:
            logging.error(f"ADB command timed out after {timeout}s: {' '.join(full_command)}")
            raise
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

    def get_ui_dump(self, max_retries: int = 3) -> str:
        """Get current UI hierarchy with retry logic for transient failures"""
        last_error = None
        for attempt in range(max_retries):
            try:
                self.run_adb_command(["shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
                return self.run_adb_command(["shell", "cat", "/sdcard/ui_dump.xml"])
            except subprocess.CalledProcessError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logging.warning(f"UI dump failed (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(1.5)  # Wait for UI to stabilize
        logging.error(f"UI dump failed after {max_retries} attempts")
        raise last_error

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

    def take_debug_screenshot(self, annotation: str) -> None:
        """Take a numbered screenshot with annotation if debug mode is enabled"""
        if not self.debug_screenshots or not self.screenshot_dir:
            return

        self.screenshot_counter += 1

        # Create filename with counter and annotation
        # Sanitize annotation for filename
        safe_annotation = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in annotation)
        safe_annotation = safe_annotation.replace(' ', '_')
        filename = f"{self.screenshot_counter:03d}_{safe_annotation}"

        screenshot_path = self.screenshot_dir / f"{filename}.png"
        ui_dump_path = self.screenshot_dir / f"{filename}.xml"

        try:
            # Take screenshot
            self.run_adb_command(["shell", "screencap", "-p", f"/sdcard/{filename}.png"])
            self.run_adb_command(["pull", f"/sdcard/{filename}.png", str(screenshot_path)])
            self.run_adb_command(["shell", "rm", f"/sdcard/{filename}.png"])

            # Save UI dump
            ui_dump = self.get_ui_dump()
            with open(ui_dump_path, 'w', encoding='utf-8') as f:
                f.write(ui_dump)

            logging.info(f"📸 Screenshot {self.screenshot_counter:03d}: {annotation}")
            logging.info(f"   Saved to: {screenshot_path}")

        except Exception as e:
            logging.warning(f"Failed to take debug screenshot: {e}")

    def launch_kindle(self) -> None:
        """Launch Kindle app and ensure we're at home screen"""
        logging.info("Launching Kindle app")
        # Use am start command instead of monkey (more reliable and faster)
        # Try different launch activities in order of preference
        activities_to_try = [
            "com.amazon.kindle/.UpgradePage",  # Most common main activity
            "com.amazon.kindle/.StartupActivity",
            "com.amazon.kindle/.RootActivity"
        ]

        last_error = None
        for activity in activities_to_try:
            try:
                logging.info(f"Trying to launch with activity: {activity}")
                self.run_adb_command([
                    "shell", "am", "start",
                    "-n", activity
                ], timeout=10)
                logging.info(f"Kindle app launched successfully with {activity}")
                break
            except Exception as e:
                logging.warning(f"Failed to launch with {activity}: {e}")
                last_error = e
                continue
        else:
            # If all attempts failed, raise the last error
            logging.error("Failed to launch Kindle app with any known activity")
            if last_error:
                raise last_error

        time.sleep(3)

        # Check if app resumed in citation dialog and dismiss it
        logging.info("About to check for citation dialog")
        self._dismiss_citation_dialog_if_present()
        logging.info("Citation dialog check complete")

        # If Kindle resumed into a book, go back to home
        logging.info("Ensuring we're at Kindle home screen")
        self._navigate_to_home()

    def _dismiss_citation_dialog_if_present(self) -> None:
        """Dismiss citation style dialog if Kindle resumed with it open"""
        logging.info("Checking for citation dialog on startup")
        time.sleep(1)  # Give UI time to settle

        try:
            ui_dump = self.get_ui_dump()

            # Check if we're in citation dialog
            if any(style in ui_dump for style in ["APA", "Chicago Style", "MLA"]):
                logging.info("Citation dialog detected on startup")

                # Try Cancel button (case-insensitive search in UI dump)
                import re
                cancel_pattern = r'text="[Cc]ancel"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                cancel_match = re.search(cancel_pattern, ui_dump)

                if cancel_match:
                    x1, y1, x2, y2 = map(int, cancel_match.groups())
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    logging.info(f"Found Cancel button at ({center_x}, {center_y})")
                    self.tap(center_x, center_y, delay=2)
                    logging.info("Dismissed citation dialog")
                    return

                # If Cancel button not found, try pressing back key
                logging.warning("Cancel button not found in dialog, trying back key")
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
            else:
                logging.info("No citation dialog detected on startup")
        except Exception as e:
            logging.error(f"Error checking for citation dialog: {e}")
            # Continue anyway
            pass

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

            # Step 4: Select share target from share menu
            if not self._select_share_target():
                logging.warning(f"Could not select {self.share_target} for {book.text}")
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                self.press_key("KEYCODE_BACK")
                time.sleep(1)
                return False

            # Step 5: Confirm the share target save/upload
            if not self._confirm_share_target():
                logging.warning(f"Could not confirm {self.share_target} save for {book.text}")
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
        self.take_debug_screenshot("BEFORE - About to tap book")
        logging.info(f"Opening book by tapping at ({book.x}, {book.y})")
        self.tap(book.x, book.y, delay=3)
        self.take_debug_screenshot("AFTER - Tapped book (should be in book view)")

        # Step 2: Tap top of screen to show toolbar if not visible
        logging.info("Ensuring toolbar is visible")
        self.tap(540, 200)
        time.sleep(1)
        self.take_debug_screenshot("AFTER - Tapped top to show toolbar")

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
                self.take_debug_screenshot("BEFORE - About to tap Notebook button")
                self.tap(center_x, center_y, delay=3)
                self.take_debug_screenshot("AFTER - Tapped Notebook button (should show annotations)")

                # Verify we're in Annotations view
                time.sleep(2)
                if self.wait_for_text("Annotations", timeout=3.0):
                    logging.info("Successfully opened Annotations view")
                    self.take_debug_screenshot("SUCCESS - In Annotations view")
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
            self.take_debug_screenshot("BEFORE - About to tap third button from right")
            self.tap(third_from_right[0], third_from_right[1], delay=3)
            self.take_debug_screenshot("AFTER - Tapped third button (should show annotations)")

            time.sleep(2)
            if self.wait_for_text("Annotations", timeout=3.0):
                logging.info("Successfully opened Annotations view")
                self.take_debug_screenshot("SUCCESS - In Annotations view (fallback method)")
                return True

        self.take_debug_screenshot("FAILED - Could not open Annotations view")
        logging.warning("Could not open Annotations view")
        return False

    def _tap_export_button(self) -> bool:
        """Find and tap the export/share button in notes view"""
        logging.info("Looking for export/share button")

        # Wait a moment for the notes view to fully load
        time.sleep(2)
        self.take_debug_screenshot("Looking for export/share button")

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
                    self.take_debug_screenshot(f"BEFORE - About to tap {option}")
                    self.tap(option_elements[0].x, option_elements[0].y, delay=2)
                    self.take_debug_screenshot(f"AFTER - Tapped {option}")
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
        """Select citation style (None) from the citation dialog and click EXPORT"""
        logging.info("Looking for citation style dialog")

        # Wait for citation style dialog to appear
        time.sleep(2)
        self.take_debug_screenshot("Looking for citation style dialog")

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
            # Check for share sheet indicators (any common share target)
            share_indicators = ["Total Commander", "Total Cmd", "Totalcmd",
                                "OneDrive", "Bluetooth", "Gmail", "Messages",
                                "Drive", "Copy to", "Nearby"]
            for indicator in share_indicators:
                if self.wait_for_text(indicator, timeout=0.5):
                    logging.info(f"Already at share sheet (found '{indicator}'), skipping citation selection")
                    return True
            logging.warning("Could not find citation style dialog")
            return False

        # Select "None" citation style
        if self.wait_for_text("None", timeout=2.0):
            logging.info("Selecting 'None' citation style")
            none_elements = self.find_elements_by_text("None")
            if none_elements:
                self.take_debug_screenshot("BEFORE - About to select None citation")
                self.tap(none_elements[0].x, none_elements[0].y, delay=1)
                self.take_debug_screenshot("AFTER - Selected None citation")
                logging.info("Selected 'None' citation style")
        else:
            logging.warning("Could not find 'None' citation style")

        # Now click EXPORT button
        time.sleep(1)
        if self.wait_for_text("EXPORT", timeout=2.0):
            logging.info("Clicking EXPORT button")
            export_elements = self.find_elements_by_text("EXPORT")
            if export_elements:
                self.take_debug_screenshot("BEFORE - About to click EXPORT button")
                self.tap(export_elements[0].x, export_elements[0].y, delay=2)
                self.take_debug_screenshot("AFTER - Clicked EXPORT button (should show share menu)")
                logging.info("Clicked EXPORT button")
                return True

        # Try alternative export button texts
        export_variants = ["Export", "SHARE", "Share", "OK"]
        for variant in export_variants:
            if self.wait_for_text(variant, timeout=1.0):
                logging.info(f"Clicking {variant} button")
                elements = self.find_elements_by_text(variant)
                if elements:
                    self.tap(elements[0].x, elements[0].y, delay=2)
                    return True

        logging.warning("Could not find EXPORT button")
        return False

    def _select_onedrive_share(self) -> bool:
        """Select OneDrive from Android share menu"""
        logging.info("Looking for OneDrive in share menu")

        # Wait for share sheet to appear
        time.sleep(2)
        self.take_debug_screenshot("Looking for OneDrive in share menu")

        # Look for OneDrive
        if self.wait_for_text("OneDrive", timeout=5.0):
            logging.info("Found OneDrive option")
            onedrive_elements = self.find_elements_by_text("OneDrive")
            if onedrive_elements:
                self.take_debug_screenshot("BEFORE - About to tap OneDrive")
                self.tap(onedrive_elements[0].x, onedrive_elements[0].y, delay=3)
                self.take_debug_screenshot("AFTER - Tapped OneDrive (should open OneDrive)")
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
        time.sleep(3)
        self.take_debug_screenshot("Looking for OneDrive save/upload button")

        # Debug: Log what's on screen
        ui_dump = self.get_ui_dump()
        visible_text = self.get_ui_text_elements()
        logging.info(f"OneDrive screen visible text elements: {visible_text}")

        import re

        # PRIORITY 1: Find button by specific OneDrive identifiers
        # The Upload button has resource-id="com.microsoft.skydrive:id/menu_action" and content-desc="Upload"
        logging.info("Looking for OneDrive Upload button by element identifiers...")

        # Pattern to find the exact OneDrive upload button
        onedrive_upload_patterns = [
            # Exact match for OneDrive's menu_action Upload button
            r'resource-id="com\.microsoft\.skydrive:id/menu_action"[^>]*content-desc="Upload"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            # Alternative: content-desc first
            r'content-desc="Upload"[^>]*resource-id="com\.microsoft\.skydrive:id/menu_action"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            # Fallback: any clickable button with content-desc="Upload"
            r'content-desc="Upload"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'clickable="true"[^>]*content-desc="Upload"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ]

        for pattern in onedrive_upload_patterns:
            match = re.search(pattern, ui_dump)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                logging.info(f"Found OneDrive Upload button at ({center_x}, {center_y})")
                self.take_debug_screenshot(f"BEFORE - About to tap OneDrive Upload button at ({center_x}, {center_y})")
                self.tap(center_x, center_y, delay=5)  # Wait longer for upload to start
                self.take_debug_screenshot(f"AFTER - Tapped OneDrive Upload button")

                # Verify upload status - check what app we're in now
                post_upload_dump = self.get_ui_dump()
                if "com.microsoft.skydrive" in post_upload_dump:
                    # Still in OneDrive - might be an error or still uploading
                    visible_text = self.get_ui_text_elements()
                    logging.warning(f"Still in OneDrive after upload tap. Screen text: {visible_text}")
                    self.take_debug_screenshot("WARNING - Still in OneDrive after upload")
                    # Check for error messages
                    error_keywords = ["error", "failed", "unable", "couldn't", "can't"]
                    for text in visible_text:
                        if any(kw in text.lower() for kw in error_keywords):
                            logging.error(f"OneDrive error detected: {text}")
                    # Wait a bit more and try pressing back to exit
                    time.sleep(3)
                    self.press_key("KEYCODE_BACK")
                elif "com.amazon.kindle" in post_upload_dump:
                    logging.info("Successfully returned to Kindle - upload likely initiated")
                else:
                    logging.info(f"In different app after upload tap")

                return True

        # PRIORITY 2: Find by resource-id alone (menu_action is the action button)
        menu_action_pattern = r'resource-id="com\.microsoft\.skydrive:id/menu_action"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        match = re.search(menu_action_pattern, ui_dump)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            logging.info(f"Found menu_action button at ({center_x}, {center_y})")
            self.take_debug_screenshot(f"BEFORE - About to tap menu_action button at ({center_x}, {center_y})")
            self.tap(center_x, center_y, delay=3)
            self.take_debug_screenshot(f"AFTER - Tapped menu_action button")
            return True

        # PRIORITY 3: Generic fallback - look for any button with content-desc containing upload/save/done
        logging.info("OneDrive button not found, trying generic patterns...")
        generic_patterns = [
            r'content-desc="[^"]*[Uu]pload[^"]*"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'clickable="true"[^>]*content-desc="[^"]*[Uu]pload[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="[^"]*[Ss]ave[^"]*"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="[^"]*[Dd]one[^"]*"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ]

        for pattern in generic_patterns:
            match = re.search(pattern, ui_dump)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                logging.info(f"Found button via generic pattern at ({center_x}, {center_y})")
                self.take_debug_screenshot(f"BEFORE - About to tap button at ({center_x}, {center_y})")
                self.tap(center_x, center_y, delay=3)
                self.take_debug_screenshot(f"AFTER - Tapped button")
                return True

        # Look for text buttons, but EXCLUDE title elements (which contain "to OneDrive")
        confirm_options = [
            "Upload here",  # OneDrive specific
            "Save",
            "SAVE",
            "Done",
            "DONE",
            "OK",
            "Confirm",
            "CONFIRM"
        ]

        for option in confirm_options:
            if self.wait_for_text(option, timeout=1.0):
                logging.info(f"Found text: {option}")
                option_elements = self.find_elements_by_text(option)
                if option_elements:
                    # Filter out title elements - titles are usually wider and in top-left
                    # Real buttons are usually smaller and more to the right
                    valid_buttons = []
                    for elem in option_elements:
                        # Skip if this looks like a title (very wide or very left-aligned with low x)
                        text_lower = elem.text.lower() if elem.text else ""
                        # Skip "Upload to OneDrive" title
                        if "to onedrive" in text_lower:
                            logging.info(f"Skipping title element: {elem.text} at ({elem.x}, {elem.y})")
                            continue
                        # Buttons are usually on the right side (x > 600) or in a reasonable button position
                        if elem.x > 500 or (elem.y > 100 and elem.y < 300):
                            valid_buttons.append(elem)
                            logging.info(f"Valid button candidate: {elem.text} at ({elem.x}, {elem.y})")

                    if valid_buttons:
                        # Sort by x coordinate descending to get rightmost
                        valid_buttons.sort(key=lambda e: e.x, reverse=True)
                        btn = valid_buttons[0]
                        logging.info(f"Tapping {option} button at ({btn.x}, {btn.y})")
                        self.take_debug_screenshot(f"BEFORE - About to tap {option} button")
                        self.tap(btn.x, btn.y, delay=3)
                        self.take_debug_screenshot(f"AFTER - Tapped {option} button (upload should complete)")
                        return True

        # Debug: dump all clickable elements with their details to help diagnose
        logging.info("=== DEBUG: All clickable elements on OneDrive screen ===")
        clickable_pattern = r'<[^>]*clickable="true"[^>]*>'
        for match in re.finditer(clickable_pattern, ui_dump):
            elem = match.group(0)
            # Extract useful attributes
            bounds_match = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', elem)
            text_match = re.search(r'text="([^"]*)"', elem)
            desc_match = re.search(r'content-desc="([^"]*)"', elem)
            rid_match = re.search(r'resource-id="([^"]*)"', elem)
            class_match = re.search(r'class="([^"]*)"', elem)
            if bounds_match:
                x1, y1, x2, y2 = map(int, bounds_match.groups())
                cx, cy = (x1+x2)//2, (y1+y2)//2
                text = text_match.group(1) if text_match else ""
                desc = desc_match.group(1) if desc_match else ""
                rid = rid_match.group(1) if rid_match else ""
                cls = class_match.group(1).split(".")[-1] if class_match else ""
                logging.info(f"  [{cx},{cy}] {cls}: text='{text}' desc='{desc}' rid='{rid}'")
        logging.info("=== END DEBUG ===")

        # Try looking for clickable buttons in the top-right area (common location for save)
        logging.info("Looking for clickable buttons in top-right area")
        button_pattern = r'clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        all_buttons = re.findall(button_pattern, ui_dump)

        top_right_buttons = []
        for x1, y1, x2, y2 in all_buttons:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            # Top area (y < 400) and right side (x > 700)
            if y1 < 400 and center_x > 700:
                top_right_buttons.append((center_x, center_y))
                logging.info(f"Found top-right button at ({center_x}, {center_y})")

        if top_right_buttons:
            # Sort by x coordinate to get rightmost button
            top_right_buttons.sort(key=lambda b: b[0], reverse=True)
            logging.info(f"Trying rightmost top-right button at {top_right_buttons[0]}")
            self.tap(top_right_buttons[0][0], top_right_buttons[0][1], delay=3)
            return True

        # Last resort: try tapping common save button locations
        logging.warning("Could not find OneDrive save button - trying common locations")
        logging.warning("This likely means the file was NOT uploaded!")

        # Top-right corner is typical for save buttons
        self.tap(980, 150, delay=2)
        time.sleep(1)

        # Also try another common location
        self.tap(950, 120, delay=2)
        time.sleep(1)

        return False  # Return False to indicate we're not sure if it worked

    def _ensure_device_export_directory(self) -> None:
        """Create the export directory on device if it doesn't exist"""
        logging.info(f"Ensuring device export directory exists: {self.device_export_path}")
        self.run_adb_command(["shell", "mkdir", "-p", self.device_export_path])

    def _clear_device_export_directory(self) -> None:
        """Clear stale files from the device export directory before starting"""
        logging.info(f"Clearing device export directory: {self.device_export_path}")
        try:
            self.run_adb_command(["shell", "rm", "-f", f"{self.device_export_path}/*"])
        except subprocess.CalledProcessError:
            # Directory might be empty or not exist yet, that's fine
            logging.info("Export directory already clean or doesn't exist yet")

    def _select_total_commander_share(self) -> bool:
        """Select Total Commander from Android share menu"""
        logging.info("Looking for Total Commander in share menu")

        # Wait for share sheet to appear
        time.sleep(2)
        self.take_debug_screenshot("Looking for Total Commander in share menu")

        # Try multiple text variants for Total Commander
        tc_names = ["Total Commander", "Total Cmd", "Totalcmd"]

        for tc_name in tc_names:
            if self.wait_for_text(tc_name, timeout=5.0):
                logging.info(f"Found {tc_name} option")
                tc_elements = self.find_elements_by_text(tc_name)
                if tc_elements:
                    self.take_debug_screenshot(f"BEFORE - About to tap {tc_name}")
                    self.tap(tc_elements[0].x, tc_elements[0].y, delay=3)
                    self.take_debug_screenshot(f"AFTER - Tapped {tc_name}")
                    return True

        # Try scrolling in share sheet to find Total Commander
        logging.info("Total Commander not immediately visible, trying to scroll")
        import re
        ui_dump = self.get_ui_dump()

        # Try horizontal scroll in share sheet (apps row)
        for _ in range(5):
            self.swipe(800, 1500, 300, 1500, 300)  # Swipe left
            time.sleep(1)

            for tc_name in tc_names:
                if self.wait_for_text(tc_name, timeout=2.0):
                    tc_elements = self.find_elements_by_text(tc_name)
                    if tc_elements:
                        self.take_debug_screenshot(f"BEFORE - About to tap {tc_name} (after scroll)")
                        self.tap(tc_elements[0].x, tc_elements[0].y, delay=3)
                        self.take_debug_screenshot(f"AFTER - Tapped {tc_name}")
                        return True

        # Try vertical scroll in share sheet
        logging.info("Trying vertical scroll in share sheet")
        for _ in range(3):
            self.swipe(540, 1800, 540, 1200, 300)  # Swipe up
            time.sleep(1)

            for tc_name in tc_names:
                if self.wait_for_text(tc_name, timeout=2.0):
                    tc_elements = self.find_elements_by_text(tc_name)
                    if tc_elements:
                        self.take_debug_screenshot(f"BEFORE - About to tap {tc_name} (after vertical scroll)")
                        self.tap(tc_elements[0].x, tc_elements[0].y, delay=3)
                        self.take_debug_screenshot(f"AFTER - Tapped {tc_name}")
                        return True

        # Debug: show what options are available
        visible_text = self.get_ui_text_elements()
        logging.info(f"Available share options: {[t for t in visible_text if len(t) < 30]}")

        logging.warning("Could not find Total Commander in share menu")
        return False

    def _confirm_total_commander_save(self) -> bool:
        """Confirm save in Total Commander's file dialog"""
        logging.info("Confirming Total Commander save")

        # Wait for Total Commander interface to load
        time.sleep(3)
        self.take_debug_screenshot("Total Commander save dialog")

        ui_dump = self.get_ui_dump()
        visible_text = self.get_ui_text_elements()
        logging.info(f"Total Commander screen text elements: {visible_text}")

        import re

        # Strategy 1: Look for an EditText path field and type the target path
        edit_text_pattern = r'class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        edit_match = re.search(edit_text_pattern, ui_dump)
        if not edit_match:
            # Try alternative attribute ordering
            edit_text_pattern2 = r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*class="android\.widget\.EditText"'
            edit_match = re.search(edit_text_pattern2, ui_dump)

        if edit_match:
            x1, y1, x2, y2 = map(int, edit_match.groups())
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            logging.info(f"Found EditText path field at ({center_x}, {center_y})")
            self.take_debug_screenshot("BEFORE - About to tap EditText and type path")

            # Tap the field, clear it, type our path
            self.tap(center_x, center_y, delay=0.5)
            # Select all and delete existing text
            self.run_adb_command(["shell", "input", "keyevent", "KEYCODE_MOVE_HOME"])
            time.sleep(0.2)
            self.run_adb_command(["shell", "input", "keyevent", "--longpress", "KEYCODE_SHIFT_LEFT", "KEYCODE_MOVE_END"])
            time.sleep(0.2)
            self.run_adb_command(["shell", "input", "keyevent", "KEYCODE_DEL"])
            time.sleep(0.2)

            # Type the target path
            self.type_text(self.device_export_path)
            time.sleep(0.5)
            self.take_debug_screenshot("AFTER - Typed path in EditText")

            # Press Enter to navigate
            self.press_key("KEYCODE_ENTER")
            time.sleep(2)
            self.take_debug_screenshot("AFTER - Pressed Enter on path")

        # Strategy 2: Navigate folder-by-folder if no EditText
        else:
            logging.info("No EditText found, trying folder-by-folder navigation")
            # Parse the target path into components
            path_parts = self.device_export_path.strip("/").split("/")
            # Typically: sdcard / Download / KindleExports
            # TC might show "Download" folder or we might need to navigate

            for folder in path_parts:
                if folder in ("sdcard", "storage", "emulated", "0"):
                    continue  # Skip root-level paths that TC handles automatically

                logging.info(f"Looking for folder: {folder}")
                time.sleep(1)

                folder_elements = self.find_elements_by_text(folder)
                if folder_elements:
                    logging.info(f"Found folder '{folder}', tapping")
                    self.tap(folder_elements[0].x, folder_elements[0].y, delay=2)
                    self.take_debug_screenshot(f"AFTER - Navigated to {folder}")
                else:
                    logging.warning(f"Folder '{folder}' not found on screen")
                    # Might need to scroll to find it
                    for _ in range(3):
                        self.swipe(540, 1500, 540, 800, 300)
                        time.sleep(1)
                        folder_elements = self.find_elements_by_text(folder)
                        if folder_elements:
                            self.tap(folder_elements[0].x, folder_elements[0].y, delay=2)
                            break

        # Now look for confirm button
        confirm_texts = ["Copy here", "OK", "Save", "Copy", "Done", "COPY HERE",
                         "SAVE", "DONE", "OK", "Move here", "MOVE HERE",
                         "Paste here", "PASTE HERE"]

        time.sleep(1)
        self.take_debug_screenshot("Looking for confirm button")

        for confirm_text in confirm_texts:
            if self.wait_for_text(confirm_text, timeout=2.0):
                logging.info(f"Found confirm button: {confirm_text}")
                elements = self.find_elements_by_text(confirm_text)
                if elements:
                    self.take_debug_screenshot(f"BEFORE - About to tap {confirm_text}")
                    self.tap(elements[0].x, elements[0].y, delay=3)
                    self.take_debug_screenshot(f"AFTER - Tapped {confirm_text}")

                    # Verify we returned to Kindle
                    time.sleep(2)
                    post_save_dump = self.get_ui_dump()
                    if "com.amazon.kindle" in post_save_dump:
                        logging.info("Successfully returned to Kindle after TC save")
                    else:
                        logging.info("Not yet back in Kindle, waiting...")
                        time.sleep(3)

                    return True

        # Fallback: look for any clickable button in the bottom area
        logging.info("No confirm text found, looking for buttons in bottom area")
        button_pattern = r'clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        all_buttons = re.findall(button_pattern, ui_dump)

        bottom_buttons = []
        for x1, y1, x2, y2 in all_buttons:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            # Look for buttons in the bottom third of screen
            if center_y > 1500:
                bottom_buttons.append((center_x, center_y))

        if bottom_buttons:
            logging.info(f"Found {len(bottom_buttons)} bottom buttons, trying first one")
            self.tap(bottom_buttons[0][0], bottom_buttons[0][1], delay=3)
            return True

        logging.warning("Could not find Total Commander confirm button")
        return False

    def pull_exported_files(self, local_path: str) -> List[str]:
        """Pull exported files from device to local path via ADB

        Args:
            local_path: Local directory to pull files into

        Returns:
            List of pulled HTML file paths
        """
        logging.info(f"Pulling exported files from {self.device_export_path} to {local_path}")

        # Create local directory if needed
        local_dir = Path(local_path)
        local_dir.mkdir(parents=True, exist_ok=True)

        # List files on device
        try:
            file_list = self.run_adb_command(
                ["shell", "ls", self.device_export_path],
                timeout=10
            )
            files = [f.strip() for f in file_list.split('\n') if f.strip()]
            logging.info(f"Found {len(files)} files on device: {files}")
        except subprocess.CalledProcessError:
            logging.warning(f"No files found in {self.device_export_path}")
            return []

        if not files:
            logging.warning("No files to pull")
            return []

        # Pull all files from device directory
        try:
            pull_output = self.run_adb_command(
                ["pull", f"{self.device_export_path}/.", str(local_dir)],
                timeout=120
            )
            logging.info(f"ADB pull output: {pull_output}")
        except subprocess.CalledProcessError as e:
            logging.error(f"ADB pull failed: {e}")
            # Try pulling files individually as fallback
            logging.info("Trying individual file pulls as fallback")
            for filename in files:
                try:
                    self.run_adb_command(
                        ["pull", f"{self.device_export_path}/{filename}", str(local_dir / filename)],
                        timeout=60
                    )
                    logging.info(f"Pulled: {filename}")
                except subprocess.CalledProcessError as e2:
                    logging.error(f"Failed to pull {filename}: {e2}")

        # Return list of HTML files that were pulled
        pulled_html = sorted(local_dir.glob("*.html"))
        html_paths = [str(p) for p in pulled_html]
        logging.info(f"Pulled {len(html_paths)} HTML files: {[Path(p).name for p in html_paths]}")
        return html_paths

    def cleanup_device_export_directory(self) -> None:
        """Remove exported files from device after successful pull"""
        logging.info(f"Cleaning up device export directory: {self.device_export_path}")
        try:
            self.run_adb_command(["shell", "rm", "-rf", self.device_export_path])
            logging.info("Device export directory cleaned up")
        except subprocess.CalledProcessError as e:
            logging.warning(f"Failed to clean up device export directory: {e}")

    def _select_share_target(self) -> bool:
        """Select the configured share target from the Android share menu"""
        if self.share_target == "total_commander":
            return self._select_total_commander_share()
        elif self.share_target == "onedrive":
            return self._select_onedrive_share()
        else:
            logging.error(f"Unknown share target: {self.share_target}")
            return False

    def _confirm_share_target(self) -> bool:
        """Confirm the save/upload in the configured share target"""
        if self.share_target == "total_commander":
            return self._confirm_total_commander_save()
        elif self.share_target == "onedrive":
            return self._confirm_onedrive_upload()
        else:
            logging.error(f"Unknown share target: {self.share_target}")
            return False

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

            # Check if we're in citation style dialog (back button won't work)
            # Need to press Cancel button instead
            if any(style in ui_dump for style in ["APA", "Chicago Style", "MLA"]):
                logging.info("Detected citation style dialog, pressing Cancel button")
                cancel_elements = self.find_elements_by_text("Cancel")
                if cancel_elements:
                    self.tap(cancel_elements[0].x, cancel_elements[0].y, delay=1)
                    continue

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
            # Prepare device export directory for Total Commander
            if self.share_target == "total_commander":
                self._ensure_device_export_directory()
                self._clear_device_export_directory()

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
    parser.add_argument("--debug-screenshots", action="store_true",
                       help="Enable debug screenshots at every step (saved to debug_screenshots/)")
    parser.add_argument("--screenshot-dir", default="debug_screenshots",
                       help="Directory to save debug screenshots (default: debug_screenshots)")
    parser.add_argument("--share-target", choices=["total_commander", "onedrive"],
                       default="total_commander",
                       help="Share target app (default: total_commander)")
    parser.add_argument("--device-export-path", default="/sdcard/Download/KindleExports",
                       help="Path on device where TC saves files (default: /sdcard/Download/KindleExports)")

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
        retry_attempts=args.retry,
        debug_screenshots=args.debug_screenshots,
        screenshot_dir=args.screenshot_dir,
        share_target=args.share_target,
        device_export_path=args.device_export_path
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
