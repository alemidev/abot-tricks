import os
import json
import time
from urllib import parse
import aiohttp

from typing import Dict

from bot import alemiBot

import wikipediaapi
import italian_dictionary
import cryptocompare
from PyDictionary import PyDictionary
from udpy import UrbanClient
from google_currency import convert
from unit_converter.converter import converts
from deep_translator import GoogleTranslator

from pydub import AudioSegment
import speech_recognition as sr

from pyrogram import Client
from pyrogram.types import Message

from util import batchify
from util.text import tokenize_json, sep
from util.getters import get_user
from util.permission import is_allowed
from util.message import edit_or_reply, ProgressChatAction
from util.command import filterCommand
from util.decorators import report_error, set_offline, cancel_chat_action
from util.help import HelpCategory

import logging
logger = logging.getLogger(__name__)

HELP = HelpCategory("APICALLS")

recognizer = sr.Recognizer()
dictionary = PyDictionary()
UClient = UrbanClient()

@HELP.add(cmd="<val> <from> <to>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["convert", "conv"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def convert_cmd(client, message):
	"""convert various measure units

	Conversion tool. Accepts many units, like `.convert 52 °C °F` \
	or `.convert 2.78 daN*mm^2 mN*µm^2`.
	"""
	if len(message.command) < 3:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	res = converts(message.command[0] + " " + message.command[1], message.command[2])
	await edit_or_reply(message, f"` → ` **{res}** {message.command[2]}")

@HELP.add(cmd="<from> [<val>] [<to>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["currency", "cconvert", "curr"], list(alemiBot.prefixes), flags=["-crypto"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def currency_convert_cmd(client, message):
	"""convert various currencies
	
	Currency price checker and conversion tool. Accept many currency tickers, like `.currency btc` \
	or `.currency btc 20 eur`.
	Will use Google Currency for values, and if currency is not found there, cryptocompare.
	Add flag `-crypto` to directly search cryptocompare.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	await client.send_chat_action(message.chat.id, "choose_contact")
	val = float(message.command[1] or 1.0)
	from_ticker = message.command[0]
	to_ticker = message.command[2] or "USD"
	converted_val = 0.0
	res = {"converted" : False}
	if not bool(message.command["-crypto"]):
		res = json.loads(convert(from_ticker, to_ticker, val))
	if res["converted"]:
		to_ticker = res["to"]
		converted_val = float(res["amount"])
	else:
		res = cryptocompare.get_price(from_ticker, currency=to_ticker)
		if not res:
			return await edit_or_reply(message, "`[!] → ` Invalid currency ticker")
		from_ticker = list(res.keys())[0]
		to_ticker = list(res[from_ticker].keys())[0]
		converted_val = val * float(res[from_ticker][to_ticker])
	await edit_or_reply(message, f"` → ` **{sep(converted_val)}** {to_ticker}")

@HELP.add(cmd="<word>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["diz", "dizionario"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
@cancel_chat_action
async def diz_cmd(client, message):
	"""search in italian dictionary
	
	Get definition of given word from italian dictionary.
	Will use www.dizionario-italiano.it.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No query given")
	await client.send_chat_action(message.chat.id, "upload_document")
	arg = message.command.text
	# Use this to get only the meaning 
	res = italian_dictionary.get_definition(arg) 

	out = f"` → {res['lemma']} ` [ {' | '.join(res['sillabe'])} ]\n"
	out += f"```{', '.join(res['grammatica'])} - {res['pronuncia']}```\n\n"
	out += "\n\n".join(res['definizione'])
	await edit_or_reply(message, out)

@HELP.add(cmd="<word>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["dic", "dictionary"], list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
@cancel_chat_action
async def dic_cmd(client, message):
	"""search in english dictionary

	Get definition of given word from English dictionary.
	Will search on wordnet.princeton.edu.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No query given")
	await client.send_chat_action(message.chat.id, "upload_document")
	arg = message.command.text
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

@HELP.add(cmd="<query>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["ud", "urban"], list(alemiBot.prefixes), options={
	"results" : ["-r", "-res"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def urbandict_cmd(client, message):
	"""search on urban dictionary
	
	Get definition from urban dictionary of given query.
	Number of results to return can be specified with `-r`, \
	will default to only one (top definition).
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No query given")
	n = int(message.command["results"] or 1)
	await client.send_chat_action(message.chat.id, "upload_document")
	res = UClient.get_definition(message.command.text)
	if len(res) < 1:
		return await edit_or_reply(message, "`[!] → ` Not found")
	out = ""
	for i in range(min(n, len(res))):
		out +=  f"<code>→ </code> <u>{res[i].word}</u> <code>[+{res[i].upvotes}|{res[i].downvotes}-]</code>\n" + \
				f"{res[i].definition}\n\n<i>{res[i].example}</i>\n\n"
	await edit_or_reply(message, out, parse_mode="html")

@HELP.add(cmd="<query>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("wiki", list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"],
	"limit" : ["-max"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def wiki_cmd(client, message):
	"""search on wikipedia
	
	Search on wikipedia, attaching initial text and a link.
	Language will default to english if not specified with `-l`.
	By default, only first 1000 characters will be printed, a different amount \
	can be specified with `-max`
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No query given")
	lang = message.command["lang"] or "en"
	limit = int(message.command["limit"] or 1000)
	await client.send_chat_action(message.chat.id, "upload_document")
	Wikipedia = wikipediaapi.Wikipedia(lang)
	page = Wikipedia.page(message.command.text)
	if not page.exists():
		return await edit_or_reply(message, "`[!] → ` No results")
	text = page.text if len(page.summary) < limit else page.summary
	if len(text) > limit:
		text = text[:limit] + " ..."
	await edit_or_reply(message, f"` → {page.title}`\n{text}\n` → ` {page.fullurl}")

@HELP.add(cmd="[<text>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["translate", "tran", "tr"], list(alemiBot.prefixes), options={
	"src" : ["-s", "-src"],
	"dest" : ["-d", "-dest"],
# 	"engine" : ["-e", "-engine"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def translate_cmd(client, message): # TODO implement more engines from deep-translator
	"""translate to/from

	Translate text from a language (autodetected if not specified with `-s`) to another \
	specified lang (defaults to eng if not specified with `-d`).
	Will work with Google Translate.
	Source language will be automatically detected if not specified otherwise.
	Language codes can be 2 letters (`en`) or full word (`english`).
	"""
	if len(message.command) < 1 and not message.reply_to_message:
		return await edit_or_reply(message, "`[!] → ` Nothing to translate")
	tr_options = {}
	# lmao I can probably pass **args directly
	source_lang = message.command["src"] or "auto"
	dest_lang = message.command["dest"] or "en"
	await client.send_chat_action(message.chat.id, "find_location")
	q = message.reply_to_message.text if message.reply_to_message is not None else message.command.text
	out = GoogleTranslator(source=source_lang, target=dest_lang).translate(text=q)
	await edit_or_reply(message, "` → ` " + out)

@HELP.add(cmd="<query>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("lmgtfy", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def lmgtfy(client, message):
	"""let me google that for you

	Generates a `Let Me Google That For You` link
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No query given")
	arg = parse.quote_plus(message.command.text)
	await edit_or_reply(message, f"<code> → </code> http://letmegooglethat.com/?q={arg}",
										disable_web_page_preview=True, parse_mode="html")


WTTR_STRING = "`→ {loc} `\n` → `**{desc}**\n` → ` {mintemp:.0f}C - {maxtemp:.0f}C `|` **{hum}%** humidity\n" + \
			  "` → ` pressure **{press}hPa** `|` wind **{wspd}m/s**\n` → ` **{vis}m** visibility (__{cld}% clouded__)"

@HELP.add(cmd="<location>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["weather", "wttr"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def weather_cmd(client, message):
	"""get weather of location
	
	Makes a request to wttr.in for provided location. Props to https://github.com/chubin/wttr.in \
	for awesome site, remember you can `curl wttr.in` in terminal.
	Result language can be specified with `-l`.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` Not enough arguments")
	# APIKEY = alemiBot.config.get("weather", "apikey", fallback="")
	# if APIKEY == "":
	#	  return await edit_or_reply(message, "`[!] → ` No APIKEY provided in config")
	await client.send_chat_action(message.chat.id, "find_location")
	q = message.command.text
	lang = message.command["lang"] or "en"

	async with aiohttp.ClientSession() as sess: # TODO reuse session
		async with sess.get(f"https://wttr.in/{q}?mnTC0&lang={lang}") as res:
			text = await res.text()

	await edit_or_reply(message, "<code> → " + text + "</code>", parse_mode="html")

	# # Why bother with OpenWeatherMap?
	# r = requests.get(f'http://api.openweathermap.org/data/2.5/weather?q={q}&APPID={APIKEY}').json()
	# if r["cod"] != 200:
	#	  return await edit_or_reply(message, "`[!] → ` Query failed")
	# await edit_or_reply(message, WTTR_STRING.format(loc=r["name"], desc=r["weather"][0]["description"],
	#												  mintemp=r["main"]["temp_min"] - 272.15,
	#												  maxtemp=r["main"]["temp_max"] - 272.15,
	#												  hum=r["main"]["humidity"], press=r["main"]["pressure"],
	#												  wspd=r["wind"]["speed"], vis=r["visibility"], cld=r["clouds"]["all"]))

@HELP.add(sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["scribe"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def transcribe_cmd(client, message):
	"""transcribes a voice message

	Reply to a voice message to transcribe it. It uses Google Speech Recognition API.
	It will work without a key but usage may get limited. You can try to get a free key here: http://www.chromium.org/developers/how-tos/api-keys
	If you have an API key, add it to your config under category [scribe] in a field named \"key\".
	You can specify speech recognition language with `-l` (using `RFC5646` language tag format :`en-US`, `it-IT`, ...)
	"""
	await client.send_chat_action(message.chat.id, "record_audio")
	msg = await edit_or_reply(message, "`→ ` Working...")
	path = None
	lang = message.command["lang"] or "en-US"
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

@HELP.add(sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["ocr"], list(alemiBot.prefixes), options={
	"lang" : ["-l", "-lang"]
}, flags=["-overlay", "-json"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def ocr_cmd(client, message):
	"""read text in photos

	Make a request to https://api.ocr.space/parse/image. The number of allowed queries \
	is limited, the result is not guaranteed and it requires an API key set up to work.
	A language for the OCR can be specified with `-l`.
	You can request OCR.space overlay in response with the `-overlay` flag.
	A media can be attached or replied to.
	Add the `-json` flag to get raw result.
	"""
	payload = {
		'isOverlayRequired': bool(message.command["-overlay"]),
		'apikey': alemiBot.config.get("ocr", "apikey", fallback=""),
		'language': message.command["lang"] or "eng",
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
			payload['file'] = f
			async with aiohttp.ClientSession() as sess:
				async with sess.post('https://api.ocr.space/parse/image', data=payload) as res:
					data = await res.json()
		if message.command["-json"]:
			raw = tokenize_json(json.dumps(data), indent=2)
			await edit_or_reply(message, f"` → `\n{raw}")
		else:
			out = ""
			for el in data["ParsedResults"]:
				out += el["ParsedText"]
			await edit_or_reply(message, f"` → ` {out}")
	else:
		return await edit_or_reply(message, "`[!] → ` No media given")

# HELP.add_help(["link"], "expand a reward url",
# 				"expand given url using `linkexpander.com`.", 
# 				cmd="<url>", sudo=False)
# @alemiBot.on_message(is_allowed & filterCommand(["link"], list(alemiBot.prefixes)))
# @report_error(logger)
# @set_offline
# async def link_expander_cmd(client, message):
# 	if "arg" not in message.command:
# 		return await edit_or_reply(message, "`[!] → ` No URL given")
# 	url = message.command["arg"]
# 	r = requests.get(f"https://www.linkexpander.com/?url={url}")
# 	await edit_or_reply(message, r.text, parse_mode=None)

_CONV : Dict[int, dict] = {} # cheap way to keep a history of conversations

@HELP.add(cmd="[<payload>]")
@alemiBot.on_message(is_allowed & filterCommand(["huggingface", "hgf"], alemiBot.prefixes, options={
	"model" : ["-m", "--model"],
	"conversation" : ["-conv", "--conversation"],
	"question" : ["-ask", "--ask_question"],
	"summary" : ["-sum", "--summary"],
	"sentiment" : ["-sent", "--sentiment"],
	"generate" : ["-gen", "--generate"],
}, flags=["-nowait"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def huggingface_cmd(client: Client, message: Message):
	"""will query Huggingface Accelerated Interface API

	Requires an API key in bot config, under [huggingface] ( key = asdasdasd )
	Will query the Accelerated Interface Api with the provided token.
	The default model can be specified with `-m`. Default model will change depending on task
	Some specific tasks are pre-programmed as options:
	-	Use `-conv` to have a conversation (pass `--reset` as argument to reset ongoing). Defaults to `microsoft/DialoGPT-large`.
	-	Use `-ask` to make a question, and specify the context inside `()`. Defaults to `deepset/roberta-base-squad2`.
	-	Use `-sum` to make a summary of given text. Defaults to `facebook/bart-large-cnn`.
	-	Use `-sent` to get sentiment analysis of text. Defaults to `distilbert-base-uncased-finetuned-sst-2-english`.
	-	Use `-gen` to generate text starting from input. Defaults to `gpt2`.
	The API is capable of more tasks (like speech recognition, table searching, zero-shot classification) but \
	these functionalities are not yet implemented in this command.
	To access unsupported tasks, raw json input can be passed with no extra options. It will be fed as-is to requested model.
	If raw json is being passed, default model will be gpt2.
	Will report request time. This will include model load time and net latency. Add flag `-nowait` to fail if the model is not readily available.
	"""
	uid = get_user(message).id
	url = "https://api-inference.huggingface.co/models/"
	headers = {"Authorization": f"Bearer api_{alemiBot.config.get('huggingface', 'key', fallback='')}"}
	
	payload = { "wait_for_model" : True, "inputs" : {} }
	if message.command["-nowait"]:
		payload["wait_for_model"] = False

	if message.command["conversation"]:
		if message.command["conversation"] == "--reset":
			_CONV.pop(uid, None)
			return await edit_or_reply(message, "` → ` Cleared conversation")
		payload["inputs"] = (_CONV[uid] if uid in _CONV else {})
		payload["inputs"]["text"] = message.command["conversation"]
		model = "microsoft/DialoGPT-large"
	elif message.command["question"]:
		if "(" in message.command["question"]:
			question, context = message.command["question"].rsplit("(", 1)
			context = context.replace(")", "")
		else:
			question = message.command["question"]
			context = ""
		payload["inputs"] = {"question":question, "context":context}
		model = "deepset/roberta-base-squad2"
	elif message.command["summary"]:
		payload["inputs"] = message.command["summary"]
		model = "facebook/bart-large-cnn"
	elif message.command["sentiment"]:
		payload["inputs"] = message.command["sentiment"]
		model = "distilbert-base-uncased-finetuned-sst-2-english"
	elif message.command["generate"]:
		payload["inputs"] = message.command["generate"]
		model = "gpt2"
	else:
		if not message.command.text:
			return await edit_or_reply(message, "` → ` No input")
		payload = json.loads(message.command[0])
		model = "gpt2"

	if message.command["model"]:
		model = message.command["model"]

	before = time.time()
	with ProgressChatAction(client, message.chat.id, action="typing") as prog:
		async with aiohttp.ClientSession() as sess:
			async with sess.post(url + model, headers=headers, json=payload) as res:
				reply = await res.json()
	inference_time = time.time() - before

	if isinstance(reply, list): # cheap trick, sometimes it comes as list
		reply = reply[0]

	if "error" in reply:
		return await edit_or_reply(message, f"` → ` [**{inference_time:.1f}**s] {reply['error']}")

	pre = f"` → ` [**{inference_time:.1f}**s] "

	if message.command["conversation"]:
		_CONV[uid] = reply["conversation"]
		await edit_or_reply(message, pre + reply["generated_text"])
	elif message.command["question"]:
		await edit_or_reply(message, pre + f'{reply["answer"]} | {reply["score"]:.3f}')
	elif message.command["summary"]:
		await edit_or_reply(message, pre + reply["summary_text"])
	elif message.command["sentiment"]:
		first, second = reply # really bad trick, couldn't you put it all in one dict????
		if first["score"] > second["score"]:
			await edit_or_reply(message, pre + f'{first["label"]} | {first["score"]:.3f}')
		else:
			await edit_or_reply(message, pre + f'{second["label"]} | {second["score"]:.3f}')
	elif message.command["generate"]:
		await edit_or_reply(message, pre + reply["generated_text"])
	else:
		await edit_or_reply(message, pre + tokenize_json(json.dumps(reply, indent=2)))

