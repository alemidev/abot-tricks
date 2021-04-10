import re

from collections import Counter

from pyrogram import filters

from bot import alemiBot

from util.permission import is_allowed, is_superuser
from util.message import edit_or_reply
from util.getters import get_text, get_username, get_channel
from util.command import filterCommand
from util.decorators import report_error, set_offline
from util.help import HelpCategory

import logging
logger = logging.getLogger(__name__)

HELP = HelpCategory("TEMPORARY")

# This doesn't really fit here, will be moved into statistics plugin once I'm done with a proper statistics plugin
HELP.add_help(["freq", "frequent"], "find frequent words in messages",
				"find most used words in last messages. If no number is given, will search only " +
				"last 100 messages. By default, 10 most frequent words are shown, but number of results " +
				"can be changed with `-r`. By default, only words of `len > 3` will be considered. " +
				"A minimum word len can be specified with `-min`. Will search in current group or any specified with `-g`. " +
				"A single user can be specified with `-u` : only messages from that user will count if provided.",
				args="[-r <n>] [-min <n>] [-g <group>] [-u <user>] [n]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["freq", "frequent"], list(alemiBot.prefixes), options={
	"results" : ["-r", "-res"],
	"minlen" : ["-min"],
	"group" : ["-g", "-group"],
	"user" : ["-u", "-user"]
}))
@report_error(logger)
@set_offline
async def frequency_cmd(client, message):
	results = int(message.command["results"]) if "results" in message.command else 10
	number = int(message.command["cmd"][0]) if "cmd" in message.command else 100
	min_len = int(message.command["minlen"]) if "minlen" in message.command else 3
	group = None
	if "group" in message.command:
		val = message.command["group"]
		group = await client.get_chat(int(val) if val.isnumeric() else val)
	else:
		group = message.chat
	user = None
	if "user" in message.command:
		val = message.command["user"]
		user = await client.get_users(int(val) if val.isnumeric() else val)
	logger.info(f"Counting {results} most frequent words in last {number} messages")
	response = await edit_or_reply(message, f"` â†’ ` Counting word occurrences...")
	words = []
	count = 0
	async for msg in client.iter_history(group.id, limit=number):
		if not user or user.id == msg.from_user.id:
			words += [ w for w in re.sub(r"[^0-9a-zA-Z\s\n]+", "", get_text(msg).lower()).split() if len(w) > min_len ]
		count += 1
		if count % 250 == 0:
			await client.send_chat_action(message.chat.id, "playing")
			await response.edit(f"` â†’ [{count}/{number}] ` Counting word occurrences...")
	count = Counter(words).most_common()
	from_who = f"(from **{get_username(user)}**)" if user else ""
	output = f"`â†’ {get_channel(group)}` {from_who}\n` â†’ ` **{results}** most frequent words __(len > {min_len})__ in last **{number}** messages:\n"
	for i in range(results):
		output += f"`{i+1:02d}]{'-'*(results-i-1)}>` `{count[i][0]}` `({count[i][1]})`\n"
	await response.edit(output, parse_mode="markdown")

HELP.add_help(["joined", "jd"], "count active chats",
				"get number of all dialogs : groups, supergroups, channels, dms, bots")
@alemiBot.on_message(is_superuser & filterCommand(["joined", "jd"], list(alemiBot.prefixes)))
async def joined_cmd(client, message):
	logger.info("Listing active dialogs")
	msg = await edit_or_reply(message, "` → ` Counting...")
	res = {}
	async for dialog in client.iter_dialogs():
		if dialog.chat.type in res:
			res[dialog.chat.type] += 1
		else:
			res[dialog.chat.type] = 1
	out = "`→ ` --Active chats-- \n"
	for k in res:
		out += f"` → {k} ` {res[k]}\n"
	await msg.edit(out)