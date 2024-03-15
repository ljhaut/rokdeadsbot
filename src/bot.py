import asyncio
from dotenv import dotenv_values
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from discord import app_commands, Embed
import discord
import aiohttp
from datetime import datetime
from imageProcessing import read_roi_and_create_output_for_amounts
from db import store_deads_info
from botConfigHandler import read_bot_config, update_bot_config_sheet_name
from constants import emote_id, embed_troop_type, result_order

bot_config = read_bot_config()
config = dotenv_values('.env.dev')

BOT_TOKEN = config['BOT_TOKEN']
ADMINS = bot_config['ADMINS']
DEBUG = True if config['DEBUG'] == 'True' else False

global is_deads_up
is_deads_up = False
deads_task_queue = []
bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

async def process_queue():
    while True:
        if deads_task_queue:
            task = deads_task_queue.pop(0)
            await task
        await asyncio.sleep(1)

def enqueue_store_deads_info_task(user_id, data):
    task = store_deads_info(user_id, data)
    deads_task_queue.append(task)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(e)
    global is_deads_up
    is_deads_up = True
    bot.loop.create_task(process_queue())
    print("Bot is online")

async def send_deny_message_to_admins(bot, data, user, img):
    for adm in ADMINS:
        admin = await bot.fetch_user(adm)
        embed = Embed(title='Report info', description=f'User display name: {user.display_name} \n User id: {user.id} \n result: {data}')
        embed.set_image(url=img)
        await admin.send(embed=embed)

def make_dead_troops_embed(data, title='Confirm dead troops', desc='Please press CONFIRM if the count of dead troops is correct, otherwise press DENY.', confirm=False, deny=False):
    embed = Embed(title=title, description=desc, color=0x00ff00)
    embed.add_field(name='Total dead troops', value='', inline=False)
    data = sorted(data.items(), key=lambda x: result_order[x[0]])
    data = {k: v for k, v in data}
    for k, v in data.items():
        embed.add_field(name='', value=f'{emote_id[k]} {embed_troop_type[k]} | {v}', inline=False)
    
    if confirm:
        return make_dead_troops_embed(data, title='Confirmed', desc='You pressed the confirm button for correct amount for dead troops')
    if deny:
        return make_dead_troops_embed(data, title='Denied', desc='You pressed the deny button for incorrect amount of dead troops')

    return embed

class DeadsCheck(View):
    def __init__(self, result, user, bot, file_url):
        super().__init__()
        self.value = None
        self.result = result
        self.user = user
        self.bot = bot
        self.file_url = file_url

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.primary)
    async def confirm_button(self, interaction: discord.Integration, button: Button):
        data = self.result
        new_embed = make_dead_troops_embed(data, title='CONFIRMED', desc='Confirmed', confirm=True)
        new_embed.add_field(name='Deads were stored!', value='')
        self.clear_items()
        await interaction.response.edit_message(embed=new_embed, view=self)
        if DEBUG == False:
            enqueue_store_deads_info_task(self.user.id, self.result)
        else:
            print(self.result)

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.primary)
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        data = self.result
        new_embed = make_dead_troops_embed(data, title='DENIED', desc='Denied', deny=True)
        new_embed.add_field(name='Leaders have been notified and will take care of the possible issues reported.', value='')
        self.clear_items()
        await interaction.response.edit_message(embed=new_embed, view=self)
        if DEBUG == False:
            if ADMINS:
                await send_deny_message_to_admins(self.bot, self.result, self.user, self.file_url)
        else:
            print('denied')

@bot.tree.command()
@app_commands.describe(file='Please attach a file')
async def deads(interaction: discord.Integration, file: discord.Attachment):

    """
    Store deads from image attachment
    """
    
    global is_deads_up
    if not is_deads_up:
        await interaction.response.send_message('Deads bot is currently turned off!', ephemeral=True)
        return

    user = interaction.user
    print(f'\n{user} used command deads {datetime.now()}')

    if file:
        if any(file.filename.lower().endswith(image_ext) for image_ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.webp']):
            await interaction.response.defer(ephemeral=True)
            async with aiohttp.ClientSession() as session:
                async with session.get(file.url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()

                        embed = Embed(title='Image found in the message! Processing the image...', description='', color=0x00ff00)
                        embed.set_image(url=file.url)
                        await interaction.followup.send(embed=embed,  ephemeral=True)

                        result = read_roi_and_create_output_for_amounts(image_data)

                        if result == {}:
                            embed = Embed(title='Error', description='There was an issue in processing your image. Please try again.', color=0x00ff00)
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                        
                        embed = make_dead_troops_embed(result)
                        view = DeadsCheck(result, user, bot, file.url)
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

                    else:
                        embed = Embed(title='Error', description='Error in image processing. Please try again', color=0x00ff00)
                        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = Embed(title='No Attachment', description='No attachment found in the message.', color=0x00ff00)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name='setup')
async def setup(interaction: discord.Integration):

    """Setup command for the bot.
    
    Define the users/roles that has access to this command in the integrations section in your discord server settings.

    options:

    - Change sheet: for changing the sheet that the bot stores the deads into

    - ON / OFF: turn the option to store deads on or off
    """
    
    print(f'\n{interaction.user} used command setup {datetime.now()}')
    
    await interaction.response.defer(ephemeral=True)

    class SetupMenu(View):
        def __init__(self):
            super().__init__()
            self.value = None

        @discord.ui.button(label='Change deads sheet', style=discord.ButtonStyle.primary)
        async def change_deads_sheet(self, interaction: discord.Interaction, button: Button):
            
            class DeadsSheetModal(Modal, title='Change deads sheet name'):
                answer = TextInput(label='Sheet name', placeholder='', required=True)

                async def on_submit(self, interaction: discord.Integration):
                    update_bot_config_sheet_name(bot_config, str(self.answer))
                    await interaction.response.send_message(f'Sheet name changed to {self.answer}', ephemeral=True)
            
            modal = DeadsSheetModal()
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label='Turn deads command ON' if not is_deads_up else 'Turn deads command OFF', style=discord.ButtonStyle.primary)
        async def turn_on_off(self, interaction: discord.Integration, button: Button):
            global is_deads_up
            is_deads_up = not is_deads_up
            button.label = 'Turn deads command ON' if not is_deads_up else 'Turn deads command OFF'
            await interaction.response.edit_message(view=self)
            msg = 'Turned deads command ON' if is_deads_up else 'Turned deads command OFF'
            await interaction.followup.send(f'{msg}', ephemeral=True)

    view = SetupMenu()

    await interaction.followup.send('Choose a setup option:', view=view, ephemeral=True)


bot.run(BOT_TOKEN)