import os
import re
import json
import asyncio
from urllib import parse

from pyrogram import filters

from bot import alemiBot

import wikipediaapi
import italian_dictionary
from PyDictionary import PyDictionary
from geopy.geocoders import Nominatim
from udpy import UrbanClient
import translators as ts
from google_currency import convert
from unit_converter.converter import converts

import requests

from pydub import AudioSegment
import speech_recognition as sr

from util import batchify
from util.text import tokenize_json
from util.permission import is_allowed
from util.message import edit_or_reply
from util.command import filterCommand
from util.decorators import report_error, set_offline
from util.help import HelpCategory

import logging
logger = logging.getLogger(__name__)

HELP = HelpCategory("APICALLS")

recognizer = sr.Recognizer()
dictionary = PyDictionary()
geolocator = Nominatim(user_agent="telegram-client")
UClient = UrbanClient()

HELP.add_help(["convert", "conv"], "convert various units",
				"convert various measure units. Accepts many units, like " +
				"`.convert 52 °C °F` or `.convert 2.78 daN*mm^2 mN*µm^2`.",
				args="<val> <from> <to>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["convert", "conv"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def convert_cmd(client, message):
	if "cmd" not in message.command or len(message.command["cmd"]) < 3:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	logger.info("Converting units")
	res = converts(message.command["cmd"][0] + " " + message.command["cmd"][1], message.command["cmd"][2])
	await edit_or_reply(message, f"` → ` {res} {message.command['cmd'][2]}")

HELP.add_help(["currency", "cconvert", "curr"], "convert across currencies",
				"convert various measure units. Accepts many currencies, like " +
				"`.convert 1 btc us`.",
				args="<val> <from> <to>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["currency", "cconvert", "curr"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def currency_convert_cmd(client, message):
	if "cmd" not in message.command or len(message.command["cmd"]) < 3:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	logger.info("Converting currency")
	await client.send_chat_action(message.chat.id, "choose_contact")
	res = json.loads(convert(message.command["cmd"][1], message.command["cmd"][2], float(message.command["cmd"][0])))
	await edit_or_reply(message, f"` → ` {res['amount']} {res['to']}")
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["diz", "dizionario"], "search in ita dict",
				"get definition from italian dictionary of given word.",
				args="<word>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["diz", "dizionario"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def diz_cmd(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No query given")
	await client.send_chat_action(message.chat.id, "upload_document")
	arg = message.command["arg"]
	logger.info(f"Searching \"{arg}\" on it dictionary")
	# Use this to get only the meaning 
	res = italian_dictionary.get_definition(arg) 

	out = f"` → {res['lemma']} ` [ {' | '.join(res['sillabe'])} ]\n"
	out += f"```{', '.join(res['grammatica'])} - {res['pronuncia']}```\n\n"
	out += "\n\n".join(res['definizione'])
	await edit_or_reply(message, out)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["dic", "dictionary"], "search in eng dict",
				"get definition from english dictionary of given word.",
				args="<word>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["dic", "dictionary"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def dic_cmd(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No query given")
	await client.send_chat_action(message.chat.id, "upload_document")
	arg = message.command["arg"]
	logger.info(f"Searching \"{arg}\" on eng dictionary")
	res = dictionary.meaning(arg)
	if res is None:
		return await edit_or_reply(message, "` → No match`")
	out = ""
	for k in res:
		out += f"`→ {k} : `"
		out += "\n * "
		out += "\n * ".join(res[k])
		out += "\n\n"
	await edit_or_reply(message, out)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["ud", "urban"], "search in urban dict",
				"get definition from urban dictionary of given query. Number of results to return can " +
				"be specified with `-r`, will default to only one (top definition).",
				args="[-r <n>] <query>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["ud", "urban"], list(alemiBot.prefixes), options={
	"results" : ["-r", "-res"]
}))
@report_error(logger)
@set_offline
async def urbandict_cmd(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No query given")
	n = int(message.command["results"]) if "results" in message.command else 1
	await client.send_chat_action(message.chat.id, "upload_document")
	logger.info(f"Searching \"{message.command['arg']}\" on urban dictionary")
	res = UClient.get_definition(message.command["arg"])
	if len(res) < 1:
		return await edit_or_reply(message, "`[!] → ` Not found")
	out = ""
	for i in range(min(n, len(res))):
		out +=  f"<code>→ </code> <u>{res[i].word}</u> <code>[+{res[i].upvotes}|{res[i].downvotes}-]</code>\n" + \
				f"{res[i].definition}\n\n<i>{res[i].example}</i>\n\n"
	await edit_or_reply(message, out, parse_mode="html")
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help("wiki", "search on wikipedia",
				"search on wikipedia, attaching initial text and a link. Language will default to " +
				"english if not specified with `-l`. By default, only first 1000 characters will be printed, " +
				"a different amount of characters to print can be specified with `-max`.", args="[-l <lang>] [-max <n>] <query>", public=True)
@alemiBot.on_message(is_allowed & filterCommand("wiki", list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"],
	"limit" : ["-max"]
}))
@report_error(logger)
@set_offline
async def wiki_cmd(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No query given")
	lang = message.command["lang"] if "lang" in message.command else "en"
	limit = int(message.command["limit"]) if "limit" in message.command else 1000
	await client.send_chat_action(message.chat.id, "upload_document")
	Wikipedia = wikipediaapi.Wikipedia(lang)
	logger.info(f"Searching \"{message.command['arg']}\" on wikipedia")
	page = Wikipedia.page(message.command["arg"])
	if not page.exists():
		return await edit_or_reply(message, "`[!] → ` No results")
	text = page.text if len(page.summary) < limit else page.summary
	if len(text) > limit:
		text = text[:limit] + " ..."
	await edit_or_reply(message, f"` → {page.title}`\n{text}\n` → ` {page.fullurl}")
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["translate", "tran", "tr"], "translate to/from",
				"translate text from a language (autodetected if not specified, `-s`) to another " +
				"specified lang (defaults to eng, `-d`). Used engine can be specified with `-e` (available `google`, `deepl`, `bing`), " +
				"only `bing` works as of now and is the default. The lang codes must be 2 letter long (en, ja...)",
				args="[-s <src>] [-d <des>] [-e <engine>]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["translate", "tran", "tr"], list(alemiBot.prefixes), options={
	"src" : ["-s", "-src"],
	"dest" : ["-d", "-dest"],
	"engine" : ["-e", "-engine"]
}))
@report_error(logger)
@set_offline
async def translate_cmd(client, message):
	args = message.command
	if "arg" not in args and message.reply_to_message is None:
		return await edit_or_reply(message, "`[!] → ` Nothing to translate")
	tr_options = {}
	# lmao I can probably pass **args directly
	if "src" in args:
		tr_options["from_language"] = args["src"]
	if "dest" in args:
		tr_options["to_language"] = args["dest"]
	engine = args["engine"] if "engine" in args else "bing"
	await client.send_chat_action(message.chat.id, "find_location")
	q = message.reply_to_message.text if message.reply_to_message is not None else args["arg"]
	logger.info(f"Translating {q}")
	out = "`[!] → ` Unknown engine"
	if engine == "google":
		out = "`[!] → ` As of now, this hangs forever, don't use yet!"
		# res = ts.google(q, **tr_options)
	elif engine == "deepl":
		out = ts.deepl(q, **tr_options)
	elif engine == "bing":
		out = "` → ` " + ts.bing(q, **tr_options)
	await edit_or_reply(message, out)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help("lmgtfy", "let me google that for you",
				"generates a `Let Me Google That For You` link.",
				args="<query>", public=True)
@alemiBot.on_message(is_allowed & filterCommand("lmgtfy", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def lmgtfy(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No query given")
	arg = parse.quote_plus(message.command["arg"])
	logger.info(f"lmgtfy {arg}")
	await edit_or_reply(message, f"<code> → </code> http://letmegooglethat.com/?q={arg}",
										disable_web_page_preview=True, parse_mode="html")


WTTR_STRING = "`→ {loc} `\n` → `**{desc}**\n` → ` {mintemp:.0f}C - {maxtemp:.0f}C `|` **{hum}%** humidity\n" + \
			  "` → ` pressure **{press}hPa** `|` wind **{wspd}m/s**\n` → ` **{vis}m** visibility (__{cld}% clouded__)"

HELP.add_help(["weather", "wttr"], "get weather of location",
				"makes a request to wttr.in for provided location. Props to https://github.com/chubin/wttr.in " +
				"for awesome site, remember you can `curl wttr.in` in terminal. Result language can be specified with `-l`.",
				# "searches OpenWeatherMap for specified location. To make queries to OpenWeatherMap " +
				# "an API key is necessary, thus registering to OpenWeatherMap. This is super early and shows very little.",
				args="[-l <lang>] <location>", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["weather", "wttr"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}))
@report_error(logger)
@set_offline
async def weather_cmd(client, message):
	if "arg" not in message.command:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	# APIKEY = alemiBot.config.get("weather", "apikey", fallback="")
	# if APIKEY == "":
	#	  return await edit_or_reply(message, "`[!] → ` No APIKEY provided in config")
	logger.info("curl wttr.in")
	await client.send_chat_action(message.chat.id, "find_location")
	q = message.command["arg"]
	lang = message.command["lang"] if "lang" in message.command else "en"
	r = requests.get(f"https://wttr.in/{q}?mnTC0&lang={lang}")
	await edit_or_reply(message, "<code> → " + r.text + "</code>", parse_mode="html")
	# # Why bother with OpenWeatherMap?
	# r = requests.get(f'http://api.openweathermap.org/data/2.5/weather?q={q}&APPID={APIKEY}').json()
	# if r["cod"] != 200:
	#	  return await edit_or_reply(message, "`[!] → ` Query failed")
	# await edit_or_reply(message, WTTR_STRING.format(loc=r["name"], desc=r["weather"][0]["description"],
	#												  mintemp=r["main"]["temp_min"] - 272.15,
	#												  maxtemp=r["main"]["temp_max"] - 272.15,
	#												  hum=r["main"]["humidity"], press=r["main"]["pressure"],
	#												  wspd=r["wind"]["speed"], vis=r["visibility"], cld=r["clouds"]["all"]))
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["scribe"], "transcribes a voice message",
				"reply to a voice message to transcribe it. It uses Google Speech Recognition API. " +
				"It will work without a key but usage may get limited. You can try to [get a free key](http://www.chromium.org/developers/how-tos/api-keys) " +
				"and add it to your config under category [scribe] in a field named \"key\". You can specify speech " +
				"recognition language with `-l` (using `RFC5646` language tag format :	`en-US`, `it-IT`, ...)",
				args="[-l <lang>]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["scribe"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}))
@report_error(logger)
@set_offline
async def transcribe_cmd(client, message):
	await client.send_chat_action(message.chat.id, "record_audio")
	msg = await edit_or_reply(message, "` → ` Working...")
	path = None
	lang = message.command["lang"] if "lang" in message.command else "en-US"
	if message.reply_to_message and message.reply_to_message.voice:
		path = await client.download_media(message.reply_to_message)
	elif message.voice:
		path = await client.download_media(message)
	else:
		return await edit_or_reply(message, "`[!] → ` No audio given")
	AudioSegment.from_ogg(path).export("data/voice.wav", format="wav")
	os.remove(path)
	voice = sr.AudioFile("data/voice.wav")
	with voice as source:
		audio = recognizer.record(source)
	out = "` → `" + recognizer.recognize_google(audio, language=lang,
						key=alemiBot.config.get("scribe", "key", fallback=None))
	await edit_or_reply(msg, out)
	await client.send_chat_action(message.chat.id, "cancel")

HELP.add_help(["ocr"], "read text in photos",
				"make a request to https://api.ocr.space/parse/image. The number of allowed queries " +
				"is limited, the result is not guaranteed and it requires an API key set up to work. " +
				"A language for the OCR can be specified with `-l`. You can request OCR.space overlay in response " +
				"with the `-overlay` flag. A media can be attached or replied to. Add the `-json` flag to get raw result.",
				args="[-l <lang>] [-overlay]", public=True)
@alemiBot.on_message(is_allowed & filterCommand(["ocr"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}, flags=["-overlay", "-json"]))
@report_error(logger)
@set_offline
async def ocr_cmd(client, message):
	payload = {
		'isOverlayRequired': "-overlay" in message.command["flags"],
		'apikey': alemiBot.config.get("ocr", "apikey", fallback=""),
		'language': message.command["lang"] if "lang" in message.command else "eng"
	}
	if payload["apikey"] == "":
		return await edit_or_reply(message, "`[!] → ` No API Key set up")
	msg = message
	if message.reply_to_message is not None:
		msg = message.reply_to_message
	if msg.media:
		await client.send_chat_action(message.chat.id, "upload_photo")
		fpath = await client.download_media(msg, file_name="data/ocr")
		with open(fpath, 'rb') as f:
			r = requests.post('https://api.ocr.space/parse/image', files={fpath: f}, data=payload)
		if "-json" in message.command["flags"]:
			raw = tokenize_json(json.dumps(json.loads(r.content.decode()), indent=2))
			await edit_or_reply(message, f"` → `\n{raw}")
		else:
			raw = json.loads(r.content.decode())
			out = ""
			for el in raw["ParsedResults"]:
				out += el["ParsedText"]
			await edit_or_reply(message, f"` → ` {out}")
	else:
		return await edit_or_reply(message, "`[!] → ` No media given")
	await client.send_chat_action(message.chat.id, "cancel")

# HELP.add_help(["link"], "expand a reward url",
# 				"expand given url using `linkexpander.com`.", 
# 				args="<url>", public=True)
# @alemiBot.on_message(is_allowed & filterCommand(["link"], list(alemiBot.prefixes)))
# @report_error(logger)
# @set_offline
# async def link_expander_cmd(client, message):
# 	if "arg" not in message.command:
# 		return await edit_or_reply(message, "`[!] → ` No URL given")
# 	url = message.command["arg"]
# 	r = requests.get(f"https://www.linkexpander.com/?url={url}")
# 	await edit_or_reply(message, r.text, parse_mode=None)