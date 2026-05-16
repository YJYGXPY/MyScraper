import inspect
import unittest

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
