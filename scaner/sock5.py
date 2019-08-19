import asyncio
import aiohttp
import aiopg
import asyncpg
from asyncpg.exceptions import TooManyConnectionsError, ConnectionDoesNotExistError
from async_timeout import timeout
import logging
import socket
import sys
import re
from struct import pack, unpack
import time
import datetime
from multiprocessing import Process
import threading
import resource

import pytz
#from geo_parser import parser
from geo_parser_mixmand import parser_maxminddb as parser
from fields import sql5_write_isp as sql

from socks5_online import AsyncSock5Online

from settings import IP, DSN, SERVER_CHECK, PORT_CHECK



logging.getLogger('sock5')
logging.DEBUG


class Job:
	run = False


def sql_start_():
	#now = datetime.datetime.utcnow()
	#now = now.replace(tzinfo=pytz.utc)
	#delta = now - datetime.timedelta(hours=2)
	
	now = datetime.datetime.now(pytz.utc)
	delta = now - datetime.timedelta(hours=2)

	ONLINE_SQL = """
		SELECT p.ip, p.port, p.id FROM proxy_proxy as p, proxy_worker as w 
		WHERE p.worker_id=w.id AND w.ip='%s' AND p.tp='socks5' 
		AND p.scan=False AND p.typeproxy='dp'
		AND p.update > TIMESTAMP '%s';""" % (IP, delta)
	return ONLINE_SQL
	

QUERY = '''
	SELECT v.typeproxy, v.tp, v.link, v.user_id, v.worker_id
	FROM vendor_vendors as v, proxy_worker as w 
	WHERE v.worker_id=w.id 
	AND w.ip='%s' AND v.tp='socks5' AND v.scan=False;
	''' % IP


ONLINE_SQL = sql_start_()


def timer():
	logging.info("стработал таймер")
	global ONLINE_SQL
	
	now = datetime.datetime.now(pytz.utc)
	delta = now - datetime.timedelta(hours=1)

	delta_no_scan = now - datetime.timedelta(hours=2)
	ONLINE_SQL = """
		SELECT p.ip, p.port, p.id FROM proxy_proxy as p, proxy_worker as w 
		WHERE p.worker_id=w.id AND w.ip='%s' AND p.tp='socks5' 
		AND p.scan=False AND p.typeproxy='dp'
		AND p.update < TIMESTAMP '%s' AND p.update <> TIMESTAMP '%s';
		""" % (IP, delta, delta_no_scan)


def Tm():
	num = 60.0 * 60.0
	#time.sleep(0.2)
	while True:
		if Job.run:
			time.sleep(30)
			continue
		
		Job.run = True
		timer()
		time.sleep(num)



class AsyncSock5Geo:
	def __init__(self, typeproxy, typesocks, url, vendor_id, worker_id, auth=False, scan=False):
		
		self.typeproxy = typeproxy
		self.typesocks = typesocks
		self.url = url
		self.vendor_id = vendor_id
		self.worker_id = worker_id
		self.auth = auth
		self.scan = scan
		self.local_ip = IP
		self._loop = asyncio.get_event_loop()
		self._sem = asyncio.Semaphore(1000)
		self.dsn = DSN
		self.port_check = PORT_CHECK
		self.server_check = SERVER_CHECK
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
					await cur.execute("SELECT ip, port FROM proxy_proxy WHERE tp='socks5'")
					res = await cur.fetchall()
					return res



	async def _write_db(self, content):
		async with self._pool.acquire() as con:
			try:
				await con.execute(sql, *content)
			except asyncio.CancelledError as exc:
				pass
			except asyncpg.exceptions.UniqueViolationError as exc:
				logging.exception(exc)
			except Exception as exc:
				logging.exception(exc)



	async def sock(self, obj):
		ip , port = obj.split(":")
		async with self._sem:
			try:
				async with timeout(15):
					start = self._loop.time()
					reader, writer = await asyncio.open_connection(ip, int(port))
					writer.write(b'\x05\x01\x00')
					data = await reader.read(1024)
					time_out = self._loop.time() - start
					if data.startswith(b'\x05\x00'):
						await self.check(reader, writer, time_out, ip, port)
					else:
						anonymity, checkers, ipreal = 'no', False, ip
						fut = self._loop.run_in_executor(
							None, parser, ip, port, ipreal,
							self.worker_id, self.vendor_id,
							time_out, self.typeproxy, self.typesocks,
							anonymity, checkers,self.auth, self.scan)

						content = await fut
						await self._write_db(content)
						writer.close()
			except (ConnectionError, ConnectionResetError, ConnectionRefusedError, \
					asyncio.TimeoutError, OSError, ConnectionResetError):
				anonymity, checkers, ipreal = 'no', False, ip
				fut = self._loop.run_in_executor(
					None, parser, ip, port, ipreal,
					self.worker_id, self.vendor_id,
					None, self.typeproxy, self.typesocks,
					anonymity, False, self.auth, self.scan)

				content = await fut
				await self._write_db(content)


	async def check(self, reader, writer, time_out, ip, port):
		data = b"\x05\x01\x00\x01" + socket.inet_aton(self.server_check) + pack("!H", self.port_check)
		anonymity, checkers, ipreal = 'no', False, ip
		try:
			writer.write(data)
			data = await reader.read(1024)
			if data:
				writer.write(b'ok')
				data = await reader.read(1024)

				if data:
					checkers = True

				if data.decode() != self.local_ip:
					anonymity = 'yes'
					ipreal = data.decode()
				else:
					anonymity = 'no'
					ipreal = ip

			fut = self._loop.run_in_executor(
				None, parser, ip, port, ipreal,
				self.worker_id, self.vendor_id,
				time_out, self.typeproxy, self.typesocks,
				anonymity, checkers,self.auth, self.scan)

			content = await fut
			await self._write_db(content)
			writer.close()
		except Exception:
			anonymity, checkers, ipreal = 'no', False, ip
			fut = self._loop.run_in_executor(
				None, parser, ip, port, ipreal,
				self.worker_id, self.vendor_id,
				time_out, self.typeproxy, self.typesocks,
				anonymity, checkers, self.auth, self.scan)

			content = await fut
			await self._write_db(content)
			writer.close()


	async def _resp_socks(self, url):
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as resp:
				data = await resp.text()
				return data



	async def _bootstrap(self, loop):
		data_db = await self._read_db()
		data_db = ['{}:{}'.format(x[0], x[1]) for x in data_db]

		data = await self._resp_socks(self.url)
		data = data.split()
		if not data:
			logging.info("страница не чего не вернула")
			return

		data = [obj for obj in data if obj not in data_db]

		response = [url for url in data if self.pattern.findall(url)]
		logging.info("%s", len(response))
		res = [s.split(":")[0] for s in response]
		logging.info("всего %s", len(list(set(res))))
		logging.info("%s", len(response))

		tasks = [self.sock(obj) for obj in response]

		for task in asyncio.as_completed(tasks):
			try:
				res = await task
			except Exception as exc:
				logging.exception(exc)


	def run(self, loop):
		try:
			loop.run_until_complete(asyncio.wait_for(self._bootstrap(loop), timeout=60*15))
		except asyncio.TimeoutError:
			logging.info('время вышло')
		finally:
			loop.run_until_complete(self._pool.close())
			#loop.close()


def do_start():
	async def _read_db():
		async with aiopg.create_pool(DSN) as pool:
			async with pool.acquire() as conn:
				async with conn.cursor() as cur:
					await cur.execute(QUERY)
					res = await cur.fetchall()
					return res
	loop = asyncio.get_event_loop()
	res = loop.run_until_complete(_read_db())
	return res


def _start_sock5_geo(obj):
	logging.info("run")
	loop = asyncio.get_event_loop()
	start = time.time()

	checker = AsyncSock5Geo(*obj)
	checker.run(loop)
	
	end = time.time() - start
	logging.info("время затраченое на ГЕО скан %s мин", int(end)//60)


def _start_sock5_online():
	start = time.time()
	checker = AsyncSock5Online(ONLINE_SQL)
	checker.go()
	Job.run = False
	end = time.time() - start
	logging.info("время затраченое на ONLINE скан %s мин", int(end)//60)



if __name__ == '__main__':
	limit_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
	limit_nproc = resource.getrlimit(resource.RLIMIT_NPROC)
	
	logging.info("лимит на файлы %s", limit_nofile)
	logging.info("лимит на процессы %s", limit_nproc)

	try:
		resource.setrlimit(resource.RLIMIT_NOFILE, (100000, 100000))
	except:
		pass

	th = threading.Thread(target=Tm)
	th.start()

	while True:
		try:
			if Job.run:
				Job.run = False
				res = do_start()
				for obj in res:
					try:
						_start_sock5_geo(obj)
					except Exception:
						pass

				_start_sock5_online()
				ONLINE_SQL = sql_start_()
			else:
				Job.run = True
				res = do_start()
				for obj in res:
					try:
						_start_sock5_geo(obj)
					except Exception:
						pass

				_start_sock5_online()

			logging.info("СПИМ 5 МИНУТ")
			time.sleep(60*5)
		except Exception  as exc:
			logging.info("ошибка в цмкле ")
			logging.exception(exc)	
