from importlib.resources import path
import logging
import sys
import time
import click

from pathlib import Path

from note_hammer.note_hammer import NoteHammer


timestamp = time.strftime("%Y-%m-%d_%H-%M-%S_%p")
logging.basicConfig(
    filename=fr"{timestamp}.log",
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.DEBUG
)
logging.getLogger().addHandler(logging.StreamHandler())
logging.info(f"Starting NoteHammer at {timestamp}.")

@click.group()
def cli():
    pass


@cli.command(name="extract_kindle")
@click.option('-i', '--input_path', default=".", help='Path to the folder containing kindle notes (in .html format, can be nested in sub-folders) or to a single .html file.')
@click.option('-o', '--output_path', default=r".\export", help='Path to the folder where the extracted notes will be saved (in .md format).')
@click.option('-b', '--backup_path', default=r".\backup", help='Path to the folder where the Kindle htmls will be backed up to before extraction process. Empty string disables backup.')
@click.option('-t', '--tags', multiple=True, help='Tags to be added to all the notes. This option can be used multiple times to add multiple tags.')
@click.option('-o', '--overwrite-older-notes', is_flag=True, help='Include this flag for overwriting older notes with the same name in the output path.')
@click.option('-sc', '--skip-confirmation', is_flag=True, help='Confirm before processing the notes.')
def extract_kindle(input_path: str, output_path: str, backup_path: str, tags: list[str], overwrite_older_notes: bool, skip_confirmation: bool):
    if not skip_confirmation:
        click.confirm(f'Are you sure you want to process the notes in {input_path}?', abort=True)
    
    note_hammer = NoteHammer()
    
    if (backup_path != ""):
        note_hammer.backup_notes(input_path=input_path, backup_path=backup_path)
    
    note_hammer.process_kindle_notes(
        input_path=input_path, 
        output_path=output_path, 
        tags=tags,
        overwrite_older_notes=overwrite_older_notes, 
        skip_confirmation=skip_confirmation
    )

if __name__ == '__main__':
    if len(sys.argv) == 1:
        with click.Context(cli) as ctx:
            click.echo(cli.get_help(ctx))
    else:
        cli()
