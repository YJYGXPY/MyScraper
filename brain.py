import argparse
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

LLM_CONFIG = {
    "ark": {
        "api_key": os.getenv("ARK_API_KEY", ""),
        "base_url": os.getenv("ARK_BASE_URL", ""),
        "model": os.getenv("ARK_MODEL", ""),
    }
}

def _get_provider_config(provider: str) -> dict[str, str]:
    if provider not in LLM_CONFIG:
        raise ValueError(f"不支持的 provider: {provider}")

    config = LLM_CONFIG[provider]
    required_keys = ["api_key", "base_url", "model"]
    missing = [k for k in required_keys if not config.get(k)]
    if missing:
        raise ValueError(
            f"{provider} 配置缺少必填项: {', '.join(missing)}。请检查 .env 文件。"
        )
    return {
        "api_key": str(config["api_key"]),
        "base_url": str(config["base_url"]),
        "model": str(config["model"]),
    }

def _create_client(config: dict[str, str]) -> OpenAI:
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
    )

def chat(prompt: str, provider: str = "ark") -> str:
    config = _get_provider_config(provider)
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


def _call_llm_json(prompt: str, provider: str = "ark", max_retry: int = 2) -> dict[str, Any]:
    current_prompt = prompt
    last_err: Exception | None = None
    for i in range(max_retry + 1):
        print(f">>>大模型思考中...:尝试{i+1}")
        raw = chat(current_prompt, provider=provider)
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
    meta = report["meta"]
    lines.append("# 数据分析报告")
    lines.append("")
    lines.append(f"- 来源文件: `{meta['source_file']}`")
    lines.append(f"- 记录数: `{meta['record_count']}`")
    lines.append(f"- 生成时间: `{meta['generated_at']}`")
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


def generate_keywords(keyword: str, provider: str = "ark") -> list[str]:
    '''
    根据输入关键词，调用大模型派生商机相关关键词
    Args:
        keyword: 原始关键词
        provider: LLM 提供商
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

    result = _call_llm_json(prompt, provider=provider)
    return result.get("keywords", [])


def analyze_data(data_path: str, provider: str = "ark") -> str:
    project_root = Path(__file__).resolve().parent
    readme_path = project_root / "README.md"
    future_dir = project_root / "future"
    future_dir.mkdir(parents=True, exist_ok=True)

    items = _read_jsonl(data_path)
    print(f">>>读取数据: {data_path}")
    
    readme_text = readme_path.read_text(encoding="utf-8")
    print(f">>>读取README文件: {readme_text}")
    
    prompt = _build_prompt(data_path, items, readme_text)
    print(f">>>构建提示词: {prompt}")

    report_json = _call_llm_json(prompt, provider=provider)
    print(f">>>得到分析结果: {report_json}")

    # 补 meta 兜底
    report_json.setdefault("meta", {})
    report_json["meta"]["source_file"] = data_path
    report_json["meta"]["record_count"] = len(items)
    report_json["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(data_path).stem
    raw_json_path = future_dir / f"analysis_{stem}_{ts}.raw.json"
    md_path = future_dir / f"analysis_{stem}_{ts}.md"

    raw_json_path.write_text(
        json.dumps(report_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    md_path.write_text(_render_markdown(report_json), encoding="utf-8")
    print(f">>>保存分析结果: {md_path}")

    return str(md_path)
