from dotenv import dotenv_values
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import discord
import aiohttp
from imageProcessing import read_roi_and_create_output_for_amounts
from db import store_deads_info
from botConfigHandler import read_bot_config, update_bot_config_channel_id, add_admins_to_bot_config, remove_admins_from_bot_config

bot_config = read_bot_config()
config = dotenv_values('.env.dev')

bot_token = config['BOT_TOKEN']
channel_id = bot_config['CHANNEL_ID']
admins = bot_config['ADMINS']
debug = True if config['DEBUG'] == 'True' else False

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print("Bot is online")

class SetupMenu(View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Change admin IDs', style=discord.ButtonStyle.primary)
    async def change_admin_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message('Please send the new admin IDs.', ephemeral=True)


@bot.command()
async def deads(ctx):

    if ctx.channel.id != channel_id:
        print('Not the designated channel for the bot')
        return
    
    user_id = ctx.author.id
    columns = {
        't4inf':'E',
        't4arch':'F',
        't4cav':'G',
        't4siege':'H',
        't5inf':'I',
        't5arch':'J',
        't5cav':'K',
        't5siege':'L'
    }
    
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if any(attachment.filename.lower().endswith(image_ext) for image_ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.webp']):
                ctx.reply('Image found in the message!')
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            await ctx.send('Processing data...')
                            image_data = await resp.read()
                            result = read_roi_and_create_output_for_amounts(image_data)

                            if result == {}:
                                await ctx.send('There was an issue in processing your image. Please try again.')
                                break

                            if debug == False:
                                await ctx.send('Storing data...')
                                for k, v in result.items():
                                    store_deads_info(user_id, v, columns[k])
                                await ctx.send(f'{result} stored!')
                            else:
                                print(result)
                                await ctx.send('Check console')

                        else:
                            await ctx.send('Error in image processing. Please try again')
    else:
        await ctx.send('No attachment found in the message.')

@bot.command()
async def setup(ctx):

    user_id = ctx.author.id
    if user_id not in bot_config['ADMINS']: 
        print(f'User {user_id} is not admin and is trying to access an admin command')
        return

    view = SetupMenu()
    await ctx.reply('Choose a setup option:', view=view)


bot.run(bot_token)