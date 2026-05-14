import argparse
import asyncio
import scrape

# 可修改配置
KEYWORD = "羽毛球鞋" # 搜索关键词[***脚本参数***]
MAX_ITEMS = 30 # 最大爬取数量[***脚本参数***]
HEADLESS = False # 是否无头模式[***脚本参数***]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书爬虫")
    parser.add_argument("--key_word", type=str, default=KEYWORD, help="搜索关键词（不能为空）")
    parser.add_argument("--max_items", type=int, default=MAX_ITEMS, help="最大爬取数量（正整数，建议 <= 500）")
    parser.add_argument("--headless", type=bool, default=HEADLESS, help="是否无头模式，默认为否")
    args = parser.parse_args()
    print(f"开始爬取关键词: {args.key_word}, 最大爬取数量: {args.max_items}")

    asyncio.run(scrape.scrape_xhs(args.key_word, args.max_items, args.headless))
