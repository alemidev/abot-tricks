import asyncio
import time
import re
import os
import secrets
import logging

from pyrogram import filters
from pyrogram.types import InputMediaAnimation, InputMediaDocument, InputMediaAudio, InputMediaVideo, InputMediaPhoto
from pyrogram.errors import PeerIdInvalid

from bot import alemiBot

from util import batchify
from util.permission import is_allowed, is_superuser, allow, disallow, serialize, list_allowed, ALLOWED
from util.user import get_username
from util.message import edit_or_reply, get_text, is_me
from util.text import split_for_window
from util.command import filterCommand
from util.time import parse_timedelta
from util.decorators import report_error, set_offline
from util.help import HelpCategory

from zalgo_text import zalgo

logger = logging.getLogger(__name__)

HELP = HelpCategory("MESSAGE")

HELP.add_help("delme", "immediately delete message",
				"add `-delme` at the end of a message to have it deleted after a time. " +
				"If no time is given, message will be immediately deleted", args="[<time>]")
@alemiBot.on_message(~filters.scheduled & filters.me & filters.regex(pattern=
	r"(?:.*|)(?:-delme)(?: |)(?P<time>[0-9]+|)$"
), group=5)
async def deleteme(client, message):
	logger.info("Deleting sent message")
	t = message.matches[0]["time"]
	if t != "":
		await asyncio.sleep(float(t))
	await message.delete()

HELP.add_help("shrug", "¯\_(ツ)_/¯", "will replace `.shrug` anywhere "+
				"in yor message with the composite emoji. (this will ignore your custom prefixes)")
@alemiBot.on_message(filters.me & filters.regex(pattern="[\\" + "\\".join(list(alemiBot.prefixes)) + "]shrug"), group=2)
async def shrug_replace(client, message):
	logger.info(f" ¯\_(ツ)_/¯ ")
	await message.edit(re.sub(r"[\.\/\!]shrug","¯\_(ツ)_/¯", message.text.markdown))

HELP.add_help("eyy", "( ͡° ͜ʖ ͡°)", "will replace `.eyy` anywhere "+
				"in yor message with the composite emoji. (this will ignore your custom prefixes)")
@alemiBot.on_message(filters.me & filters.regex(pattern="[\\" + "\\".join(list(alemiBot.prefixes)) + "]eyy"), group=3)
async def eyy_replace(client, message):
	logger.info(f" ( ͡° ͜ʖ ͡°) ")
	await message.edit(re.sub(r"[\.\/\!]eyy","( ͡° ͜ʖ ͡°)", message.text.markdown))

HELP.add_help("holup", "(▀̿Ĺ̯▀̿ ̿)", "will replace `.holup` anywhere "+
				"in yor message with the composite emoji. (this will ignore your custom prefixes)")
@alemiBot.on_message(filters.me & filters.regex(pattern="[\\" + "\\".join(list(alemiBot.prefixes)) + "]holup"), group=4)
async def holup_replace(client, message):
	logger.info(f" (▀̿Ĺ̯▀̿ ̿) ")
	await message.edit(re.sub(r"[\.\/\!]holup","(▀̿Ĺ̯▀̿ ̿)", message.text.markdown))

HELP.add_help(["merge"], "join multiple messages into one",
				"join multiple messages sent by you into one. Reply to the first one to merge, bot will join " +
				"every consecutive message you sent. You can stop the bot from deleting merged messages with " +
				"`-nodel` flag. You can specify a separator with `-s`, it will default to `\n`. You can specify max " +
				"number of messages to merge with `-max`. Merge will stop at first message with attached media or that " +
				"is a reply.", args="[-s <sep>] [-max <n>] [-nodel]", public=False)
@alemiBot.on_message(is_superuser & filterCommand(["merge"], list(alemiBot.prefixes), options={
	"separator" : ["-s"],
	"max" : ["-max"]
}, flags=["-nodel"]))
@report_error(logger)
@set_offline
async def merge_cmd(client, message):
	if not message.reply_to_message:
		return await edit_or_reply(message, "`[!] → ` No start message given")
	m_id = message.reply_to_message.message_id
	sep = message.command["separator"] if "separator" in message.command else "\n"
	del_msg = "-nodel" not in message.command["flags"]
	max_to_merge = int(message.command["max"]) if "max" in message.command else -1
	logger.info(f"Merging messages")
	out = ""
	count = 0
	async for msg in client.iter_history(message.chat.id, offset_id=m_id, reverse=True):
		if msg.message_id == message.message_id or not is_me(msg) or msg.media \
		or msg.reply_to_message or (max_to_merge > 0 and count >= max_to_merge):
			break
		out += msg.text.markdown + sep
		count += 1
		if del_msg and msg.message_id != m_id: # don't delete the one we want to merge into
			await msg.delete()
	await message.reply_to_message.edit(out)
	await edit_or_reply(message, f"` → ` Merged {count} messages")

def make_media_group(files):
	if all(fname.endswith((".jpg", ".jpeg", ".png")) for fname in files):
		return [ InputMediaPhoto(fname) for fname in files ]
	elif all(fname.endswith((".gif", ".mp4", ".webm")) for fname in files):
		return [ InputMediaVideo(fname) for fname in files ]
	elif all(fname.endswith((".webp", ".tgs")) for fname in files):
		return [ InputMediaAnimation(fname) for fname in files ]
	elif all(fname.endswith((".mp3", ".ogg", ".wav")) for fname in files):
		return [ InputMediaAudio(fname) for fname in files ]
	else:
		return [ InputMediaDocument(fname) for fname in files ]

HELP.add_help(["album"], "join multiple media into one message",
				"send a new album containing last media you sent. If no number is specified, only consecutive media " +
				"will be grouped. Original messages will be deleted, but this can be prevented with the `-nodel` flag. " +
				"Reply to a message to start grouping from that message. Add the `-all` flag to group messages from anyone.",
				args="[-nodel] [-all] [n]", public=False)
@alemiBot.on_message(is_superuser & filterCommand(["album"], list(alemiBot.prefixes), flags=["-nodel", "-all"]))
@report_error(logger)
@set_offline
async def album_cmd(client, message):
	out = ""
	logger.info(f"Making album")
	del_msg = "-nodel" not in message.command["flags"]
	from_all = "-all" in message.command["flags"]
	max_to_merge = int(message.command["cmd"][0]) \
			if "cmd" in message.command and message.command["cmd"][0].isnumeric() else -1
	opts = {}
	if message.reply_to_message:
		opts["offset_id"] = message.reply_to_message.message_id
	files = []
	msgs = []
	count = 0
	out += "` → ` Searching media"
	await edit_or_reply(message, out)
	if message.reply_to_message and message.media:
		files.append(await client.download_media(message.edit_or_reply))
		msgs.append(message.reply_to_message)
		count += 1
	async for msg in client.iter_history(message.chat.id, **opts):
		if max_to_merge < 0 and not from_all and not is_me(msg):
			break
		if (from_all or is_me(msg)) and msg.media:
			try:
				files.append(await client.download_media(msg))
				msgs.append(msg)
				count += 1
			except ValueError:
				pass # ignore, go forward
		if max_to_merge > 0 and count >= max_to_merge:
			break
		if count >= 10: # max 10 items anyway
			break
	media = make_media_group(files)
	out += " [`OK`]\n` → ` Uploading album"
	await edit_or_reply(message, out)
	await client.send_media_group(message.chat.id, media)
	out += " [`OK`]\n` → ` Cleaning up"
	await edit_or_reply(message, out)
	for f in files:
		os.remove(f)
	if del_msg:
		for m in msgs:
			await m.delete()
	out += " [`OK`]\n` → ` Done"
	await edit_or_reply(message, out)

HELP.add_help(["slow", "sl"], "make text appear slowly",
				"edit message adding batch of characters every time. If no batch size is " +
				"given, it will default to 1. If no time is given, it will default to 0.5s.",
				args="[-t <time>] [-b <batch>] <text>")
@alemiBot.on_message(is_superuser & filterCommand(["slow", "sl"], list(alemiBot.prefixes), options={
		"time" : ["-t"],
		"batch" : ["-b"]
}))
@set_offline
async def slowtype_cmd(client, message):
	args = message.command
	if "arg" not in args:
		return
	logger.info(f"Making text appear slowly")
	interval = 0.5
	batchsize = 1
	if "time" in args:
		interval = float(args["time"])
	if "batch" in args:
		batchsize = int(args["batch"])
	out = ""
	msg = message if is_me(message) else await message.reply("` → ` Ok, starting")
	try:
		for seg in batchify(args["arg"], batchsize):
			out += seg
			if seg.isspace() or seg == "":
				continue # important because sending same message twice causes an exception
			await client.send_chat_action(message.chat.id, "typing")
			await msg.edit(out, parse_mode=None)
			await asyncio.sleep(interval) # does this "start" the coroutine early?
	except:
		logger.exception("Error in .slow command")
		pass # msg was deleted probably
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["zalgo"], "h̴͔̣̰̲̣̫̲͉̞͍͖̩͖̭͓̬̼ͫ̈͒̊͟͟͠e̵̙͓̼̻̳̝͍̯͇͕̳̝͂̌͐ͫ̍ͬͨ͑̕ ̷̴̢̛̝̙̼̣̔̎̃ͨ͆̾ͣͦ̑c̵̥̼͖̲͓̖͕̭ͦ̽ͮͮ̇ͭͥ͠o̷̷͔̝̮̩͍͉͚͌̿ͥ̔ͧ̉͛ͭ͊̀͜ͅm̵̸̡̰̭͓̩̥͚͍͎̹͖̠̩͙̯̱͙͈͍͉͂ͩ̄̅͗͞e̢̛͖̪̞̐̒̈̓̒́͒̈́̀ͅṡ̡̢̟͖̩̝̣͙̣͔̑́̓̿̊̑̍̉̓͘͢",
				"Will completely fuck up the text with 'zalgo' patterns. You can increase noise " +
				"with the `-n` flag, otherwise will default to 1. You can increase overrall damage with `-d` " +
				"(should be a float from 0 to 1, default to 0). The max number of extra characters per " +
				"letter can be specified with `-max`, with default 10.", args="[-n <n>] [-d <n>] [-max <n>] <text>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["zalgo"], list(alemiBot.prefixes), options={
	"noise" : ["-n", "-noise"],
	"damage" : ["-d", "-damage"],
	"max" : ["-max"]
}))
@report_error(logger)
@set_offline
async def zalgo_cmd(client, message):
	logger.info(f"Making message zalgoed")
	text = re.sub(r"-delme(?: |)(?:[0-9]+|)", "", message.command["raw"])
	if text == "":
		return 
	noise = int(message.command["noise"]) if "noise" in message.command else 1
	damage = max(min(float(message.command["damage"]), 1.0), 0.0) if "damage" in message.command else 0
	max_accents = int(message.command["max"]) if "max" in message.command else 10
	z = zalgo.zalgo()
	z.maxAccentsPerLetter = max_accents
	z.numAccentsUp = ( 1+ (damage*noise), 3 * noise )
	z.numAccentsDown = ( 1+ (damage*noise), 3 * noise )
	z.numAccentsMiddle = ( 1+ (damage*noise), 2 * noise )
	out = z.zalgofy(text)

	first = True # kinda ugly but this is kinda different from edit_or_reply
	for batch in batchify(out, 4090):
		if first and is_me(message):
			await message.edit(batch)
		else:
			await client.send_message(message.chat.id, batch)
		first = False

HELP.add_help(["rc", "randomcase"], "make text randomly capitalized",
				"will edit message applying random capitalization to every letter, like the spongebob meme.",
				args="<text>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["rc", "randomcase"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def randomcase_cmd(client, message):
	logger.info(f"Making message randomly capitalized")
	text = message.command["arg"]
	if text == "":
		return 
	msg = "" # omg this part is done so badly
	val = 0  # but I want a kinda imbalanced random
	upper = False
	for c in text:
		last = val
		val = secrets.randbelow(4)
		if val > 2:
			msg += c.upper()
			upper = True
		elif val < 1:
			msg += c
			upper = False
		else:
			if upper:
				msg += c
				upper = False
			else:
				msg += c.upper()
				upper = True
	await message.edit(msg)

def interval(delta):
	if delta > 100:
		return 10
	if delta > 50:
		return 5
	if delta > 20:
		return 3
	if delta > 10:
		return 1
	if delta > 5:
		return 0.5
	if delta > 2:
		return 0.25
	return 0

HELP.add_help(["cd", "countdown"], "count down",
				"will edit message to show a countdown. If no time is given, it will be 5s.",
				args="[<time>]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["countdown", "cd"], list(alemiBot.prefixes)))
@set_offline
async def countdown_cmd(client, message):
	if is_me(message):
		tgt_msg = message
	else:
		tgt_msg = await message.reply("` → `")
	end = time.time() + 5
	if "cmd" in message.command:
		try:
			end = time.time() + float(message.command["cmd"][0])
		except ValueError:
			return await tgt_msg.edit("`[!] → ` argument must be a float")
	msg = tgt_msg.text + "\n` → Countdown ` **{:.1f}**"
	last = ""
	logger.info(f"Countdown")
	while time.time() < end:
		curr = msg.format(time.time() - end)
		if curr != last: # with fast counting down at the end it may try to edit with same value
			await tgt_msg.edit(msg.format(time.time() - end))
			last = curr
		await asyncio.sleep(interval(end - time.time()))
	await tgt_msg.edit(msg.format(0))
