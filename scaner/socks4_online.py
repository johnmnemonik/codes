import asyncio
import aiohttp
import aiopg
import asyncpg
from asyncpg.exceptions import TooManyConnectionsError, ConnectionDoesNotExistError
import aiosocks
from async_timeout import timeout
import logging
import socket
import sys
from struct import pack, unpack
import datetime

from fields import sql4_online_true as sql_true
from fields import sql4_online_false as sql_false


from settings import IP, DSN, SERVER_CHECK, PORT_CHECK


logging.basicConfig(
	filename='log/sock4.log',
	format="%(levelname)-10s строка %(lineno)d '|' %(asctime)s %(message)s",
	level=logging.INFO
)

	

class AsyncSock4Online:
	def __init__(self, SQL, loop=None):
		self._sem  = asyncio.BoundedSemaphore(1000)
		self.server_check = SERVER_CHECK
		self.port_check = PORT_CHECK
		self.dst = (self.server_check, self.port_check)
		self._loop = loop or asyncio.get_event_loop()
		self.sql = SQL
		self.sql_true = sql_true
		self.sql_false = sql_false
		self.local_ip = IP
		self.dsn = DSN
		self._pool = self._loop.run_until_complete(
			asyncpg.create_pool(
				dsn=self.dsn,
				max_size=10,
				min_size=5,
				max_queries=1,
				loop=self._loop))
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
			except ConnectionDoesNotExistError:
				logging.info("ошибка в бд в execute")
			except TooManyConnectionsError as exc:
				logging.exception(exc)
			except Exception as exc:
				logging.exception(exc)


	async def _write_db(self, sql, checker, anonymity, ip, port, id):
		logging.info("пишем %s", (checker, ip, port))
		con = await self._pool.acquire()
		try:
			await con.execute(sql, checker, anonymity, ip, port, id)
		except TooManyConnectionsError as exc:
			logging.exception(exc)
		except ConnectionDoesNotExistError as exc:
			logging.exception(exc)
		finally:
			await self._pool.release(con)

			

	async def sock(self, obj):
		ip, port, id = obj
		anonymity = 'no'
		async with self._sem:
			try:
				socks4_addr = aiosocks.Socks4Addr(ip, int(port))
				async with timeout(15):
					reader, writer = await aiosocks.open_connection(
						proxy=socks4_addr, proxy_auth=None, dst=self.dst)
					data = await reader.read(1024)
					if data.decode() != self.local_ip:
						anonymity = 'yes'
						return (True, anonymity, ip, port, id)
					elif data:
						return (True, anonymity, ip, port, id)
					else:
						return (False, anonymity, ip, port, id)
					writer.close()

			except Exception:
			    return (False, anonymity, ip, port, id)
		

	async def _resp_socks(self, url):
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as resp:
				data = await resp.text()
				return data



	async def _bootstrap(self, loop):
		data = await self._read_db()
	
		if not data:
			logging.info("страница не чего не вернула")
			return

		logging.info("всего на скан %s", len(data))

		restore = []

		logging.info("запуск")
		tasks = [loop.create_task(self.sock(obj)) for obj in data]
		for task in asyncio.as_completed(tasks):
			res = await task
			if res[0]:
				await self._queue_true.put(res)
			else:
				restore.append((res[2], res[3], res[4]))
			
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
