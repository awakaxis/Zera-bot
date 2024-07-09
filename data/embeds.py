import discord
from util import log_helper

logger = log_helper.get_logger(__name__)

class Message:

    @staticmethod
    def reply_message(author_name, avatar_url, content: str, has_embeds=False):
        embed = discord.Embed(color=discord.Color.from_rgb(3, 191, 153))
        embed.set_author(name=author_name, icon_url=avatar_url)
        embed.description = content
        embed.set_footer(text='This reply had embeds' if has_embeds else '')
        return embed
    
    @staticmethod
    def emoji_display(emojis):
        embed = discord.Embed(color=discord.Color.from_rgb(3, 191, 153))
        embed.description = '|'
        for emoji, count in emojis:
            embed.description += f' {discord.PartialEmoji.from_str(emoji)}: `{count}` |'
        embed.set_footer(text='The above message had these reactions.')
        return embed

class Thread:

    @staticmethod
    def bad_thread(thread_maker, thread_maker_avatar):
        embed = discord.Embed(color=discord.Color.from_rgb(255, 0, 0))
        # embed.set_author(name=thread_maker, icon_url=thread_maker_avatar)
        embed.title = "❌ Unable to determine matching thread:"
        embed.description = "A thread was created here, but after analysis of possible identifiers, no matching thread was found. This requires a manual fix."
        embed.set_footer(text='The thread creator was: ' + thread_maker)
        return embed
    
    @staticmethod
    def thread_sysmessage(thread_maker, thread_maker_avatar, jump_url, thread_name):
        embed = discord.Embed(color=discord.Color.from_rgb(75, 172, 244))
        # embed.set_author(name=thread_maker, icon_url=thread_maker_avatar)
        embed.description = f'{thread_maker} started a thread: **[{thread_name}]({jump_url})**'
        # embed.set_footer(text='Due to discord limitations, I can\'t guarantee the linked thread is correct.')
        return embed
    
    @staticmethod
    def deleted_thread_sysmessage(thread_maker, thread_maker_avatar):
        embed = discord.Embed(color=discord.Color.from_rgb(75, 172, 244))
        # embed.set_author(name=thread_maker, icon_url=thread_maker_avatar)
        embed.description = f'{thread_maker} started a thread, but it was deleted.'
        return embed
    
    @staticmethod
    def thread_import_init_message(thread_owner, thread_name):
        embed = discord.Embed(color=discord.Color.from_rgb(75, 172, 244))
        embed.description = f'Imported thread `{thread_name}`, initially created by {thread_owner}.'
        return embed