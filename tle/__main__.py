import argparse
import asyncio
import distutils.util
import logging
import os
import base64
import discord
from logging.handlers import TimedRotatingFileHandler
from os import environ
from pathlib import Path
from json import loads
from os import environ
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage

import tle.embed_handler as embed_handler

STORAGE_BUCKET = str(environ.get('STORAGE_BUCKET'))
bucket = None
if STORAGE_BUCKET!='None':
    cred = credentials.Certificate(loads(base64.b64decode(environ.get('FIREBASE_ADMIN_JSON')).decode('UTF-8')))
    firebase_admin.initialize_app(cred, {
        'storageBucket': STORAGE_BUCKET
    })
    bucket = storage.bucket()

import seaborn as sns
from discord.ext import commands
from matplotlib import pyplot as plt

from tle import constants
from tle.util import codeforces_common as cf_common
from tle.util import discord_common, font_downloader
from tle.util import clist_api

prefix = ';'

bot = commands.Bot(command_prefix=commands.when_mentioned_or(prefix), intents=intents)

def setup():
    # Make required directories.
    for path in constants.ALL_DIRS:
        os.makedirs(path, exist_ok=True)
    
    # Update the user.db file from firebase
    if bucket!=None:
        try:
            blob = bucket.blob('tle.db')
            blob.download_to_filename(constants.USER_DB_FILE_PATH)
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

class CustomHelp(commands.HelpCommand):

    async def send_bot_help(self, mapping):

        cogs = {}

        embed = embed_handler.single_message(bot, "Help")
        embed.title = "Commands list"

        for cog in bot.cogs:
            embed.add_field(name = f"{cog}", value = "`" + "`, `".join(cmd.name for cmd in bot.cogs[cog].walk_commands()) + "`", inline = False)     

        embed.add_field(name = f"Use `{prefix}help <command/category>` for more info.", value = "\u200b", inline = False)

        await self.context.reply(embed = embed, mention_author = False)

    async def send_command_help(self, command):
 
        embed = embed_handler.single_message(bot, "Help")

        embed.title = self.get_command_signature(command)
        embed.add_field(name = "Description", value = command.description)

        if command.aliases:
            embed.add_field(name = "Aliases", value = "`" + "`, `".join(command.aliases) + "`", inline = False)
        else:
            embed.add_field(name = "Aliases", value = "No alias", inline = False)

        await self.context.reply(embed = embed, mention_author = False)

    async def send_cog_help(self, cog):

        embed = embed_handler.single_message(bot, "Help")

        embed.title = cog.qualified_name
        embed.description = "\n".join(f'`{command.qualified_name}`ㅤㅤㅤ{command.brief}' for command in cog.walk_commands())

        await self.context.reply(embed = embed, mention_author = False)

    async def send_error_message(self, error):

        embed = embed_handler.single_message(bot, "Command or cog not found")
        
        if str(error).startswith("No command called"):

            command = error.split(" ")[3].replace('"', '')

            embed.description = f'Command or cog named `{command}` not found.'

            await self.context.reply(embed = embed, mention_author = False)

        else:

            embed = embed_handler.single_message(bot, "Unknown error occured")

            embed.description = f'```py{str(error)}```'
            embed.title = "An error occurred."

            await self.context.reply(embed = embed, mention_author = False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nodb', action='store_true')
    args = parser.parse_args()

    token = "OTc5NzU5NTI5MTc0NjYzMzA4.GQbfZe.M4sVGsGGvlULzTjXkK1SJTaS2Os8NjGosCNJ44"
    if not token:
        logging.error('Token required')
        return

    allow_self_register = environ.get('ALLOW_DUEL_SELF_REGISTER')
    if allow_self_register:
        constants.ALLOW_DUEL_SELF_REGISTER = bool(distutils.util.strtobool(allow_self_register))

    setup()
    
    intents = discord.Intents.default()
    intents.members = True

    bot.help_command = CustomHelp()

    cogs = [file.stem for file in Path('tle', 'cogs').glob('*.py')]
    for extension in cogs:
        bot.load_extension(f'tle.cogs.{extension}')
    logging.info(f'Cogs loaded: {", ".join(bot.cogs)}')

    def no_dm_check(ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('Private messages not permitted.')
        return True
    
    def ban_check(ctx):
        banned = cf_common.user_db.get_banned_user(ctx.author.id)
        if banned is None:
            return True
        return False

    # Restrict bot usage to inside guild channels only.
    bot.add_check(no_dm_check)
    bot.add_check(ban_check)

    # cf_common.initialize needs to run first, so it must be set as the bot's
    # on_ready event handler rather than an on_ready listener.
    @discord_common.on_ready_event_once(bot)
    async def init():
        clist_api.cache()
        await cf_common.initialize(args.nodb)
        asyncio.create_task(discord_common.presence(bot))

    bot.add_listener(discord_common.bot_error_handler, name='on_command_error')
    bot.run(token)


if __name__ == '__main__':
    main()
