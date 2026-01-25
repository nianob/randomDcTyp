## About this project
This is the code from the @randomDcTyp#3551 discord bot for the [Good Game Clan](https://discord.gg/HUypbqwpy7).\
Its a bit of a mess but it works

## How to install:
- Make sure you are running Python 3.11
- run following command to install packages: `python3 -m pip install discord.py "discord[voice]" regex`
- go to the [discord developer portal](https://discord.com/developers/applications), create or select a bot and copy your bot token
- create a file named `bot_token.hidden.txt` and put the token in there
- create `config.json` from `confic_template.jsonc`, make sure to remove the comments
- create `.env` in `activity` from `env_template.txt` and fill in the values appropriately
- in `activity/data` create `sessions.sqlite` and leave the file empty

## How to run
- cd to this folder and run `python3 bot.py`
