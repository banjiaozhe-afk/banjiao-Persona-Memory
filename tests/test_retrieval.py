import unittest

from persona_memory import MemoryRetriever, SQLiteMemoryStore


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteMemoryStore(":memory:")
        self.retriever = MemoryRetriever(self.store)
        self.store.add(
            "喜欢恐怖游戏，但不喜欢频繁跳吓",
            subject="viewer:1",
            category="preference",
            importance=0.9,
        )
        self.store.add(
            "喜欢赛车游戏",
            subject="viewer:2",
            category="preference",
        )
        self.store.add(
            "上一场恐怖游戏在医院地图卡关",
            subject="global",
            category="event",
        )

    def tearDown(self):
        self.store.close()

    def test_retrieves_related_memories_without_leaking_other_subjects(self):
        results = self.retriever.search("今晚玩恐怖游戏吗", subject="viewer:1")
        contents = [item.memory.content for item in results]
        self.assertIn("喜欢恐怖游戏，但不喜欢频繁跳吓", contents)
        self.assertIn("上一场恐怖游戏在医院地图卡关", contents)
        self.assertNotIn("喜欢赛车游戏", contents)
        self.assertTrue(all(0 < item.relevance <= 1 for item in results))
        self.assertEqual(
            [item.memory.id for item in results],
            [item.memory.id for item in sorted(results, key=lambda item: item.score, reverse=True)],
        )

    def test_default_search_only_uses_global_memories(self):
        results = self.retriever.search("恐怖游戏")
        contents = [item.memory.content for item in results]
        self.assertEqual(contents, ["上一场恐怖游戏在医院地图卡关"])

    def test_subject_is_trimmed_and_duplicate_content_is_merged(self):
        self.store.add("喜欢恐怖游戏，但不喜欢频繁跳吓", subject="global", importance=0.1)
        results = self.retriever.search("恐怖游戏", subject=" viewer:1 ")
        matching = [
            item for item in results
            if item.memory.content == "喜欢恐怖游戏，但不喜欢频繁跳吓"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].memory.subject, "viewer:1")

    def test_unrelated_and_empty_queries_return_empty(self):
        self.assertEqual(self.retriever.search("完全不相关的量子计算"), [])
        self.assertEqual(self.retriever.search(""), [])

    def test_limit_and_score_validation(self):
        self.store.add("恐怖游戏 恐怖游戏 恐怖游戏", subject="viewer:1")
        self.assertEqual(len(self.retriever.search("恐怖游戏", limit=1)), 1)
        with self.assertRaises(ValueError):
            self.retriever.search("恐怖游戏", limit=0)
        with self.assertRaises(ValueError):
            self.retriever.search("恐怖游戏", min_score=1.1)


if __name__ == "__main__":
    unittest.main()
