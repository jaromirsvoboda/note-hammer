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


if __name__ == '__main__':
    if len(sys.argv) == 1:
        with click.Context(cli) as ctx:
            click.echo(cli.get_help(ctx))
    else:
        cli()
