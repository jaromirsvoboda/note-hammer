from collections import defaultdict
import datetime
import logging
import math
import os
import re
import shutil
import click
from timeit import default_timer
from note_hammer.note import Note


class NoteHammer():
    def __init__(
        self,
        input_path: str, 
        output_path: str,
        backup_path: str,
        tags: list[str] = [],
        overwrite_older_notes: bool = False, 
        skip_confirmation: bool = False
    ):
        self.input_path = os.path.abspath(input_path)
        self.output_path = os.path.abspath(output_path)
        self.backup_path = os.path.abspath(backup_path)
        self.tags: list[str] = tags
        self.overwrite_older_notes: bool = overwrite_older_notes 
        self.skip_confirmation: bool = skip_confirmation
    
    def process_kindle_notes(
        self, 
        # input_path: str, 
        # output_path: str, 
        # tags: list[str] = [],
        # overwrite_older_notes: bool = False, 
        # skip_confirmation: bool = False
    ):
        start = default_timer()
        if self.backup_path:
            logging.info(f"NoteHammer: Backing up notes to {self.backup_path}")
            self.backup_notes()
        
        logging.info(f"NoteHammer: Extracting markdown notes from Kindle html files in {self.input_path}, md files will be saved to {self.output_path}")
        
        notes = self.extract_notes()
        notes = self.remove_duplicate_notes(notes)
        self.write_notes(
            notes=notes, 
        )

        end = default_timer()

        logging.info(f"NoteHammer: Processed {len(notes)} notes in {round(end - start, 2)} seconds")
        
    def backup_notes(self):
        backup_folder = os.path.join(self.backup_path, f"backup_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")

        shutil.copytree(self.input_path, backup_folder)

    def extract_notes(self) -> list[Note]:
        """
        Args:
            input_path (str): Either path to a single HTML file or a directory (or a tree of directories) containing HTML files.

        Returns:
            list[Note]: _description_
        """
        logging.info(f"NoteHammer: Reading html files from {self.input_path}")
        
        assert os.path.isdir(self.input_path) or os.path.splitext(self.input_path)[1] == ".html"
        walk = list(os.walk(self.input_path))
        notes: list[Note] = []

        if not walk and self.input_path.endswith(".html"):
            notes.append(Note.from_kindle_html(self.input_path))
        else:
            all_html_file_paths = []
            for root, dirs, files in walk:
                all_html_file_paths.extend([os.path.join(root, file) for file in files if file.endswith(".html")])
            with click.progressbar(all_html_file_paths, label="NoteHammer: Reading html files") as bar:
                for html_file_path in bar:
                    notes.append(Note.from_kindle_html(html_file_path))
        return notes

    def write_notes(self, notes: list[Note]):
        logging.info(f"NoteHammer: Writing markdown notes to {self.output_path}")
        
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        
        assert os.path.isdir(self.output_path)
        for note in notes:
            self.write_note(note)

    def write_note(self, note: Note):
        filename = self.remove_invalid_chars_from_filename(self.remove_tags(note.title)) + ".md"
        filepath = os.path.join(self.output_path, filename)
        
        if not self.overwrite_older_notes and os.path.exists(filepath):
            logging.warning(f"NoteHammer: Skipping file {filepath} because it already exists . Use -o or --overwrite-older-notes flag to overwrite such notes")
            return
        
        if not self.skip_confirmation:
            confirmed = click.confirm(f'Are you sure you want to overwrite existing note {filepath}? Use -sc or --skip-confirmations flag to not get asked again.', abort=False)
            if not confirmed:
                logging.info(f"NoteHammer: Skipping file {filepath} because it already exists")
                return
        
        if os.path.exists(filepath):
            logging.info(f"NoteHammer: Overwriting {filepath}")
        with open(filepath, "w",  encoding="utf-8") as file:
            note_as_md = note.to_markdown()
            file.write(note_as_md)
    
    @staticmethod     
    def remove_duplicate_notes(notes: list[Note]) -> list[Note]:
        logging.info("NoteHammer: Removing duplicate notes")
        
        note_freq = defaultdict(int)
        for note in notes:
            note_freq[note] += 1

        unique_notes = []
        duplicates = []
        for note, freq in note_freq.items():
            if freq == 1:
                unique_notes.append(note)
            else:
                duplicates.extend([note] * freq)
        for duplicate in duplicates:
            logging.warning(f"NoteHammer: Removed duplicate note {duplicate.title}")
        return unique_notes

    @staticmethod
    def remove_tags(string: str) -> str:
        last_index_of_opening_bracket = string.rfind('[')
        if last_index_of_opening_bracket == -1:
            return string.strip()
        else:
            return string[:last_index_of_opening_bracket].strip()

    @staticmethod
    def remove_invalid_chars_from_filename(filename_with_invalid_chars: str) -> str:
        pattern = re.compile('[/\\:*?"<>|]')
        return pattern.sub('', filename_with_invalid_chars)
