import os
import sys

def add_html_extension(directory):
  """Add a .html extension to any files in the specified directory that do not already have such an extension."""
  # Loop through all files in the directory
  for filename in os.listdir(directory):
    # Check if the file already has a .html extension
    if not filename.endswith('.html'):
      # Split the file into name and extension
      name, ext = os.path.splitext(filename)
      # Rename the file with a .html extension
      os.rename(os.path.join(directory, filename), f"{os.path.join(directory, name)}.html")
      print(f"Renamed {filename} to {name}.html")
    else:
      print(f"{filename} already has a .html extension")

# Set the default directory
DEFAULT_DIRECTORY = r'C:\OneDrive\exported notes modified'

# Check if a directory was provided as a command line argument
if len(sys.argv) > 1:
  directory = sys.argv[1]
else:
  directory = DEFAULT_DIRECTORY

# Confirm with the user that they want to add the .html extension to the files in the directory
confirmation = input(f"Add .html extension to files in {directory}? (y/n) ")

if confirmation.lower() == 'y':
  # Add the .html extension to any files in the directory that do not already have such an extension
  add_html_extension(directory)
  print("Done renaming files!")
else:
  print("Cancelled.")