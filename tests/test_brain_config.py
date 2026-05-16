import unittest
from unittest.mock import patch

from brain import _load_llm_config


class TestBrainConfig(unittest.TestCase):
    def test_load_llm_config_success(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://example.com/v1",
                "LLM_MODEL": "test-model",
            },
            clear=False,
        ):
            config = _load_llm_config()

        self.assertEqual(
            config,
            {
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
                "model": "test-model",
            },
        )

    def test_load_llm_config_missing_fields(self) -> None:
        with patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=True):
            with self.assertRaises(ValueError) as exc_info:
                _load_llm_config()

        err_text = str(exc_info.exception)
        self.assertIn("LLM_BASE_URL", err_text)
        self.assertIn("LLM_MODEL", err_text)
