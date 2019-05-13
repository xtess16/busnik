import getpass

import core
import vk_bot
import keyring

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

bot.longpoll_listen()
