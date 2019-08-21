import asyncio
import aiosocks
#from aiosocks.connector import ProxyConnector, ProxyClientRequest
import aiohttp
from async_timeout import timeout
import aiofiles

from datetime import datetime, timezone
import time
import json
from contextlib import suppress
from threading import Thread as thread
import re
import sys
import os
import argparse
import pickle

import zmq, zmq.asyncio

ctx = zmq.asyncio.Context(io_threads=10)


pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\:\d{1,5}")
ADDRESS = ("127.0.0.1", 5566)



def _exception_handler(loop, context):
	# если раскоментироать поваляться ошибки
    # связаные с самими соксами (не доступен/офлаин итд)
    # в основном это служит для перехвата исключений в самом loop
    # loop.default_exception_handler(context)

    exception = context.get('exception')
    if isinstance(exception, (asyncio.TimeoutError, ConnectionRefusedError, Exception)):
    	pass



class AsyncSock4:
	def __init__(self, result, timeout, number, repeat, type_sock, out):
		self.dst = ADDRESS
		self.result = result
		self.timeout = timeout
		self.sem = asyncio.Semaphore(number)
		self.lock = asyncio.Lock()
		self.repeat = repeat
		self._out = out
		self._format_ipreal = "{}:{}\t{}"
		self._format_ip_port = "{}:{}"
		self.restore = asyncio.Queue()
		#self._running = None
		self.path = '../server.sock'
		self._name = __file__
		if type_sock == 5:
			self._type = 'socks5'
			self._sock = aiosocks.Socks5Addr
			self._check = self.sock
		elif type_sock == 4:
			self._type = 'socks4'
			self._check = self.sock
			self._sock = aiosocks.Socks4Addr
		else:
			self._type = 'http'
			self._check = self.sock_http
		self._n = 0



	async def sock_http(self, obj):
		ip, port = obj
		async with self.sem:
			try:
				async with timeout(self.timeout):
					async with aiohttp.ClientSession() as session:
						async with session.get('http://{}:{}'.format(*self.dst), \
								proxy='http://{ip}:{port}'.format(ip=ip, port=port), proxy_auth=None) as resp:
							if resp.status == 200:
								data = await resp.text()
								if data:
									if self._out == "ipreal":
										async with self.lock:
											print(self._format_ipreal.format(ip, port, data.decode()), end='\n')
									else:
										async with self.lock:
											print(self._format_ip_port.format(ip, port))
							await resp.close()
			except Exception:
			    if self.repeat:
			    	await self.restore.put(obj)



	async def sock(self, obj):
		ip, port = obj
		async with self.sem:
			try:
				socks_addr = self._sock(ip, int(port))
				async with timeout(self.timeout):
					reader, writer = await aiosocks.open_connection(
						proxy=socks_addr, proxy_auth=None, dst=self.dst)
					data = await reader.read(1024)
					if data:
						if self._out == "ipreal":
							async with self.lock:
								print(self._format_ipreal.format(ip, port, data.decode()), end='\n')
						else:
							async with self.lock:
								print(self._format_ip_port.format(ip, port))
				writer.close()
			except Exception as exc:
				if self.repeat:
					await self.restore.put(obj)

	async def _resp_socks(self, url):
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as resp:
				data = await resp.text()
				return data

	
	async def monitor_unix_client(self, msg):
		reader, writer = await asyncio.open_unix_connection(self.path)
		writer.write(msg)
		writer.write_eof()
		writer.close()


	async def _bootstrap(self, loop):
		now = time.time()
		date = datetime.now().strftime('%H:%M:%S')
		msg = dict(
			scan_status="run",
			scan_type=self._type,
			scan_name=self._name,
			scan_start=date,
			scan_end="---",
			scan_start_next="---"
			)
		obj = pickle.dumps(msg)
		await self.monitor_unix_client(obj)
		if not self.restore:
			tasks = [loop.create_task(self._check(obj)) for obj in self.result]
			for task in asyncio.as_completed(tasks):
				res = await task
		else:
			tasks = [loop.create_task(self._check(obj)) for obj in self.result]
			for task in asyncio.as_completed(tasks):
				res = await task
			for _ in range(self.repeat):
				restore = []
				for res in range(self.restore.qsize()):
					restore.append(self.restore.get_nowait())
				tasks = [loop.create_task(self._check(obj)) for obj in restore]
				for task in asyncio.as_completed(tasks):
					res = await task
		msg = dict(
			scan_status="stop",
			scan_type=self._type,
			scan_name=self._name,
			scan_start=date,
			scan_end=int(time.time() - now) // 60,
			scan_start_next=5
			)
		print(msg)
		obj = pickle.dumps(msg)
		await self.monitor_unix_client(obj)


	def go(self):
		loop = asyncio.get_event_loop()
		loop.set_exception_handler(_exception_handler)
		loop.run_until_complete(self._bootstrap(loop))




def main(result, timeout, number, repeat, type_sock, out):
	checker = AsyncSock4(result, timeout, number, repeat, type_sock, out)
	checker.go()


def do_scan(name, types, path='.'):
	result = []
	with open(name, "rt") as f:
		if types == 'masscan':
			for obj in f:
				try:
					_, _, port, ip, _ = obj.split()
					result.append((ip, port))
				except:
					pass
		elif types == 'list':
			for obj in f:
				try:
					ip, port = pattern.findall(obj)[0].split(":")
					result.append((ip, port))
				except Exception as exc:
					print(exc)
	if not result:
		raise ValueError("пустой результат")
	return result


def splitter(name, number):
	os.system('split -l {number} {name}'.format(number=number, name=name))
	res = [x for x in os.listdir() if not x.endswith(('.txt', '.py', '__pycache__'))]
	return res



if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-i', '--input',   type=str, help="имя файла и путь")
	parser.add_argument('-f', '--format',  type=str, help='формат листов: masscan (masscan) или ip:port (list)')
	parser.add_argument('-s', '--split',   type=int, help='разбивка листов на множество (1000000)', default=0)
	parser.add_argument('-sock', '--type', help='тив скарирования socks4 или socks5', type=int, default=0)
	parser.add_argument('-t', '--timeout', type=int, help='тай-аут скана')
	parser.add_argument('-n', '--number',  type=int, help='Количество потоков', default=1000)
	parser.add_argument('-r', '--repeat',  type=int, help='', default=0)
	parser.add_argument('-o', '--out',     type=str, help='формат вывода, ip:port ("ip:port") или ip:port tab ipreal \
		(ipreal)',default='ip:port')


	args = parser.parse_args()
	if args.split:
		data = splitter(args.input, args.split)
		for name in data:
			result = do_scan(name, args.format)
			main(result, args.timeout, args.number, args.repeat, args.type, args.out)
	else:
		result = do_scan(args.input, args.format)
		main(result, args.timeout, args.number, args.repeat, args.type, args.out)
	print("END")
	ctx.term()
