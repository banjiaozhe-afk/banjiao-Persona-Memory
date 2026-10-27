import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from persona_memory.cli import main

ROOT = Path(__file__).resolve().parents[1]
PERSONA = str(ROOT / "config" / "persona.json")


class CliTests(unittest.TestCase):
    def invoke(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_demo_is_self_contained(self):
        code, stdout, stderr = self.invoke(["--persona", PERSONA, "demo"])
        self.assertEqual(code, 0, stderr)
        data = json.loads(stdout)
        self.assertIn(1, data["used_memory_ids"])
        self.assertLessEqual(len(data["used_memory_ids"]), 2)
        self.assertIn("喜欢恐怖游戏", data["prompt"])
        self.assertIn("game_selection", data["prompt"])

    def test_crud_search_and_build_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "cli.db")
            prefix = ["--db", db, "--persona", PERSONA]
            code, stdout, stderr = self.invoke(
                prefix
                + [
                    "add",
                    "喜欢合作解谜游戏",
                    "--subject",
                    "viewer:cli",
                    "--category",
                    "preference",
                ]
            )
            self.assertEqual(code, 0, stderr)
            memory_id = json.loads(stdout)["id"]

            code, stdout, _ = self.invoke(prefix + ["search", "解谜游戏", "--subject", "viewer:cli"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout)[0]["id"], memory_id)

            code, stdout, _ = self.invoke(
                prefix
                + [
                    "build",
                    "推荐一个解谜游戏",
                    "--subject",
                    "viewer:cli",
                    "--state",
                    '{"scene":"game"}',
                    "--turn",
                    "user:上一场结束了",
                ]
            )
            self.assertEqual(code, 0)
            self.assertIn("喜欢合作解谜游戏", json.loads(stdout)["prompt"])

            code, stdout, _ = self.invoke(
                prefix + ["update", str(memory_id), "--content", "现在喜欢合作建造游戏"]
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout)["content"], "现在喜欢合作建造游戏")

            code, _, _ = self.invoke(prefix + ["delete", str(memory_id)])
            self.assertEqual(code, 0)
            code, stdout, _ = self.invoke(prefix + ["list"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout), [])

    def test_build_can_disable_memories(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "cli.db")
            code, stdout, stderr = self.invoke(
                ["--db", db, "--persona", PERSONA, "build", "你好", "--max-memories", "0"]
            )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["used_memory_ids"], [])

    def test_expected_errors_have_exit_code_two(self):
        code, _, stderr = self.invoke(["--persona", "missing.json", "validate"])
        self.assertEqual(code, 2)
        self.assertIn("not found", stderr)

        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "cli.db")
            code, _, stderr = self.invoke(["--db", db, "add", "密码是 hunter2"])
        self.assertEqual(code, 2)
        self.assertIn("sensitive", stderr)

        with tempfile.TemporaryDirectory() as directory:
            code, _, stderr = self.invoke(["--db", directory, "list"])
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)


if __name__ == "__main__":
    unittest.main()
