CREATED BY EXIDA / SEE HIM ON DISCORD: dsc.gg/exida 
# Discord Twitch Sub Checker Bot

This bot checks every 24 hours whether Discord users with linked Twitch accounts are subscribed to **plenton769** on Twitch. If a user is subscribed, they are given a special role on Discord. If the subscription ends, the role is removed. The bot also logs these changes in a `#logs` channel.

## Features

- Automatically checks Twitch subscriptions
- Assigns/removes a custom Discord role
- Posts updates in a logs channel
- Built with `discord.py` and Twitch API

## Setup

### 1. Environment Variables

Set the following in your Render dashboard or a `.env` file (for local development):

### 2. Install Requirements


### 3. Run the Bot

## Note

You must manually link Discord users to their Twitch usernames in the code (`linked_accounts` dictionary) unless you implement a system to do it automatically.

## License

MIT License (or whatever you prefer)


