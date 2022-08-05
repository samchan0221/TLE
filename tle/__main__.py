import argparse
import asyncio
import distutils.util
import logging
import os
import base64
import disnake
import topgg

from logging.handlers import TimedRotatingFileHandler
from os import environ
from pathlib import Path
from json import loads
from os import environ
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage

STORAGE_BUCKET = str(environ.get('STORAGE_BUCKET'))
bucket = None

if STORAGE_BUCKET!='None':
    cred = credentials.Certificate(loads(base64.b64decode(environ.get('FIREBASE_ADMIN_JSON')).decode('UTF-8')))
    firebase_admin.initialize_app(cred, {
        'storageBucket': STORAGE_BUCKET
    })
    bucket = storage.bucket()

import seaborn as sns
from disnake.ext import commands
from matplotlib import pyplot as plt

from tle import constants
from tle.util import codeforces_common as cf_common
from tle.util import discord_common, font_downloader
from tle.util import clist_api

import discord
from discord.ext import commands as dommands

def setup():
    # Make required directories.
    for path in constants.ALL_DIRS:
        os.makedirs(path, exist_ok=True)
    
    # Update the user.db file from firebase
    if bucket!=None:
        try:
            user = bucket.blob('tle.db')
            user.download_to_filename(constants.USER_DB_FILE_PATH)
        except:
            # File is not present in Firebase Storage
            pass

        try:
            cache = bucket.blob('tle_cache.db')
            cache.download_to_filename(constants.CACHE_DB_FILE_PATH)
        except:
            # File is not present in Firebase Storage
            pass

    # logging to console and file on daily interval
    logging.basicConfig(format='{asctime}:{levelname}:{name}:{message}', style='{',
                        datefmt='%d-%m-%Y %H:%M:%S', level=logging.INFO,
                        handlers=[logging.StreamHandler(),
                                  TimedRotatingFileHandler(constants.LOG_FILE_PATH, when='D',
                                                           backupCount=3, utc=True)])

    # matplotlib and seaborn
    plt.rcParams['figure.figsize'] = 7.0, 3.5
    sns.set()
    options = {
        'axes.edgecolor': '#A0A0C5',
        'axes.spines.top': False,
        'axes.spines.right': False,
    }
    sns.set_style('darkgrid', options)

    # Download fonts if necessary
    font_downloader.maybe_download()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nodb', action='store_true')
    args = parser.parse_args()

    token = environ.get('BOT_TOKEN')
    if not token:
        logging.error('Token required')
        return

    allow_self_register = environ.get('ALLOW_DUEL_SELF_REGISTER')
    if allow_self_register:
        constants.ALLOW_DUEL_SELF_REGISTER = bool(distutils.util.strtobool(allow_self_register))

    setup()
    
    intents = disnake.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix=commands.when_mentioned_or(';'), intents=intents)

    cogs = [file.stem for file in Path('tle', 'cogs').glob('*.py')]
    for extension in cogs:
        bot.load_extension(f'tle.cogs.{extension}')
    logging.info(f'Cogs loaded: {", ".join(bot.cogs)}')

    # cf_common.initialize needs to run first, so it must be set as the bot's
    # on_ready event handler rather than an on_ready listener.
    @discord_common.on_ready_event_once(bot)
    async def init():
        clist_api.cache()
        await cf_common.initialize(args.nodb)
        asyncio.create_task(discord_common.presence(bot))

    async def no_dm_check(inter):
        if inter.guild is None:
            await inter.response.send_message('Slash command in DM is not permitted.')
            return False
        return True

    intents = discord.Intents.default()
    guild_count = dommands.Bot(command_prefix=dommands.when_mentioned_or(';'), intents=intents)
    guild_count.topggpy = topgg.DBLClient(guild_count, environ.get('TOPGG_TOKEN'))

    @tasks.loop(minutes=5)
    async def update_stats():
        try:
            await guild_count.topggpy.post_guild_count()
            logging.info(f"Posted server count ({guild_count.topggpy.guild_count})")
        except Exception as e:
            logging.info(f"Failed to post server count\n{e.__class__.__name__}: {e}")

    update_stats.start()
    
    # Restrict bot usage to inside guild channels only.
    bot.add_app_command_check(no_dm_check, slash_commands = True)

    bot.add_listener(discord_common.bot_error_handler, name='on_slash_command_error')
    bot.run(token)
    guild_count.run(token)

if __name__ == '__main__':
    main()
