import os
import json
import discord
from discord.ext import tasks, commands
import aiohttp
from dotenv import load_dotenv

load_dotenv()  # Only needed for local dev

# Load secrets from environment
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
TWITCH_SUB_ROLE_ID = int(os.getenv('TWITCH_SUB_ROLE_ID'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_STREAMER_ID = os.getenv('TWITCH_STREAMER_ID')  # This is numeric: e.g. 831220169 for plenton769

LINKED_ACCOUNTS_FILE = 'linked_accounts.json'

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

access_token = None


def load_links():
    if not os.path.exists(LINKED_ACCOUNTS_FILE):
        return {}
    with open(LINKED_ACCOUNTS_FILE, 'r') as f:
        return json.load(f)


def save_links(data):
    with open(LINKED_ACCOUNTS_FILE, 'w') as f:
        json.dump(data, f)


@bot.command()
async def link(ctx, twitch_username: str):
    """Link your Discord account to your Twitch username."""
    data = load_links()
    data[str(ctx.author.id)] = twitch_username.lower()
    save_links(data)
    await ctx.send(f"{ctx.author.mention}, your Twitch account has been linked to `{twitch_username}`.")


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

        # Get user ID
        async with session.get(f'https://api.twitch.tv/helix/users?login={twitch_user_login}', headers=headers) as user_resp:
            user_data = await user_resp.json()
            if not user_data['data']:
                return False
            user_id = user_data['data'][0]['id']

        # Check sub
        async with session.get(
            f'https://api.twitch.tv/helix/subscriptions/user?broadcaster_id={TWITCH_STREAMER_ID}&user_id={user_id}',
            headers=headers
        ) as sub_resp:
            return sub_resp.status == 200


@tasks.loop(hours=24)
async def check_subs():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    role = guild.get_role(TWITCH_SUB_ROLE_ID)
    log_channel = discord.utils.get(guild.text_channels, name='logs')
    links = load_links()

    for discord_id, twitch_username in links.items():
        member = guild.get_member(int(discord_id))
        if not member:
            continue

        try:
            subbed = await is_user_subbed(twitch_username)

            if subbed and role not in member.roles:
                await member.add_roles(role)
                if log_channel:
                    await log_channel.send(f"{member.mention} subbed on Twitch.")
            elif not subbed and role in member.roles:
                await member.remove_roles(role)
                if log_channel:
                    await log_channel.send(f"{member.mention} is not a sub anymore.")
        except Exception as e:
            print(f"Error checking {twitch_username}: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    check_subs.start()
