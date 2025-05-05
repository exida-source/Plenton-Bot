import os
import discord
from discord.ext import tasks, commands
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()  # Only needed for local development; ignored on Render

# Load variables from environment
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
TWITCH_SUB_ROLE_ID = int(os.getenv('TWITCH_SUB_ROLE_ID'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_STREAMER_ID = os.getenv('TWITCH_STREAMER_ID')  # Numeric Twitch user ID

# Mapping: Discord User ID -> Twitch Username
linked_accounts = {
    123456789012345678: 'twitch_username1',
    234567890123456789: 'twitch_username2',
    # Add your real data here
}

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

access_token = None


async def get_twitch_app_access_token():
    async with aiohttp.ClientSession() as session:
        url = 'https://id.twitch.tv/oauth2/token'
        params = {
            'client_id': TWITCH_CLIENT_ID,
            'client_secret': TWITCH_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        async with session.post(url, params=params) as resp:
            data = await resp.json()
            return data['access_token']


async def is_user_subbed(twitch_user_login):
    global access_token
    if access_token is None:
        access_token = await get_twitch_app_access_token()

    async with aiohttp.ClientSession() as session:
        headers = {
            'Client-ID': TWITCH_CLIENT_ID,
            'Authorization': f'Bearer {access_token}'
        }

        # Get user ID from login
        async with session.get(f'https://api.twitch.tv/helix/users?login={twitch_user_login}', headers=headers) as user_resp:
            user_data = await user_resp.json()
            if not user_data['data']:
                return False
            user_id = user_data['data'][0]['id']

        # Check subscription
        async with session.get(
            f'https://api.twitch.tv/helix/subscriptions/user?broadcaster_id={TWITCH_STREAMER_ID}&user_id={user_id}',
            headers=headers
        ) as sub_resp:
            return sub_resp.status == 200


@tasks.loop(hours=24)
async def check_subs():
    guild = bot.get_guild(GUILD_ID)
    log_channel = discord.utils.get(guild.text_channels, name='logs')
    role = guild.get_role(TWITCH_SUB_ROLE_ID)

    for user_id, twitch_name in linked_accounts.items():
        member = guild.get_member(user_id)
        if member is None:
            continue

        try:
            subbed = await is_user_subbed(twitch_name)

            if subbed and role not in member.roles:
                await member.add_roles(role)
                await log_channel.send(f"{member.mention} subbed on Twitch")
            elif not subbed and role in member.roles:
                await member.remove_roles(role)
                await log_channel.send(f"{member.mention} is not a sub anymore")

        except Exception as e:
            print(f"Error checking sub for {twitch_name}: {e}")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_subs.start()


bot.run(TOKEN)
