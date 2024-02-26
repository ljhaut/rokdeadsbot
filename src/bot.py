from dotenv import dotenv_values
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands, Embed
import discord
import aiohttp
from imageProcessing import read_roi_and_create_output_for_amounts
from db import store_deads_info
from botConfigHandler import read_bot_config, update_bot_config_channel_id, add_admins_to_bot_config, remove_admins_from_bot_config
from constants import emote_id, columns, embed_troop_type, result_order

bot_config = read_bot_config()
config = dotenv_values('.env.dev')

bot_token = config['BOT_TOKEN']
channel_id = bot_config['CHANNEL_ID']
admins = bot_config['ADMINS']
debug = True if config['DEBUG'] == 'True' else False
bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(e)
    print("Bot is online")

async def send_deny_message_to_admins(bot, data, user, img):
    admin = await bot.fetch_user(admins[0])
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
        if debug == False:
            for k, v in self.result.items():
                store_deads_info(self.user.id, v, columns[k])
        else:
            print(self.result)

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.primary)
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        data = self.result
        new_embed = make_dead_troops_embed(data, title='DENIED', desc='Denied', deny=True)
        new_embed.add_field(name='Leaders have been notified and will take care of the possible issues reported.', value='')
        self.clear_items()
        await interaction.response.edit_message(embed=new_embed, view=self)
        await send_deny_message_to_admins(self.bot, self.result, self.user, self.file_url)

class SetupMenu(View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Change admin IDs', style=discord.ButtonStyle.primary)
    async def change_admin_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message('Please send the new admin IDs.', ephemeral=True)


@bot.tree.command(name='deads')
@app_commands.describe(file='Please attach a file')
async def deads(interaction: discord.Integration, file: discord.Attachment):

    """
    Store deads from pasted image attachment
    """

    if interaction.channel_id != channel_id:
        print('Not the designated channel for the bot')
        return
    
    user = interaction.user
    
    if file:
        if any(file.filename.lower().endswith(image_ext) for image_ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.webp']):
            await interaction.response.defer(ephemeral=True)
            async with aiohttp.ClientSession() as session:
                async with session.get(file.url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()

                        embed = Embed(title='Image found in the message!', description='', color=0x00ff00)
                        embed.set_image(url=file.url)
                        await interaction.followup.send(embed=embed,  ephemeral=True)

                        result = read_roi_and_create_output_for_amounts(image_data)

                        if result == {}:
                            embed = Embed(title='Error', description='There was an issue in processing your image. Please try again.', color=0x00ff00)
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                        
                        if debug == False:
                            embed = make_dead_troops_embed(result)
                        else:
                            embed = make_dead_troops_embed(result, 'Debug', 'Check console')
                        view = DeadsCheck(result, user, bot, file.url)
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

                    else:
                        embed = Embed(title='Error', description='Error in image processing. Please try again', color=0x00ff00)
                        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = Embed(title='No Attachment', description='No attachment found in the message.', color=0x00ff00)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.command()
async def setup(ctx):
    ctx.inter
    user_id = ctx.author.id
    if user_id not in bot_config['ADMINS']: 
        print(f'User {user_id} is not admin and is trying to access an admin command')
        return

    view = SetupMenu()
    await ctx.reply('Choose a setup option:', view=view)


bot.run(bot_token)