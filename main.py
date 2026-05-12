import argparse
import asyncio
from datetime import datetime
import json
import os
import re
from playwright.async_api import BrowserContext , async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# 配置
STATE_PATH = "state.json" # 登录态保存路径
DATA_PATH = "data/" # 数据保存路径
URL = "https://www.xiaohongshu.com/explore" # 首页URL
KEYWORD = "羽毛球鞋" # 搜索关键词
MAX_ITEMS = 30 # 最大爬取数量
MAX_IDLE_ROUNDS = 3 # 最大空闲轮次
TIME_FILTER = ["一天内", "一周内", "半年内", "不限"] # 发布时间筛选

async def _need_login(page: Page) -> bool:
    '''
    判断是否需要登录
    Args:
        page: 页面对象
    Returns:
        bool: 是否需要登录
    '''
    await page.wait_for_load_state("domcontentloaded")

    # 只要看到任一登录相关元素，就认为需要登录
    login_signals = [
        page.get_by_text("获取验证码"),
        page.get_by_placeholder("输入验证码"),
        page.locator("form").get_by_role("button", name="登录"),
    ]

    for loc in login_signals:
        try:
            if await loc.first.is_visible(timeout=1500):
                return True
        except Exception:
            pass

    return False

async def _save_login_info(state_path: str, page: Page):
    '''
    保存登录信息
    Args:
        state_path: 保存登录信息的文件路径
    '''
    await page.context.storage_state(path=state_path)
    print(f"登录态已保存到 {state_path}")

async def _load_login_info(state_path: str, browser: BrowserContext)-> BrowserContext:
    '''
    加载登录信息
    Args:
        state_path: 加载登录信息的文件路径
        browser: 浏览器对象
    Returns:
        Context: 上下文对象
    '''
    if os.path.exists(state_path):
        context = await browser.new_context(storage_state=state_path)
        print("已加载本地登录态")
    else:
        context = await browser.new_context()
        print("未加载本地登录态")
    return context

async def _wait_login_success(page: Page, timeout_ms: int = 20000) -> bool:
    '''
    等待登录成功
    Args:
        page: 页面对象
        timeout_ms: 超时时间
    Returns:
        bool: 是否登录成功
    '''
    # 登录表单相关元素（你现有代码里已有）
    code_input = page.get_by_placeholder("输入验证码")

    # 登录后信号（请按页面真实 DOM 调整一个最稳定的）
    logged_in_signals = [
        page.get_by_role("link", name="我", exact=True), # 个人主页入口
    ]
    # 先尝试等待“登录表单消失”
    try:
        await code_input.wait_for(state="hidden", timeout=timeout_ms)
    except TimeoutError:
        pass

    # 检查任一“已登录信号”
    for loc in logged_in_signals:
        try:
            await loc.wait_for(state="visible", timeout=3000)
            return True
        except TimeoutError :
            continue
    return False

async def _login_by_msg(page: Page):
    '''
    登录信息
    Args:
        page: 页面对象
    '''
    # Step1: 输入手机号
    # 1. 等待验证码输入框出现
    phone_input = page.get_by_placeholder("输入手机号")
    # 2. 人工输入
    print(">>> 请输入手机号")
    phone = input("验证码: ")
    # 3. 填入页面
    await phone_input.fill(phone)

    # Step2: 同意用户隐私
    await page.locator(".icon-wrapper").first.click()

    # Step3: 点击获取验证码
    await page.get_by_text("获取验证码").click()

    # Step4: 输入验证码
    # 1. 等待验证码输入框出现
    captcha_input = page.get_by_placeholder("输入验证码")
    # 2. 人工输入（你之前问过的场景）
    print(">>> 请输入短信验证码")
    code = input("验证码: ")
    # 3. 填入页面
    await captcha_input.fill(code)

    # Step5: 点击登录
    await page.locator("form").get_by_role("button", name="登录").click()

    # Step6: 等待登录成功
    ok = await _wait_login_success(page)
    if not ok:
        raise RuntimeError("登录未成功，请检查验证码或页面选择器")
    
    # Step7: 保存登录信息
    print(">>>登录成功")
    await _save_login_info(STATE_PATH,page)

def _safe_filename(text: str) -> str:
    '''
    安全文件名
    Args:
        text: 文本
    Returns:
        str: 安全文件名
    '''
    # Windows 文件名非法字符替换
    return re.sub(r'[\\/:*?"<>|]', "_", text).strip()

def _save_items_to_jsonl(items: list[dict], keyword: str, max_items: int, data_path: str = DATA_PATH) -> str:
    '''
    保存数据到jsonl文件
    Args:
        items: 数据列表
        keyword: 搜索关键词
        max_items: 最大爬取数量
        data_path: 数据保存路径
    Returns:
        str: 文件路径
    '''
    os.makedirs(data_path, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = _safe_filename(keyword)
    filename = f"xhs_{safe_keyword}_{max_items}_{ts}.jsonl"
    filepath = os.path.join(data_path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return filepath

async def _search_keyword(page: Page, keyword: str, max_items: int = MAX_ITEMS, max_idle_rounds: int = MAX_IDLE_ROUNDS):
    '''
    搜索关键词
    Args:
        page: 页面对象
        keyword: 搜索关键词
        max_items: 最大爬取数量
        max_idle_rounds: 最大空闲轮次
    '''
    search_input = page.get_by_role("textbox", name="搜索小红书")
    await search_input.fill(keyword)
    await search_input.press("Enter")

    # filter_button = page.locator("div").filter(
    #     has_text=re.compile(r"^筛选$")
    # )
    # await filter_button.hover()

    # 发布时间筛选（默认一天内）
    # time_filter = page.locator(".filters").filter(has_text="发布时间").first
    # filter_1day = time_filter.locator(".tags:not([aria-hidden='true'])").filter(has_text="一天内").first
    # await filter_1day.click()

    # 爬取数据
    items = await _iter_notes(page, max_items=max_items, max_idle_rounds=max_idle_rounds)
    
    # 保存数据
    saved_path = _save_items_to_jsonl(items, keyword, max_items)
    print(f"已保存 {len(items)} 条到: {saved_path}")

async def _iter_notes(page, max_items=MAX_ITEMS, max_idle_rounds=MAX_IDLE_ROUNDS)->list[dict]:
    '''
    爬取数据
    Args:
        page: 页面对象
        max_items: 最大爬取数量
        max_idle_rounds: 最大空闲轮次
    Returns:
        list[dict]: 爬取数据
            index: 序号
            id: 笔记ID(假)
            author: 作者
            description: 笔记内容
            tag_description: 笔记tag
            time_location: 时间地点
            title: 笔记标题
    '''
    await page.wait_for_selector(".feeds-container section.note-item")
    seen_ids = set()
    results = []
    idle_rounds = 0

    while len(results) < max_items and idle_rounds < max_idle_rounds:
        before = len(seen_ids)
        cards = page.locator(".feeds-container section.note-item")
        total_count = await cards.count()
        
        for i in range(total_count):
            card = cards.nth(i)

            # 只处理当前视口内的新卡片：优先用 href
            note_id = await card.evaluate(
                """(el) => {
                    const anchor = el.querySelector("a[href^='/explore/']");
                    if (anchor) {
                        return anchor.getAttribute("href");
                    }
                    return "";
                }"""
            )
            if note_id == "" or note_id in seen_ids:
                continue
            
            # 获取note_id
            seen_ids.add(note_id)

            # 获取详情的数据
            await card.click()
            try:
                close_button = page.locator(".close").first
                await close_button.wait_for(state="visible", timeout=2500)
            except PlaywrightTimeoutError:
                continue
            try:
                # 获取标题
                title_dom = page.locator("#detail-title")
                title = ""
                if await title_dom.count() > 0:
                    title = (await title_dom.inner_text()).strip() 

                # 作者
                author_dom = page.locator("div.author-container span.username")
                author = (await author_dom.inner_text()).strip() if await author_dom.count() > 0 else ""
                    
                # 笔记内容
                content_container = page.locator("#detail-desc span.note-text")
                description_dom_list = content_container.locator(":scope > span")
                description_dom_count = await description_dom_list.count()
                description = ""
                for i in range(description_dom_count):
                    description_dom = description_dom_list.nth(i)
                    description += (await description_dom.inner_text()).strip() + " "
                description = description.strip() if description else ""  

                # 笔记tag
                tag_doms = page.locator("#detail-desc").locator("a.tag")
                tag_count = await tag_doms.count()
                tag_description = ""
                for i in range(tag_count):
                    tag_dom = tag_doms.nth(i)
                    tag_name = (await tag_dom.inner_text()).strip()
                    tag_description += tag_name + " "
                tag_description = tag_description.strip() if tag_description else ""

                # 时间地点
                time_location_dom = page.locator("div.bottom-container span.date")
                time_location = (await time_location_dom.inner_text()).strip() if await time_location_dom.count() > 0 else ""

                # 获取数据
                results.append({
                    "index": len(results) + 1,
                    "id": note_id, 
                    "title": title,
                    "author": author,
                    "description": description,
                    "tag_description": tag_description,
                    "time_location": time_location
                    }
                )
                print(f"{results[-1]}")
            except PlaywrightTimeoutError:
                continue
            
            # 关闭详情
            if await close_button.is_visible():
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            
            if len(results) >= max_items:
                break

            await card.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)

        idle_rounds = idle_rounds + 1 if len(seen_ids) == before else 0
    return results

async def _scrape(keyword: str, max_items: int, headless: bool):
    '''
    爬取数据（）
    Args:
        keyword: 搜索关键词
        max_items: 最大爬取数量
        headless: 是否无头模式
    '''
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless, 
            slow_mo=50,
            # args=["--auto-open-devtools-for-tabs"]
        )

        context = await _load_login_info(STATE_PATH, browser)
        page = await context.new_page()
        await page.goto(URL)

        if await _need_login(page):await _login_by_msg(page)

        # 搜索关键词
        await _search_keyword(page, keyword=keyword, max_items=max_items, max_idle_rounds=MAX_IDLE_ROUNDS)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书爬虫")
    parser.add_argument("--key_word", type=str, default=KEYWORD, help="搜索关键词（不能为空）")
    parser.add_argument("--max_items", type=int, default=MAX_ITEMS, help="最大爬取数量（正整数，建议 <= 500）")
    parser.add_argument("--headless", type=bool, default=False, help="是否无头模式，默认为否")
    args = parser.parse_args()
    print(f"开始爬取关键词: {args.key_word}, 最大爬取数量: {args.max_items}")

    asyncio.run(_scrape(args.key_word, args.max_items, args.headless))
