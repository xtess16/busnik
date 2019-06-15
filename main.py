"""
    :author: xtess16
"""
import getpass
import traceback

import keyring
from sqlalchemy.orm import session

import core
from vk_api_shell import vk_bot

SPIDER = core.Spider()
BOT = vk_bot.Bot(SPIDER)

while True:
    TOKEN = keyring.get_password('busnik.group_token', getpass.getuser())
    if TOKEN is None or not BOT.auth(TOKEN):
        keyring.set_password(
            'busnik.group_token',
            getpass.getuser(), getpass.getpass('Group token: ')
        )
    else:
        break

while True:
    try:
        BOT.longpoll_listen()
    except KeyboardInterrupt:
        session.close_all_sessions()
        print('\nЗавершено')
        break
    except Exception:
        print(traceback.format_exc())
        SPIDER.db_session().rollback()
