# import html2markdown
# from markdownify import markdownify as md
import datetime
import logging
import math
import os
import re
import shutil
from timeit import default_timer

from bs4 import BeautifulSoup

from note_hammer.note import Note


class NoteHammer():
    def extract_kindle_notes(self, input_path: str, output_path: str):
        start = default_timer()
        logging.info(f"NoteHammer: Started extracting markdown notes from Kindle html files in {input_path}, md files will be saved to {output_path}.")
        
        notes = self.extract_notes(input_path)
        self.write_notes(notes, output_path)

        end = default_timer()

        logging.info(f"NoteHammer: Extracted {len(notes)} notes in {round(end - start, 2)} seconds.")
        
    def backup_notes(self, input_path: str, backup_path: str):
        backup_folder = os.path.join(backup_path, f"backup_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")

        # if not os.path.exists(backup_folder):
        #     os.makedirs(backup_folder)

        shutil.copytree(input_path, backup_folder)

    def extract_notes(self, input_path: str) -> list[Note]:
        """
        Args:
            input_path (str): Either path to a single HTML file or a directory (or a tree of directories) containing HTML files.

        Returns:
            list[Note]: _description_
        """
        logging.info(f"NoteHammer: Extracting notes from html (this might take a while)...")
        
        assert os.path.isdir(input_path) or os.path.splitext(input_path)[1] == ".html"
        walk = list(os.walk(input_path))
        notes: list[Note] = []

        if not walk and input_path.endswith(".html"):
            notes.append(Note.from_kindle_html(input_path))
        else:
            for root, dirs, files in walk:
                html_files = [file for file in files if file.endswith(".html")]
                notes.extend(
                    Note.from_kindle_html(os.path.join(root, html_file))
                    for html_file in html_files
                )
        return notes

    def write_notes(self, notes: list[Note], output_path: str):
        logging.info(f"NoteHammer: Writing notes to markdown...")
        
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        assert os.path.isdir(output_path)
        for note in notes:
            self.write_note(note, output_path)

    def write_note(self, note: Note, output_folder: str):
        with open(os.path.join(output_folder, self.remove_invalid_chars_from_filename(self.remove_tags(note.title)) + ".md"), "w",  encoding="utf-8") as file:
            note_as_md = note.to_markdown()
            file.write(note_as_md)

        # # Read the HTML file
        # with open(r'C:\Projects\note_hammer\test_resources\exported notes\[Prediction] What war between the USA and China wo - Notebook.html', 'r') as f:
        #     html = f.read()

        # # Convert the HTML to Markdown
        # markdown1 = html2markdown.convert(html)
        # markdown2 = md(html)

        # # Save the Markdown to a file
        # with open('output.md', 'w') as f:
        #     f.write(markdown2)

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
