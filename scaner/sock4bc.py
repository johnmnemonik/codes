import asyncio
import aiohttp
import aiopg
import asyncpg
from asyncpg.exceptions import TooManyConnectionsError, ConnectionDoesNotExistError
import aiosocks
from async_timeout import timeout
import logging
import socket
import re
import sys
from struct import pack, unpack


#from geo_parser_bp import parser
from .geo_parser_bp_mixmand import parser_maxminddb_bp as parser
from .fields import sql4_write_bp_isp as sql

logging.getLogger('geo.socks5')
logging.INFO

query = '''
	SELECT v.typeproxy, v.tp, v.link, v.user_id, v.worker_id
	FROM vendor_vendors as v, proxy_worker as w 
	WHERE v.worker_id=w.id AND w.ip='185.235.245.14' 
	AND v.tp='socks4' AND v.typeproxy = 'bp' AND v.scan=False;
	'''

class AsyncSock4GeoBp:
	def __init__(self, typeproxy, typesocks, url, vendor_id, worker_id, auth=False, scan=False):
		self.typeproxy = typeproxy
		self.typesocks = typesocks
		self.url = url
		self.vendor_id = vendor_id
		self.worker_id = worker_id
		self.auth = auth
		self.scan = scan

		self._loop = asyncio.get_event_loop()
		self._sem = asyncio.BoundedSemaphore(1000)
		self.dsn = 'postgresql://djwoms:Djwoms18deuj_234567hfd@185.235.245.10:6432/djproxy'
		self.local = '185.235.245.4'
		self.dst = ('185.235.245.17', 5566)

		self.pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\:\d{1,5}")
		self._pool = self._loop.run_until_complete(
			asyncpg.create_pool(
				dsn=self.dsn,
				max_size=5,
				min_size=2,
				max_queries=1,
				loop=self._loop))


	async def _read_db(self):
		async with aiopg.create_pool(self.dsn) as pool:
			async with pool.acquire() as conn:
				async with conn.cursor() as cur:
					await cur.execute("SELECT ip, port FROM proxy_proxy WHERE tp='socks4'")
					res = await cur.fetchall()
					return res


	async def _write_db(self, content):
		#logging.info("пишем")
		async with self._pool.acquire() as con:
			try:
				await con.execute(sql, *content)
			except asyncio.CancelledError:
				pass


	async def sock(self, obj):
		ip , port = obj.split(":")
		anonymity, checkers, ipreal = 'no', False, ip
		async with self._sem:
			try:
				start = self._loop.time()
				socks4_addr = aiosocks.Socks4Addr(ip, int(port))
				async with timeout(20):
					reader, writer = await aiosocks.open_connection(
						proxy=socks4_addr, proxy_auth=None, dst=self.dst)
					data = await reader.read(1024)
					time_out = self._loop.time() - start
					if data:
						checkers = True

						if data.decode() != self.local:
							anonymity = 'yes'
							ipreal = data.decode()
						else:
							anonymity = 'no'
							ipreal = data.decode()
					else:
						checkers = False
						anonymity = 'no'

					fut = self._loop.run_in_executor(
						None, parser, ip, port, ipreal,
						self.worker_id, self.vendor_id,
						time_out, self.typeproxy, self.typesocks,
						anonymity, checkers, self.auth, self.scan)

					content = await fut
					await self._write_db(content)
					writer.close()

			except (ConnectionError, ConnectionResetError, ConnectionRefusedError, asyncio.TimeoutError, OSError, ConnectionResetError, aiosocks.errors.SocksError, AttributeError):
				fut = self._loop.run_in_executor(
					None, parser, ip, port, ipreal,
					self.worker_id, self.vendor_id,
					None, self.typeproxy, self.typesocks,
					anonymity, False, self.auth, self.scan)

				content = await fut
				await self._write_db(content)
		

	async def _resp_socks(self, url):
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as resp:
				data = await resp.text()
				return data


	#async def _pool(self):
	#	self.pool = await asyncpg.create_pool(self.dsn)
	#	#self.conn = await self.pool.acquire()



	def bootstrap(self):
		#loop = asyncio.new_event_loop()
		#asyncio.set_event_loop(loop)

		loop = asyncio.get_event_loop()
		data_db = loop.run_until_complete(self._read_db())
		data_db = ['{}:{}'.format(x[0], x[1]) for x in data_db]

		#loop.run_until_complete(self._pool())
		data = loop.run_until_complete(self._resp_socks(self.url))
		data = data.split()
		if not data:
			raise ValueError("страница не чего не вернула")

		data = [obj for obj in data if obj not in data_db]

		response = [url for url in data if self.pattern.findall(url)]
		res = [s.split(":")[0] for s in response]
		print(len(list(set(res))))

		tasks = [self.sock(obj) for obj in data]

		loop.run_until_complete(asyncio.gather(*tasks))
		loop.run_until_complete(self._pool.close())
		loop.close()
		print(len(data))


	def go(self):
		self.bootstrap()

def do_main():
	dsn = 'postgresql://djwoms:Djwoms18deuj_234567hfd@185.235.245.10:6432/djproxy'
	async def _read_db():
		async with aiopg.create_pool(dsn) as pool:
			async with pool.acquire() as conn:
				async with conn.cursor() as cur:
					await cur.execute(query)
					res = await cur.fetchall()
					return res
	loop = asyncio.get_event_loop()
	res = loop.run_until_complete(_read_db())
	return res


def main(obj):
	import time
	start = time.time()
	checker = AsyncSock4GeoBp(*obj)
	checker.go()
	end = time.time() - start
	logging.info("время затраченое на ГЕО скан %s мин", int(end)/60)


if __name__ == '__main__':
	res = do_main()
	for obj in res:
		main(obj)