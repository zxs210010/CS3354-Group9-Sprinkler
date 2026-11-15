import unittest
from sprinkler_service import add_sprinkler, rename_sprinkler, remove_sprinkler

class SprinklerServiceTests(unittest.TestCase):

    def test_add_sprinkler(self):
        sprinklers = {}

        result = add_sprinkler(
            sprinklers, "Home", "WXEZ"
        )

        self.assertEqual(result, "Sprinkler connected successfully")

    def test_add_sprinkler_already_connected(self):
        sprinklers = {"WXEZ": {"name": "Home"}}

        result = add_sprinkler(
            sprinklers, "Home", "WXEZ"
        )

        self.assertEqual(sprinklers["WXEZ"], {"name": "Home"})
        self.assertEqual(result, "Sprinkler already connected")

    def test_rename_sprinkler(self):
        sprinklers = {"WXEZ": {"name": "Home"}}
        result = rename_sprinkler(sprinklers, "WXEZ", "Backyard")

        self.assertEqual(result, "Sprinkler renamed successfully")

        self.assertEqual(sprinklers["WXEZ"]["name"],"Backyard")

    def test_remove_sprinkler(self):
        sprinklers = {"WXEZ": {"name": "Home"}}

        result = remove_sprinkler(sprinklers, "WXEZ")

        self.assertEqual(result, "Sprinkler removed successfully")
        self.assertNotIn("WXEZ", sprinklers)

    def test_remove_nonexistent_sprinkler(self):
        sprinklers = {"WXEZ": {"name": "Home"}}

        result = remove_sprinkler(sprinklers, "GTA")

        self.assertEqual(result, "Sprinkler not found")
        self.assertIn("WXEZ", sprinklers)

    def test_rename_nonexistent_sprinkler(self):
        sprinklers = {"WXEZ": {"name": "Home"}}

        result = rename_sprinkler(
            sprinklers, "GTA", "Backyard"
        )

        self.assertEqual(result, "Sprinkler not found")
        self.assertEqual(
            sprinklers["WXEZ"]["name"],"Home")