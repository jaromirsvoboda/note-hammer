import unittest
import sys

from note_hammer.note import Note


class NoteTest(unittest.TestCase):
    def test_extract_tags(self):
        default_tags = ["KindleExport"]
        self.assertEqual(Note.extract_tags(authors="", title="hello [world]", default_tags=default_tags),
                         frozenset(["KindleExport", "World"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1,world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1, world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1,,world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1, ,world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1, , world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [world1 , ,world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [,world1 , ,world2]", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [,world1 , ,world2] ", default_tags=default_tags),
                         frozenset(["KindleExport", "World1", "World2"]))
        # Tags not at end of title should not be extracted
        self.assertEqual(Note.extract_tags(authors="", title="[,world1 , ,world2] hello ", default_tags=default_tags),
                         frozenset(["KindleExport"]))
        self.assertEqual(Note.extract_tags(authors="", title="[,world1 , ,world2] hello [", default_tags=default_tags),
                         frozenset(["KindleExport"]))
        self.assertEqual(Note.extract_tags(authors="", title="[,world1 , ,world2] hello ]", default_tags=default_tags),
                         frozenset(["KindleExport"]))
        self.assertEqual(Note.extract_tags(authors="", title="[,world1 , ,world2] hello []", default_tags=default_tags),
                         frozenset(["KindleExport"]))
        self.assertEqual(Note.extract_tags(authors="", title="[,world1 , ,world2] hello [this should be matched]", default_tags=default_tags),
                         frozenset(["KindleExport", "This should be matched"]))
        self.assertEqual(Note.extract_tags(authors="", title="hello [a,b,c,d    ,e,f,    g,h,i]  ", default_tags=default_tags),
                         frozenset(["KindleExport", "A", "B", "C", "D", "E", "F", "G", "H", "I"]))
        self.assertEqual(Note.extract_tags(authors="", title="  hello [a,b,c,d    ,e,f,    g,h,i]   \n", default_tags=default_tags),
                         frozenset(["KindleExport", "A", "B", "C", "D", "E", "F", "G", "H", "I"]))

    def test_extract_tags_with_authors(self):
        default_tags = ["KindleExport"]
        result = Note.extract_tags(authors="John Smith", title="Some Book [tag1]", default_tags=default_tags)
        self.assertIn("KindleExport", result)
        self.assertIn("Tag1", result)
        self.assertIn("JohnSmith", result)


if __name__ == '__main__':
    unittest.main()
