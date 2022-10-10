import asyncio
import time
import re
import os
import secrets
import logging

from pyrogram import filters
from pyrogram.enums import ChatAction
from pyrogram.types import InputMediaAnimation, InputMediaDocument, InputMediaAudio, InputMediaVideo, InputMediaPhoto
from pyrogram.errors import PeerIdInvalid

from alemibot import alemiBot

from alemibot.util.command import _Message as Message
from alemibot.util import (
	batchify, is_allowed, sudo, get_username, get_text, ProgressChatAction, edit_or_reply, is_me, 
	filterCommand, parse_timedelta, report_error, set_offline, cancel_chat_action, HelpCategory
)

from zalgo_text import zalgo

logger = logging.getLogger(__name__)

HELP = HelpCategory("MESSAGE")

@HELP.add(title="delme", cmd="[<time>]")
@alemiBot.on_message(~filters.scheduled & filters.me & filters.regex(pattern=
	r"(?:.*|)(?:-delme)(?: |)(?P<time>[0-9]+|)$"
), group=5)
async def deleteme(client:alemiBot, message:Message):
	"""immediately delete message

	Add `-delme [<time>]` at the end of a message to have it deleted after specified time.
	If no time is given, message will be immediately deleted.
	If message is another command, it will run first and then message will be deleted.
	"""
	t = message.matches[0]["time"]
	if t != "":
		await asyncio.sleep(float(t))
	await message.delete()

@HELP.add(title="shrug")
@alemiBot.on_message(filters.me & filters.regex(pattern=r":shrug:"), group=2)
async def shrug_replace(client:alemiBot, message:Message):
	"""will replace :shrug: ¯\_(ツ)_/¯ anywhere in message (like tdesktop)"""
	await message.edit(re.sub(r":shrug:","¯\_(ツ)_/¯", message.text.markdown))

@HELP.add(title="eyy")
@alemiBot.on_message(filters.me & filters.regex(pattern=r":eyy:"), group=3)
async def eyy_replace(client:alemiBot, message:Message):
	"""will replace :eyy: with ( ͡° ͜ʖ ͡°) anywhere in message"""
	await message.edit(re.sub(r":eyy:","( ͡° ͜ʖ ͡°)", message.text.markdown))

@HELP.add(title="holup")
@alemiBot.on_message(filters.me & filters.regex(pattern=":holup:"), group=4)
async def holup_replace(client:alemiBot, message:Message):
	"""will replace :holup: with (▀̿Ĺ̯▀̿ ̿) anywhere in message"""
	await message.edit(re.sub(r":holup:","(▀̿Ĺ̯▀̿ ̿)", message.text.markdown))

@HELP.add(cmd="[<n>]")
@alemiBot.on_message(sudo & filterCommand(["merge"], options={
	"separator" : ["-s", "--separator"],
}, flags=["-nodel"]))
@report_error(logger)
@set_offline
async def merge_cmd(client:alemiBot, message:Message):
	"""join multiple messages into one

	Reply to the first one to merge, bot will join	every consecutive message you sent.
	You can stop the bot from deleting merged messages with `-nodel` flag.
	You can specify a separator with `-s`, it will default to `\n`.
	You can specify max number of messages to merge as command argument.
	Merge will stop at first message with attached media or that is a reply.
	"""
	if not message.reply_to_message:
		return await edit_or_reply(message, "`[!] → ` No start message given")
	if not is_me(message.reply_to_message):
		return await edit_or_reply(message, "`[!] → ` Can't merge message of others")
	m_id = message.reply_to_message.id
	sep = message.command["separator"] or "\n"
	del_msg = not bool(message.command["-nodel"])
	max_to_merge = int(message.command[0] or -1)
	out = ""
	count = 0
	async for msg in client.iter_history(message.chat.id, offset_id=m_id, reverse=True):
		if msg.id == message.id or not is_me(msg) or msg.media \
		or msg.reply_to_message or (max_to_merge > 0 and count >= max_to_merge):
			break
		out += msg.text.markdown + sep
		count += 1
		if del_msg and msg.id != m_id: # don't delete the one we want to merge into
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

@HELP.add(cmd="[<n>]")
@alemiBot.on_message(sudo & filterCommand(["album"], flags=["-nodel", "-all"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def album_cmd(client:alemiBot, message:Message): # TODO add uploading_file chat action progress
	"""join multiple media into one message

	Send a new album containing last media you sent. Reply to a message to start grouping from that message.
	If no number is specified, only consecutive media will be grouped.
	Original messages will be deleted, but this can be prevented with the `-nodel` flag.
	Media will be downloaded and reuploaded, so it may take some time
	Add the `-all` flag to group messages from anyone.
	"""
	out = ""
	del_msg = not bool(message.command["-nodel"])
	from_all = bool(message.command["-all"])
	max_to_merge = min(int(message.command[0] or 10), 10)
	prog = ProgressChatAction(client, message.chat.id)
	opts = {}
	if message.reply_to_message:
		opts["offset_id"] = message.reply_to_message.id
	files = []
	msgs = []
	count = 0
	out += "` → ` Searching media"
	await edit_or_reply(message, out)
	if message.reply_to_message and message.media:
		files.append(await client.download_media(message.edit_or_reply, progress=prog.tick))
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
		if count >= max_to_merge:
			break
	media = make_media_group(files)
	out += " [`OK`]\n` → ` Uploading album"
	await edit_or_reply(message, out)
	await prog.tick()
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

@HELP.add(cmd="<text>")
@alemiBot.on_message(sudo & filterCommand(["slow", "sl"], options={
		"time" : ["-t"],
		"batch" : ["-b"]
}))
@set_offline
async def slowtype_cmd(client:alemiBot, message:Message):
	"""make text appear slowly

	Edit message adding batch of characters every time.
	If no batch size is given, it will default to 1.
	If no time is given, it will default to 0.5s.
	"""
	if len(message.command) < 1:
		return
	intrv = float(message.command["time"] or 0.5)
	batchsize = int(message.command["batch"] or 1)
	out = ""
	msg = message if is_me(message) else await message.reply("` → ` Ok, starting")
	try:
		for seg in batchify(message.command.text, batchsize):
			out += seg
			if seg.isspace() or seg == "":
				continue # important because sending same message twice causes an exception
			await client.send_chat_action(message.chat.id, ChatAction.TYPING)
			await msg.edit(out, parse_mode=None)
			await asyncio.sleep(intrv) # does this "start" the coroutine early?
	except:
		logger.exception("Error in .slow command")
		pass # msg was deleted probably
	await client.send_chat_action(message.chat.id, ChatAction.CANCEL)

@HELP.add(cmd="<text>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["zalgo"], options={
	"noise" : ["-n", "-noise"],
	"damage" : ["-d", "-damage"],
	"max" : ["-max"]
}))
@report_error(logger)
@set_offline
async def zalgo_cmd(client:alemiBot, message:Message):
	"""h̴͔̣̰̲̣̫̲͉̞͍͖̩͖̭͓̬̼ͫ̈͒̊͟͟͠e̵̙͓̼̻̳̝͍̯͇͕̳̝͂̌͐ͫ̍ͬͨ͑̕ ̷̴̢̛̝̙̼̣̔̎̃ͨ͆̾ͣͦ̑c̵̥̼͖̲͓̖͕̭ͦ̽ͮͮ̇ͭͥ͠o̷̷͔̝̮̩͍͉͚͌̿ͥ̔ͧ̉͛ͭ͊̀͜ͅm̵̸̡̰̭͓̩̥͚͍͎̹͖̠̩͙̯̱͙͈͍͉͂ͩ̄̅͗͞e̢̛͖̪̞̐̒̈̓̒́͒̈́̀ͅṡ̡̢̟͖̩̝̣͙̣͔̑́̓̿̊̑̍̉̓͘͢

	Will completely fuck up the text with 'zalgo' patterns.
	You can increase noise with the `-n` flag, otherwise will default to 1.
	You can increase overrall damage with `-d` (should be a float from 0 to 1, default to 0).
	The max number of extra characters per letter can be specified with `-max`, with default 10.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	text = re.sub(r"-delme(?: |)(?:[0-9]+|)", "", message.command.text)
	noise = int(message.command["noise"] or 1)
	damage = max(min(float(message.command["damage"] or 0), 1.0), 0.0)
	max_accents = int(message.command["max"] or 10)
	z = zalgo.zalgo()
	z.maxAccentsPerLetter = max_accents
	z.numAccentsUp = ( 1+ int(damage*noise), 3 * noise )
	z.numAccentsDown = ( 1+ int(damage*noise), 3 * noise )
	z.numAccentsMiddle = ( 1+ int(damage*noise), 2 * noise )
	out = z.zalgofy(text)

	first = True # kinda ugly but this is kinda different from edit_or_reply
	for batch in batchify(out, 4090):
		if first and is_me(message):
			await message.edit(batch)
		else:
			await client.send_message(message.chat.id, batch)
		first = False

@HELP.add(cmd="<text>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["rc", "randomcase"]))
@report_error(logger)
@set_offline
async def randomcase_cmd(client:alemiBot, message:Message):
	"""make text randomly capialized

	Will edit message applying random capitalization to every letter, like the spongebob meme.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	text = message.command.text
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
	await edit_or_reply(message, msg)

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

@HELP.add(cmd="[<seconds>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["countdown", "cd"]))
@set_offline
async def countdown_cmd(client:alemiBot, message:Message):
	"""count down

	Will edit message to show a countdown. If no time is given, it will be 5s.
	"""
	if is_me(message):
		tgt_msg = message
	else:
		tgt_msg = await message.reply("` → `")
	end = time.time() + float(message.command[0] or 5)
	msg = tgt_msg.text + "\n` → Countdown ` **{:.1f}**"
	last = ""
	while time.time() < end:
		curr = msg.format(time.time() - end)
		if curr != last: # with fast counting down at the end it may try to edit with same value
			await tgt_msg.edit(msg.format(time.time() - end))
			last = curr
		await asyncio.sleep(interval(end - time.time()))
	await tgt_msg.edit(msg.format(0))
