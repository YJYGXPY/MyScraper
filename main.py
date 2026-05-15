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

    # 2. 循环抓取每个关键词
    saved_paths: list[str] = []
    for kw in all_keywords:
        print(f"\n>>>开始爬取关键词: {kw}, 最大爬取数量: {args.max_items}")
        path = asyncio.run(scrape.scrape_xhs(kw, args.max_items, args.headless))
        saved_paths.append(path)

    # 3. 合并数据
    if len(saved_paths) > 1:
        merged_path = _merge_jsonl(saved_paths, args.key_word, args.max_items)
        print(f">>>已合并 {len(saved_paths)} 个文件到: {merged_path}")
    else:
        merged_path = saved_paths[0]

    # 4. 统一分析
    print(f">>>开始分析数据: {merged_path}")
    brain.analyze_data(merged_path)