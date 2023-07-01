import unittest
import sys

from note_hammer.note_hammer import NoteHammer
# sys.path.append(r"C:\Projects\WeldChecker\weld_checker")


class note_hammerTest(unittest.TestCase):
    ...
    # def test_extract_tags(self):
    #     note_hammer = note_hammer()
    #     self.assertListEqual(note_hammer.extract_tags("hello [world]"), ["world"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1,world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1, world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1,,world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1, ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1, , world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [world1 , ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [,world1 , ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [,world1 , ,world2] "), ["world1", "world2"])
    #     self.assertListEqual(note_hammer.extract_tags("[,world1 , ,world2] hello "), [])
    #     self.assertListEqual(note_hammer.extract_tags("[,world1 , ,world2] hello ["), [])
    #     self.assertListEqual(note_hammer.extract_tags("[,world1 , ,world2] hello ]"), [])
    #     self.assertListEqual(note_hammer.extract_tags("[,world1 , ,world2] hello []"), [])
    #     self.assertListEqual(note_hammer.extract_tags("[,world1 , ,world2] hello [this should be matched]"), ["this should be matched"])
    #     self.assertListEqual(note_hammer.extract_tags("hello [a,b,c,d    ,e,f,    g,h,i]  "), ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
    #     self.assertListEqual(note_hammer.extract_tags("  hello [a,b,c,d    ,e,f,    g,h,i]   \n"), ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
        
        
        
        
    # def test_upper(self):
    #     self.assertEqual('foo'.upper(), 'FOO')

    # def test_isupper(self):
    #     self.assertTrue('FOO'.isupper())
    #     self.assertFalse('Foo'.isupper())

    # def test_split(self):
    #     s = 'hello world'
    #     self.assertEqual(s.split(), ['hello', 'world'])
    #     # check that s.split fails when the separator is not a string
    #     with self.assertRaises(TypeError):
    #         s.split(2)


if __name__ == '__main__':
    unittest.main()
