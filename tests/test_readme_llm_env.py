import unittest
from pathlib import Path


README_PATH = Path(__file__).resolve().parents[1] / "README.md"


class TestReadmeLlmEnv(unittest.TestCase):
    def test_readme_uses_llm_env_names(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")

        for required_key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
            self.assertIn(required_key, readme_text)

        for legacy_key in ("ARK_API_KEY", "ARK_BASE_URL", "ARK_MODEL"):
            self.assertNotIn(legacy_key, readme_text)
