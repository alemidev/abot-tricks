import asyncio
import secrets
import random
import html
import os
import io
import re

from PIL import Image, ImageEnhance, ImageOps

from pyrogram import filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo

from bot import alemiBot

from util import batchify
from util.permission import is_allowed, is_superuser
from util.message import ProgressChatAction, edit_or_reply, is_me, send_media
from util.text import order_suffix
from util.getters import get_text
from util.command import filterCommand
from util.decorators import report_error, set_offline, cancel_chat_action
from util.help import HelpCategory

import logging
logger = logging.getLogger(__name__)

HELP = HelpCategory("MEME")
INTERRUPT = False

@HELP.add(cmd="[<name>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("meme", list(alemiBot.prefixes), options={
	"batch" : ["-b"]
}, flags=["-list", "-stats"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def meme_cmd(client, message):
	"""get a meme from collection

	If a name was specified, get meme matching requested name (regex). Otherwise, get random meme.
	Use flag `-list` to get all meme names and flag `-stats` to get count and disk usage.
	You can send a bunch of random memes together by specifying how many in the `-b` (batch) option \
	(only photos will be sent if a batch is requested).
	Memes can be any filetype.
	"""
	batchsize = max(min(int(message.command["batch"] or 10), 10), 2)
	reply_to = message.message_id
	if is_me(message) and message.reply_to_message is not None:
		reply_to = message.reply_to_message.message_id
	if message.command["-stats"]:
		memenumber = len(os.listdir("plugins/alemibot-tricks/data/meme"))
		proc_meme = await asyncio.create_subprocess_exec( # ewww this is not cross platform but will do for now
			"du", "-b", "plugins/alemibot-tricks/data/meme/",
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.STDOUT)
		stdout, _stderr = await proc_meme.communicate()
		memesize = float(stdout.decode('utf-8').split("\t")[0])
		await edit_or_reply(message, f"` → ` **{memenumber}** memes collected\n`  → ` folder size **{order_suffix(memesize)}**")
	elif message.command["-list"]:
		memes = os.listdir("plugins/alemibot-tricks/data/meme")
		memes.sort()
		out = f"` → ` **Meme list** ({len(memes)} total) :\n[ "
		out += ", ".join(memes)
		out += "]"
		await edit_or_reply(message, out)
	elif len(message.command) > 0 and (len(message.command) > 1 or message.command[0] != "-delme"):
		search = re.compile(message.command[0])
		for meme in os.listdir("plugins/alemibot-tricks/data/meme"):
			if search.match(meme):
				return await send_media(client, message.chat.id, 'plugins/alemibot-tricks/data/meme/' + meme, reply_to_message_id=reply_to,
						caption=f"` → ` **{meme}**")
		await edit_or_reply(message, f"`[!] → ` no meme matching `{message.command[0]}`")
	else: 
		if "batch" in message.command:
			with ProgressChatAction(client, message.chat.id, action="upload_photo") as prog:
				pool = [ x for x in filter(lambda x: x.endswith((".jpg", ".jpeg", ".png")), os.listdir("plugins/alemibot-tricks/data/meme")) ]
				def pick(pool):
					pick = secrets.choice(pool)
					pool.remove(pick)
					return pick
				memes = [InputMediaPhoto("plugins/alemibot-tricks/data/meme/" + pick(pool)) for _ in range(batchsize)]
				await client.send_media_group(message.chat.id, memes)
		else:
			fname = secrets.choice(os.listdir("plugins/alemibot-tricks/data/meme"))
			await send_media(client, message.chat.id, 'plugins/alemibot-tricks/data/meme/' + fname, reply_to_message_id=reply_to,
					caption=f"` → ` [--random--] **{fname}**")

@HELP.add(cmd="<name>")
@alemiBot.on_message(is_superuser & filterCommand("steal", list(alemiBot.prefixes), flags=["-pasta"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def steal_cmd(client, message):
	"""steal a meme

	Save a meme to collection.
	Either attach an image or reply to one.
	A name for the meme must be given (and must not contain spaces)
	Add flag `-pasta` to save given file (or message text) to copypasta directory
	"""
	is_pasta = message.command["-pasta"]
	dir_path = "pasta" if is_pasta else "meme"
	msg = message
	newname = message.command[0]
	# check if a file with this name already exists
	if newname in [ fname.rsplit(".", 1)[0] for fname in os.listdir(f"plugins/alemibot-tricks/data/{dir_path}/") ]:
		return await edit_or_reply(message, f"`[!] → ` {dir_path} with same name already exists")
	prog = ProgressChatAction(client, message.chat.id, action="record_video")
	if len(message.command) < 1:
		return await edit_or_reply(message, f"`[!] → ` No {dir_path} name provided")
	if message.reply_to_message:
		msg = message.reply_to_message
	if msg.media:
		fpath = await client.download_media(msg, progress=prog.tick) # + message.command[0])
		# await edit_or_reply(message, '` → ` saved meme as {}'.format(fpath))
		path, fname = os.path.splitext(fpath) # this part below is trash, im waiting for my PR on pyrogram
		extension = fname.split(".")
		if len(extension) > 1:
			extension = extension[1]
		else:
			extension = "txt" if is_pasta else "jpg" # cmon most memes will be jpg
		newname = newname '.' + extnsion
		os.rename(fpath, f"plugins/alemibot-tricks/data/{dir_path}/{newname}")
		await edit_or_reply(message, f'` → ` saved {dir_path} as {newname}')
	elif message.command["-pasta"]:
		with open(f"plugins/alemibot-tricks/data/pasta/{message.command[0]}.txt", "w") as f:
			f.write(msg.text)
		await edit_or_reply(message, f'` → ` saved pasta as {message.command[0]}.txt')
	else:
		await edit_or_reply(message, "`[!] → ` No input")

#
# This is from https://github.com/Ovyerus/deeppyer
#	I should do some license stuff here but TODO
#

async def fry_image(img: Image) -> Image:
	colours = ( # TODO tweak values
		(random.randint(50, 200), random.randint(40, 170), random.randint(40, 190)),
		(random.randint(190, 255), random.randint(170, 240), random.randint(180, 250))
	)

	img = img.copy().convert("RGB")

	# Crush image to hell and back
	img = img.convert("RGB")
	width, height = img.width, img.height
	img = img.resize((int(width ** random.uniform(0.8, 0.9)), int(height ** random.uniform(0.8, 0.9))), resample=Image.LANCZOS)
	img = img.resize((int(width ** random.uniform(0.85, 0.95)), int(height ** random.uniform(0.85, 0.95))), resample=Image.BILINEAR)
	img = img.resize((int(width ** random.uniform(0.89, 0.98)), int(height ** random.uniform(0.89, 0.98))), resample=Image.BICUBIC)
	img = img.resize((width, height), resample=Image.BICUBIC)
	img = ImageOps.posterize(img, random.randint(3, 7))

	# Generate colour overlay
	overlay = img.split()[0]
	overlay = ImageEnhance.Contrast(overlay).enhance(random.uniform(1.0, 2.0))
	overlay = ImageEnhance.Brightness(overlay).enhance(random.uniform(1.0, 2.0))

	overlay = ImageOps.colorize(overlay, colours[0], colours[1])

	# Overlay red and yellow onto main image and sharpen the hell out of it
	img = Image.blend(img, overlay, random.uniform(0.1, 0.4))
	img = ImageEnhance.Sharpness(img).enhance(random.randint(5, 300))

	return img

@HELP.add(sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("fry", list(alemiBot.prefixes), options={
	"count" : ["-c", "--count"],
}))
@report_error(logger)
@set_offline
@cancel_chat_action
async def deepfry_cmd(client, message):
	"""deepfry an image

	Will deepfry an image (won't add "laser eyes").
	The number of frying rounds can be specified with `-c`. Will default to 1.
	Code from https://github.com/Ovyerus/deeppyer.
	"""
	target = message.reply_to_message if message.reply_to_message is not None else message
	prog = ProgressChatAction(client, message.chat.id, action="upload_photo")
	if target.media:
		msg = await edit_or_reply(message, "` → ` Downloading...")
		count = int(message.command["count"] or 1)
		fpath = await client.download_media(target, progress=prog.tick)
		msg.edit(get_text(message) + "\n` → ` Downloading [OK]\n` → ` Frying...")
		image = Image.open(fpath)

		for _ in range(count):
			await prog.tick()
			image = await fry_image(image)
		if message.from_user is not None and message.from_user.is_self:
			await msg.edit(get_text(message) +
				"\n` → ` Downloading [OK]\n` → ` Frying [OK]\n` → ` Uploading...")

		fried_io = io.BytesIO()
		fried_io.name = "fried.jpg"
		image.save(fried_io, "JPEG")
		fried_io.seek(0)
		await client.send_photo(message.chat.id, fried_io, reply_to_message_id=message.message_id,
									caption=f"` → Fried {count} time{'s' if count > 1 else ''}`", progress=prog.tick)
		if message.from_user is not None and message.from_user.is_self:
			await msg.edit(get_text(message) +
				"\n` → ` Downloading [OK]\n` → ` Frying [OK]\n` → ` Uploading [OK]")
		os.remove(fpath)
	else:
		await edit_or_reply(message, "`[!] → ` you need to attach or reply to a file, dummy")

#
#	This comes from https://github.com/anuragrana/Python-Scripts/blob/master/image_to_ascii.py
#

def ascii_image(img:Image, new_width:int=120) -> str:
	# resize the image
	width, height = img.size
	aspect_ratio = height/width
	new_height = aspect_ratio * new_width * 0.55
	img = img.resize((new_width, int(new_height)))
	img = img.convert('L')
	
	pixels = img.getdata()
	
	# replace each pixel with a character from array
	chars = ["B","S","#","&","@","$","%","*","!",":","."]
	new_pixels = [chars[pixel//25] for pixel in pixels]
	new_pixels = ''.join(new_pixels)
	
	# split string of chars into multiple strings of length equal to new width and create a list
	new_pixels_count = len(new_pixels)
	ascii_image = [new_pixels[index:index + new_width] for index in range(0, new_pixels_count, new_width)]
	ascii_image = "\n".join(ascii_image)
	return ascii_image

@HELP.add(cmd="[<width>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("ascii", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
@cancel_chat_action
async def ascii_cmd(client, message):
	"""make ascii art of picture

	Roughly convert a picture into ascii art.
	You can specify width of the resulting image in characters as command argument (default is 120).
	If the requested width is lower than 50 characters,	the result will be printed directly into telegram. Else, a txt will be attached.
	Code comes from https://github.com/anuragrana/Python-Scripts/blob/master/image_to_ascii.py.
	"""
	msg = message
	if message.reply_to_message is not None:
		msg = message.reply_to_message
	prog = ProgressChatAction(client, message.chat.id, action="upload_document")
	width = int(message.command[0] or 120)
	if msg.media:
		fpath = await client.download_media(msg, file_name="toascii")
		image = Image.open(fpath)

		ascii_result = ascii_image(image, new_width=width)

		if width <= 50:
			await edit_or_reply(message, "``` →\n" + ascii_result + "```")
		else:
			out = io.BytesIO(ascii_result.encode('utf-8'))
			out.name = "ascii.txt"
			await client.send_document(message.chat.id, out, reply_to_message_id=message.message_id,
										caption=f"` → Made ASCII art `", progress=prog.tick)
	else:
		await edit_or_reply(message, "`[!] → ` you need to attach or reply to a file, dummy")

INTERRUPT_PASTA = False

@HELP.add(cmd="<fpath>")
@alemiBot.on_message(is_superuser & filterCommand("pasta", list(alemiBot.prefixes), options={
	"separator" : ["-s", "-sep"],
	"interval" : ["-i", "-intrv"]
}, flags=["-stop", "-mono", "-edit"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def pasta_cmd(client, message):
	"""drop a copypasta

	Give copypasta name or path to any file containing long text and bot will drop it in chat.
	Use flag `-stop` to stop ongoing pasta.
	A separator can be specified with `-s` to split the copypasta (for example, at newlines `\\n`).
	Long messages will still be split in chunks of 4096 characters due to telegram limit.
	Messages will be sent at an interval of 1 second by default. A different interval can be specified with `-i`.
	Add flag `-mono` to print pasta monospaced.
	Add flag `-edit` to always edit the first message instead of sending new ones.
	Reply to a message while invoking this command to have all pasta chunks reply to that message.
	"""
	global INTERRUPT_PASTA
	if message.command["-stop"]:
		INTERRUPT_PASTA = True
		return
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	repl_id = None
	if message.reply_to_message:
		repl_id = message.reply_to_message.message_id
	sep = message.command["separator"]
	intrv = float(message.command["interval"] or 1.0)
	monospace = bool(message.command["-mono"])
	edit_this = await client.send_message(message.chat.id, "` → ` Starting", reply_to_message_id=repl_id) \
			if bool(message.command["-edit"]) else None
	p_mode = 'html' if monospace else None
	# Find correct path
	path = message.command[0]
	try:
		pattern = re.compile(message.command[0])
		for pasta in os.listdir("plugins/alemibot-tricks/data/pasta"):
			if pattern.match(pasta):
				path = f"plugins/alemibot-tricks/data/pasta/{pasta}"
				break
	except re.error:
		pass
	# load text, make it a list so it's iterable
	with open(path, "rb") as f:
		text = [ f.read().decode('utf-8', 'ignore') ]
	# apply separator if requested
	if sep:
		text = re.split(sep, text[0])
	with ProgressChatAction(client, message.chat.id, action="typing") as prog:
		for section in text:
			for chunk in batchify(section, 4096):
				if len(chunk.strip()) < 1:
					continue
				if monospace:
					chunk = "<code>" + html.escape(chunk) + "</code>"
				if edit_this:
					await edit_this.edit(chunk, parse_mode=p_mode)
				else:
					await client.send_message(message.chat.id, chunk, parse_mode=p_mode, reply_to_message_id=repl_id)
				await asyncio.sleep(intrv)
				if INTERRUPT_PASTA:
					INTERRUPT_PASTA = False
					raise Exception("Interrupted by user")
		if edit_this:
			await edit_this.edit("` → ` Done")
