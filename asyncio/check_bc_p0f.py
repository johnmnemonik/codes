import asyncio
import logging
import sys
import re
import datetime

import aiohttp
import aiopg
import asyncpg

import aiosocks
from async_timeout import timeout
from tqdm import tqdm

from p0f3 import P0f, P0fException

now = datetime.datetime.now()
delta =  now - datetime.timedelta(hours=1)

update_os = """
		UPDATE proxy_proxy
		SET 
		os=$1 WHERE ip=$2 AND id=$3
	"""


logging.basicConfig(
	format="%(lineno)d '|' %(message)s",
	level=logging.INFO
)


class AsyncChecker:
	def __init__(self, db):
		self.update_os = update_os
		self.sem = asyncio.Semaphore(500)
		self._loop = asyncio.get_event_loop()
		self.dst = ('185.235.245.17', 5566)
		self.db = db
		self.p0f = P0f("new_test/scaner/sock.sock")

		self.log = logging.getLogger()
		self.pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\:\d{1,5}")
		self.iprealre = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
		self.dsn = 'postgresql://djwoms:Djwoms18deuj_234567hfd@127.0.0.1:6432/djproxy'

		self._pool = self._loop.run_until_complete(
			asyncpg.create_pool(
				dsn=self.dsn,
				max_size=5,
				min_size=2,
				max_queries=1,
				loop=self._loop))

		self._sock = set()

		self.total = 0
		self.qsock = asyncio.Queue()



	async def _read_db(self):
		async with aiopg.create_pool(self.dsn) as pool:
			async with pool.acquire() as conn:
				async with conn.cursor() as cur:
					await cur.execute("SELECT ip, port, id FROM proxy_proxy WHERE tp='socks5'")
					res = await cur.fetchall()
					return res



	async def _write_db(self, os, ip, id):
		logging.info("пишем %s", os)
		async with self._pool.acquire() as con:
			try:
				await con.execute(self.update_os, os, ip, id)
			except asyncio.CancelledError:
				logging.info("ошибка")




	async def check(self, obj):
		try:
			ip, port, id = obj
		except AttributeError:
			self.log.info(obj)
			return obj
		async with self.sem:
			try:
				socks5_addr = aiosocks.Socks5Addr(ip, int(port))
				async with timeout(10):
					reader, writer = await aiosocks.open_connection(
						proxy=socks5_addr, proxy_auth=None, dst=self.dst)
					data = await reader.read(1024)
					if data:
						try:
							ipreal = self.iprealre.findall(data.decode('latin1'))[0]
							if not ipreal:
								ipreal = ip
							await self.qsock.put(ipreal)
							
							try:
								fut = self._loop.run_in_executor(None, self.p0f.get_info, ip)
								data = await fut
								if data['os_name']:
									try:
										await self._write_db(data['os_name'].decode(), ip, id)
									except Exception as exc:
										print(exc)
							except (P0fException, AttributeError, Exception) as exc:
								pass
							writer.close()
							return
						except UnicodeDecodeError as exc:
							self.log.info(data)
							return obj
						except Exception:
							return obj
					else:
						return obj
					writer.close()
			except Exception:
				return obj


	async def _bootstrap(self, loop):
		if self.db:
			self.log.info("чекаем из биржи")
			response = await self._read_db()
			self.log.info("всего в базе: %s соксов", len(response))
		

		tasks = [self.check(obj) for obj in response]
		restore = []
		for task in asyncio.as_completed(tasks):
			try:
				await task
			except Exception as exc:
				logging.exception(exc)

		logging.info("всего %s", self.qsock.qsize())

		

	def run(self):
		loop = asyncio.get_event_loop()
		try:
			loop.run_until_complete(asyncio.wait_for(self._bootstrap(loop), timeout=60*25))
		except asyncio.TimeoutError:
			logging.info('время вышло')
		finally:
			loop.run_until_complete(self._pool.close())
			self.p0f.close()


def main(db):
	check = AsyncChecker(db)
	check.run()


if __name__ == '__main__':
	main(sys.argv[1])

