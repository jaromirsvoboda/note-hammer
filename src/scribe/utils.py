import shutil
import time
import os

def create_timestamped_backup(folder_path: str, backup_path: str) -> None:
    # Get the current timestamp in a formatted string
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

    # Create the backup folder if it doesn't exist
    if not os.path.exists(backup_path):
        os.makedirs(backup_path)

    # Create the path for the timestamped backup folder
    timestamped_backup_folder = os.path.join(backup_path, timestamp)

    # Copy the contents of the folder to the timestamped backup folder
    shutil.copytree(folder_path, timestamped_backup_folder)