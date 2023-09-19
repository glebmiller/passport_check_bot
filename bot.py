from aiogram import Bot, Dispatcher, executor, types
import aiogram.utils.markdown as fmt
import pymongo
import re
import asyncio
import os
import os.path
import glob
import logging
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from time import sleep
from urllib.request import urlopen
from datetime import datetime
import time
from pytz import timezone
import random
import locale
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re
import requests
import aioschedule
import settings




storage = MemoryStorage()

bot = Bot(settings.bot_token)
dp = Dispatcher(bot, storage=storage)

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client.Passport_check
users = db.test_users

ANSWERS = ['Я сам пришлю сообщение, когда статус готовности паспорта изменится']

URL = "https://info.midpass.ru/api/request_ex/99501/"

greeting = """Это бот для проверки гражданами РФ статуса готовности своего заграничного паспорта при получении его в Секции интересов посольства Швейцарии в Тбилиси. 
"""

def check_if_first_time(chatid):
    check_user = list(users.find({"_id": chatid}))
    
    day = datetime.now(timezone('Asia/Tbilisi')).today()
    if len(check_user)>0:
        if day.date() == check_user[0]["day"].date():
            return False
        else:
            users.find_one_and_update({"_id": chatid}, {"$set": {"day": day}})
            return True
    else:
        query = {"_id": chatid, "day": day}
        users.insert_one(query)
        return True

def add_user_to_db(chatid: int) -> None:
    query = {"_id": chatid}
    users.insert_one(query)


def update_user(status_id: str, status_name: str, percent, chatid: int):
    users.find_one_and_update({"_id": chatid}, {"$set": {"status_id": status_id, "status": status_name, "percent": percent}})

def make_request(url: str):
    r = requests.get(url = url)
    data = r.json()
    #print(data)
    passportStatus_name = data[0]["passportStatus"]["name"]
    internalStatus_percent = data[0]["internalStatus"]["percent"]
    return passportStatus_name, internalStatus_percent


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user_to_db(message.chat.id)
    await bot.send_message(message.chat.id, greeting)
    await bot.send_message(message.chat.id, "Для проверки готовности введите /check номер справки, например, /check 123456")


@dp.message_handler(commands=['check'])
async def check(message: types.Message):
    status_id = message.text.replace("/check ", "")
    if status_id.isdigit():
        status_name, percent = make_request(URL + status_id)
        update_user(status_id, status_name, percent, message.chat.id)
        text = f"""Состояние: \n{status_name}\nготовность - {percent}%\nВы получите обновление по этой заявке автоматически"""
        await bot.send_message(message.chat.id, text)
    else:
        await bot.send_message(message.chat.id, "Неправильный формат номера справки!")


@dp.message_handler(commands=['print'])
async def print(message: types.Message): 
    chatid = message.chat.id
    check_user = list(users.find({"_id": chatid}))
    #print(check_user)
    text = f"""Состояние: \n{check_user[0]["status"]}\nготовность - {check_user[0]["percent"]}%"""
    await bot.send_message(message.chat.id, check_user[0])
    await bot.send_message(message.chat.id, text)


async def check_users():
    all_users = list(users.find())
    for user in all_users:
        #await print(user)
        try:
            old_percent = user["percent"]
            old_status = user["status"]
            new_status, new_percent = make_request(URL + user["status_id"])
            if old_status != new_status or old_percent != new_percent:
                update_user(user["status_id"], new_status, new_percent, user["_id"])
                text = f"""Состояние: \n{new_status}\nготовность - {new_percent}%\nВы получите обновление по этой заявке автоматически"""
                await bot.send_message(user["_id"], text)
        except:
            pass


async def scheduler():
    aioschedule.every().day.at("12:00").do(check_users)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)

async def on_startup(_):
    asyncio.create_task(scheduler())
    await check_users()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
