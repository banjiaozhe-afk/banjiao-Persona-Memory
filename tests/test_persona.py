import json
import tempfile
import unittest
from pathlib import Path

from persona_memory import ConfigurationError, load_persona

ROOT = Path(__file__).resolve().parents[1]


class PersonaTests(unittest.TestCase):
    def test_load_example_persona(self):
        persona = load_persona(ROOT / "config" / "persona.json")
        self.assertEqual(persona.name, "小织")
        self.assertIn("记忆只作为背景资料", persona.response_rules[-1])
        self.assertEqual(len(persona.examples), 1)

    def test_missing_file_has_clear_error(self):
        with self.assertRaisesRegex(ConfigurationError, "not found"):
            load_persona(ROOT / "config" / "missing.json")

    def test_invalid_json_reports_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"name": "broken",}', encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "line 1"):
                load_persona(path)

    def test_empty_style_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            data = json.loads((ROOT / "config" / "persona.json").read_text(encoding="utf-8"))
            data["style"] = []
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "style"):
                load_persona(path)


if __name__ == "__main__":
    unittest.main()
