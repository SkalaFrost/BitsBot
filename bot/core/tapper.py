import asyncio
from datetime import datetime,timezone
import html
import json
import random
from urllib.parse import unquote
from dateutil import parser
import traceback
import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions import account
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName
from .agents import generate_random_user_agent
from bot.config import settings
from typing import Callable
import functools
from bot.utils import logger
from bot.utils.scripts import login_in_browser
from bot.exceptions import InvalidSession
from .headers import headers
from pyrogram.raw.types import InputBotAppShortName, InputNotifyPeer, InputPeerNotifySettings
import inspect
from .helper import format_duration,getCode

def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            caller_frame = inspect.stack()[1]
            caller_function_name = caller_frame.function
            
            logger.error(f"Error in function '{caller_function_name}': {e}")
            await asyncio.sleep(1)
    return wrapper

class Tapper:
    def __init__(self, tg_client: Client, lock: asyncio.Lock):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None
        self.lock = lock
        self.params = None

        self.session_ug_dict = self.load_user_agents() or []
        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.success(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
        
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()

                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
            
            while True:
                try:
                    peer = await self.tg_client.resolve_peer('bits')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")
                    await asyncio.sleep(fls + 3)
            
            ref_id = settings.REF_ID if random.randint(0, 100) <= 70 and settings.REF_ID != '' else "W9azPCfKHxDDGpxgZjWFCv"
            
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name="BitsAirdrops"),
                platform='android',
                write_allowed=True,
                start_param=ref_id
            ))

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            me = await self.tg_client.get_me()
            self.user_id = me.id

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return auth_url

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error: {error}")
            await asyncio.sleep(delay=3)
        
        
    async def join_and_mute_tg_channel(self, link: str):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
            
        parsed_link = link if 'https://t.me/+' in link else link[13:]
        try:
            try:
                chat = await self.tg_client.join_chat(parsed_link)
                logger.info(f"{self.session_name} | Successfully joined chat <y>{chat.title}</y>")
            except Exception as join_error:
                if "USER_ALREADY_PARTICIPANT" in str(join_error):
                    logger.info(f"{self.session_name} | Already a member of the chat: {link}")
                    chat = await self.tg_client.get_chat(parsed_link)
                else:
                    
                    raise join_error

            chat_id = chat.id
            chat_title = getattr(chat, 'title', link)

            await asyncio.sleep(random.randint(5, 10))

            peer = await self.tg_client.resolve_peer(chat_id)
            await self.tg_client.invoke(account.UpdateNotifySettings(
                peer=InputNotifyPeer(peer=peer),
                settings=InputPeerNotifySettings(mute_until=2147483647)
            ))
            logger.info(f"{self.session_name} | Successfully muted chat <y>{chat_title}</y>")

        except Exception as e:
            logger.error(f"{self.session_name} | Error joining/muting channel {link}: {str(e)}")

        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

        await asyncio.sleep(random.randint(10, 20))

    @error_handler
    async def make_request(self, http_client, method, endpoint=None, url=None, **kwargs):
        full_url = url or f"https://api-bits.apps-tonbox.me/api/v1{endpoint or ''}"
        response = await http_client.request(method, full_url, ssl = False, **kwargs)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return await response.json()
        else:
            return await response.text()
        
    @error_handler
    async def get_user(self, http_client):
       return await self.make_request(http_client, 'GET', endpoint="/me", params = self.params)
    
    @error_handler
    async def collect(self, http_client):
       return await self.make_request(http_client, 'GET', endpoint="/passive/collect",params = self.params)
    
    @error_handler
    async def start(self, http_client):
       return await self.make_request(http_client, 'GET', endpoint="/passive/start",params = self.params)
    
    @error_handler
    async def get_dailyReward(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/daily-reward",params = self.params)
    
    @error_handler
    async def collect_dailyReward(self, http_client,position):
        return await self.make_request(http_client, 'POST', endpoint=f"/daily-reward/{position}/collect",params = self.params)

    @error_handler
    async def get_locale(self, http_client):
        data = {"locale":"en"}
        return await self.make_request(http_client, 'POST', endpoint="/get_locale",params = self.params, json = data)

    @error_handler
    async def get_socialtasks(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/socialtasks",params = self.params)
    
    @error_handler
    async def get_referalIncome(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/referal_income",params = self.params)
    
    @error_handler
    async def collect_referalIncome(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/referal_income/collect",params = self.params)
    
    @error_handler
    async def start_socialtasks(self, http_client, task_name, adId = None):
        data = {"name":task_name,"adId":adId}

        return await self.make_request(http_client, 'POST'
                                       ,endpoint="/socialtask/start"
                                       ,params = self.params
                                       ,json = data)
    
    async def claim_socialtasks(self, http_client, task_name):
        data = {"name":task_name}

        return await self.make_request(http_client, 'POST'
                                       ,endpoint="/socialtask/claim"
                                       ,params = self.params
                                       ,json = data)
    
    @error_handler
    async def get_passive(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/passive",params = self.params)
    
    @error_handler
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        response = await self.make_request(http_client, 'GET', url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
        if response and response.get('origin',None):
            ip = response.get('origin',None)
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        else:
            logger.warning(f"{self.session_name} | Can't check proxy {proxy}")

    async def run(self, proxy: str | None) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)
        login_need = True

        while True:
            try: 
                if login_need:
                    auth_url = self.get_tg_web_data(proxy=proxy)
                    async with self.lock:
                        app_token, access_token, sid = await login_in_browser(auth_url, proxy=proxy)
                    if app_token and access_token and sid:
                        login_need = False  
                        http_client.headers['App-Token'] = app_token
                        http_client.headers['Sid'] = sid
                        self.params = {
                                        'access_token': access_token
                                    }
                    else: 
                        await asyncio.sleep(random.randint(500,600))
                        continue

                locale = await self.get_locale(http_client=http_client)

                get_user_res = await self.get_user(http_client=http_client)

                if get_user_res:
                    coins = get_user_res.get("coins",0)
                    totalInvitesIncome = get_user_res.get("totalInvitesIncome",0)
                    totalRewardsIncome = get_user_res.get("totalRewardsIncome",0)
                    totalTasksIncome = get_user_res.get("totalTasksIncome",0)
                    self.info(  f"Balance: <cyan>{coins}</cyan> - "
                                f"Total Invites Income: <cyan>{totalInvitesIncome}</cyan> - "
                                f"Total Rewards Income: <cyan>{totalRewardsIncome}</cyan> - "
                                f"Total Tasks Income: <cyan>{totalTasksIncome}</cyan>"
                            )
                    
                daily_reward_res = await self.get_dailyReward(http_client=http_client)
                if daily_reward_res and daily_reward_res.get('dailyRewards',[]):
                    for item in daily_reward_res.get('dailyRewards',[]):
                        if item.get("status") == "Waiting":
                            collect_reward_res = await self.collect_dailyReward(http_client = http_client,position = item.get("position"))
                            if collect_reward_res and collect_reward_res[-1].get("value",0):
                                amount  = collect_reward_res[-1].get("value",0)
                                self.success(f"Collect daily reward successfully, amount: <cyan>{amount}</cyan>")
                            else:
                                self.warning(f"Failed to collect daily reward")
                            break

                social_task = await self.get_socialtasks(http_client=http_client)
                code = getCode()
                if settings.AUTO_TASK and isinstance(social_task,list):
                    for task in social_task:
                        task_name = task["socialTask"]["name"]
                        desc = task["socialTask"]["description"]

                        desc_esc = html.escape(locale.get(desc)) if locale.get(desc) else " "
                        if task["socialTask"]["taskType"] in ["TonTransaction","Stars","JettonTransaction"] \
                                or task["socialTask"]["questId"] ==  "friends":
                            continue
        
                        if task["status"] == "None":
                            if "sub" in task_name and 't.me' in task["socialTask"]["data"]:
                                # await self.join_and_mute_tg_channel(task["socialTask"]["data"])
                                continue
                            Verify_code = None
                            if task["socialTask"]["taskType"] == "YoutubeVerify":
                                Verify_code = code.get(task_name,None)

                            start_task = await self.start_socialtasks(http_client=http_client,task_name = task_name,verify_code = Verify_code)
                            
                            if start_task:
                                self.info(f"Start task <cyan>{desc_esc}</cyan> successfully")
                            else: 
                                self.warning(f"Failed to start task <cyan>{desc_esc}</cyan>")
                            await asyncio.sleep(random.randint(2,10))

                        elif task["status"] == "Validated":
                            claim_task = await self.claim_socialtasks(http_client=http_client,task_name = task_name)
                            if claim_task and claim_task[-1].get("value"):
                                coins = claim_task[-1].get("value")
                                self.info(f"Task <cyan>{desc_esc}</cyan> is completed, get <cyan>{coins}</cyan> coins")
                            else: 
                                self.warning(f"Failed to complete task <cyan>{desc_esc}</cyan> (res: {claim_task})")

                            await asyncio.sleep(random.randint(2,10))

                referal_income_res = await self.get_referalIncome(http_client=http_client)
                if referal_income_res: 
                    total = referal_income_res.get("total",0)
                    if total > 0: 
                        collect_ref = await self.collect_referalIncome(http_client=http_client)
                        if collect_ref and collect_ref[0].get("value",None):
                            income = collect_ref[0].get("value",0)
                            self.info(f"Collect ref income successfully, total <cyan>{income}</cyan>")
                        else:
                            self.info(f"Failed to collect ref income")

                passiveIncome = await self.get_passive(http_client=http_client)
                if passiveIncome and passiveIncome.get("isStarted",None) == False:
                    await self.start(http_client=http_client)
                    self.info(f"Start farming!")

                elif passiveIncome and passiveIncome.get("isComplete",None) == True:
                    collect = await self.collect(http_client=http_client)
                    if collect and collect[0].get("value"):
                        self.info(f"Collect <cyan>{collect[0].get('value')}</cyan> coins successfully")
                    else:
                        self.warning("Failed to collect coins")
                
                passiveIncome = await self.get_passive(http_client=http_client)
                next_time = parser.isoparse(passiveIncome["next"])
                utc_now = parser.isoparse(passiveIncome["utcNow"])
                time_to_sleep = next_time - utc_now
                self.info(f"Sleep {format_duration(time_to_sleep.seconds)}")
                login_need = True
                await asyncio.sleep(time_to_sleep.seconds)

            except InvalidSession as error:
                raise error

            except Exception as error:
                self.error(f"Unknown error: {error} - traceback: {traceback.format_exc() }")
                await asyncio.sleep(delay=3)
            
            
async def run_tapper(tg_client: Client, proxy: str | None, lock: asyncio.Lock):
    try:
        await Tapper(tg_client=tg_client, lock=lock).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
