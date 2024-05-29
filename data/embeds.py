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