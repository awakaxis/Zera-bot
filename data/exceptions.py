import discord
class DuplicateThreadException(Exception):
    def __init__(self, count: int, message: discord.Message):
        self.count = count
        self.message = message
        super().__init__(self.table, self.channel, self.guild)

    def __str__(self):
        return f"{type(self).__name__} -- found {self.count} possible threads for message {self.message.id} in channel {self.message.channel.id} in guild {self.message.guild.id} - Should be at most 1."

    pass