from importlib.resources import path
import logging
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

@click.command()
@click.option('--input_path', default=".", help='Path to the folder containing kindle notes (in .html format, can be nested in sub-folders) or to a single .html file.')
@click.option('--output_path', default=".", help='Path to the folder where the notes will be saved (in .md format).')
def main(input_path: str, output_path: str):
    print(path)
    note_hammer = NoteHammer()
    note_hammer.run(input_path=input_path, output_path=output_path)

if __name__ == '__main__':
    main()  # type: ignore