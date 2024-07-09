import ast
import importlib
import io
import os
import re
import aiohttp
from discord import app_commands as ap
from util import log_helper
from data import embeds as em
from data.exceptions import *
import discord
import datetime
import csv

logger = log_helper.get_logger(__name__)

should_stop = False

async def load_command_groups(bot, module_name: str):
    """
    Loads command groups from a file.
    :param bot: Bot to load the commands into.
    :param module_name: File to load the commands from.
    :return: Void
    """
    logger.debug(f"Loading command groups from {module_name}.")
    module = importlib.import_module(module_name)
    instances = {}

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, ap.Group) and attr is not ap.Group:
            instance = attr()
            instances[attr_name] = instance
    logger.debug(instances)

    for name, instance in instances.items():
        parent_name = type(instance.parent).__name__ if instance.parent else None
        logger.debug(f"Checking command group {name}.")
        logger.debug(f'Parent name: {parent_name if parent_name else "None"}')
        if parent_name and parent_name in instances:
            logger.debug(f'adding {instance} to {parent_name}')
            instances[parent_name].add_command(instance)
        logger.debug(f"Checked command group {name}." + (f" Parent: {parent_name}" if instance.parent else ''))

    for name, instance in instances.items():
        if not instance.parent:
            logger.debug(f'loading {instance}')
            bot.tree.add_command(instance)
            logger.debug(f'loaded {instance}')


async def get_message_count(channel: discord.TextChannel):
    """
    Gets the number of messages in a channel.
    :param channel: Channel to count messages in.
    :return: Tuple of count and time taken.
    """
    start_time = datetime.datetime.now()
    message_count = 0
    async for _ in channel.history(limit=None):
        message_count += 1
    end_time = datetime.datetime.now()
    time_taken = end_time - start_time
    logger.debug(f"Counted {message_count} messages in {time_taken.total_seconds()} seconds.")
    return message_count, time_taken.total_seconds()

async def write_forum_csvs(messages, file_name: str) -> discord.File:
    """
    Writes forum thread atlas to a csv, and indexed forum messages to another csv.
    :param messages: list<dict<list, int>>: list of dicts of lists of messages and the thread id for those messages.
    """

async def write_messages_csv(messages, file_name: str) -> discord.File:
    """
    Writes messages to a csv file.\n
    messages are stored in the following format:\n
    [author's name, author's avatar url, message content, message embeds, message id, message reference id (reply id), interaction name, interaction user's name, message reactions, message attachments, message stickers, message components, boolean whether the message is pinned (0 or 1)]
    :param message: Messages to write to the file.
    :return: discord.File
    """
    # reversed because discord returns channel history from newest to oldest
    messages = messages[::-1]
    with open(file_name, 'w', newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        for message in messages:

            if message.type == discord.MessageType.thread_created:
                # if the message isnt a thread sysmessage, this code wont run and the flag is 0
                # if the message has no thread, the flag is 1
                # if the message has a thread but it couldnt be associated, the flag is 2
                # if the message has a thread and it could be associated, the flag is the thread id
                thread = associate_thread(message)
                thread_flag = 1
                if thread:
                    thread_flag = thread.id
                else:
                    thread_flag = 2 if message.flags.value == 32 else 1
                writer.writerow([message.author.name, message.author.display_avatar.url, "thread placeholder text" if not thread else thread.name, [], message.id, 0, 0, 0, [], [], [], [], 0, thread_flag])
            
            embeds = []
            for embed in message.embeds:
                embeds.append(embed.to_dict())
            
            emojis = []
            for reaction in message.reactions:
                emojis.append((reaction.emoji if type(reaction.emoji) == str else f'<:{reaction.emoji.name}:{reaction.emoji.id}>', reaction.count))
            
            attachments = []
            for attachment in message.attachments:
                attachments.append(attachment.url)
            
            stickers = []
            for sticker in message.stickers:
                stickers.append(sticker.url)

            components = []
            for component in message.components:
                components.append(component_to_dict(component))
            if message.reference:
                for message2 in messages:
                    if message2.id == message.reference.message_id:
                        writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, message.reference.message_id, 0, 0, emojis, attachments, stickers, components, 1 if message.pinned else 0, 0])
            elif message.type == discord.MessageType.chat_input_command:
                writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, 0, message.interaction.name, message.interaction.user.name, emojis, attachments, stickers, components, 1 if message.pinned else 0, 0])
            else:
                writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, 0, 0, 0, emojis, attachments, stickers, components, 1 if message.pinned else 0, 0])
        return discord.File(file_name, filename='export.csv')
    

async def read_attachment_url(url: str) -> (bytes, int):
    """
    Reads an attachment URL and returns file bytes and file size.
    :param url: URL to read.
    :return: Tuple containing file bytes and file size.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            stream = io.BytesIO(await resp.read())
            return stream, resp.content_length
        
def component_to_dict(component):
    """
    Converts a component to a dictionary.
    :param component: Component to convert.
    :return: Dictionary of the component.
    """
    dict = {}
    if component.type == discord.ComponentType.action_row:
        dict['type'] = discord.ComponentType.action_row.value
        dict['children'] = [component_to_dict(child) for child in component.children]
    elif component.type == discord.ComponentType.button:
        dict['type'] = component.type.value
        dict['style'] = component.style.value
        dict['label'] = component.label
        dict['emoji'] = (component.emoji.name if component.emoji.id == None else f'<:{component.emoji.name}:{component.emoji.id}>') if component.emoji else None
        dict['custom_id'] = component.custom_id
        dict['url'] = component.url
        dict['disabled'] = component.disabled
    elif component.type == discord.ComponentType.select:
        dict['type'] = component.type.value
        dict['custom_id'] = component.custom_id
        dict['options'] = [{'label': option.label, 'value': option.value, 'description': option.description, 'emoji': option.emoji if type(option.emoji) == str else f'<:{option.emoji.name}:{option.emoji.id}>', 'default': option.default} for option in component.options]
        dict['placeholder'] = component.placeholder
        dict['min_values'] = component.min_values
        dict['max_values'] = component.max_values
        dict['disabled'] = component.disabled
    return dict

def dict_to_component(dictionary: dict, row: int):
    """
    Converts a dictionary to a component.
    :param dict: Dictionary to convert.
    :return: Component of the dictionary.
    """
    if type(dictionary) != dict:
        raise TypeError("dict_to_component requires a dictionary.")
    if dictionary['type'] == discord.ComponentType.button.value:
        return discord.ui.Button(row=row, style=discord.ButtonStyle(dictionary['style']), custom_id=dictionary['custom_id'], url=dictionary['url'], disabled=dictionary['disabled'], label=dictionary['label'], emoji=discord.PartialEmoji.from_str(dictionary['emoji']) if dictionary['emoji'] else None)
    elif dictionary['type'] == discord.ComponentType.select.value:
        return discord.ui.Select(row=row, custom_id=dictionary['custom_id'], placeholder=dictionary['placeholder'], min_values=dictionary['min_values'], max_values=dictionary['max_values'], options=[discord.SelectOption(label=option['label'], value=option['value'], description=option['description'], emoji=discord.PartialEmoji.from_str(option['emoji']), default=option['default']) for option in dictionary['options']], disabled=dictionary['disabled'])
    return None

def view_with_components(components):
    """
    Creates a view with components.
    :param components: Components to add to the view.
    :return: View with components.
    """
    view = EmptyView()
    for component in components:
        view.add_item(component)
    return view

class EmptyView(discord.ui.View):
    """
    Empty view class.
    """
    def __init__(self):
        super().__init__()

async def forum_tag_to_dict(forum_tag: discord.ForumTag, guild):
    emoji = None
    if forum_tag.emoji:
        emoji = str(forum_tag.emoji) if forum_tag.emoji.id == None else await guild.fetch_emoji(forum_tag.emoji.id)
    return {'emoji': emoji if type(emoji) == str or not emoji else f'<:{emoji.name}:{emoji.id}>',
            'moderated': forum_tag.moderated,
            'name': forum_tag.name,}

def dict_to_forum_tag(dictionary: dict):
    return discord.ForumTag(emoji=dictionary['emoji'], moderated=dictionary['moderated'], name=dictionary['name'])

def associate_thread(message) -> discord.Thread:
    """
    Associates a thread with a message based on the starter message's creation date.
    :param message: Message to associate a thread with.
    :return: Associated thread.
    """
    if message.type != discord.MessageType.thread_created:
        raise TypeError('Message is not a thread creation sysmessage.')
    
    possible_matches = []

    for thread in message.channel.threads:
        if thread.created_at == message.created_at:
            possible_matches.append(thread)
    if (len(possible_matches) == 1):
        return possible_matches[0]
    elif (len(possible_matches) == 0):
        return None
    else:
        logger.error(DuplicateThreadException(len(possible_matches), message))
    return None

async def fetch_messages(channel):
    actually_fetched = 0
    messages = []
    # fetch the most recent n messages and add them to the list
    async for message in channel.history(limit=None):
        try:
            if message.type == discord.MessageType.default or message.type == discord.MessageType.reply:
                messages.append(message)
                actually_fetched += 1
            elif message.type == discord.MessageType.chat_input_command or message.type == discord.MessageType.context_menu_command:
                messages.append(message)
                actually_fetched += 1
            elif message.type == discord.MessageType.thread_created:
                messages.append(message)
                actually_fetched += 1
            else:
                logger.info(f'Found a message of type {message.type}.')

        except Exception as e:
            logger.error(f'error: {e}')
            pass
    total_messages = await get_message_count(channel)
    return messages, total_messages[0], actually_fetched

async def handle_messages(reader, interaction, channel, channel_name, bot, rows, last_import):
    global should_stop
    sent = []
    rows = []
    for row in reader:
        rows.append(row)
    thread_doodad = discord.utils.MISSING
    if type(channel) == discord.Thread:
        webhook = await channel.parent.create_webhook(name='zerahook', avatar=None)
        thread_doodad = channel
    else:
        webhook = await channel.create_webhook(name=f'zerahook', avatar=None)
    timeprev = None
    timepost = None
    for rownum, row in enumerate(rows):
        if should_stop:
            if row[5] != 0:
                await webhook.delete()
                rows2 = rows[rownum:]
                with open(f'{channel_name}_in_progress.csv', 'w', newline='', encoding='utf-8') as file2:
                    writer = csv.writer(file2)
                    for row2 in rows2:
                        writer.writerow(row2)
                rows = []
                should_stop = False
                await interaction.user.send('Import cancelled.')
                return
        print("rownum = " + str(rownum))
        if rownum == 0:
            timeprev = datetime.datetime.now()
        try:
            author_name, author_avatar_url, content, embeds, original_id, reference_id, inter_name, inter_user, reactions, attachments, stickers, components, pin_flag, thread_flag = row

            # system messages
            if int(thread_flag) != 0:
                if int(thread_flag) == 1:
                    await webhook.send(embed=em.Thread.deleted_thread_sysmessage(author_name, author_avatar_url), username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                elif int(thread_flag) == 2:
                    await webhook.send(embed=em.Thread.bad_thread(author_name, author_avatar_url), username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                else:
                    # embed=em.Thread.thread_sysmessage(author_name)
                    # test = await webhook.send(content="** **", username=f'{author_name} started a thread.', avatar_url=author_avatar_url, wait=True)
                    thread = await channel.create_thread(name=content, type=discord.ChannelType.public_thread, reason='Thread import')
                    await channel.last_message.delete()
                    await webhook.send(embed=em.Thread.thread_sysmessage(author_name, author_avatar_url, thread.jump_url, thread.name), username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                if rownum == len(rows) - 1:
                    timepost = datetime.datetime.now()
                continue

            embeds2 = []
            embeds = eval(embeds)
            for i in range(len(embeds)):
                embed = dict(embeds[i])
                embeds2.append(discord.Embed.from_dict(embed))
            
            files = []
            large_files = []
            if attachments != '[]':
                for attachment in eval(attachments):
                    filedata = await read_attachment_url(attachment)
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
                        filedata = await read_attachment_url(sticker)
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
                            complist.append(dict_to_component(comp2, rowcount - 1))
                    else:
                        complist.append(dict_to_component(comp, rowcount -1))
                view = view_with_components(complist)
            # handle reply messages
            elif int(reference_id) != 0:
                for message, original_id in sent:
                    if original_id == reference_id:
                        embeds2.insert(0, em.Message.reply_message(author_name, author_avatar_url, content, len(embeds) > 1))
                        message2 = await message.reply(embeds=embeds2, files=files[0] if files else None, view=view if view else EmptyView())
                        for i, filelist in enumerate(files):
                            if i == 0:
                                pass
                            else:
                                await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                        if (large_files):
                            message_text = ''
                            for large_file in large_files:
                                message_text += large_file + '\n'
                            await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                        break
            # handle interaction messages
            elif inter_name != '0':
                try:
                    message2 = await webhook.send(content=content, embeds=embeds2, username=f'{inter_user} used {inter_name}', avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else EmptyView(), wait=True, thread=thread_doodad)
                except Exception as e:
                    message2 = None
                for i, filelist in enumerate(files):
                    if i == 0:
                        pass
                    else:
                        if not message2:
                            message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True, thread=thread_doodad)
                        else:
                            await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                if (large_files):
                    message_text = ''
                    for large_file in large_files:
                        message_text += large_file + '\n'
                    if not message2:
                        message = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True, thread=thread_doodad)
                    else:
                        await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
            # handle normal messages
            else:
                try:
                    contents = [content[i:i+2000] for i in range(0, len(content), 2000)]
                    message2 = await webhook.send(content=contents[0] if len(contents) > 0 else None, embeds=embeds2, username=author_name, avatar_url=author_avatar_url, files=files[0] if files else None, view=view if view else EmptyView(), wait=True, thread=thread_doodad)
                    if len(contents) > 1:
                        for con_slice in contents[1:]:
                            await webhook.send(content=con_slice, username=author_name, avatar_url=author_avatar_url, wait=True, thread=thread_doodad)
                except Exception as e:
                    print(f'message2 error: {e}')
                    message2 = None
                for i, filelist in enumerate(files):
                    if i == 0:
                        pass
                    else:
                        if not message2:
                            message2 = await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, wait=True, thread=thread_doodad)
                        else:
                            await webhook.send(files=filelist, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
                if (large_files):
                    message_text = ''
                    for large_file in large_files:
                        message_text += large_file + '\n'
                    if not message2:
                        message2 = await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, wait=True, thread=thread_doodad)
                    else:
                        await webhook.send(content=message_text, username=author_name, avatar_url=author_avatar_url, thread=thread_doodad)
            sent.append((message2, original_id))
            if int(pin_flag) == 1:
                await message2.pin()
            # send secondary messages with the reactions
            if reactions != '[]':
                await message2.reply(embed=em.Message.emoji_display(eval(reactions)))
            last_import = rownum
        except Exception as e:
            print(e)
            print(row)
            print(rownum)
            with open(f'badexit.csv', 'w', newline='', encoding='utf-8') as file2:
                writer = csv.writer(file2)
                rows2 = rows[rownum:]
                for row in rows2:
                    writer.writerow(row)
            return
        if rownum == len(rows) - 1:
                timepost = datetime.datetime.now()
    if os.path.exists(f'{channel_name}_in_progress.csv'):
        os.remove(f'{channel_name}_in_progress.csv')
    await webhook.delete()
    await interaction.user.send(f'Imported {len(rows)} messages in {timepost - timeprev} seconds.')
    rows = []

