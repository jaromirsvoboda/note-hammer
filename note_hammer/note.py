from dataclasses import dataclass
from functools import cache
import os
import re
import time

from bs4 import BeautifulSoup

@dataclass
class Note():
    title: str
    authors: str
    citation: str
    tags: list[str]
    sections_to_notes: dict[str, list[str]]
    
    # def __str__(self):
    #     return f"Title: {self.title}
    
    @classmethod
    def from_kindle_html(cls, html_path: str):
        assert os.path.splitext(html_path)[1] == ".html"
        with open(html_path, encoding='utf-8') as fp:
            # content = fp.read()
            soup = BeautifulSoup(fp, 'html.parser')
            # print(soup)

            title = soup.find('div', {'class': ['bookTitle']})
            authors = soup.find('div', {'class': ['authors']})
            citation = soup.find('div', {'class': ['citation']})
            # sectionHeadings = soup.find('div', {'class': ['sectionHeading']})

            all_note_texts = soup.find_all('div', {'class': ['noteText']})
            sections_to_notes: dict[str, list[str]] = {}
            for note_text in all_note_texts:
                section_heading = cls.remove_leading_and_trailing_newlines(note_text.find_previous_sibling('div', {'class': {'sectionHeading'}}).text)
                if section_heading not in sections_to_notes:
                    sections_to_notes[section_heading] = []
                sections_to_notes[section_heading].append(cls.remove_leading_and_trailing_newlines(note_text.text))

            return cls(
                title=cls.remove_leading_and_trailing_newlines(title.text) if title else "",
                authors=cls.remove_leading_and_trailing_newlines(authors.text) if authors else "",
                citation=cls.remove_leading_and_trailing_newlines(citation.text) if citation else "",
                tags=cls.extract_tags(title.text if title else ""),
                sections_to_notes=sections_to_notes
            )
            
    @staticmethod
    def extract_tags(string: str) -> list[str]:
        pattern = r'\w+ \[(.*)\]\s*$'

        match = re.search(pattern, string)

        tags = ["KindleExport"]

        if match:
            extracted_text = match.group(1)
            parts = extracted_text.split(',')
            stripped_parts = [part.strip() for part in parts if part.strip() != '']
            tags.extend(stripped_parts)
        
        return tags

    @staticmethod
    @cache
    def remove_leading_and_trailing_newlines(string: str):
        if string and string[0] == '\n':
            string = string[1:]
        if string and string[-1] == '\n':
            string = string[:-1]
        return string
    
    def to_markdown(self) -> str:
        text = ""
        # text += f"# {self.title}\n"
        # text += "\n"
        text += f"#### {self.authors}\n"
        text += "\n"
        text += f"#### {self.citation}\n"
        text += "\n"
        for tag in self.tags:
            text += f"#{tag}\n"
        
        text += f"\n\n- Created: {time.strftime('%Y-%m-%d_%H-%M-%S')}\n"
        text += "\n---\n\n"
        
        for section, notes in self.sections_to_notes.items():
            text += f"### {section}\n"
            for note in notes:
                text += f"- {note}\n"
                
        return text
    
    
