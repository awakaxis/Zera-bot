import csv
import os
import discord
from util import log_helper, utility
from discord import app_commands as ap
from data import embeds as em
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
    await bot.change_presence(activity=discord.CustomActivity(name='Standby'))

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
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion.', ephemeral=True)
        await bot.change_presence(activity=discord.CustomActivity(name='Exporting messages...'))
        start_time = datetime.datetime.now()
        messages, total_messages, actually_fetched = await utility.fetch_messages(interaction)
        await utility.write_messages_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages} in {total_time.total_seconds()} seconds.')
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))
    
    @ap.command(name='user', description='Export messages to a csv *that is sent to you*.')
    @ap.default_permissions()
    async def csv_out_user(self, interaction: discord.Interaction):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion containing the output file. If the file is too large to be sent over discord, it will fallback to storing the file in the bot.', ephemeral=True)
        await bot.change_presence(activity=discord.CustomActivity(name='Exporting messages...'))
        start_time = datetime.datetime.now()
        messages, total_messages, actually_fetched = await utility.fetch_messages(interaction)
        file = await utility.write_messages_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages} in {total_time.total_seconds()} seconds.', file=file)
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))

    @ap.command(name='forum', description='Export a forum channel and all of it\'s threads. Due to complexity, no user option is available.')
    @ap.default_permissions()
    async def forum_out(self, interaction: discord.Interaction, channel: discord.ForumChannel):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion.', ephemeral=True)
        await bot.change_presence(activity=discord.CustomActivity(name='Exporting forum...'))
        start_time = datetime.datetime.now()
        total_total_messages = 0
        total_total_fetched = 0
        with open(f'{channel.id}_forum_data.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            encoded_tags = [await utility.forum_tag_to_dict(tag, interaction.guild) for tag in channel.available_tags]
            writer.writerow([channel.name, encoded_tags, channel.default_reaction_emoji if type(channel.default_reaction_emoji) == str or not channel.default_reaction_emoji else await interaction.guild.fetch_emoji(channel.default_reaction_emoji.id), channel.topic])
            total_threads = 0
            for thread in channel.threads:
                total_threads += 1
                owner = await bot.fetch_user(thread.owner_id)
                encoded_applied_tag_names = [tag.name for tag in thread.applied_tags]
                writer.writerow([thread.id, thread.name, 1 if thread.locked else 0, owner.name if owner else 'Unknown', encoded_applied_tag_names])
                messages, total_messages, actually_fetched = await utility.fetch_messages(thread)
                total_total_messages += total_messages
                total_total_fetched += actually_fetched
                await utility.write_messages_csv(messages, f'{thread.id}.csv')
            async for thread in channel.archived_threads():
                total_threads += 1
                owner = await bot.fetch_user(thread.owner_id)
                encoded_applied_tag_names = [tag.name for tag in thread.applied_tags]
                writer.writerow([thread.id, thread.name, 1 if thread.locked else 0, owner.name if owner else 'Unknown', encoded_applied_tag_names])
                messages, total_messages, actually_fetched = await utility.fetch_messages(thread)
                total_total_messages += total_messages
                total_total_fetched += actually_fetched
                await utility.write_messages_csv(messages, f'{thread.id}.csv')

        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(f'Fetched and exported {total_threads} threads from `{channel.name}` ({channel.id}) in {total_time.total_seconds()} seconds.\nTotal message count: {total_total_fetched}, Total fetched: {total_total_fetched}')
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))



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
        
        await bot.change_presence(activity=discord.CustomActivity(name='Importing messages...'))
        with open(filename, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            await utility.handle_messages(reader, interaction, interaction.channel, channel_id, bot, rows, last_import)
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))
    
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
        await bot.change_presence(activity=discord.CustomActivity(name='Importing messages...'))
        file_byes = await csv_file.read()
        file_name = csv_file.filename
        file = file_byes.decode('utf-8')
        reader = csv.reader(iter(file.splitlines()))
        await utility.handle_messages(reader, interaction, interaction.channel, file_name, bot, rows, last_import)
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))

    @ap.command(name='forum', description='Import a forum channel and all of it\'s threads. Due to complexity, no user option is available.')
    @ap.default_permissions()
    async def forum_in(self, interaction, channel_id: str):
        global rows
        global should_stop
        global last_import

        if not channel_id.isnumeric():
            await interaction.response.send_message('Invalid channel id. (must be number)', ephemeral=True)
            return
        if not os.path.exists(f'{channel_id}_forum_data.csv'):
            await interaction.response.send_message('Forum thread atlas not found.', ephemeral=True)
            return

        await interaction.response.send_message('Importing forum from csv.', ephemeral=True)
        await bot.change_presence(activity=discord.CustomActivity(name='Importing forum...'))
        start_time = datetime.datetime.now()
        with open(f'{channel_id}_forum_data.csv', 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            forum_name, tags_unparsed, default_reaction_emoji, topic = next(reader)
            # overriding the default_reaction_emoji param with a placeholder emoji
            forum_channel = await interaction.guild.create_forum(name=forum_name, topic=topic, default_reaction_emoji="🔥", available_tags=[utility.dict_to_forum_tag(tag) for tag in eval(tags_unparsed)], category=interaction.channel.category, reason='Importing forum')
            for row in reader:
                thread_id = int(row[0])
                thread_name = row[1]
                locked = bool(row[2])
                owner = row[3]
                available_tags_indxs = {tag.name: i for i, tag in enumerate(forum_channel.available_tags)}
                print(available_tags_indxs)
                applied_tags = [forum_channel.available_tags[available_tags_indxs[tag]] for tag in eval(row[4])]
                threadwithmessage = await forum_channel.create_thread(name=thread_name, embed=em.Thread.thread_import_init_message(owner, thread_name), applied_tags=applied_tags, reason='Importing thread')
                thread = threadwithmessage[0]
                await utility.handle_messages(csv.reader(open(f'{thread_id}.csv', 'r', newline='', encoding='utf-8')), interaction, thread, thread_id, bot, rows, last_import)
                    
        await interaction.user.send(f'Imported forum from `{forum_name}` ({channel_id}) in {datetime.datetime.now() - start_time}.')
        await bot.change_presence(activity=discord.CustomActivity(name='Standby'))
    
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