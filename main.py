import getpass
import traceback

import core
from vk_api_shell import vk_bot
import keyring
from sqlalchemy.orm import session
spider = core.Spider()

bot = vk_bot.Bot(spider)

while True:
    token = keyring.get_password('busnik.group_token', getpass.getuser())
    if token is None or not bot.auth(token):
        keyring.set_password(
            'busnik.group_token',
            getpass.getuser(), getpass.getpass('Group token: ')
        )
    else:
        break
while True:
    try:
        bot.longpoll_listen()
    except KeyboardInterrupt:
        session.close_all_sessions()
        break
    except Exception as e:
        print(traceback.format_exc())
        break
