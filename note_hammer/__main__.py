from importlib.resources import path
import logging
import sys
import time
import click

from pathlib import Path

from note_hammer.note_hammer import NoteHammer
from note_hammer.android_automation import AndroidKindleAutomator


timestamp = time.strftime("%Y-%m-%d_%H-%M-%S_%p")
logging.basicConfig(
    filename=fr"{timestamp}.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.DEBUG
)
logging.getLogger().addHandler(logging.StreamHandler())
logging.info(f"Starting NoteHammer at {timestamp}")

@click.group()
def cli():
    pass


@cli.command(name="extract_kindle")
@click.option('-i', '--input_path', default=".", help='Path to the folder containing kindle notes (in .html format, can be nested in sub-folders) or to a single .html file.')
@click.option('-o', '--output_path', default=r".\export", help='Path to the folder where the extracted notes will be saved (in .md format).')
@click.option('-b', '--backup_path', default=r".\backup", help='Path to the folder where the Kindle htmls will be backed up to before extraction process. Empty string disables backup.')
@click.option('-dt', '--default-tags', multiple=True, help='Tags to be added to all the notes. This option can be used multiple times to add multiple tags.')
@click.option('-o', '--overwrite-older-notes', is_flag=True, help='Include this flag for overwriting older notes with the same name in the output path.')
@click.option('-sc', '--skip-confirmation', is_flag=True, help='Confirm before processing the notes.')
def extract_kindle(input_path: str, output_path: str, backup_path: str, default_tags: list[str], overwrite_older_notes: bool, skip_confirmation: bool):
    if not skip_confirmation:
        click.confirm(f'Are you sure you want to process the notes in {input_path}?', abort=True)

    note_hammer = NoteHammer(
        input_path=input_path,
        output_path=output_path,
        backup_path=backup_path,
        default_tags=default_tags,
        overwrite_older_notes=overwrite_older_notes,
        skip_confirmation=skip_confirmation
    )

    note_hammer.process_kindle_notes()


@cli.command(name="automate_android")
@click.option('--device', help='ADB device ID (optional if only one device connected)')
@click.option('--collection', default='To Export', help='Name of the Kindle collection to export')
@click.option('--export-delay', default=3.0, type=float, help='Delay in seconds after each export operation')
@click.option('--max-books', type=int, help='Maximum number of books to export (for testing)')
@click.option('--retry', default=2, type=int, help='Number of retry attempts per book')
@click.option('--onedrive-path', help='Path to OneDrive folder where exported files are saved')
@click.option('--output-path', default=r".\export", help='Path where final markdown notes will be saved')
@click.option('--backup-path', default=r".\backup", help='Path for backing up original files')
@click.option('-dt', '--default-tags', multiple=True, help='Tags to add to all exported notes')
@click.option('--skip-confirmation', is_flag=True, help='Skip confirmation prompts')
def automate_android(device, collection, export_delay, max_books, retry, onedrive_path, output_path, backup_path, default_tags, skip_confirmation):
    """Automate complete note extraction from Android Kindle app collection"""

    if not skip_confirmation:
        click.confirm(f'This will automate your Android device to export notes from "{collection}" collection. Continue?', abort=True)

    # Step 1: Automate Android app to export notes
    click.echo(f"Starting Android automation for collection: {collection}")
    automator = AndroidKindleAutomator(
        device_id=device,
        collection_name=collection,
        export_delay=export_delay,
        max_books=max_books,
        retry_attempts=retry
    )

    try:
        stats = automator.export_collection_notes()

        click.echo(f"\nAndroid automation complete!")
        click.echo(f"Successfully exported: {stats['successful']}/{stats['attempted']} books")

        if stats['failed'] > 0:
            click.echo(f"\nFailed exports: {stats['failed']}")
            click.echo("Failed books:")
            for book in stats['failed_books']:
                click.echo(f"  - {book}")

        if stats['successful'] == 0:
            click.echo("\nNo books were successfully exported. Check the logs for details.")
            return

    except KeyboardInterrupt:
        click.echo("\nAutomation interrupted by user.")
        return
    except Exception as e:
        click.echo(f"Android automation failed: {e}")
        logging.error(f"Android automation error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Process exported files with NoteHammer
    if onedrive_path:
        click.echo(f"\nProcessing exported files from OneDrive: {onedrive_path}")

        # Wait a moment for OneDrive sync
        click.echo("Waiting for OneDrive to sync...")
        time.sleep(10)

        note_hammer = NoteHammer(
            input_path=onedrive_path,
            output_path=output_path,
            backup_path=backup_path,
            default_tags=list(default_tags),
            overwrite_older_notes=True,
            skip_confirmation=True
        )

        note_hammer.process_kindle_notes()
        click.echo(f"\nComplete! Markdown notes saved to: {output_path}")
    else:
        click.echo("\nOneDrive path not specified. You'll need to manually process the exported files.")
        click.echo(f"Use: note-hammer extract_kindle -i <onedrive_kindle_folder> -o {output_path}")


@cli.command(name="check_android")
def check_android():
    """Diagnose Android/ADB connection issues"""
    import os
    import subprocess
    import shutil

    # Use port 5039 for ADB to avoid Windows Hyper-V port exclusion range
    os.environ.setdefault("ANDROID_ADB_SERVER_PORT", "5039")
    adb_port = os.environ.get("ANDROID_ADB_SERVER_PORT", "5037")

    click.echo("=== Android Connection Diagnostic ===\n")
    click.echo(f"   Using ADB port: {adb_port}\n")

    # Step 1: Check if ADB is in PATH
    click.echo("1. Checking if ADB is in PATH...")
    adb_path = shutil.which("adb")
    if adb_path:
        click.echo(f"   ✓ ADB found: {adb_path}")
    else:
        click.echo("   ✗ ADB not found in PATH!")
        click.echo("   Fix: Install Android Platform Tools and add to PATH")
        click.echo("   Windows: choco install adb")
        click.echo("   Or run: setup-android-tools.ps1")
        return

    # Step 2: Try to kill any existing ADB server
    click.echo("\n2. Restarting ADB server...")
    try:
        kill_result = subprocess.run(
            ["adb", "kill-server"],
            capture_output=True,
            text=True,
            timeout=10
        )
        click.echo("   Killed existing ADB server")
    except Exception as e:
        click.echo(f"   Note: {e}")

    # Step 3: Start fresh ADB server
    click.echo("\n3. Starting ADB server...")
    try:
        start_result = subprocess.run(
            ["adb", "start-server"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if start_result.returncode == 0:
            click.echo("   ✓ ADB server started")
        else:
            click.echo(f"   ✗ Failed to start ADB server")
            click.echo(f"   stdout: {start_result.stdout}")
            click.echo(f"   stderr: {start_result.stderr}")
            click.echo("\n   Possible fixes:")
            click.echo("   - Close any Android emulators")
            click.echo("   - Close Android Studio")
            click.echo("   - Check if port 5037 is in use: netstat -ano | findstr 5037")
            click.echo("   - Try running as Administrator")
            return
    except subprocess.TimeoutExpired:
        click.echo("   ✗ ADB server start timed out")
        return
    except Exception as e:
        click.echo(f"   ✗ Error: {e}")
        return

    # Step 4: List devices
    click.echo("\n4. Checking connected devices...")
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        click.echo(f"   Output:\n{result.stdout}")

        lines = [l.strip() for l in result.stdout.strip().split('\n')[1:] if l.strip()]
        devices = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                device_id = parts[0]
                status = parts[1]
                devices.append((device_id, status))

        if not devices:
            click.echo("   ✗ No devices connected!")
            click.echo("\n   To connect your phone:")
            click.echo("   1. Enable Developer Options (tap Build Number 7 times)")
            click.echo("   2. Enable USB Debugging in Developer Options")
            click.echo("   3. Connect phone via USB cable")
            click.echo("   4. Accept the debugging prompt on your phone")
        else:
            for device_id, status in devices:
                if status == "device":
                    click.echo(f"   ✓ {device_id} - Ready")
                elif status == "unauthorized":
                    click.echo(f"   ✗ {device_id} - UNAUTHORIZED")
                    click.echo("     Check your phone for a debugging authorization prompt")
                elif status == "offline":
                    click.echo(f"   ✗ {device_id} - OFFLINE")
                    click.echo("     Try unplugging and reconnecting the device")
                else:
                    click.echo(f"   ? {device_id} - {status}")

            ready_devices = [d for d, s in devices if s == "device"]
            if ready_devices:
                click.echo(f"\n=== SUCCESS: {len(ready_devices)} device(s) ready ===")
                click.echo("You can now run: note-hammer automate_android")

    except Exception as e:
        click.echo(f"   ✗ Error listing devices: {e}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        with click.Context(cli) as ctx:
            click.echo(cli.get_help(ctx))
    else:
        cli()
