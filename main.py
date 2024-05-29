import ast
import csv
import os
import discord
from util import log_helper, utility
from discord import app_commands as ap
import datetime
from data import embeds as em
import regex as re
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
        actually_fetched = 0
        messages = []
        # fetch the most recent n messages and add them to the list
        async for message in interaction.channel.history(limit=None):
            try:
                if message.type == discord.MessageType.default or message.type == discord.MessageType.reply:
                    messages.append(message)
                    actually_fetched += 1
                elif message.type == discord.MessageType.chat_input_command or message.type == discord.MessageType.context_menu_command:
                    messages.append(message)
                    actually_fetched += 1

            except Exception as e:
                logger.error(f'error: {e}')
                pass
        total_messages = await utility.get_message_count(interaction.channel)
        await utility.write_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages[0]} in {total_time.total_seconds()} seconds.')
    
    @ap.command(name='user', description='Export messages to a csv *that is sent to you*.')
    @ap.default_permissions()
    async def csv_out_user(self, interaction: discord.Interaction):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion containing the output file. If the file is too large to be sent over discord, it will fallback to storing the file in the bot.',
                                                ephemeral=True)
        start_time = datetime.datetime.now()
        actually_fetched = 0
        messages = []
        # fetch the most recent n messages and add them to the database
        async for message in interaction.channel.history(limit=None):
            try:
                if message.type == discord.MessageType.default or message.type == discord.MessageType.reply:
                    messages.append(message)
                    actually_fetched += 1
                elif message.type == discord.MessageType.chat_input_command or message.type == discord.MessageType.context_menu_command:
                    messages.append(message)
                    actually_fetched += 1

            except Exception as e:
                logger.error(f'error: {e}')
                pass
        total_messages = await utility.get_message_count(interaction.channel)
        file = await utility.write_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages[0]} in {total_time.total_seconds()} seconds.', file=file)


class ImportToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='import', description='Tools for importing messages.', parent=ArchiveToolsGroup())

    @ap.command(name='bot', description='Import messages from a csv *that was stored by the bot*.')
    @ap.default_permissions()
    async def csv_in(self, interaction: discord.Interaction, channel_id: str):
        if not channel_id.isnumeric():
            await interaction.response.send_message('Invalid channel id. (must be number)', ephemeral=True)
            return
        if os.path.exists('badexit.csv'):
            await interaction.response.send_message('There is an unresolved badexit.csv file. Please resolve it before continuing.', ephemeral=True)
            return

        channel_id = int(channel_id)
        filename = f'{channel_id}.csv' if not os.path.exists(f'{channel_id}_in_progress.csv') else f'{channel_id}_in_progress.csv'
        await interaction.response.send_message('Importing messages from csv.', ephemeral=True)

        with open(filename, 'r', encoding='utf-8') as file:
            global rows
            global should_stop
            global last_import
            reader = csv.reader(file)
            sent = []
            rows = []
            for row in reader:
                rows.append(row)
            rows = rows[::-1]
            webhook = await interaction.channel.create_webhook(name=f'zerahook', avatar=None)
            timeprev = None
            timepost = None
            for rownum, row in enumerate(rows):
                if should_stop:
                    if row[5] != 0:
                        await webhook.delete()
                        rows = rows[rownum:]
                        rows = rows[::-1]
                        with open(f'{channel_id}_in_progress.csv', 'w', newline='', encoding='utf-8') as file2:
                            writer = csv.writer(file2)
                            for row in rows:
                                writer.writerow(row)
                        rows = []
                        should_stop = False
                        await interaction.user.send('Import cancelled.')
                        return
                if rownum == 0:
                    timeprev = datetime.datetime.now()
                try:
                    author_name, author_avatar_url, content, embeds, original_id, reference_id, inter_name, inter_user, reactions, attachments, stickers, components = row

                    embeds2 = []
                    embeds = eval(embeds)
                    for i in range(len(embeds)):
                        embed = dict(embeds[i])
                        embeds2.append(discord.Embed.from_dict(embed))
                    
                    files = []
                    large_files = []
                    if attachments != '[]':
                        for attachment in eval(attachments):
                            filedata = await utility.read_attachment_url(attachment)
                            if filedata[1] > 8_000_000 and bot.get_guild(interaction.guild_id).premium_tier < 2:
                                logger.debug('An attachment was too large!')
                                large_files.append(attachment)
                                continue
                            elif filedata[1] > 50_000_000:
                                logger.debug('An attachment was too large!')
                                large_files.append(attachment)
                                continue
                            else:
                                files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', attachment)[0]))
                    if stickers != '[]':
                            for sticker in eval(stickers):
                                filedata = await utility.read_attachment_url(sticker)
                                files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', sticker)[0]))
                    # split files into a list of lists of 10 files
                    files = [files[i:i + 10] for i in range(0, len(files), 10)] if files else [[]]

                    # handle components
                    view = None
                    if components != '[]':
                        components = ast.literal_eval(components)
                        complist = []
                        rowcount = 0
                        for comp in components:
                            if comp['type'] == 1:
                                rowcount += 1
                                for comp2 in comp['children']:
                                    complist.append(utility.dict_to_component(comp2, rowcount - 1))
                            else:
                                complist.append(utility.dict_to_component(comp, rowcount -1))
                        view = utility.view_with_components(complist)
                    
                    # handle reply messages
                    if int(reference_id) != 0:
                        for message, original_id in sent:
                            if original_id == reference_id:
                                embeds2.insert(0, em.Message.reply_message(author_name, author_avatar_url, content, len(embeds) > 1))
                                message2 = await message.reply(embeds=embeds2, files=files[0] if files else None, view=view if view else utility.EmptyView())
                                for i, filelist in enumerate(files):
                                    if i == 0:
                                        pass
                                    else:
                                        await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                                if (large_files):
                                    message_text = ''
                                    for large_file in large_files:
                                        message_text += large_file + '\n'
                                    await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                                sent.append((message2, original_id))
                                break
                    # handle interaction messages
                    elif inter_name != '0':
                        try:
                            message2 = await webhook.send(content=content, embeds=embeds2, username=f'{inter_user} used {inter_name}', avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                        except Exception as e:
                            message2 = None
                        for i, filelist in enumerate(files):
                            if i == 0:
                                pass
                            else:
                                if not message2:
                                    message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True)
                                else:
                                    await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                        if (large_files):
                            message_text = ''
                            for large_file in large_files:
                                message_text += large_file + '\n'
                            if not message2:
                                message = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True)
                            else:
                                await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                        sent.append((message2, original_id))
                    # handle normal messages
                    else:
                        try:
                            message2 = await webhook.send(content=content, embeds=embeds2, username=author_name, avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                        except Exception as e:
                            message2 = None
                        for i, filelist in enumerate(files):
                            if i == 0:
                                pass
                            else:
                                if not message2:
                                    message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True)
                                else:
                                    await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                        if (large_files):
                            message_text = ''
                            for large_file in large_files:
                                message_text += large_file + '\n'
                            if not message2:
                                message2 = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True)
                            else:
                                await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                        sent.append((message2, original_id))
                    # send secondary messages with the reactions
                    if reactions != '[]':
                        await message2.reply(embed=em.Message.emoji_display(author_name, author_avatar_url, eval(reactions)))
                    last_import = rownum
                except Exception as e:
                    with open(f'badexit.csv', 'w', newline='', encoding='utf-8') as file2:
                        writer = csv.writer(file2)
                        rows = rows[rownum:]
                        for row in rows:
                            writer.writerow(row)
                if rownum == len(rows) - 1:
                        timepost = datetime.datetime.now()
            if os.path.exists(f'{channel_id}_in_progress.csv'):
                os.remove(f'{channel_id}_in_progress.csv')
            await webhook.delete()
            await interaction.user.send(f'Imported {len(rows)} messages in {timepost - timeprev} seconds.')
    
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
        file = file_byes.decode('utf-8')
        reader = csv.reader(iter(file.splitlines()))
        sent = []
        rows = []
        for row in reader:
            rows.append(row)
        rows = rows[::-1]
        webhook = await interaction.channel.create_webhook(name=f'zerahook', avatar=None)
        timeprev = None
        timepost = None
        for rownum, row in enumerate(rows):
            if (should_stop):
                if row[5] != 0:
                    await webhook.delete()
                    rows = rows[rownum:]
                    rows = rows[::-1]
                    with open(f'{csv_file.filename}_in_progress.csv', 'w', newline='', encoding='utf-8') as file2:
                        writer = csv.writer(file2)
                        for row in rows:
                            writer.writerow(row)
                    rows = []
                    should_stop = False
                    await interaction.user.send('Import cancelled.')
                    return
            if rownum == 0:
                timeprev = datetime.datetime.now()
            try:
                author_name, author_avatar_url, content, embeds, original_id, reference_id, inter_name, inter_user, reactions, attachments, stickers, components = row

                embeds2 = []
                embeds = eval(embeds)
                for i in range(len(embeds)):
                    embed = dict(embeds[i])
                    embeds2.append(discord.Embed.from_dict(embed))
                
                files = []
                large_files = []
                if attachments != '[]':
                    for attachment in eval(attachments):
                        filedata = await utility.read_attachment_url(attachment)
                        if filedata[1] > 8_000_000 and bot.get_guild(interaction.guild_id).premium_tier < 2:
                            logger.debug('An attachment was too large!')
                            large_files.append(attachment)
                            continue
                        elif filedata[1] > 50_000_000:
                            logger.debug('An attachment was too large!')
                            large_files.append(attachment)
                            continue
                        else:
                            files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', attachment)[0]))
                if stickers != '[]':
                        for sticker in eval(stickers):
                            filedata = await utility.read_attachment_url(sticker)
                            files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', sticker)[0]))
                # split files into a list of lists of 10 files
                files = [files[i:i + 10] for i in range(0, len(files), 10)] if files else [[]]

                # handle components
                view = None
                if components != '[]':
                    components = ast.literal_eval(components)
                    complist = []
                    rowcount = 0
                    for comp in components:
                        if comp['type'] == 1:
                            rowcount += 1
                            for comp2 in comp['children']:
                                complist.append(utility.dict_to_component(comp2, rowcount - 1))
                        else:
                            complist.append(utility.dict_to_component(comp, rowcount -1))
                    view = utility.view_with_components(complist)
                
                # handle reply messages
                if int(reference_id) != 0:
                    for message, original_id in sent:
                        if original_id == reference_id:
                            embeds2.insert(0, em.Message.reply_message(author_name, author_avatar_url, content, len(embeds) > 1))
                            message2 = await message.reply(embeds=embeds2, files=files[0] if files else None, view=view if view else utility.EmptyView())
                            for i, filelist in enumerate(files):
                                if i == 0:
                                    pass
                                else:
                                    await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                            if (large_files):
                                message_text = ''
                                for large_file in large_files:
                                    message_text += large_file + '\n'
                                await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                            sent.append((message2, original_id))
                            break
                # handle interaction messages
                elif inter_name != '0':
                    try:
                        message2 = await webhook.send(content=content, embeds=embeds2, username=f'{inter_user} used {inter_name}', avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                    except Exception as e:
                        message2 = None
                    for i, filelist in enumerate(files):
                        if i == 0:
                            pass
                        else:
                            if not message2:
                                message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True)
                            else:
                                await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                    if (large_files):
                        message_text = ''
                        for large_file in large_files:
                            message_text += large_file + '\n'
                        if not message2:
                            message = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True)
                        else:
                            await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                    sent.append((message2, original_id))
                # handle normal messages
                else:
                    try:
                        message2 = await webhook.send(content=content, embeds=embeds2, username=author_name, avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                    except Exception as e:
                        message2 = None
                    for i, filelist in enumerate(files):
                        if i == 0:
                            pass
                        else:
                            if not message2:
                                message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True)
                            else:
                                await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url)
                    if (large_files):
                        message_text = ''
                        for large_file in large_files:
                            message_text += large_file + '\n'
                        if not message2:
                            message2 = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True)
                        else:
                            await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url)
                    sent.append((message2, original_id))
                # send secondary messages with the reactions
                if reactions != '[]':
                    await message2.reply(embed=em.Message.emoji_display(author_name, author_avatar_url, eval(reactions)))
                last_import = rownum
            except Exception as e:
                with open(f'badexit.csv', 'w', newline='', encoding='utf-8') as file2:
                        writer = csv.writer(file2)
                        rows = rows[rownum:]
                        for row in rows:
                            writer.writerow(row)
            if rownum == len(rows) - 1:
                timepost = datetime.datetime.now()
        if os.path.exists(f'{csv_file.filename}_in_progress.csv'):
            os.remove(f'{csv_file.filename}_in_progress.csv')
        await webhook.delete()
        await interaction.user.send(f'Imported {len(rows)} messages in {timepost - timeprev} seconds.')
    
    @ap.command(name='cancel', description='Cancel the current import process.')
    @ap.default_permissions()
    async def cancel(self, interaction: discord.Interaction):
        global should_stop
        should_stop = True
        await interaction.response.send_message('Cancel flag set.', ephemeral=True)

def on_stop():
    global rows
    global last_import
    global last_export
    if rows:
        rows = rows[last_import:]
        rows = rows[::-1]
        with open(f'badexit.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for row in rows:
                    writer.writerow(row)
        logger.error('Unexpected exit. Wrote to badexit.csv.')

atexit.register(on_stop)

bot.run(token)