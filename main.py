import argparse
import asyncio
import json
import os
from datetime import datetime
import scrape
import brain

# 可修改配置
KEYWORD = "羽毛球鞋" # 搜索关键词[***脚本参数***]
MAX_ITEMS = 30 # 最大爬取数量[***脚本参数***]
HEADLESS = False # 是否无头模式[***脚本参数***]
MAX_CONCURRENCY = 2 # 并行抓取关键词数量上限[***脚本参数***]

DATA_PATH = "data/" # 数据保存路径


def _merge_jsonl(paths: list[str], keyword: str, max_items: int) -> str:
    '''
    合并多个jsonl文件为一个
    Args:
        paths: jsonl文件路径列表
        keyword: 原始关键词
        max_items: 最大爬取数量
    Returns:
        str: 合并后的文件路径
    '''
    all_items: list[dict] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_items.append(json.loads(line))

    os.makedirs(DATA_PATH, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"xhs_{ts}_{keyword}_{max_items}_merged.jsonl"
    filepath = os.path.join(DATA_PATH, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        for item in all_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return filepath


async def _scrape_keywords_parallel(
    keywords: list[str],
    max_items: int,
    headless: bool,
    max_concurrency: int = MAX_CONCURRENCY,
) -> tuple[list[str], list[str]]:
    '''
    并行抓取关键词（带并发上限）
    Args:
        keywords: 关键词列表
        max_items: 每个关键词最大抓取数量
        headless: 是否无头模式
        max_concurrency: 最大并发数
    Returns:
        tuple[list[str], list[str]]: (成功路径列表, 失败关键词列表)
    '''
    semaphore = asyncio.Semaphore(max_concurrency)
    success_paths: list[str | None] = [None] * len(keywords)
    failed_keywords: list[str] = []

    async def _run_one(idx: int, kw: str):
        async with semaphore:
            print(f"\n>>>开始爬取关键词: {kw}, 最大爬取数量: {max_items}")
            try:
                path = await scrape.scrape_xhs(kw, max_items, headless)
                success_paths[idx] = path
            except Exception as exc:
                failed_keywords.append(kw)
                print(f"[WARN] 关键词抓取失败: {kw}, err={exc}")

    await asyncio.gather(*[_run_one(i, kw) for i, kw in enumerate(keywords)])
    return [p for p in success_paths if p], failed_keywords


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书爬虫")
    parser.add_argument("--key_word", type=str, default=KEYWORD, help="搜索关键词（不能为空）")
    parser.add_argument("--max_items", type=int, default=MAX_ITEMS, help="搜索关键词（正整数，建议 <= 500）")
    parser.add_argument("--headless", type=bool, default=HEADLESS, help="是否无头模式，默认为否")
    args = parser.parse_args()

    # 1. 派生关键词
    print(f">>>原始关键词: {args.key_word}")
    derived = brain.generate_keywords(args.key_word)
    all_keywords = derived
    print(f">>>全部关键词: {all_keywords}")

    # 2. 并行抓取每个关键词（带并发上限）
    saved_paths, failed_keywords = asyncio.run(
        _scrape_keywords_parallel(
            all_keywords,
            args.max_items,
            args.headless,
            max_concurrency=MAX_CONCURRENCY,
        )
    )
    if failed_keywords:
        print(f">>>以下关键词抓取失败（已跳过）: {failed_keywords}")
    if not saved_paths:
        raise RuntimeError("所有关键词抓取均失败，无法进入合并与分析阶段。")

    # 3. 合并数据
    if len(saved_paths) > 1:
        merged_path = _merge_jsonl(saved_paths, args.key_word, args.max_items)
        print(f">>>已合并 {len(saved_paths)} 个文件到: {merged_path}")
    else:
        merged_path = saved_paths[0]

    # 4. 统一分析
    print(f">>>开始分析数据: {merged_path}")
    brain.analyze_data(merged_path)