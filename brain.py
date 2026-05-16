import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI

SYSTEM_PROMPT = """
你是数据分析专家。请严格按用户给定 schema 输出 JSON。
"""

load_dotenv()

def _load_llm_config() -> dict[str, str]:
    config = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
        "LLM_MODEL": os.getenv("LLM_MODEL", ""),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(
            f"LLM 配置缺少必填项: {', '.join(missing)}。请检查环境变量。"
        )
    return {
        "api_key": str(config["LLM_API_KEY"]),
        "base_url": str(config["LLM_BASE_URL"]),
        "model": str(config["LLM_MODEL"]),
    }

def _create_client(config: dict[str, str]) -> OpenAI:
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
    )

def chat(prompt: str) -> str:
    config = _load_llm_config()
    client = _create_client(config)
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""

def _read_jsonl(path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def _build_schema() -> dict[str, Any]:
    return {
        "meta": {
            "source_file": "string",
            "record_count": 0,
            "generated_at": "ISO-8601"
        },
        "signals": [
            {
                "id": "S1",
                "title": "string",
                "strength": "high|medium|low",
                "summary": "string",
                "evidence": [
                    {
                        "note_id": "string",
                        "field": "description|tag_description|comment_content|reply_content|like_count|collect_count|comment_count|comment_like_count|comment_reply_count|reply_like_count",
                        "quote": "string",
                        "reason": "string"
                    }
                ],
                "suggestions": [
                    {
                        "action": "string",
                        "why": "string",
                        "target_user": "string"
                    }
                ]
            }
        ],
        "overall_strategy": {
            "positioning": "string",
            "first_offer": "string",
            "conversion_path": ["string"]
        }
    }

def _build_prompt(data_path: str, items: list[dict[str, Any]], readme_text: str) -> str:
    schema = _build_schema()
    full_data = items
    return f"""
你是数据分析专家。请基于输入数据识别“已付费或强付费意愿”信号。

必须遵守：
1) 只输出一个 JSON 对象，不要输出 Markdown，不要代码块，不要解释文字。
2) 输出必须可被 json.loads 解析。
3) 字段必须严格匹配 schema 的结构（顶层字段不可增删）。
4) strength 只能是 high / medium / low。
5) 每个 signal 至少 1 条 evidence 和 1 条 suggestion。
6) quote 必须来自输入数据，不得编造。

【schema】
{json.dumps(schema, ensure_ascii=False, indent=2)}

【README 规则】
{readme_text}

【输入】
source_file: {data_path}
record_count: {len(items)}
all_records(全量):
{json.dumps(full_data, ensure_ascii=False)}
""".strip()


def _call_llm_json(prompt: str, max_retry: int = 2) -> dict[str, Any]:
    current_prompt = prompt
    last_err: Exception | None = None
    for i in range(max_retry + 1):
        print(f">>>大模型思考中...:第{i+1}次尝试")
        raw = chat(current_prompt)
        try:
            return json.loads(raw)
        except Exception as e:
            last_err = e
            current_prompt = (
                prompt
                + "\n\n你上一次输出不是合法 JSON。请仅返回合法 JSON 对象，不要包含 ``` 或解释。"
            )
    raise ValueError(f"模型输出无法解析为 JSON: {last_err}")


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    meta = report.get("meta", {})
    lines.append("# 数据分析报告")
    lines.append("")
    lines.append(f"- 来源文件: `{meta.get('source_file', 'N/A')}`")
    lines.append(f"- 记录数: `{meta.get('record_count', 0)}`")
    lines.append(f"- 生成时间: `{meta.get('generated_at', '')}`")
    if "keyword_count" in meta:
        lines.append(f"- 关键词数: `{meta.get('keyword_count', 0)}`")
    if "keyword_coverages" in meta:
        lines.append("")
        lines.append("## 关键词覆盖率")
        for cov in meta.get("keyword_coverages", []):
            lines.append(
                f"- `{cov.get('keyword', '')}`: total={cov.get('total_batches', 0)}, "
                f"success={cov.get('success_batches', 0)}, failed={cov.get('failed_batches', 0)}"
            )
    lines.append("")

    lines.append("## 已付费/强付费意愿点")
    for s in report.get("signals", []):
        lines.append(f"### {s['id']} - {s['title']} ({s['strength']})")
        lines.append(s["summary"])
        lines.append("")
        lines.append("**证据**")
        for ev in s.get("evidence", []):
            lines.append(f"- [{ev['note_id']}] `{ev['field']}`: {ev['quote']}（{ev['reason']}）")
        lines.append("")
        lines.append("**建议**")
        for sug in s.get("suggestions", []):
            lines.append(f"- 动作：{sug['action']}；原因：{sug['why']}；目标用户：{sug['target_user']}")
        lines.append("")

    st = report.get("overall_strategy", {})
    lines.append("## 整体策略")
    lines.append(f"- 定位：{st.get('positioning', '')}")
    lines.append(f"- 首单方案：{st.get('first_offer', '')}")
    lines.append("- 转化路径：")
    for step in st.get("conversion_path", []):
        lines.append(f"  - {step}")

    return "\n".join(lines)


def _estimate_tokens(obj: Any) -> int:
    text = json.dumps(obj, ensure_ascii=False)
    return max(1, len(text) // 4)


def _split_items_by_budget(
    items: list[dict[str, Any]],
    max_prompt_tokens: int,
    fixed_overhead_tokens: int = 10000,
) -> list[list[dict[str, Any]]]:
    budget = max(1, max_prompt_tokens - fixed_overhead_tokens)
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    used_tokens = 0

    for item in items:
        item_tokens = _estimate_tokens(item)
        if current and used_tokens + item_tokens > budget:
            batches.append(current)
            current = []
            used_tokens = 0
        current.append(item)
        used_tokens += item_tokens

    if current:
        batches.append(current)
    return batches


def _merge_partial_reports(partials: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for part in partials:
        for signal in part.get("signals", []):
            key = signal.get("title", "").strip() or signal.get("id", "")
            if not key:
                continue
            if key not in merged:
                merged[key] = {
                    "id": signal.get("id", "S1"),
                    "title": signal.get("title", ""),
                    "strength": signal.get("strength", "medium"),
                    "summary": signal.get("summary", ""),
                    "evidence": [],
                    "suggestions": [],
                }
            for evidence in signal.get("evidence", []):
                if evidence not in merged[key]["evidence"]:
                    merged[key]["evidence"].append(evidence)
            for suggestion in signal.get("suggestions", []):
                if suggestion not in merged[key]["suggestions"]:
                    merged[key]["suggestions"].append(suggestion)

    return {
        "signals": list(merged.values()),
        "overall_strategy": {
            "positioning": "",
            "first_offer": "",
            "conversion_path": [],
        },
    }


def _analyze_keyword_batches(
    keyword: str,
    data_path: str,
    items: list[dict[str, Any]],
    readme_text: str,
    max_prompt_tokens: int,
    fixed_overhead_tokens: int = 10000,
) -> dict[str, Any]:
    batches = _split_items_by_budget(
        items=items,
        max_prompt_tokens=max_prompt_tokens,
        fixed_overhead_tokens=fixed_overhead_tokens,
    )
    partials: list[dict[str, Any]] = []
    failed_batches = 0

    for i, batch in enumerate(batches):
        prompt = _build_prompt(data_path, batch, readme_text)
        try:
            partial = _call_llm_json(prompt)
            partials.append(partial)
        except Exception as exc:
            failed_batches += 1
            print(f"[WARN] 关键词 `{keyword}` 第{i+1}/{len(batches)} 批分析失败: {exc}")

    merged = _merge_partial_reports(partials)
    merged.setdefault("meta", {})
    merged["meta"]["keyword"] = keyword
    merged["meta"]["coverage"] = {
        "total_batches": len(batches),
        "success_batches": len(partials),
        "failed_batches": failed_batches,
    }
    return merged


def _merge_keyword_reports_global(keyword_reports: list[dict[str, Any]]) -> dict[str, Any]:
    merged = _merge_partial_reports(keyword_reports)
    keyword_coverages: list[dict[str, Any]] = []
    for report in keyword_reports:
        meta = report.get("meta", {})
        coverage = meta.get("coverage", {})
        keyword_coverages.append({
            "keyword": meta.get("keyword", ""),
            "total_batches": coverage.get("total_batches", 0),
            "success_batches": coverage.get("success_batches", 0),
            "failed_batches": coverage.get("failed_batches", 0),
        })

    merged.setdefault("meta", {})
    merged["meta"]["keyword_count"] = len(keyword_reports)
    merged["meta"]["keyword_coverages"] = keyword_coverages
    merged["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")
    return merged


def analyze_data_multi_stage(
    keyword_paths: list[str],
    keywords: list[str],
    max_prompt_tokens: int,
    analyze_max_concurrency: int = 4,
) -> dict[str, Any]:
    if len(keyword_paths) != len(keywords):
        raise ValueError("keyword_paths 与 keywords 长度不一致，无法进行对应分析。")

    project_root = Path(__file__).resolve().parent
    readme_text = (project_root / "README.md").read_text(encoding="utf-8")

    async def _run_parallel() -> tuple[list[dict[str, Any]], list[str]]:
        semaphore = asyncio.Semaphore(max(1, analyze_max_concurrency))
        keyword_reports: list[dict[str, Any]] = []
        failed_keywords: list[str] = []

        async def _run_one(keyword: str, data_path: str) -> None:
            async with semaphore:
                try:
                    items = _read_jsonl(data_path)
                    print(f"[ANALYZE] keyword={keyword} start, records={len(items)}")
                    keyword_report = await asyncio.to_thread(
                        _analyze_keyword_batches,
                        keyword,
                        data_path,
                        items,
                        readme_text,
                        max_prompt_tokens,
                    )
                    keyword_reports.append(keyword_report)
                    print(f"[ANALYZE] keyword={keyword} done")
                except Exception as exc:
                    failed_keywords.append(keyword)
                    print(f"[ANALYZE][WARN] keyword={keyword} err={exc}")

        await asyncio.gather(*[_run_one(kw, path) for kw, path in zip(keywords, keyword_paths)])
        return keyword_reports, failed_keywords

    keyword_reports, failed_keywords = asyncio.run(_run_parallel())
    if not keyword_reports:
        raise RuntimeError(f"所有关键词分析失败: {failed_keywords}")

    merged = _merge_keyword_reports_global(keyword_reports)
    merged.setdefault("meta", {})
    merged["meta"]["failed_keywords"] = failed_keywords
    return merged


def save_global_report(report_json: dict[str, Any], stem: str = "global") -> str:
    project_root = Path(__file__).resolve().parent
    future_dir = project_root / "future"
    future_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_json_path = future_dir / f"analysis_{stem}_{ts}.raw.json"
    md_path = future_dir / f"analysis_{stem}_{ts}.md"

    raw_json_path.write_text(
        json.dumps(report_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(report_json), encoding="utf-8")
    return str(md_path)


def generate_keywords(keyword: str) -> list[str]:
    '''
    根据输入关键词，调用大模型派生商机相关关键词
    Args:
        keyword: 原始关键词
    Returns:
        list[str]: 派生关键词列表（最多5个，不含原始关键词）
    '''
    prompt = f"""
你是商业机会挖掘专家。请根据用户给出的关键词，派生出最多5个相关的商机关键词。

规则：
1) 派生关键词应围绕"挖掘商机"目标，聚焦用户购买意愿、消费场景、痛点需求等方向。
2) 不要返回原始关键词本身。
3) 只输出一个 JSON 对象，不要输出 Markdown，不要代码块，不要解释文字。
4) 输出必须可被 json.loads 解析。
5) 格式如下：{{"keywords": ["关键词1", "关键词2", ...]}}

【原始关键词】
{keyword}
""".strip()

    result = _call_llm_json(prompt)
    return result.get("keywords", [])