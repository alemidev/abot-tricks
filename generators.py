import asyncio
import secrets
import re
import os
import io
import json
import time

from typing import Dict, List, Any, Union, Tuple, Optional

from pyrogram import filters
from pyrogram.enums import ParseMode, ChatAction

from alemibot.bot import alemiBot

from alemibot.util.command import _Message as Message
from alemibot.util import (
	is_allowed, ProgressChatAction, edit_or_reply, is_me, get_text, get_username, get_channel, 
	tokenize_json, cleartermcolor, sep, filterCommand, report_error, set_offline, cancel_chat_action, 
	HelpCategory
)

from collections import Counter
from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr

from PIL import Image
import qrcode
import pyfiglet
from geopy.geocoders import Nominatim

import logging
logger = logging.getLogger(__name__)

recognizer = sr.Recognizer()

FIGLET_FONTS = pyfiglet.FigletFont.getFonts()
FIGLET_FONTS.sort()

geolocator = Nominatim(user_agent="telegram-client")

HELP = HelpCategory("GENERATORS")

@HELP.add(cmd="[<choices>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["rand", "random", "roll"], options={
	"batchsize" : ["-n"]
}))
@report_error(logger)
@set_offline
async def rand_cmd(client:alemiBot, message:Message):
	"""get random choices

	This can be used as a dice roller (`.roll 3d6`).
	If a list of choices is given, a random one will be chosen from that.
	If a number is given, it will choose a value from 1 to <n>, both included.
	You can specify how many extractions to make with `-n`.
	"""
	res : List[Any] = []
	times = 1
	out = ""
	maxval = None
	if len(message.command) > 0:
		pattern = r"(?P<batch>[0-9]*)d(?P<max>[0-9]+)"
		m = re.search(pattern, message.command.text)
		if m:
			maxval = int(m["max"])
			if m["batch"] != "":
				times = int(m["batch"])
		elif message.command[0].isnumeric():
			maxval = int(message.command[0])
	if "batchsize" in message.command:
		times = int(message.command["batchsize"]) # overrule dice roller formatting
		
	if maxval is not None:
		for _ in range(times):
			res.append(secrets.randbelow(maxval) + 1)
		if times > 1:
			out += f"`→ ` Rolled `{times}d{maxval}` : **{sum(res)}**\n"
	elif len(message.command) > 0:
		for _ in range(times):
			res.append(secrets.choice(message.command.arg))
		if times > 1: # This is kinda ugly but pretty handy
			res_count = Counter(res).most_common()
			max_times = res_count[0][1]
			out += "`→ Random choice ` **"
			for el in res_count:
				if el[1] < max_times:
					break
				out += el[0] + " "
			out += "**\n"
	else:
		for _ in range(times):
			res.append(secrets.randbelow(2))
		if times > 1:
			out += "`→ Binary " + "".join(str(x) for x in res) + "`\n"
			# this is a very ugly way to prevent the formatted print below
			res = []
			times = 0
	out += "` → ` [ " + " ".join(sep(r) for r in res) + " ]"
	await edit_or_reply(message, out)

@HELP.add(cmd="<text>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["qrcode", "qr"], options={
	"border" : ["-border"],
	"size" : ["-size"],
	"boxsize" : ["-box"],
	"back" : ["-b"],
	"front" : ["-f"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def qrcode_cmd(client:alemiBot, message:Message):
	"""generate a qr code

	Make a qr code with given text.
	Size of specific boxes can be specified with `-box`, image border with `-border`, qrcode size with `-size`.
	QR colors can be specified too: background with `-b` and front color with `-f`
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	text = message.command.text.replace("-delme", "") # just in case
	size = int(message.command["size"]) if "size" in message.command else None
	box_size = int(message.command["boxsize"] or 10)
	border = int(message.command["border"] or 4)
	bg_color = message.command["back"] or "black"
	fg_color = message.command["front"] or "white"
	prog = ProgressChatAction(client, message.chat.id, action="upload_photo")
	await prog.tick()
	qr = qrcode.QRCode(
		version=size,
		error_correction=qrcode.constants.ERROR_CORRECT_L,
		box_size=box_size,
		border=border,
	)
	qr.add_data(text)
	qr.make(fit=True)

	image = qr.make_image(fill_color=fg_color, back_color=bg_color)
	qr_io = io.BytesIO()
	qr_io.name = "qrcode.jpg"
	image.save(qr_io, "JPEG")
	qr_io.seek(0)
	await client.send_photo(message.chat.id, qr_io, reply_to_message_id=message.id, progress=prog.tick)

@HELP.add(cmd="( <hex> | <r> <g> <b> )", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["color"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def color_cmd(client:alemiBot, message:Message):
	"""send a solid color image

	Create a solid color image and send it.
	Color can be given as hex or by specifying each channel individally.
	Each channel can range from 0 to 256.
	"""
	clr : Optional[Union[str, Tuple[int, ...]]] = None
	if len(message.command) > 0:
		if len(message.command) > 2:
			clr = tuple([ int(k) for k in message.command.arg[:3] ])
		else:
			clr = str(message.command[0])
			if not clr.startswith("#"):
				clr = "#" + clr
	else:
		return await edit_or_reply(message, "`[!] → ` Not enough args given")
	prog = ProgressChatAction(client, message.chat.id, action="upload_photo")
	await prog.tick()
	image = Image.new("RGB", (200, 200), clr)
	color_io = io.BytesIO()
	color_io.name = "color.jpg"
	image.save(color_io, "JPEG")
	color_io.seek(0)
	await client.send_photo(message.chat.id, color_io, reply_to_message_id=message.id, progress=prog.tick)

@HELP.add(cmd="<text>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["voice"], options={
	"lang" : ["-l", "-lang"]
}, flags=["-slow", "-mp3", "-file"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def voice_cmd(client:alemiBot, message:Message):
	"""convert text to voice

	Create a voice message using Google Text to Speech.
	By default, english will be	used as lang, but another one can be specified with `-l`.
	You can add `-slow` flag to make the generated speech slower.
	TTS result will be converted to `.ogg`. You can skip this step and send as mp3 by adding the `-mp3` flag.
	You can add the `-file` flag to make tts of a replied to or attached text file.
	"""
	text = ""
	opts = {}
	from_file = bool(message.command["-file"])
	if message.reply_to_message is not None:
		if from_file and message.reply_to_message.media:
			fpath = await client.download_media(message.reply_to_message)
			with open(fpath) as f:
				text = f.read()
			os.remove(fpath)
		else:
			text = get_text(message.reply_to_message)
	elif from_file and message.media:
		fpath = await client.download_media(message)
		with open(fpath) as f:
			text = f.read()
		os.remove(fpath)
	elif len(message.command) > 0:
		text = re.sub(r"-delme(?: |)(?:[0-9]+|)", "", message.command.text)
	else:
		return await edit_or_reply(message, "`[!] → ` No text given")
	prog = ProgressChatAction(client, message.chat.id, action="record_audio")
	lang = message.command["lang"] or "en"
	slow = bool(message.command["-slow"])
	if message.reply_to_message is not None:
		opts["reply_to_message_id"] = message.reply_to_message.id
	elif not is_me(message):
		opts["reply_to_message_id"] = message.id
	await prog.tick()
	gTTS(text=text, lang=lang, slow=slow).save("data/tts.mp3")
	if message.command["-mp3"]:
		await client.send_audio(message.chat.id, "data/tts.mp3", progress=prog.tick, **opts)
	else:
		AudioSegment.from_mp3("data/tts.mp3").export("data/tts.ogg", format="ogg", codec="libopus")
		await client.send_voice(message.chat.id, "data/tts.ogg", progress=prog.tick, **opts)

@HELP.add(cmd="(<lat> <long> | <loc>)", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["loc", "location"], options={
	"title" : ["-t"]
}))
@report_error(logger)
@set_offline
async def location_cmd(client:alemiBot, message:Message):
	"""send a location

	Target location can be specified via latitude and longitude (range [-90,90]) or with an address.
	If a title is given with the `-t` option, the location will be sent as venue.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	latitude = 0.0
	longitude = 0.0
	try:
		latitude = float(message.command[0])
		longitude = float(message.command[1])
	except (ValueError, IndexError):
		await client.send_chat_action(message.chat.id, ChatAction.FIND_LOCATION)
		location = geolocator.geocode(message.command.text)
		await client.send_chat_action(message.chat.id, ChatAction.CANCEL)
		if location is None:
			return await edit_or_reply(message, "`[!] → ` Not found")
		latitude = location.latitude
		longitude = location.longitude
	if latitude > 90 or latitude < -90 or longitude > 180 or longitude < -180:
		return await edit_or_reply(message, "`[!] → ` Invalid coordinates")
	if "title" in message.command:
		adr = (message.command.text or f"{latitude:.2f} {longitude:.2f}")
		await client.send_venue(message.chat.id, latitude, longitude,
									title=message.command["title"], address=adr)
	else:
		await client.send_location(message.chat.id, latitude, longitude)

@HELP.add(cmd="<text>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("figlet", options={
	"font" : ["-f", "-font"],
	"width" : ["-w", "-width"]
}, flags=["-list", "-rand"]))
@report_error(logger)
@set_offline
async def figlet_cmd(client:alemiBot, message:Message):
	"""make a figlet art

	Run figlet and make a text art. You can specify a font (`-f <font>`), or request a random one (`-rand`).
	Get list of available fonts with `-list`.
	You can specify max figlet width (`-w`), default is 30.
	"""
	if message.command["-list"]:
		msg = f"<code> → </code> <u>Figlet fonts</u> : <b>{len(FIGLET_FONTS)}</b>\n[ "
		msg += " ".join(FIGLET_FONTS)
		msg += " ]"
		return await edit_or_reply(message, msg, parse_mode=ParseMode.HTML)
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")

	width = int(message.command["width"] or 30)
	font = "slant"
	if message.command["-rand"]:
		font = secrets.choice(FIGLET_FONTS)
	elif "font" in message.command:
		f = message.command["font"]
		if f != "" and f in FIGLET_FONTS:
			font = f

	result = pyfiglet.figlet_format(message.command.text, font=font, width=width)
	await edit_or_reply(message, "<code> →\n" + result + "</code>", parse_mode=ParseMode.HTML)

@HELP.add(sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["fortune"], flags=["-cow"]))
@report_error(logger)
@set_offline
async def fortune_cmd(client:alemiBot, message:Message):
	"""do you feel fortuname!?

	Run `fortune` on terminal to get a random sentence. Like fortune bisquits!
	"""
	stdout = b""
	if message.command["-cow"]:
		proc = await asyncio.create_subprocess_shell(
				"fortune | cowsay -W 30",
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.STDOUT)
		stdout, _stderr = await proc.communicate()
		stdout = b"\n" + stdout
	else:
		proc = await asyncio.create_subprocess_exec(
				"fortune",
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.STDOUT)
		stdout, _stderr = await proc.communicate()
	output = cleartermcolor(stdout.decode())
	await edit_or_reply(message, "``` → " + output + "```")

ONCE = None
async def check_firefox():
	global ONCE
	if ONCE is not None:
		return ONCE
	proc = await asyncio.create_subprocess_shell("which firefox", stdout=asyncio.subprocess.PIPE)
	stdout, _stderr = await proc.communicate()
	if len(stdout) > 1:
		ONCE = stdout.decode('utf-8')
	else:
		ONCE = False
	return ONCE

@HELP.add(sudo=False, cmd="<url>")
@alemiBot.on_message(is_allowed & filterCommand(["webshot"], flags=["-raw"]))
@report_error(logger)
@set_offline
async def webshot_cmd(client:alemiBot, message:Message):
	"""capture a website screenshot

	Will run headlessly firefox in background to create a screenshot, and then upload it.
	Add `-raw` to get the image as a document (uncompressed).
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	executable = await check_firefox()
	if not executable:
		return await edit_or_reply(message, "`[!] → ` firefox not installed")
	url = message.command[0]
	# if requests.head(url).status_code >= 400:
	# 	return await edit_or_reply(message, "`[!] → ` Invalid URL")
	raw = bool(message.command["-raw"])
	with ProgressChatAction(client, message.chat.id, "upload_document" if raw else "upload_photo") as prog:
		proc = await asyncio.create_subprocess_exec(
			executable.strip(), "--screenshot", f"{os.getcwd()}/data/webshot.png", url,
			stderr=asyncio.subprocess.STDOUT,
			stdout=asyncio.subprocess.PIPE
		)
		stdout, _stderr = await proc.communicate()
		caption = f"`→ ` {url}"
		if raw:
			await client.send_document(message.chat.id, "data/webshot.png", progress=prog.tick, caption=caption)
		else:
			await client.send_photo(message.chat.id, "data/webshot.png", progress=prog.tick, caption=caption)

@HELP.add(cmd="[<n>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["iter_freq"], options={
	"results" : ["-r", "-res"],
	"minlen" : ["-min"],
	"group" : ["-g", "-group"],
	"user" : ["-u", "-user"]
}))
@report_error(logger)
@set_offline
async def cmd_frequency_iter(client:alemiBot, message:Message):
	"""search most frequent words in messages

	**[!]** --This will search with telegram API calls--
	Find most used words in last messages. If no number is given, will search only last 100 messages.
	By default, 10 most frequent words are shown, but number of results can be changed with `-r`.
	By default, only words of `len > 3` will be considered. A minimum word len can be specified with `-min`.
	Will search in current group or any specified with `-g`.
	A single user can be specified with `-u` : only messages from that user will count if provided.
	"""
	results = int(message.command["results"] or 10)
	number = int(message.command[0] or 100)
	min_len = int(message.command["minlen"] or 3)
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
	response = await edit_or_reply(message, f"` → ` Counting word occurrences...")
	words = []
	count = 0
	async for msg in client.iter_history(group.id, limit=number):
		if not user or user.id == msg.from_user.id:
			words += [ w for w in re.sub(r"[^0-9a-zA-Z\s\n]+", "", get_text(msg).lower()).split() if len(w) > min_len ]
		count += 1
		if count % 250 == 0:
			await client.send_chat_action(message.chat.id, ChatAction.PLAYING)
			await response.edit(f"` → [{count}/{number}] ` Counting word occurrences...")
	counter = Counter(words).most_common()
	from_who = f"(from **{get_username(user)}**)" if user else ""
	output = f"`→ {get_channel(group)}` {from_who}\n` → ` **{results}** most frequent words __(len > {min_len})__ in last **{number}** messages:\n"
	for i in range(results):
		output += f"`{i+1:02d}]{'-'*(results-i-1)}>` `{counter[i][0]}` `({counter[i][1]})`\n"
	await response.edit(output, parse_mode=ParseMode.MARKDOWN)

