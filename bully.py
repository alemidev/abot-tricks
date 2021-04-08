import asyncio
import logging
import re
import json
import time

from pyrogram import filters
from pyrogram.errors import BadRequest, FloodWait
from pyrogram.raw.functions.contacts import ResolveUsername

from bot import alemiBot

from util.permission import is_allowed, is_superuser
from util.message import is_me, edit_or_reply
from util.getters import get_username
from util.command import filterCommand
from util.time import parse_timedelta
from util.decorators import report_error, set_offline
from util.help import HelpCategory

logger = logging.getLogger(__name__)

HELP = HelpCategory("BULLY")


INTERRUPT_STEALER = False

async def attack_username(client, message, chat, username, interval, limit):
	global INTERRUPT_STEALER
	attempts = 0
	while not INTERRUPT_STEALER and time.time() < limit: # TODO maybe redo this and make it not exception based, damn
		try:
			attempts += 1
			await client.send(ResolveUsername(username=username)) # this should bypass cache and will get me floodwaited very reliably (:
			await message.edit(f"` → ` Attempting to claim --@{username}-- (**{attempts}** attempts)")
			await asyncio.sleep(interval)
		except BadRequest as e: # Username not occupied!
			try:
				await client.update_chat_username(chat.id, username) # trying this every time would get me even more floodwaited
				await message.edit(f"` → ` Successfully claimed --@{username}-- in **{attempts}** attempts")
				INTERRUPT_STEALER = False
				return
			except FloodWait as e:
				await message.edit(f"` → ` Attempting to claim --@{username}-- (**{attempts}** attempts) [RENAME FLOOD: sleeping {e.x}s]")
				await asyncio.sleep(e.x)
			except Exception as e: # Username is invalid or user owns too many channels
				logger.exception("Error in .username command")
				await message.edit(f"` → ` Failed claiming --@{username}--\n`[!] → ` " + str(e))
				await client.delete_channel(chat.id)
				INTERRUPT_STEALER = False
				return
		except FloodWait as e:
			await message.edit(f"` → ` Attempting to claim --@{username}-- (**{attempts}** attempts) [LOOKUP FLOOD: sleeping {e.x}s]")
			await asyncio.sleep(e.x)
		except Exception as e: # Username is invalid or user owns too many channels
			logger.exception("Error in .username command")
			await message.edit(f"` → ` Failed claiming --@{username}--\n`[!] → ` " + str(e))
			await client.delete_channel(chat.id)
			INTERRUPT_STEALER = False
			return
	INTERRUPT_STEALER = False
	await message.edit(f"`[!] → ` Failed claiming --@{username}-- (made **{attempts}** attempts)")
	await client.delete_channel(chat.id)

HELP.add_help(["username"], "tries to claim an username",
			"Will create an empty channel and then attempt to rename it to given username until it succeeds or " +
			"max time is reached. Attempts interval can be specified (`-i`), defaults to 60 seconds. By default " +
			"it will give up after 5 minutes of attempts, set a time limit with `-lim`. Manually stop attempts with `-stop`. " +
			"This is very aggressive and will cause FloodWaits super easily if abused, be wary!",
			args="[-stop] [-i <n>] [-lim <time>] <username>")
@alemiBot.on_message(is_superuser & filterCommand("username", list(alemiBot.prefixes), options={
	"interval" : ["-i", "-int"],
	"limit" : ["-lim", "-limit"]
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def steal_username_cmd(client, message):
	global INTERRUPT_STEALER
	if "-stop" in message.command["flags"]:
		INTERRUPT_STEALER = True
		return await edit_or_reply(message, "` → ` Stopping")
	if "cmd" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No username given")
	uname = message.command["cmd"][0]
	if uname.startswith("@"):
		uname = uname[1:]
	chan = await client.create_channel(f"getting {uname}", "This channel was automatically created to occupy an username")
	time_limit = time.time() + parse_timedelta(message.command["limit"] if "limit" in message.command else "5min").total_seconds()
	interval = float(message.command["interval"]) if "interval" in message.command else 60
	await edit_or_reply(message, "` → ` Created channel")
	asyncio.get_event_loop().create_task(attack_username(client, message, chan, uname, interval, time_limit))

TYPING_INTERRUPT = False

async def fake_typing(client, tgt, cycle_n, sleep_t, action, message):
	global TYPING_INTERRUPT
	for _ in range(cycle_n):
		if TYPING_INTERRUPT:
			TYPING_INTERRUPT = False
			break
		await asyncio.sleep(sleep_t)
		await client.send_chat_action(tgt, action)
	try:
		await edit_or_reply(message, "` → ` Done")
	except: # maybe deleted?
		pass

HELP.add_help(["typing"], "will show as typing on chat",
			"makes you show as typing on a certain chat. You can specify an username or a chat/user id. If none is " +
			"given, it will work in current chat. It works by sending a chat action every 4 seconds (they last 5), but a custom " +
			"interval can be specified with `-i`. You can specify for how long chat actions should be sent with a packed string like this : " +
			"`8y3d4h15m3s` (years, days, hours, minutes, seconds), any individual token can be given in any position " +
			"and all are optional, it can just be `30s` or `5m`. If you want to include spaces, wrap the 'time' string in `\"`. " +
			"A different chat action from 'typing' can be specified with `-a`. Available chat actions are: `typing`, `upload_photo`, " +
			"`record_video`, `upload_video`, `record_audio`, `upload_audio`, `upload_document`, `find_location`, `record_video_note`, " +
			"`upload_video_note`, `choose_contact`, `playing`, `speaking`, `cancel`. You can terminate ongoing typing with `-stop`, but if " +
			"more than one is running, a random one will be stopped.", args="[-stop] [-t <target>] [-a <action>] [-i <n>] <time>")
@alemiBot.on_message(is_superuser & filterCommand("typing", list(alemiBot.prefixes), options={
	"target" : ["-t"],
	"interval" : ["-i"],
	"action" : ["-a", "-action"]
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def typing_cmd(client, message):
	global TYPING_INTERRUPT
	if "-stop" in message.command["flags"]:
		TYPING_INTERRUPT = True
		return await edit_or_reply(message, "` → ` Stopping")
	if "cmd" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No amount of time given")
	interval = int(message.command["interval"]) if "interval" in message.command else 4
	cycles = int(parse_timedelta(message.command["cmd"][0]).total_seconds() / interval)
	tgt = message.chat.id
	action = message.command["action"] if "action" in message.command else "typing"
	if "target" in message.command:
		tgt = message.command["target"]
		if tgt.startswith("@"):
			tgt = (await client.get_chat(tgt)).id
		elif tgt.isnumeric():
			tgt = int(tgt)
	await client.send_chat_action(tgt, action)
	asyncio.get_event_loop().create_task(fake_typing(client, tgt, cycles, interval, action, message))
	await edit_or_reply(message, f"` → ` {action} ...")
	
HELP.add_help(["everyone"], "will mention everyone in the chat",
			"will mention every member in current chat. A new message will be sent for the mentions." +
			"This is super lame, don't abuse.")
@alemiBot.on_message(is_superuser & filterCommand("everyone", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def mass_mention(client, message):
	msg = await edit_or_reply(message, "` → ` Looking up members")
	n = 0
	text = ""
	async for member in message.chat.iter_members():
		uname = get_username(member.user, mention=True)
		if len(text + uname) >= 4096 or n >= 100: # I think you can mention max 100 ppl per message?
			await msg.edit(text)
			n = 0
			text = ""
		text += uname + " "
		n += 1
	if len(text) > 0:
		await msg.reply(text)

INTERRUPT_SPAM = False

HELP.add_help(["spam", "flood"], "pretty self explainatory",
			"will send many (`-n`) messages in this chat at a specific (`-t`) interval. " +
			"If no number is given, will default to 3. If no interval is specified, " +
			"messages will be sent as soon as possible. You can reply to a message and " +
			"all spammed msgs will reply to that one too. If you add `-delme`, messages will be " +
			"immediately deleted. To stop an ongoing spam, you can do `.spam -cancel`.",
			args="[-stop] [-n <n>] [-t <t>] <text>")
@alemiBot.on_message(is_superuser & filterCommand("spam", list(alemiBot.prefixes), options={
	"number" : ["-n"],
	"time" : ["-t"],
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def spam(client, message): # TODO start another task so that it doesn't stop from rebooting
	global INTERRUPT_SPAM
	args = message.command
	if "-stop" in args["flags"]:
		INTERRUPT_SPAM = True
		return await edit_or_reply(message, "` → ` Stopping")
	wait = 0
	number = 3
	text = "."
	delme = False
	if "arg" in args:
		delme = args["arg"].endswith("-delme")
		text = args["arg"].replace("-delme", "") # in case
	if "time" in args:
		wait = float(args["time"])
	if "number" in args:
		number = int(args["number"])
	elif text.split(" ", 1)[0].isnumeric(): # this is to support how it worked originally
		number = int(text.split(" ", 1)[0])
		text = text.split(" ", 1)[1]
	logger.info(f"Spamming \"{text}\" for {number} times")
	extra = {}
	if message.reply_to_message is not None:
		extra["reply_to_message_id"] = message.reply_to_message.message_id
	for i in range(number):
		msg = await client.send_message(message.chat.id, text, **extra)
		await asyncio.sleep(wait)
		if delme:
			await msg.delete()
		if INTERRUPT_SPAM:
			INTERRUPT_SPAM = False
			await edit_or_reply(message, f"` → ` Canceled after {i + 1} events")
			break