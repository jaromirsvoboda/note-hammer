import uiautomator2 as u2
import json
import time
from datetime import datetime
from pathlib import Path

class KindleUIInspector:
    def __init__(self):
        self.device = u2.connect()
        self.output_dir = Path("ui_dumps")
        self.output_dir.mkdir(exist_ok=True)

    def dump_current_ui(self, description=""):
        """Dump the current UI state with both XML and screenshot."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{timestamp}_{description}".replace(" ", "_")
        
        # Take screenshot
        screenshot_path = self.output_dir / f"{base_name}.png"
        self.device.screenshot(str(screenshot_path))
        
        # Dump UI hierarchy
        xml_path = self.output_dir / f"{base_name}.xml"
        
        # Get UI hierarchy
        xml_content = self.device.dump_hierarchy()
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
            
        # Parse and save UI elements in a more readable format
        json_path = self.output_dir / f"{base_name}_elements.json"
        elements = self._get_clickable_elements()
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(elements, f, indent=2)
            
        print("\nUI state dumped to:")
        print(f"Screenshot: {screenshot_path}")
        print(f"XML Hierarchy: {xml_path}")
        print(f"Elements JSON: {json_path}")

    def _get_clickable_elements(self):
        """Get all clickable elements and their properties."""
        elements = []
        xml_content = self.device.dump_hierarchy()
        
        # Parse the hierarchy to find clickable elements
        for line in xml_content.split('\n'):
            if 'clickable="true"' in line:
                element = {}
                # Extract text
                if 'text="' in line:
                    element['text'] = line.split('text="')[1].split('"')[0]
                else:
                    element['text'] = ""
                    
                # Extract resource ID
                if 'resource-id="' in line:
                    element['resourceId'] = line.split('resource-id="')[1].split('"')[0]
                else:
                    element['resourceId'] = ""
                    
                # Extract class name
                if 'class="' in line:
                    element['className'] = line.split('class="')[1].split('"')[0]
                else:
                    element['className'] = ""
                    
                # Extract content description
                if 'content-desc="' in line:
                    element['description'] = line.split('content-desc="')[1].split('"')[0]
                else:
                    element['description'] = ""
                    
                # Extract bounds
                if 'bounds="' in line:
                    element['bounds'] = line.split('bounds="')[1].split('"')[0]
                else:
                    element['bounds'] = ""
                
                elements.append(element)
        
        return elements

    def _find_elements(self, search_text):
        """Find and print details of UI elements containing the search text."""
        print(f"\nSearching for elements containing: {search_text}")
        print("-" * 50)
        
        search_text = search_text.lower()
        found_elements = []
        
        # Get all elements
        xml_content = self.device.dump_hierarchy()
        
        # Search through the hierarchy
        for line in xml_content.split('\n'):
            element_info = {}
            
            # Check text attribute
            if 'text="' in line:
                text = line.split('text="')[1].split('"')[0]
                if search_text in text.lower():
                    element_info['text'] = text
                    
                    # Get additional attributes if we found matching text
                    if 'resource-id="' in line:
                        element_info['resourceId'] = line.split('resource-id="')[1].split('"')[0]
                    if 'class="' in line:
                        element_info['className'] = line.split('class="')[1].split('"')[0]
                    if 'content-desc="' in line:
                        element_info['description'] = line.split('content-desc="')[1].split('"')[0]
                    if 'clickable="' in line:
                        element_info['clickable'] = line.split('clickable="')[1].split('"')[0] == 'true'
                    if 'bounds="' in line:
                        element_info['bounds'] = line.split('bounds="')[1].split('"')[0]
                        
                    found_elements.append(element_info)
            
            # Check content-desc attribute
            elif 'content-desc="' in line:
                desc = line.split('content-desc="')[1].split('"')[0]
                if search_text in desc.lower():
                    element_info['description'] = desc
                    
                    # Get additional attributes
                    if 'resource-id="' in line:
                        element_info['resourceId'] = line.split('resource-id="')[1].split('"')[0]
                    if 'class="' in line:
                        element_info['className'] = line.split('class="')[1].split('"')[0]
                    if 'text="' in line:
                        element_info['text'] = line.split('text="')[1].split('"')[0]
                    if 'clickable="' in line:
                        element_info['clickable'] = line.split('clickable="')[1].split('"')[0] == 'true'
                    if 'bounds="' in line:
                        element_info['bounds'] = line.split('bounds="')[1].split('"')[0]
                        
                    found_elements.append(element_info)
        
        if found_elements:
            print("\nFound elements:")
            for i, elem in enumerate(found_elements, 1):
                print(f"\nElement {i}:")
                if 'text' in elem and elem['text']:
                    print(f"Text: {elem['text']}")
                if 'description' in elem and elem['description']:
                    print(f"Description: {elem['description']}")
                if 'resourceId' in elem and elem['resourceId']:
                    print(f"Resource ID: {elem['resourceId']}")
                if 'className' in elem and elem['className']:
                    print(f"Class: {elem['className']}")
                if 'clickable' in elem:
                    print(f"Clickable: {elem['clickable']}")
                if 'bounds' in elem and elem['bounds']:
                    print(f"Bounds: {elem['bounds']}")
                print("-" * 30)
        else:
            print("\nNo elements found matching the search text.")
        
        return found_elements

    def interactive_inspection(self):
        """Interactive UI inspection tool."""
        print("\nKindle UI Inspector")
        print("=" * 50)
        print("\nCommands:")
        print("- dump: Dump current UI state")
        print("- click <text>: Click element with text")
        print("- find <text>: Find elements containing text")
        print("- back: Press back button")
        print("- refresh: Refresh UI hierarchy")
        print("- quit: Exit inspector")
        
        while True:
            command = input("\nEnter command: ").strip()
            
            if command == "quit":
                break
            elif command == "dump":
                description = input("Enter description for this dump: ")
                self.dump_current_ui(description)
            elif command.startswith("click "):
                text = command[6:]
                try:
                    self.device(text=text).click()
                    print(f"Clicked element with text: {text}")
                    time.sleep(1)  # Wait for UI to update
                except Exception as e:
                    print(f"Failed to click: {e}")
            elif command.startswith("find "):
                text = command[5:]
                self._find_elements(text)
            elif command == "back":
                self.device.press("back")
                print("Pressed back button")
                time.sleep(1)
            elif command == "refresh":
                print("Refreshing UI hierarchy...")
                self.dump_current_ui("refresh")
            else:
                print("Unknown command")

def main():
    inspector = KindleUIInspector()
    
    print("\nStarting Kindle UI Inspector...")
    print("First, let's dump the current UI state.")
    inspector.dump_current_ui("initial_state")
    
    print("\nWould you like to:")
    print("1. Start interactive inspection")
    print("2. Just dump current UI state")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ")
    
    if choice == "1":
        inspector.interactive_inspection()
    elif choice == "2":
        description = input("Enter description for this UI state: ")
        inspector.dump_current_ui(description)

if __name__ == "__main__":
    main()