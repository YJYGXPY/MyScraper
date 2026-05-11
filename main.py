import asyncio
import re
import os
from playwright.async_api import BrowserContext , async_playwright, Page

STATE_PATH = "state.json"
URL = "https://www.xiaohongshu.com/explore"

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

async def _scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False, 
            slow_mo=50,
            # args=["--auto-open-devtools-for-tabs"]
        )

        page = await _load_login_info(STATE_PATH, browser).new_page()
        await page.goto(URL)

        if await _need_login(page):await _login_by_msg(page)

        await page.pause()

if __name__ == "__main__":
    asyncio.run(_scrape())