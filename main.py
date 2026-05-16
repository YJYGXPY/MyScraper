import argparse
import asyncio
import json
import os
from datetime import datetime
import scrape
import brain

# 可修改配置
KEYWORD = "羽毛球鞋" # 搜索关键词[***脚本参数***]
MAX_ITEMS = 10 # 最大爬取数量[***内部配置***]
HEADLESS = False # 是否无头模式[***内部配置***]
MAX_CONCURRENCY = 5 # 并行抓取关键词数量上限[***内部配置***]

# 常量
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


def run_pipeline(keyword: str) -> str:
    '''
    执行完整抓取与分析流程
    Args:
        keyword: 原始关键词
    Returns:
        str: 合并后的数据路径
    '''
    # 1. 派生关键词
    print(f">>>原始关键词: {keyword}")
    derived = brain.generate_keywords(keyword)
    all_keywords = derived
    print(f">>>全部关键词: {all_keywords}")

    # 2. 并发前统一登录预检
    print(f">>>开始登录预检")
    asyncio.run(scrape.ensure_login_ready(headless=HEADLESS))
    print(f">>>登录预检完成")

    # 3. 并行抓取每个关键词（带并发上限）
    saved_paths, failed_keywords = asyncio.run(
        _scrape_keywords_parallel(
            all_keywords,
            MAX_ITEMS if MAX_ITEMS <= len(all_keywords) else len(all_keywords),
            HEADLESS,
            max_concurrency=MAX_CONCURRENCY,
        )
    )
    if failed_keywords:
        print(f">>>以下关键词抓取失败（已跳过）: {failed_keywords}")
    if not saved_paths:
        raise RuntimeError("所有关键词抓取均失败，无法进入合并与分析阶段。")

    # 4. 合并数据
    if len(saved_paths) > 1:
        merged_path = _merge_jsonl(saved_paths, keyword, MAX_ITEMS)
        print(f">>>已合并 {len(saved_paths)} 个文件到: {merged_path}")
    else:
        merged_path = saved_paths[0]

    # 5. 统一分析
    print(f">>>开始分析数据: {merged_path}")
    brain.analyze_data(merged_path)
    return merged_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书爬虫")
    parser.add_argument("key_word", type=str, nargs="?", default=KEYWORD, help="你想探索的方向（关键词）")
    args = parser.parse_args()
    run_pipeline(args.key_word)