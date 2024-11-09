import asyncio
from urllib.parse import unquote
from annotated_types import LowerCase
from playwright.async_api import async_playwright,expect
from better_proxy import Proxy
import random
import time
from urllib.parse import urlparse, parse_qs

async def login_in_browser(auth_url: str,  proxy: str | None = None ,user_agent: str | None = None) -> tuple[str, str, str]:
    if proxy:
           proxy_con = Proxy(proxy).as_playwright_proxy()
    else:
        proxy_con = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True) 

            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 600, "height": 800},
                proxy=proxy_con,
            )
            page = await context.new_page()

            app_token, access_token, sid = None, None, None

            async def handle_request(request):
                nonlocal app_token, access_token, sid
                
                parsed_url = urlparse(request.url)
                query_params = parse_qs(parsed_url.query)

                if "https://api-bits.apps-tonbox.me/api/v1/me" in request.url and 'access_token' in query_params:
                    access_token = query_params.get("access_token",[])[0]
                
                    headers = request.headers
                    app_token = headers.get('app-token') or headers.get('App-Token')
                    sid = headers.get('sid', '') or headers.get('Sid', '')

            page.on("request", handle_request)
            await page.goto(auth_url)

            await page.wait_for_timeout(3000)
            # next_btn = page.get_by_role("button",name = "Next")
            # await next_btn.wait_for(state='visible', timeout=10000)
            # await browser.close()

            return app_token, access_token, sid
