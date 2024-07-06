import csv
import os
import discord
from util import log_helper, utility
from discord import app_commands as ap
import datetime
import atexit

token = os.getenv('ZERABOT_TOKEN')

logger = log_helper.get_logger(__name__)
if token is None:
    logger.error('Token not found. Please set the ZERABOT_TOKEN environment variable.')
    exit(1)
bot = discord.Client(intents=discord.Intents.all())
bot.tree = ap.CommandTree(bot)

should_stop = False
rows = []
last_import = 0
last_export = 0

@bot.event
async def on_ready():
    await utility.load_command_groups(bot, __name__)
    syncs = await bot.tree.sync()
    logger.debug(f'Syncs: {len(syncs)}')
    print(f'{bot.user} has connected to Discord!')

@ap.default_permissions()
class ArchiveToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='archivetools', description='Tools for archiving messages.')


class ExportToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='export', description='Tools for exporting messages.', parent=ArchiveToolsGroup())

    @ap.command(name='bot', description='Export messages to a csv *that is stored by the bot*.')
    @ap.default_permissions()
    async def csv_out(self, interaction: discord.Interaction):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion.',
                                                ephemeral=True)
        start_time = datetime.datetime.now()
        messages, total_messages, actually_fetched = await utility.fetch_messages(interaction)
        await utility.write_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages} in {total_time.total_seconds()} seconds.')
    
    @ap.command(name='user', description='Export messages to a csv *that is sent to you*.')
    @ap.default_permissions()
    async def csv_out_user(self, interaction: discord.Interaction):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion containing the output file. If the file is too large to be sent over discord, it will fallback to storing the file in the bot.',
                                                ephemeral=True)
        start_time = datetime.datetime.now()
        messages, total_messages, actually_fetched = await utility.fetch_messages(interaction)
        file = await utility.write_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages} in {total_time.total_seconds()} seconds.', file=file)


class ImportToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='import', description='Tools for importing messages.', parent=ArchiveToolsGroup())

    @ap.command(name='bot', description='Import messages from a csv *that was stored by the bot*.')
    @ap.default_permissions()
    async def csv_in(self, interaction: discord.Interaction, channel_id: str):
        global rows
        global should_stop
        global last_import

        if not channel_id.isnumeric():
            await interaction.response.send_message('Invalid channel id. (must be number)', ephemeral=True)
            return
        if os.path.exists('badexit.csv'):
            await interaction.response.send_message('There is an unresolved badexit.csv file. Please resolve it before continuing.', ephemeral=True)
            return

        channel_id = int(channel_id)
        filename = f'{channel_id}.csv' if not os.path.exists(f'{channel_id}_in_progress.csv') else f'{channel_id}_in_progress.csv'
        await interaction.response.send_message('Importing messages from csv.', ephemeral=True)

        with open(filename, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            await utility.handle_messages(reader, interaction, channel_id, bot, rows, last_import)
    
    @ap.command(name='user', description='Import messages from a csv *that is provided by you*.')
    @ap.default_permissions()
    async def csv_in_user(self, interaction: discord.Interaction, csv_file: discord.Attachment):
        global rows
        global should_stop
        global last_import
        if os.path.exists('badexit.csv'):
            await interaction.response.send_message('There is an unresolved badexit.csv file. Please resolve it before continuing.', ephemeral=True)
            return

        await interaction.response.send_message('Importing messages from csv.', ephemeral=True)
        
        file_byes = await csv_file.read()
        file_name = csv_file.filename
        file = file_byes.decode('utf-8')
        reader = csv.reader(iter(file.splitlines()))
        await utility.handle_messages(reader, interaction, file_name, bot, rows, last_import)
    
    @ap.command(name='cancel', description='Cancel the current import process.')
    @ap.default_permissions()
    async def cancel(self, interaction: discord.Interaction):
        utility.should_stop = True
        await interaction.response.send_message('Cancel flag set.', ephemeral=True)

def on_stop():
    global rows
    global last_import
    global last_export
    if rows:
        rows = rows[last_import:]
        with open(f'badexit.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for row in rows:
                    writer.writerow(row)
        logger.error('Unexpected exit. Wrote to badexit.csv.')

atexit.register(on_stop)

try:
    bot.run(token)
except Exception as e:
    logger.critical(f'Unexpected exit: {e}')
    on_stop()
    exit(1)