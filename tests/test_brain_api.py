import inspect
import unittest
from unittest.mock import patch

from brain import _call_llm_json, analyze_data, chat, generate_keywords


class TestBrainApiSignatures(unittest.TestCase):
    def test_chat_signature_has_no_provider(self) -> None:
        params = list(inspect.signature(chat).parameters.keys())
        self.assertEqual(params, ["prompt"])

    def test_call_llm_json_signature_has_no_provider(self) -> None:
        params = list(inspect.signature(_call_llm_json).parameters.keys())
        self.assertEqual(params, ["prompt", "max_retry"])

    def test_generate_keywords_signature_has_no_provider(self) -> None:
        params = list(inspect.signature(generate_keywords).parameters.keys())
        self.assertEqual(params, ["keyword"])

    def test_analyze_data_signature_has_no_provider(self) -> None:
        params = list(inspect.signature(analyze_data).parameters.keys())
        self.assertEqual(params, ["data_path"])


class TestBrainApiBehavior(unittest.TestCase):
    def test_generate_keywords_calls_llm_json_and_returns_keywords(self) -> None:
        mock_result = {"keywords": ["A", "B"]}
        with patch("brain._call_llm_json", return_value=mock_result) as mock_call:
            result = generate_keywords("游戏")

        self.assertEqual(result, ["A", "B"])
        mock_call.assert_called_once()
        called_prompt = mock_call.call_args.args[0]
        self.assertIn("游戏", called_prompt)

    def test_call_llm_json_retries_and_succeeds_on_second_response(self) -> None:
        with patch("brain.chat", side_effect=["not-json", '{"ok": true}']) as mock_chat:
            result = _call_llm_json("test-prompt", max_retry=2)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_chat.call_count, 2)
        self.assertEqual(mock_chat.call_args_list[0].args[0], "test-prompt")
        self.assertIn("你上一次输出不是合法 JSON", mock_chat.call_args_list[1].args[0])
