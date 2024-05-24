import ast
import csv
import os
import discord
from util import log_helper, utility
from discord import app_commands as ap
import datetime
from data import embeds as em
import regex as re

token = os.getenv('ZERABOT_TOKEN')

logger = log_helper.get_logger(__name__)
if token is None:
    logger.error('Token not found. Please set the ZERABOT_TOKEN environment variable.')
    exit(1)
bot = discord.Client(intents=discord.Intents.all())
bot.tree = ap.CommandTree(bot)

@bot.event
async def on_ready():
    await utility.load_command_groups(bot, __name__)
    syncs = await bot.tree.sync()
    logger.debug(f'Syncs: {len(syncs)}')
    print(f'{bot.user} has connected to Discord!')

class ArchiveToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='archivetools', description='Tools for archiving messages.')


class ExportToolsGroup(ap.Group):
    def __init__(self):
        super().__init__(name='export', description='Tools for exporting messages.', parent=ArchiveToolsGroup())
    
    @ap.command(name='bot', description='Export messages to a csv *that is stored by the bot*.')
    async def csv_out(self, interaction: discord.Interaction):
        await interaction.response.send_message('Started fetching messages. You will receive a dm upon completion.',
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
        await utility.write_csv(messages, f'{interaction.channel_id}.csv')
        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        await interaction.user.send(
            f'Fetched and exported {actually_fetched} messages out of {total_messages[0]} in {total_time.total_seconds()} seconds.')
    
    @ap.command(name='user', description='Export messages to a csv *that is sent to you*.')
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
    async def csv_in(self, interaction: discord.Interaction, channel_id: str):
        if not channel_id.isnumeric():
            await interaction.response.send_message('Invalid channel id. (must be number)', ephemeral=True)
            return
        channel_id = int(channel_id)
        await interaction.response.send_message('Importing messages from csv.', ephemeral=True)

        with open(f'{channel_id}.csv', 'r', encoding='utf-8') as file:
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
                if rownum == 1:
                    timeprev = datetime.datetime.now()
                elif rownum == len(rows) - 1:
                    timepost = datetime.datetime.now()
                author_name, author_avatar_url, content, embeds, original_id, reference_id, inter_name, inter_user, reactions, attachments, stickers, components = row

                embeds2 = []
                embeds = eval(embeds)
                for i in range(len(embeds)):
                    embed = dict(embeds[i])
                    embeds2.append(discord.Embed.from_dict(embed))
                
                files = []
                if attachments != '[]':
                    for attachment in eval(attachments):
                        filedata = await utility.read_attachment_url(attachment)
                        files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', attachment)[0]))
                if stickers != '[]':
                        for sticker in eval(stickers):
                            filedata = await utility.read_attachment_url(sticker)
                            files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', sticker)[0]))
                # split files into a list of lists of 10 files
                files = [files[i:i + 10] for i in range(0, len(files), 10)] if files else [[]]
                print(files)

                # handle components
                view = None
                if components != '[]':
                    components = ast.literal_eval(components)
                    print(components)
                    complist = []
                    rowcount = 0
                    for comp in components:
                        print(f'\n\n\n{comp}\n\n\n')
                        print(type(comp))
                        if comp['type'] == 1:
                            rowcount += 1
                            for comp2 in comp['children']:
                                print(f'\n\n\nin row comp: {comp2}\n\n\n')
                                complist.append(utility.dict_to_component(comp2, rowcount - 1))
                        else:
                            complist.append(utility.dict_to_component(comp, rowcount -1))
                    # print(complist)
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
                                    await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                            sent.append((message2, original_id))
                            break
                # handle interaction messages
                elif inter_name != '0':
                    message2 = await webhook.send(content=content, embeds=embeds2, username=f'{inter_user} used {inter_name}', avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                    for i, filelist in enumerate(files):
                        if i == 0:
                            pass
                        else:
                            await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                    sent.append((message2, original_id))
                # handle normal messages
                else:
                    message2 = await webhook.send(content=content, embeds=embeds2, username=author_name, avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                    for i, filelist in enumerate(files):
                        if i == 0:
                            pass
                        else:
                            await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                    sent.append((message2, original_id))
                # send secondary messages with the reactions
                if reactions != '[]':
                    await message2.reply(embed=em.Message.emoji_display(author_name, author_avatar_url, eval(reactions)))
            await webhook.delete()
            await interaction.user.send(f'Imported {len(rows)} messages in {timepost - timeprev} seconds.')
    
    @ap.command(name='user', description='Import messages from a csv *that is provided by you*.')
    async def csv_in_user(self, interaction: discord.Interaction, csv_file: discord.Attachment):
        await interaction.response.send_message('Importing messages from csv.', ephemeral=True)
        
        file_byes = await csv_file.read()
        file = file_byes.decode('utf-8')
        reader = csv.reader(iter(file.splitlines()))
        sent = []
        rows = []
        for row in reader:
            rows.append(row)
        rows = rows[::-1]
        webhook = await interaction.channel.create_webhook(name='zerahook', avatar=None)
        for row in rows:
            author_name, author_avatar_url, content, embeds, original_id, reference_id, inter_name, inter_user, reactions, attachments, stickers, components = row
            
            embeds2 = []
            embeds = eval(embeds)
            for i in range(len(embeds)):
                embed = dict(embeds[i])
                embeds2.append(discord.Embed.from_dict(embed))
            
            files = []
            if attachments != '[]':
                for attachment in eval(attachments):
                    filedata = await utility.read_attachment_url(attachment)
                    files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', attachment)[0]))
            if stickers != '[]':
                    for sticker in eval(stickers):
                        filedata = await utility.read_attachment_url(sticker)
                        files.append(discord.File(filedata[0], filename=re.match(r'.*/(.*\.\w+)', sticker)[0]))
            # split files into a list of lists of 10 files
            files = [files[i:i + 10] for i in range(0, len(files), 10)]

            # handle components
            view = None
            if components != '[]':
                complist = [utility.dict_to_component(comp) for comp in eval(components)]
                view = utility.view_with_components(complist)
            
            # handle reply messages
            if int(reference_id) != 0:
                for message, original_id in sent:
                    if original_id == reference_id:
                        embeds2.insert(0, em.Message.reply_message(author_name, author_avatar_url, content, True))
                        message2 = await message.reply(embeds=embeds2, files=files[0] if files else None, view=view if view else utility.EmptyView())
                        for i, filelist in enumerate(files):
                            if i == 0:
                                pass
                            else:
                                await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                        sent.append((message2, original_id))
                        break
            # handle interaction messages
            elif inter_name != '0':
                message2 = await webhook.send(content=content, embeds=embeds2, username=f'{inter_user} used {inter_name}', avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                for i, filelist in enumerate(files):
                    if i == 0:
                        pass
                    else:
                        await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                sent.append((message2, original_id))
            # handle normal messages
            else:
                message2 = await webhook.send(content=content, embeds=embeds2, username=author_name, avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else utility.EmptyView(), wait=True)
                for i, filelist in enumerate(files):
                    if i == 0:
                        pass
                    else:
                        await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, view=view if view else utility.EmptyView())
                sent.append((message2, original_id))
            # send secondary messages with the reactions
            if reactions != '[]':
                await message2.reply(embed=em.Message.emoji_display(author_name, author_avatar_url, eval(reactions)))
        await webhook.delete()

bot.run(token)