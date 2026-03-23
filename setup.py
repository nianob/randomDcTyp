import sys
import subprocess

print("Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "discord.py", "discord[voice]", "regex", "ollama"])

# bot_token.hidden.txt
print("Please go to the discord developer portal (https://discord.com/developers/applications) and create or select a bot.")
token = input("Please input the Bot-Token: ").strip()
with open("bot_token.hidden.txt", "x") as f:
    f.write(token)

# config.json
with open("config_template.jsonc", "r") as f_template:
    with open("config.json", "x") as f:
        for line in f_template.readlines():
            data, *comments = line.split("//")
            if not data:
                continue
            if ": " not in data:
                f.write(data+"\n")
                continue
            name, current = data.split(": ")
            new = input("Please input "+"//".join(comments).strip()+(" (leave empty to disable functionality)" if current.strip(" \n\t,")=="null" else "")+": ").strip()
            if new == "":
                new = "null"
            f.write(f"{name}: {new}{',' if current.strip()[-1] == ',' else ''}\n")

            
        