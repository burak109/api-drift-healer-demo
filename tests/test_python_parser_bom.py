import tempfile
import unittest
from pathlib import Path

from api_drift_healer.python_parser import (
    parse_python_file,
)


class PythonParserBomTests(unittest.TestCase):
    def test_parses_utf8_bom_python_file(self) -> None:
        source = (
            "import requests\n"
            "\n"
            "def test_create_user():\n"
            "    requests.post(\n"
            '        "http://localhost:3000/users",\n'
            '        json={"userEmail": "qa@example.com"},\n'
            "    )\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_create_user.py"

            file_path.write_text(
                source,
                encoding="utf-8-sig",
            )

            result = parse_python_file(file_path)

            self.assertIsNotNone(result)
            self.assertEqual(len(result.requests), 1)


if __name__ == "__main__":
    unittest.main()
