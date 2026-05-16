# Brain Single-LLM Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove multi-provider concepts from `brain.py` and fully standardize runtime config naming to `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL`.

**Architecture:** Keep the existing analysis workflow and schema intact while collapsing configuration to a single flat model. Remove provider parameters end-to-end (`chat` -> `_call_llm_json` -> public APIs), then align README and environment usage to the same naming model.

**Tech Stack:** Python 3.11, OpenAI-compatible SDK (`openai`), dotenv, unittest, markdown docs.

---

### Task 1: Replace Provider-Based Config With Single LLM Config

**Files:**
- Modify: `brain.py`
- Test: `tests/test_brain_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
import os
import unittest
from unittest.mock import patch

import brain


class BrainConfigTests(unittest.TestCase):
    def test_load_single_llm_config_success(self):
        with patch.dict(os.environ, {
            "LLM_API_KEY": "k",
            "LLM_BASE_URL": "https://example.com/v1",
            "LLM_MODEL": "gpt-x",
        }, clear=False):
            cfg = brain._load_llm_config()
            self.assertEqual(cfg["api_key"], "k")
            self.assertEqual(cfg["base_url"], "https://example.com/v1")
            self.assertEqual(cfg["model"], "gpt-x")

    def test_load_single_llm_config_missing_fields_raises(self):
        with patch.dict(os.environ, {
            "LLM_API_KEY": "",
            "LLM_BASE_URL": "",
            "LLM_MODEL": "",
        }, clear=False):
            with self.assertRaises(ValueError) as cm:
                brain._load_llm_config()
            self.assertIn("LLM_API_KEY", str(cm.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_brain_config -v`  
Expected: FAIL because `_load_llm_config()` does not exist yet.

- [ ] **Step 3: Implement minimal single-config loader in `brain.py`**

```python
def _load_llm_config() -> dict[str, str]:
    config = {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", ""),
        "model": os.getenv("LLM_MODEL", ""),
    }
    missing = [k for k, v in {
        "LLM_API_KEY": config["api_key"],
        "LLM_BASE_URL": config["base_url"],
        "LLM_MODEL": config["model"],
    }.items() if not v]
    if missing:
        raise ValueError(f"LLM 配置缺少必填项: {', '.join(missing)}。请检查 .env 文件。")
    return {k: str(v) for k, v in config.items()}
```

- [ ] **Step 4: Re-run tests to verify pass**

Run: `python -m unittest tests.test_brain_config -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add brain.py tests/test_brain_config.py
git commit -m "refactor: collapse brain config to single LLM env model"
```

### Task 2: Remove Provider Parameters Across Public APIs

**Files:**
- Modify: `brain.py`
- Test: `tests/test_brain_api.py`

- [ ] **Step 1: Write failing API-surface tests**

```python
import inspect
import unittest

import brain


class BrainApiTests(unittest.TestCase):
    def test_public_functions_have_no_provider_parameter(self):
        self.assertNotIn("provider", inspect.signature(brain.chat).parameters)
        self.assertNotIn("provider", inspect.signature(brain.generate_keywords).parameters)
        self.assertNotIn("provider", inspect.signature(brain.analyze_data).parameters)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_brain_api -v`  
Expected: FAIL because signatures still contain `provider`.

- [ ] **Step 3: Implement minimal signature and call-chain cleanup**

```python
def chat(prompt: str) -> str:
    config = _load_llm_config()
    client = _create_client(config)
    # ...

def _call_llm_json(prompt: str, max_retry: int = 2) -> dict[str, Any]:
    raw = chat(current_prompt)
    # ...

def generate_keywords(keyword: str) -> list[str]:
    result = _call_llm_json(prompt)
    return result.get("keywords", [])

def analyze_data(data_path: str) -> str:
    report_json = _call_llm_json(prompt)
    # ...
```

- [ ] **Step 4: Re-run tests to verify pass**

Run: `python -m unittest tests.test_brain_api -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add brain.py tests/test_brain_api.py
git commit -m "refactor: remove provider argument from brain api surface"
```

### Task 3: Ensure No Provider/ARK Coupling Remains

**Files:**
- Modify: `brain.py`
- Test: `tests/test_brain_naming.py`

- [ ] **Step 1: Write failing naming tests**

```python
import unittest
from pathlib import Path


class BrainNamingTests(unittest.TestCase):
    def test_brain_file_no_provider_or_ark_tokens(self):
        text = Path("brain.py").read_text(encoding="utf-8")
        self.assertNotIn("provider", text)
        self.assertNotIn("ARK_API_KEY", text)
        self.assertNotIn("ARK_BASE_URL", text)
        self.assertNotIn("ARK_MODEL", text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_brain_naming -v`  
Expected: FAIL before cleanup.

- [ ] **Step 3: Remove leftover constants/functions/messages tied to provider**

```python
# Remove:
# - LLM_CONFIG = {"ark": ...}
# - _get_provider_config(...)
# - provider mention in docstrings/errors
# Keep:
# - single _load_llm_config() + _create_client()
```

- [ ] **Step 4: Re-run tests to verify pass**

Run: `python -m unittest tests.test_brain_naming -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add brain.py tests/test_brain_naming.py
git commit -m "chore: remove remaining provider/ARK naming from brain module"
```

### Task 4: Update README and Environment Instructions

**Files:**
- Modify: `README.md`
- Modify: `.env` (local verification only, do not commit secret values)
- Test: `tests/test_readme_llm_env.py`

- [ ] **Step 1: Write failing README consistency test**

```python
import unittest
from pathlib import Path


class ReadmeEnvTests(unittest.TestCase):
    def test_readme_mentions_llm_env_and_not_ark_env(self):
        text = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("LLM_API_KEY", text)
        self.assertIn("LLM_BASE_URL", text)
        self.assertIn("LLM_MODEL", text)
        self.assertNotIn("ARK_API_KEY", text)
        self.assertNotIn("ARK_BASE_URL", text)
        self.assertNotIn("ARK_MODEL", text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_readme_llm_env -v`  
Expected: FAIL before README update.

- [ ] **Step 3: Update README `.env` and config description**

```markdown
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
```

- [ ] **Step 4: Verify local `.env` uses `LLM_*` names**

Run: `rg "^(LLM_|ARK_)" ".env"`  
Expected: only `LLM_*` keys present.

- [ ] **Step 5: Re-run tests to verify pass**

Run: `python -m unittest tests.test_readme_llm_env -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md tests/test_readme_llm_env.py
git commit -m "docs: align environment naming to single LLM variables"
```

### Task 5: End-to-End Verification of Brain Pipeline

**Files:**
- Modify: none required unless bug found

- [ ] **Step 1: Run full unit suite**

Run: `python -m unittest discover -s tests -v`  
Expected: PASS with newly added brain/readme tests.

- [ ] **Step 2: Run compile check for changed files**

Run: `python -m py_compile brain.py main.py scrape.py`  
Expected: PASS (no syntax errors).

- [ ] **Step 3: Do smoke run for keyword generation path**

Run: `uv run python main.py 游戏赛道`  
Expected: reaches LLM call with `LLM_*` config and continues normal flow.

- [ ] **Step 4: If smoke run fails, fix and re-verify**

Run: `python -m unittest discover -s tests -v && python -m py_compile brain.py`  
Expected: PASS after fixes.

- [ ] **Step 5: Commit**

```bash
git add brain.py README.md tests/
git commit -m "refactor: standardize brain module to single LLM configuration"
```
