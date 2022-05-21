import asyncio
import logging
import re
import json
import time

from pyrogram import filters
from pyrogram.errors import BadRequest, FloodWait
from pyrogram.raw.functions.contacts import ResolveUsername
from pyrogram.raw.functions.messages import SendScreenshotNotification

from alemibot import alemiBot

from alemibot.util.command import _Message as Message
from alemibot.util import (
	is_allowed, sudo, is_me, edit_or_reply, get_username, filterCommand, parse_timedelta,
	report_error, set_offline, HelpCategory
)

logger = logging.getLogger(__name__)

HELP = HelpCategory("BULLY")


async def attack_username(client, message, chat, username, interval, limit):
	attempts = 0
	while not client.ctx.INTERRUPT_STEALER and time.time() < limit: # TODO maybe redo this and make it not exception based, damn
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
	client.ctx.INTERRUPT_STEALER = False
	await message.edit(f"`[!] → ` Failed claiming --@{username}-- (made **{attempts}** attempts)")
	await client.delete_channel(chat.id)

@HELP.add(cmd="<username>")
@alemiBot.on_message(sudo & filterCommand(["steal_username", "steal_user"], options={
	"interval" : ["-i", "-int"],
	"limit" : ["-lim", "-limit"]
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def steal_username_cmd(client:alemiBot, message:Message):
	"""tries to claim an username

	Will create an empty channel and then attempt to rename it to given username until it succeeds or max time is reached.
	Attempts interval can be specified (`-i`), defaults to 60 seconds.
	By default it will give up after 5 minutes of attempts, set a time limit with `-lim`.
	Manually stop attempts with `-stop`.
	This is very aggressive and will cause FloodWaits super easily if abused, be wary!
	"""
	if message.command["-stop"]:
		client.ctx.INTERRUPT_STEALER = True
		return await edit_or_reply(message, "` → ` Stopping")
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	uname = message.command[0]
	if uname.startswith("@"):
		uname = uname[1:]
	chan = await client.create_channel(f"getting {uname}", "This channel was automatically created to occupy an username")
	time_limit = time.time() + parse_timedelta(message.command["limit"] or "5min").total_seconds()
	interval = float(message.command["interval"] or 60)
	await edit_or_reply(message, "` → ` Created channel")
	asyncio.get_event_loop().create_task(attack_username(client, message, chan, uname, interval, time_limit))

async def fake_typing(client, tgt, cycle_n, sleep_t, action, message):
	for _ in range(cycle_n):
		if client.ctx.TYPING_INTERRUPT:
			client.ctx.TYPING_INTERRUPT = False
			break
		await asyncio.sleep(sleep_t)
		await client.send_chat_action(tgt, action)
	try:
		await edit_or_reply(message, "` → ` Done")
	except Exception: # maybe deleted?
		pass
	await client.send_chat_action(tgt, "cancel")

@HELP.add(cmd="<time>")
@alemiBot.on_message(sudo & filterCommand("typing", options={
	"target" : ["-t"],
	"interval" : ["-i"],
	"action" : ["-a", "-action"]
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def typing_cmd(client:alemiBot, message:Message):
	"""show typing status in chat

	Makes you show as typing on a certain chat. You can specify an username or a chat/user id. If none is given, it will work in current chat.
	It works by sending a chat action every 4 seconds (they last 5), but a custom interval can be specified with `-i`.
	You can specify for how long chat actions should be sent with a packed string like this : \
	`8y3d4h15m3s` (years, days, hours, minutes, seconds), any individual token can be given in any position \
	and all are optional, it can just be `30s` or `5m`. If you want to include spaces, wrap the 'time' string in `\"`.
	A different chat action from 'typing' can be specified with `-a`. Available chat actions are: `typing`, `upload_photo`, \
	`record_video`, `upload_video`, `record_audio`, `upload_audio`, `upload_document`, `find_location`, `record_video_note`, \
	`upload_video_note`, `choose_contact`, `playing`, `speaking`, `cancel`.
	You can terminate ongoing typing with `-stop`, but if more than one is running, a random one will be stopped."
	"""
	if message.command["-stop"]:
		client.ctx.TYPING_INTERRUPT = True
		return await edit_or_reply(message, "` → ` Stopping")
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	interval = float(message.command["interval"] or 4.75)
	cycles = int(parse_timedelta(message.command[0]).total_seconds() / interval)
	tgt = message.chat.id
	action = message.command["action"] or "typing"
	if "target" in message.command:
		tgt = message.command["target"]
		if tgt.startswith("@"):
			tgt = (await client.get_chat(tgt)).id
		elif tgt.isnumeric():
			tgt = int(tgt)
	await client.send_chat_action(tgt, action)
	asyncio.get_event_loop().create_task(fake_typing(client, tgt, cycles, interval, action, message))
	await edit_or_reply(message, f"` → ` {action} ...")

@HELP.add()
@alemiBot.on_message(sudo & filterCommand("everyone"))
@report_error(logger)
@set_offline
async def mass_mention(client:alemiBot, message:Message):
	"""mention everyone in current chat

	Will send messages mentioning every member in current chat.
	Since edits won't trigger mentions, a new message is always sent.
	There can be max 50 mentions in a single message, so for groups with bigger member count, \
	more than 1 message will be sent.
	This is super lame.
	"""
	msg = await edit_or_reply(message, "` → ` Looking up members")
	n = 0
	text = ""
	async for member in message.chat.iter_members():
		uname = get_username(member.user, mention=True)
		if len(text + uname) >= 4096 or n >= 50:
			await msg.edit(text)
			n = 0
			text = ""
		text += uname + " "
		n += 1
	if len(text) > 0:
		await msg.reply(text)

@HELP.add()
@alemiBot.on_message(filters.private & sudo & filterCommand(["ss", "screenshot"], flags=["-0"]))
@report_error(logger)
@set_offline
async def screenshot_cmd(client:alemiBot, message:Message):
	"""send screenshot notification

	**Only works in private chats!**
	Notify other user in a private chat that a screenshot was taken.
	Add flag `-0` to make it not specify any particular message.
	Credits to [ColinShark/Pyrogram-Snippets](https://github.com/ColinShark/Pyrogram-Snippets).
	"""
	await client.send(
		SendScreenshotNotification(
			peer=await client.resolve_peer(message.chat.id),
			reply_to_msg_id=0 if bool(message.command["-0"]) else message.id,
			random_id=client.rnd_id(),
		)
	)
	await edit_or_reply(message, "` → ` Screenshotted")

@HELP.add(cmd="<text>")
@alemiBot.on_message(sudo & filterCommand(["spam", "flood"], options={
	"number" : ["-n", "--number"],
	"interval" : ["-i", "--interval"],
	"schedule" : ["-s", "--schedule"],
	"target" : ["-t", "--target"],
}, flags=["-stop"]))
@report_error(logger)
@set_offline
async def spam(client:alemiBot, message:Message): # TODO start another task so that it doesn't stop from rebooting
	"""pretty self explainatory

	Will send many (`-n`) messages in this chat at a specific (`-i`) interval.
	If no number is given, will default to 3. If no interval is specified, messages will be sent as soon as possible.
	You can reply to a message and all spammed msgs will reply to that one too.
	You can schedule messages instead of sending them immediately. Command works the same. Add a schedule offset \
	with `-s` (can also be 0 to schedule immediately).
	If flag `-delme` is added, messages will be immediately deleted (except when scheduled).
	To stop an ongoing spam, you can do `.spam -stop`.
	Specify another chat to spam into with `-t`.
	"""
	if message.command["-stop"]:
		client.ctx.INTERRUPT_SPAM = True
		return await edit_or_reply(message, "` → ` Stopping")
	wait = parse_timedelta(message.command["interval"] or "0s").total_seconds()
	number = int(message.command["number"] or 3)
	text = message.command.text or "."
	delme = text.endswith("-delme")
	scheduled = bool(message.command["schedule"])
	target = message.chat
	if delme:
		text = text.replace("-delme", "")
	if len(message.command) > 0 and message.command[0].isnumeric(): # allow older usage
		number = int(message.command[0])
		text = text.replace(message.command[0] + " ", "", 1)
	if "target" in message.command:
		tgt = message.command["target"]
		target = await client.get_chat(int(tgt) if tgt.isnumeric() else tgt)
	extra = {}
	if scheduled:
		extra["schedule_date"] = int(time.time() + parse_timedelta(message.command["schedule"]).total_seconds())
	if message.reply_to_message is not None:
		extra["reply_to_message_id"] = message.reply_to_message.id
	for i in range(number):
		msg = await client.send_message(target.id, text, **extra)
		if scheduled:
			extra["schedule_date"] = int(extra["schedule_date"] + wait)
		else:
			await asyncio.sleep(wait)
			if delme:
				await msg.delete()
		if client.ctx.INTERRUPT_SPAM:
			client.ctx.INTERRUPT_SPAM = False
			return await edit_or_reply(message, f"` → ` Canceled after {i + 1} events")
	await edit_or_reply(message, "` → ` Done")
