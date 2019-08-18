# metric-server.py
import asyncio
from contextlib import suppress
import zmq
import zmq.asyncio
from zmq.auth.asyncio import AsyncioAuthenticator

import aiohttp
from aiohttp import web
from aiohttp_sse import sse_response
from weakref import WeakSet
import json
import aiohttp_jinja2
import jinja2

from conf.settings import worker

# zmq.asyncio.install()
ctx = zmq.asyncio.Context(io_threads=100)

connections = WeakSet()



async def collector():
	sock = ctx.socket(zmq.SUB)
	# получать все сообщения ''
	sock.setsockopt_string(zmq.SUBSCRIBE, '')
	sock.bind('tcp://*:5555')
	with suppress(asyncio.CancelledError):
		while True:
			print("ждем данные")
			data = await sock.recv_json()
			print("*"*100, "\n", data)
			for q in connections:
				await q.put(data)
	sock.close()



async def feed(request):
	queue = asyncio.Queue()
	connections.add(queue)
	with suppress(asyncio.CancelledError):
		async with sse_response(request) as resp:
			while True:
				data = await queue.get()
				print("$"*100, "\n", 'sending data:', data)
				await resp.send(json.dumps(data))
		return resp



@aiohttp_jinja2.template('index.html')
async def index(request):
	return {'worker': worker, 'request': request}



@aiohttp_jinja2.template('charts.html')
async def load_server(request):
	return {"worker": worker}



async def smoothie(request):
	return web.FileResponse('static/js/smoothie.js')



async def start_collector(app):
	app['collector'] = app.loop.create_task(collector())



async def stop_collector(app):
	print('Stopping collector...')
	app['collector'].cancel()
	await app['collector']
	ctx.term()


async def go():
	app = web.Application()
	aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates/'))
	app.router.add_route('GET', '/detail/{ip}', load_server)
	app.router.add_route('GET', '/', load_server)
	app.router.add_route('GET', '/smoothie-js', smoothie)
	app.router.add_route('GET', '/detail/smoothie-js', smoothie)
	app.router.add_route('GET', '/feed', feed)
	app.on_startup.append(start_collector)
	app.on_cleanup.append(stop_collector)
	return app



if __name__ == '__main__':
	app = web.Application()
	aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates/'))
	app.router.add_route('GET', '/detail/{ip}', load_server)
	app.router.add_route('GET', '/', load_server)
	app.router.add_route('GET', '/smoothie-js', smoothie)
	app.router.add_route('GET', '/detail/smoothie-js', smoothie)
	app.router.add_route('GET', '/feed', feed)
	app.on_startup.append(start_collector)
	app.on_cleanup.append(stop_collector)
	web.run_app(app, host='127.0.0.1', port=8000)
