import asyncio
import secrets
import re
import os
import io
import json
import time
import requests

from collections import Counter
from gtts import gTTS 
from pydub import AudioSegment
import speech_recognition as sr

from pyrogram import filters

from bot import alemiBot

from util.permission import is_allowed
from util.message import edit_or_reply, is_me
from util.getters import get_text
from util.text import tokenize_json, cleartermcolor
from util.command import filterCommand
from util.decorators import report_error, set_offline
from util.help import HelpCategory

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

HELP.add_help(["rand", "random", "roll"], "get random choices",
				"this can be used as a dice roller (`.roll 3d6`). If a list of choices is given, a random one " +
				"will be chosen from that. If a number is given, it will choose a value from 1 to <n>, both included. " +
				"You can specify how many extractions to make", args="[-n <n>] [choices] | [n]d<max>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["rand", "random", "roll"], list(alemiBot.prefixes), options={
	"batchsize" : ["-n"]
}))
@report_error(logger)
@set_offline
async def rand_cmd(client, message):
	args = message.command
	res = []
	times = 1
	out = ""
	maxval = None
	if "arg" in args:
		pattern = r"(?P<batch>[0-9]*)d(?P<max>[0-9]+)"
		m = re.search(pattern, args["arg"])
		if m is not None:
			maxval = int(m["max"])
			if m["batch"] != "":
				times = int(m["batch"])
		elif len(args["cmd"]) == 1 and args["cmd"][0].isnumeric():
			maxval = int(args["cmd"][0])
	if "batchsize" in args:
		times = int(args["batchsize"]) # overrule dice roller formatting
		
	if maxval is not None:
		logger.info(f"Rolling d{maxval}")
		for _ in range(times):
			res.append(secrets.randbelow(maxval) + 1)
		if times > 1:
			out += f"`→ Rolled {times}d{maxval}` : **{sum(res)}**\n"
	elif "cmd" in args:
		logger.info(f"Rolling {args['cmd']}")
		for _ in range(times):
			res.append(secrets.choice(args['cmd']))
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
		logger.info(f"Rolling binary")
		for _ in range(times):
			res.append(secrets.randbelow(2))
		if times > 1:
			out += "`→ Binary " + "".join(str(x) for x in res) + "`\n"
			# this is a very ugly way to prevent the formatted print below
			res = []
			times = 0
	if times <= 20:
		for r in res:
			out += f"` → ` ** {r} **\n"
	else:
		out += f"` → ` [ " + " ".join(str(r) for r in res) + " ]"
	await edit_or_reply(message, out)

HELP.add_help(["qrcode", "qr"], "make qr code",
				"make a qr code with given text. Many parameters can be specified : size of specific boxes (`-box`), " +
				"image border (`-border`), qrcode size (`-size`). QR colors can be specified too: " +
				"background with `-b` and front color with `-f`",
				args="[-border <n>] [-size <n>] [-box <n>] [-b <color>] [-f <color>] <text>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["qrcode", "qr"], list(alemiBot.prefixes), options={
	"border" : ["-border"],
	"size" : ["-size"],
	"boxsize" : ["-box"],
	"back" : ["-b"],
	"front" : ["-f"]
}))
@report_error(logger)
@set_offline
async def qrcode_cmd(client, message):
	args = message.command
	if "arg" not in args:
		return await edit_or_reply(message, "`[!] → ` No text given")
	text = args["arg"].replace("-delme", "") # just in case
	size = int(args["size"]) if "size" in args else None
	box_size = int(args["boxsize"]) if "boxsize" in args else 10
	border = int(args["border"]) if "border" in args else 4
	bg_color = args["back"] if "back" in args else "black"
	fg_color = args["front"] if "front" in args else "white"
	await client.send_chat_action(message.chat.id, "upload_photo")
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
	await client.send_photo(message.chat.id, qr_io, reply_to_message_id=message.message_id)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["color"], "send solid color image",
				"create a solid color image and send it. Color can be given as hex or " +
				"by specifying each channel individally. Each channel can range from 0 to 256. ",
				args="( <hex> | <r> <g> <b> )", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["color"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def color_cmd(client, message):
	clr = None
	if "cmd" in message.command:
		if len(message.command["cmd"]) > 2:
			clr = tuple([int(k) for k in message.command["cmd"]][:3])
		else:
			clr = message.command["cmd"][0]
			if not clr.startswith("#"):
				clr = "#" + clr
	else:
		return await edit_or_reply(message, "`[!] → ` Not enough args given")
	await client.send_chat_action(message.chat.id, "upload_photo")
	image = Image.new("RGB", (200, 200), clr)
	color_io = io.BytesIO()
	color_io.name = "color.jpg"
	image.save(color_io, "JPEG")
	color_io.seek(0)
	await client.send_photo(message.chat.id, color_io, reply_to_message_id=message.message_id)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["voice"], "convert text to voice",
				"create a voice message using Google Text to Speech. By default, english will be " +
				"used as lang, but another one can be specified with `-l`. You can add `-slow` flag " +
				"to make the generated speech slower. If command comes from self, will delete original " +
				"message. TTS result will be converted to `.ogg`. You can skip this step and send as mp3 by " +
				"adding the `-mp3` flag. You can add the `-file` flag to make tts of a replied to or attached text file.",
				args="[-l <lang>] [-slow] [-mp3] <text>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["voice"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}, flags=["-slow", "-mp3", "-file"]))
@report_error(logger)
@set_offline
async def voice_cmd(client, message):
	text = ""
	opts = {}
	from_file = "-file" in message.command["flags"]
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
	elif "arg" in message.command:
		text = re.sub(r"-delme(?: |)(?:[0-9]+|)", "", message.command["arg"])
	else:
		return await edit_or_reply(message, "`[!] → ` No text given")
	lang = message.command["lang"] if "lang" in message.command else "en"
	slow = "-slow" in message.command["flags"]
	if message.reply_to_message is not None:
		opts["reply_to_message_id"] = message.reply_to_message.message_id
	elif not is_me(message):
		opts["reply_to_message_id"] = message.message_id
	await client.send_chat_action(message.chat.id, "record_audio")
	gTTS(text=text, lang=lang, slow=slow).save("data/tts.mp3")
	if "-mp3" in message.command["flags"]:
		await client.send_audio(message.chat.id, "data/tts.mp3", **opts)
	else:
		AudioSegment.from_mp3("data/tts.mp3").export("data/tts.ogg", format="ogg", codec="libopus")
		await client.send_voice(message.chat.id, "data/tts.ogg", **opts)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["loc", "location"], "send a location",
				"send a location for specific latitude and longitude. Both has " +
				"to be given and are in range [-90, 90]. If a title is given with the `-t` " +
				"option, the location will be sent as venue.", args="[-t <title>] (<lat> <long> | <loc>)", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["loc", "location"], list(alemiBot.prefixes), options={
	"title" : ["-t"]
}))
@report_error(logger)
@set_offline
async def location_cmd(client, message):
	args = message.command
	latitude = 0.0
	longitude = 0.0
	logger.info("Getting a location")
	if "arg" in args:
		try:
			coords = args["arg"].split(" ", 2)
			latitude = float(coords[0])
			longitude = float(coords[1])
		except (ValueError, IndexError):
			await client.send_chat_action(message.chat.id, "find_location")
			location = geolocator.geocode(args["arg"])
			await client.send_chat_action(message.chat.id, "cancel")
			if location is None:
				return await edit_or_reply(message, "`[!] → ` Not found")
			latitude = location.latitude
			longitude = location.longitude
	if latitude > 90 or latitude < -90 or longitude > 90 or longitude < -90:
		return await edit_or_reply(message, "`[!] → ` Invalid coordinates")
	if "title" in args:
		adr = (args["arg"] if "arg" in args else f"{latitude:.2f} {longitude:.2f}")
		await client.send_venue(message.chat.id, latitude, longitude,
									title=args["title"], address=adr)
	else:
		await client.send_location(message.chat.id, latitude, longitude)

HELP.add_help("figlet", "make a figlet art",
				"run figlet and make a text art. You can specify a font (`-f`), or request a random one (`-r`). " +
				"Get list of available fonts with `-list`. You can specify max figlet width (`-w`), default is 30.",
				args="[-list] [-r | -f <font>] [-w <n>] <text>", public=True)
@alemiBot.on_message(is_allowed & filterCommand("figlet", list(alemiBot.prefixes), options={
	"font" : ["-f", "-font"],
	"width" : ["-w", "-width"]
}, flags=["-list", "-r"]))
@report_error(logger)
@set_offline
async def figlet_cmd(client, message):
	args = message.command
	if "-list" in args["flags"]:
		msg = f"<code> → </code> <u>Figlet fonts</u> : <b>{len(FIGLET_FONTS)}</b>\n[ "
		msg += " ".join(FIGLET_FONTS)
		msg += " ]"
		return await edit_or_reply(message, msg, parse_mode='html')

	if "arg" not in args:
		return # no text to figlet!

	width = 30
	if "width" in args:
		width = int(args["width"])
	font = "slant"
	if "-r" in args["flags"]:
		font = secrets.choice(FIGLET_FONTS)
	elif "font" in args:
		f = args["font"]
		if f != "" and f in FIGLET_FONTS:
			font = f

	logger.info(f"figlet-ing {args['arg']}")
	result = pyfiglet.figlet_format(args["arg"], font=font, width=width)
	await edit_or_reply(message, "<code> →\n" + result + "</code>", parse_mode="html")

HELP.add_help("fortune", "do you feel fortunate!?",
				"run `fortune` to get a random sentence. Like fortune bisquits!", args="[-cow]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["fortune"], list(alemiBot.prefixes), flags=["-cow"]))
@report_error(logger)
@set_offline
async def fortune_cmd(client, message):
	logger.info(f"Running command \"fortune\"")
	stdout = b""
	if "-cow" in message.command["flags"]:
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