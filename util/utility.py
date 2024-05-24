import importlib
import io
import aiohttp
from discord import app_commands as ap
from util import log_helper
import discord
import datetime
import csv

logger = log_helper.get_logger(__name__)

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
    start_time = datetime.datetime.utcnow()
    message_count = 0
    async for _ in channel.history(limit=None):
        message_count += 1
    end_time = datetime.datetime.utcnow()
    time_taken = end_time - start_time
    logger.debug(f"Counted {message_count} messages in {time_taken.total_seconds()} seconds.")
    return message_count, time_taken.total_seconds()


async def write_csv(messages, file_name: str) -> discord.File:
    """
    Writes messages to a csv file.
    :param message: Messages to write to the file.
    :return: Void
    """
    with open(file_name, 'w', newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        for message in messages:
            
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
            print(components)
            
            if message.reference:
                for message2 in messages:
                    if message2.id == message.reference.message_id:
                        writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, message.reference.message_id, 0, 0, emojis, attachments, stickers, components])
            elif message.type == discord.MessageType.chat_input_command:
                writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, 0, message.interaction.name, message.interaction.user.name, emojis, attachments, stickers, components])
            else:
                writer.writerow([message.author.name, message.author.display_avatar.url, message.content, embeds, message.id, 0, 0, 0, emojis, attachments, stickers, components])
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
    print(components)
    for component in components:
        print(component)
        print(type(component))
        view.add_item(component)
    return view

class EmptyView(discord.ui.View):
    """
    Empty view class.
    """
    def __init__(self):
        super().__init__()
