import os
import discord
from discord.ext import tasks, commands
import aiohttp
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()  # Optional for local testing

# Environment Variables
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
TWITCH_SUB_ROLE_ID = int(os.getenv('TWITCH_SUB_ROLE_ID'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_STREAMER_ID = os.getenv('TWITCH_STREAMER_ID')
UPSTASH_REDIS_URL = os.getenv("UPSTASH_REDIS_URL")
UPSTASH_REDIS_TOKEN = os.getenv("UPSTASH_REDIS_TOKEN")

# Redis Setup
redis_client = redis.from_url(
    UPSTASH_REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    username="default",
    password=UPSTASH_REDIS_TOKEN
)

LINK_KEY_PREFIX = "linked:"

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

access_token = None

# Redis functions
async def get_linked_twitch(discord_id):
    return await redis_client.get(LINK_KEY_PREFIX + str(discord_id))

async def set_linked_twitch(discord_id, twitch_username):
    await redis_client.set(LINK_KEY_PREFIX + str(discord_id), twitch_username)

async def get_all_links():
    keys = await redis_client.keys(LINK_KEY_PREFIX + "*")
    return [
        {"key": key.replace(LINK_KEY_PREFIX, ""), "twitch_username": await redis_client.get(key)}
        for key in keys
    ]

# Twitch API
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

        async with session.get(f'https://api.twitch.tv/helix/users?login={twitch_user_login}', headers=headers) as user_resp:
            user_data = await user_resp.json()
            if not user_data['data']:
                return False
            user_id = user_data['data'][0]['id']

        async with session.get(
            f'https://api.twitch.tv/helix/subscriptions/user?broadcaster_id={TWITCH_STREAMER_ID}&user_id={user_id}',
            headers=headers
        ) as sub_resp:
            return sub_resp.status == 200

# Discord commands and events
@bot.command()
async def link(ctx, twitch_username: str):
    """Link your Discord account to your Twitch username."""
    await set_linked_twitch(ctx.author.id, twitch_username.lower())
    await ctx.send(f"{ctx.author.mention}, your Twitch account has been linked to `{twitch_username}`.")

@tasks.loop(hours=24)
async def check_subs():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    role = guild.get_role(TWITCH_SUB_ROLE_ID)
    log_channel = discord.utils.get(guild.text_channels, name='logs')
    linked_users = await get_all_links()

    for user in linked_users:
        discord_id = int(user["key"])
        twitch_username = user["twitch_username"]
        member = guild.get_member(discord_id)
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
    print(f"Bot is online as {bot.user}")
    check_subs.start()

bot.run(TOKEN)
