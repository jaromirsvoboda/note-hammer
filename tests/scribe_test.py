import unittest
import sys

from scribe.scribe import Scribe
# sys.path.append(r"C:\Projects\WeldChecker\weld_checker")


class ScribeTest(unittest.TestCase):
    ...
    # def test_extract_tags(self):
    #     scribe = Scribe()
    #     self.assertListEqual(scribe.extract_tags("hello [world]"), ["world"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1,world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1, world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1,,world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1, ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1, , world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [world1 , ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [,world1 , ,world2]"), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("hello [,world1 , ,world2] "), ["world1", "world2"])
    #     self.assertListEqual(scribe.extract_tags("[,world1 , ,world2] hello "), [])
    #     self.assertListEqual(scribe.extract_tags("[,world1 , ,world2] hello ["), [])
    #     self.assertListEqual(scribe.extract_tags("[,world1 , ,world2] hello ]"), [])
    #     self.assertListEqual(scribe.extract_tags("[,world1 , ,world2] hello []"), [])
    #     self.assertListEqual(scribe.extract_tags("[,world1 , ,world2] hello [this should be matched]"), ["this should be matched"])
    #     self.assertListEqual(scribe.extract_tags("hello [a,b,c,d    ,e,f,    g,h,i]  "), ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
    #     self.assertListEqual(scribe.extract_tags("  hello [a,b,c,d    ,e,f,    g,h,i]   \n"), ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
        
        
        
        
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
