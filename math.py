import math, cmath
import asyncio

from pyrogram import filters

from alemibot import alemiBot

from alemibot.util.command import _Message as Message
from alemibot.util import (
	batchify, is_allowed, ProgressChatAction, edit_or_reply, filterCommand, 
	report_error, set_offline, cancel_chat_action, HelpCategory
)

import sympy
from sympy.solvers import solve
from sympy.plotting import plot3d, plot3d_parametric_line
from sympy.parsing.sympy_parser import parse_expr
from sympy import preview, plot

import logging
logger = logging.getLogger(__name__)

# This is maybe should be in the statistics module? I dunno, lmk if it fits in tricks
HELP = HelpCategory("MATH")

@HELP.add(cmd="<expr>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["expr", "math"], flags=["-latex"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def expr_cmd(client:alemiBot, message:Message):
	"""convert to LaTeX formula

	This command accepts sympy syntax and will generate a LaTeX formula as image.
	Add flag `-latex` to directly pass LaTeX.
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	expr = message.command.text
	prog = ProgressChatAction(client, message.chat.id, action="upload_document")
	if message.command["-latex"]:
		preview(expr, viewer='file', filename='expr.png', dvioptions=["-T", "bbox", "-D 300", "--truecolor", "-bg", "Transparent"])
	else:
		res = parse_expr(expr)
		preview(res, viewer='file', filename='expr.png', dvioptions=["-T", "bbox", "-D 300", "--truecolor", "-bg", "Transparent"])
	await client.send_photo(message.chat.id, "expr.png", reply_to_message_id=message.id,
									caption=f"` → {expr} `", progress=prog.tick)

@HELP.add(cmd="<expr>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand(["plot", "graph"], flags=["-3d"]))
@report_error(logger)
@set_offline
@cancel_chat_action
async def graph_cmd(client:alemiBot, message:Message):
	"""plot provided function

	This command will run sympy `plot` and return result as image.
	You can add the `-3d` argument to plot in 3d (pass functions with 3 variables!)
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	prog = ProgressChatAction(client, message.chat.id, action="upload_document")
	expr = message.command.text
	eq = []
	for a in expr.split(", "):
		eq.append(parse_expr(a).simplify())

	if message.command["-3d"]:
		plot3d(*eq, show=False).save("graph.png")
	else:
		plot(*eq, show=False).save("graph.png")
	
	await client.send_photo(message.chat.id, "graph.png", reply_to_message_id=message.id,
									caption=f"` → {eq} `", progress=prog.tick)

@HELP.add(cmd="<expr>", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("solve", flags=["-simpl"]))
@report_error(logger)
@set_offline
async def solve_cmd(client:alemiBot, message:Message):
	"""attempt to solve equation

	This command will run sympy `solve` to find the equation roots.
	Systems are accepted too!
	Add flag `-simpl` to simplify your input (won't work on systems).
	"""
	if len(message.command) < 1:
		return await edit_or_reply(message, "`[!] → ` No input")
	expr = message.command.text
	in_expr = parse_expr(expr).simplify()
	res = solve(in_expr)
	out = f"` → {str(in_expr)}`\n```" + str(res) + "```"
	await edit_or_reply(message, out)
