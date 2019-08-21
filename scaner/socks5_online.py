import asyncio
import aiohttp
import aiopg
import asyncpg
import uvloop
from asyncpg.exceptions import TooManyConnectionsError, ConnectionDoesNotExistError
from async_timeout import timeout
import aiosocks
import logging
import socket
import sys
import json
from struct import pack, unpack
from multiprocessing import Process
import datetime

from fields import sql5_online_true as sql_true
from fields import sql5_online_false as sql_false

from settings import IP, DSN, SERVER_CHECK, PORT_CHECK


logging.basicConfig(
	filename='log/sock5.log',
	format="%(levelname)-10s строка %(lineno)d '|' %(asctime)s %(message)s",
	level=logging.INFO
)




class AsyncSock5Online:
	def __init__(self, SQL, loop=None):
		self._loop = loop or asyncio.get_event_loop()
		self._sem = asyncio.Semaphore(1000)
		self.local_ip = IP
		self.server_check = SERVER_CHECK
		self.port_check = PORT_CHECK
		self.sql = SQL
		self.sql_true = sql_true
		self.sql_false = sql_false
		self.dsn = DSN
		self._pool = self._loop.run_until_complete(
			asyncpg.create_pool(
				dsn=self.dsn,
				max_size=10,
				min_size=5,
				max_queries=1,
				loop=self._loop))
		self._num = 0
		self._queue_true = asyncio.Queue()
		self._queue_false = asyncio.Queue()


	async def _read_db(self):
		async with aiopg.create_pool(self.dsn) as pool:
			async with pool.acquire() as conn:
				async with conn.cursor() as cur:
					await cur.execute(self.sql)
					res = await cur.fetchall()
					return res


	async def _write_db_many(self, sql, objlist):
		async with self._pool.acquire() as con:
			try:
				await con.executemany(sql, objlist)
			except ConnectionDoesNotExistError as exc:
				logging.exception(exc)
			except TooManyConnectionsError as exc:
				logging.exception(exc)
			except Exception as exc:
				logging.exception(exc)


	async def _write_db(self, sql, checker, ip, port, id):
		async with self._pool.acquire() as con:
			try:
				await con.execute(sql, checker, ip, str(port), id)
			except ConnectionDoesNotExistError:
				logging.info("ошибка в бд в execute")
			except TooManyConnectionsError as exc:
				logging.exception(exc)
			except Exception as exc:
				logging.exception(exc)


	async def sock_raw(self, obj):
		ip, port, id = obj
		async with self._sem:
			try:
				async with timeout(10):
					reader, writer = await asyncio.open_connection(ip, int(port))
					writer.write(b'\x05\x01\x00')
					data = await reader.read(1024)
					if data.startswith(b'\x05\x00'):
						return await self.check(reader, writer, ip, port, id)
					else:
						writer.close()
						return (False, ip, port, id)
			except Exception:
			    return (False, ip, port, id)

	
	async def sock(self, obj):
		ip, port, id = obj
		async with self._sem:
			try:
				socks5_addr = aiosocks.Socks5Addr(ip, int(port))
				async with timeout(10):
					reader, writer = await aiosocks.open_connection(
						proxy=socks5_addr, proxy_auth=None, dst=(self.server_check, self.port_check))
					data = await reader.read(1024)
					if data or data == b'':
						writer.close()
						return (True, ip, port, id)
					writer.close()
					return (True, ip, port, id)
			except Exception as exc:
				return (False, ip, port, id)

		

	async def check(self, reader, writer, ip, port, id):
		try:
			data = b"\x05\x01\x00\x01" + socket.inet_aton(self.server_check) + pack("!H", self.port_check)
			writer.write(data)
			data = await reader.read(1024)
			if data:
				writer.write(b'ok')
				data = await reader.read(1024)
				if data or data == b'':
					writer.close()
					return (True, ip, port, id)
				else:
					writer.close()
					return (False, ip, port, id)
			else:
				writer.close()
				return (False, ip, port, id)
			
		except (asyncio.TimeoutError, Exception):
			return (False, ip, port, id)



	async def _bootstrap(self, loop):
		data = await self._read_db()
		logging.info("всего %s", len(data))
		if not data:
			raise ValueError("страница не чего не вернула")

		restore = []
		logging.info("запуск")
		tasks = [loop.create_task(self.sock(obj)) for obj in data]
		for task in asyncio.as_completed(tasks):
			res = await task
			#continue
			
			if res[0]:
				await self._queue_true.put(res)
			else:
				restore.append((res[1], res[2], res[3]))
			
		logging.info("ПОВТОР")
		logging.info("на повтор отправлено %s соксов", len(restore))

		tasks = [loop.create_task(self.sock(obj)) for obj in restore]
		for task in asyncio.as_completed(tasks):
			res = await task
		
			if res[0]:
				await self._queue_true.put(res)
			else:
				await self._queue_false.put(res)
		logging.info("запись")
		writer_true = []
		writer_false = []
		for i in range(self._queue_true.qsize()):
			writer_true.append(self._queue_true.get_nowait())
		await self._write_db_many(self.sql_true, writer_true)

		for i in range(self._queue_false.qsize()):
			writer_false.append(self._queue_false.get_nowait())
		await self._write_db_many(self.sql_false, writer_false)




	def go(self):
		loop = asyncio.get_event_loop()
		try:
			loop.run_until_complete(asyncio.wait_for(self._bootstrap(loop), timeout=60*15))
		except asyncio.TimeoutError:
			logging.info('время вышло')
		finally:
			loop.run_until_complete(self._pool.close())
			#loop.close()