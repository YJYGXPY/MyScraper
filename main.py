import asyncio
import os
import re
from playwright.async_api import BrowserContext , async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# 配置
STATE_PATH = "state.json" # 登录态保存路径
URL = "https://www.xiaohongshu.com/explore" # 首页URL
KEYWORD = "羽毛球鞋" # 搜索关键词
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

async def _iter_note_items_once(page: Page)->list[dict]:
    '''
    爬取一次数据
    Args:
        page: 页面对象
    '''
    # 等待列表出现
    await page.wait_for_selector(".feeds-container section.note-item")
    items = page.locator(".feeds-container section.note-item")
    count = await items.count()
    print(f"当前可见 note-item 数量: {count}")

    for i in range(count):
        item = items.nth(i)
        await item.click()

        close_button = page.locator(".close").first
        await close_button.wait_for(state="visible")

        title_text = page.locator("#detail-title")
        if await title_text.count() > 0:
            title = await title_text.inner_text()
            print(f"{i+1}-标题: {title}")
        else:
            print(f"{i+1}-未找到标题")

        # 关闭弹窗详情页
        await close_button.click()
        await close_button.wait_for(state="hidden")
        
    return []

async def _search_keyword(page: Page, keyword: str):
    '''
    搜索关键词
    Args:
        page: 页面对象
        keyword: 搜索关键词
    '''    
    search_input = page.get_by_role("textbox", name="搜索小红书")
    await search_input.fill(keyword)
    await search_input.press("Enter")

    filter_button = page.locator("div").filter(
        has_text=re.compile(r"^筛选$")
    )
    await filter_button.hover()

    # 发布时间筛选（默认一天内）
    time_filter = page.locator(".filters").filter(has_text="发布时间").first
    filter_1day = time_filter.locator(".tags:not([aria-hidden='true'])").filter(has_text="一天内").first
    await filter_1day.click()

    # 爬取数据
    items = await _iter_notes(page, max_items=30, max_idle_rounds=2)

async def _iter_notes(page, max_items=100, max_idle_rounds=3)->list[dict]:
    '''
    爬取数据
    Args:
        page: 页面对象
        max_items: 最大爬取数量
        max_idle_rounds: 最大空闲轮次
    Returns:
        list[dict]: 爬取数据
            id: 笔记ID
            title: 笔记标题
    '''
    await page.wait_for_selector(".feeds-container section.note-item")
    feed = page.locator(".feeds-container").first
    seen_ids = set()
    results = []
    idle_rounds = 0
    while len(results) < max_items and idle_rounds < max_idle_rounds:
        before = len(seen_ids)
        cards = page.locator(".feeds-container section.note-item")
        total_count = await cards.count()

        for i in range(total_count):
            card = cards.nth(i)
            in_viewport = await card.evaluate(
                """(el) => {
                    const feed = document.querySelector(".feeds-container");
                    if (!feed) return false;
                    const r = el.getBoundingClientRect();
                    const f = feed.getBoundingClientRect();
                    return r.bottom > f.top && r.top < f.bottom && r.right > f.left && r.left < f.right;
                }"""
            )
            if not in_viewport:
                continue

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
            
            seen_ids.add(note_id)

            await card.scroll_into_view_if_needed()
            await card.click()

            try:
                close_button = page.locator(".close").first
                await close_button.wait_for(state="visible", timeout=2500)
            except PlaywrightTimeoutError:
                continue

            title = None
            try:
                await page.wait_for_selector("#detail-title", timeout=2000)
                title = (await page.locator("#detail-title").inner_text()).strip()
            except PlaywrightTimeoutError:
                pass

            results.append({"id": note_id, "title": title})

            print(f"{len(results)} - {title or '未找到标题'}")
            
            await close_button.click()
            await close_button.wait_for(state="hidden", timeout=2500)

            if len(results) >= max_items:
                break

        # 当前视口处理完后再滚动，触发下一批数据渲染
        await feed.evaluate("el => el.scrollBy(0, Math.floor(el.clientHeight * 0.9))")
        await page.wait_for_timeout(700)
        idle_rounds = idle_rounds + 1 if len(seen_ids) == before else 0
    return results


async def _scrape():
    '''
    爬取数据（）
    '''
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False, 
            slow_mo=50,
            # args=["--auto-open-devtools-for-tabs"]
        )

        context = await _load_login_info(STATE_PATH, browser)
        page = await context.new_page()
        await page.goto(URL)

        if await _need_login(page):await _login_by_msg(page)

        # 搜索关键词
        await _search_keyword(page, KEYWORD)

if __name__ == "__main__":
    asyncio.run(_scrape())