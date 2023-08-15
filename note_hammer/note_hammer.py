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
    def extract_kindle_notes(self, input_path: str, output_path: str, overwrite_older_notes: bool = False):
        start = default_timer()
        logging.info(f"NoteHammer: Started extracting markdown notes from Kindle html files in {input_path}, md files will be saved to {output_path}.")
        
        notes = self.extract_notes(input_path)
        notes = self.remove_duplicate_notes(notes)
        self.write_notes(notes, output_path, overwrite_older_notes=overwrite_older_notes)

        end = default_timer()

        logging.info(f"NoteHammer: Extracted {len(notes)} notes in {round(end - start, 2)} seconds.")
        
    def backup_notes(self, input_path: str, backup_path: str):
        backup_folder = os.path.join(backup_path, f"backup_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")

        shutil.copytree(input_path, backup_folder)

    def extract_notes(self, input_path: str) -> list[Note]:
        """
        Args:
            input_path (str): Either path to a single HTML file or a directory (or a tree of directories) containing HTML files.

        Returns:
            list[Note]: _description_
        """
        logging.info(f"NoteHammer: Started reading html files from {input_path}.")
        
        assert os.path.isdir(input_path) or os.path.splitext(input_path)[1] == ".html"
        walk = list(os.walk(input_path))
        notes: list[Note] = []

        if not walk and input_path.endswith(".html"):
            notes.append(Note.from_kindle_html(input_path))
        else:
            all_html_file_paths = []
            for root, dirs, files in walk:
                all_html_file_paths.extend([os.path.join(root, file) for file in files if file.endswith(".html")])
            with click.progressbar(all_html_file_paths, label="NoteHammer: Reading html files") as bar:
                for html_file_path in bar:
                    notes.append(Note.from_kindle_html(html_file_path))
        return notes

    def write_notes(self, notes: list[Note], output_path: str, overwrite_older_notes: bool = False):
        logging.info(f"NoteHammer: Writing notes to markdown...")
        
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        assert os.path.isdir(output_path)
        for note in notes:
            self.write_note(note, output_path, overwrite_older_notes=overwrite_older_notes)

    def write_note(self, note: Note, output_folder: str, overwrite_older_notes: bool = False):
        filename = self.remove_invalid_chars_from_filename(self.remove_tags(note.title)) + ".md"
        filepath = os.path.join(output_folder, filename)
        if not overwrite_older_notes and os.path.exists(filepath):
            logging.warning(f"NoteHammer: Skipping file {filename} because it already exists in {output_folder}. Use -o or --overwrite-older-notes to overwrite such notes.")
            return
        
        with open(os.path.join(output_folder, self.remove_invalid_chars_from_filename(self.remove_tags(note.title)) + ".md"), "w",  encoding="utf-8") as file:
            note_as_md = note.to_markdown()
            file.write(note_as_md)
    
    @staticmethod     
    def remove_duplicate_notes(notes: list[Note]) -> list[Note]:
        logging.info("NoteHammer: Removing duplicate notes...")
        
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
            logging.warning(f"NoteHammer: Removed duplicate note {duplicate.title}.")
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
