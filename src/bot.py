from dotenv import dotenv_values
from discord.ext import commands
import discord
import aiohttp
from imageProcessing import read_roi_and_create_output_for_amounts

config = dotenv_values('.env.dev')

bot_token = config['BOT_TOKEN']
channel_id = int(config['CHANNEL_ID'])

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print("bot rdy")
    channel = bot.get_channel(channel_id)

@bot.command()
async def add(ctx, x, y):
    result = int(x) + int(y)
    await ctx.send(result)

@bot.command()
async def deads(ctx):
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if any(attachment.filename.lower().endswith(image_ext) for image_ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.webp']):
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            result = read_roi_and_create_output_for_amounts(image_data)
                            await ctx.send(f'{result}')
                        else:
                            await ctx.send('Error in image processing')
    else:
        await ctx.send('No image found in the message')

bot.run(bot_token)