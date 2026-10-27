import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from persona_memory import (
    DuplicateMemoryError,
    MemoryNotFoundError,
    SensitiveContentError,
    SQLiteMemoryStore,
    ValidationError,
)


class SQLiteMemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteMemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_add_get_update_list_delete(self):
        memory = self.store.add(
            "  喜欢解谜游戏  ",
            subject="viewer:1",
            category="preference",
            importance=0.8,
            confidence=0.9,
            source="test",
        )
        self.assertEqual(memory.content, "喜欢解谜游戏")
        self.assertEqual(self.store.get(memory.id).subject, "viewer:1")

        updated = self.store.update(memory.id, content="现在更喜欢策略游戏")
        self.assertEqual(updated.content, "现在更喜欢策略游戏")
        self.assertGreaterEqual(updated.updated_at, memory.updated_at)
        self.assertEqual(len(self.store.list("viewer:1")), 1)

        self.store.delete(memory.id)
        with self.assertRaises(MemoryNotFoundError):
            self.store.get(memory.id)

    def test_duplicate_is_case_and_whitespace_insensitive(self):
        self.store.add("Likes   Puzzle Games", subject="viewer:1")
        with self.assertRaises(DuplicateMemoryError):
            self.store.add("likes puzzle games", subject="viewer:1")

    def test_sensitive_values_are_rejected(self):
        samples = (
            "我的密码是 hunter2",
            "密码 hunter2",
            "password hunter2",
            "api_key = abcdef123456",
            "token sk-abcdef123456",
            "身份证号：11010119900307001X",
        )
        for content in samples:
            with self.subTest(content=content), self.assertRaises(SensitiveContentError):
                self.store.add(content)
        self.assertEqual(self.store.list(), [])

    def test_normal_password_related_topics_are_allowed(self):
        first = self.store.add("I use a password manager")
        second = self.store.add("Password reset workflow should be documented")
        self.assertEqual(first.content, "I use a password manager")
        self.assertEqual(second.content, "Password reset workflow should be documented")

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.add(" ")
        with self.assertRaises(ValidationError):
            self.store.add("content", category="unknown")
        with self.assertRaises(ValidationError):
            self.store.add("content", importance=1.1)
        with self.assertRaises(ValidationError):
            self.store.get(0)

    def test_missing_update_and_delete_raise(self):
        with self.assertRaises(MemoryNotFoundError):
            self.store.update(999, content="new")
        with self.assertRaises(MemoryNotFoundError):
            self.store.delete(999)

    def test_home_directory_is_expanded_for_sqlite_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"USERPROFILE": directory, "HOME": directory}
            ):
                with SQLiteMemoryStore("~/memories.db") as store:
                    store.add("测试路径")
            self.assertTrue((Path(directory) / "memories.db").exists())

    def test_data_survives_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.db"
            with SQLiteMemoryStore(path) as first:
                memory = first.add("记得这个项目使用 SQLite", source="test")
            with SQLiteMemoryStore(path) as second:
                self.assertEqual(second.get(memory.id).content, "记得这个项目使用 SQLite")


if __name__ == "__main__":
    unittest.main()
