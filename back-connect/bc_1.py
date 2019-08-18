import argparse
import asyncio
import logging
import sys

from threading import Thread
import time
import re
import random
from functools import partial
from struct import unpack, pack
import socket
from socket import TCP_NODELAY
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, RetryError
import aiosocks
from async_timeout import timeout
import asyncpg
from asyncpg.exceptions import TooManyConnectionsError, ConnectionDoesNotExistError
import aiohttp


from daemonize import daemonize

logging.basicConfig(
	filename='bc_1.log',
	format="%(asctime)s %(lineno)d '|' %(message)s",
	level=logging.DEBUG,
)


log = logging.getLogger(__name__)


SQL = "INSERT INTO bc_1 (loc_ip, loc_port, ip, port, ipreal, online) \
	   VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (ipreal) DO UPDATE \
	   SET ip=$7, port=$8, online=$9"



SQL_AUTH = "INSERT INTO bc_1 (loc_ip, loc_port, ip, port, ipreal, online, login, password) \
	   		VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (ipreal) DO UPDATE \
	   		SET ip=$9, port=$10, online=$11"


SQL_FIND 	  	   = "SELECT ip, port, ipreal FROM bc_1 WHERE ipreal=$1 AND online=$2"
CHANGE_STATUS 	   = "UPDATE bc_1 SET online=$1 WHERE ip=$2 AND port=$3"
CHANGE_STATUS_AUTH = "UPDATE bc_1 SET online=$1 WHERE ip=$2 AND port=$3 AND login=$4 AND password=$5"
DEBUG = False

msg = "postgresql://{user}:{password}@{host}:{port}/{database}"
DSN = msg.format(user='john', password='loginn',host='localhost', port=5432, database='proj')

sem = asyncio.BoundedSemaphore(100)
db_sem = asyncio.BoundedSemaphore(50)

pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\:\d{1,5}")
iprealre = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

SERVER = "185.235.245.14"


def _exception_handler(loop, context):
	# если раскоментироать поваляться ошибки
	# loop.default_exception_handler(context)
	exception = context.get('exception')

	if isinstance(exception, Exception):
		log.exception(context)
		#log.info("перехватил")

# циклы
loop_bc = asyncio.new_event_loop()
asyncio.set_event_loop(loop_bc)
loop_bc.set_exception_handler(_exception_handler)

loop_db = asyncio.new_event_loop()
loop_db.set_exception_handler(_exception_handler)

asyncio.set_event_loop(loop_db)
lock = asyncio.Lock()


QU_port_and_auth = asyncio.Queue()
QU_server 		 = asyncio.Queue()
RANDOM_PORT 	 = asyncio.Queue()

if DEBUG:
	loop_bc.set_debug(True)
	loop_bc.slow_callback_duration = 0.003
	loop_db.set_debug(True)
	loop_db.slow_callback_duration = 0.003



class AsyncThreadBc(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.name = "bc"
		self.loop = loop_bc
		#self.loop_db = loop_db
		self.log = logging.getLogger(__name__)
		self.status = True
		self.SQL 			= "SELECT loc_ip, loc_port, ip, port, ipreal FROM bc_1 WHERE online=%s" % True
		self.SQL_FIND 		= "SELECT ip, port, ipreal FROM bc_1 WHERE ipreal=$1 AND online=$2"
		self.CHANGE_STATUS 	= "UPDATE bc_1 SET online=$1 WHERE ip=$2 AND port=$3 AND ipreal=$4"
		self.server = SERVER
		self.qu = QU_port_and_auth
		self._pool = self.loop.run_until_complete(
			asyncpg.create_pool(
				dsn=DSN,
				max_size=5,
				min_size=2,
				max_queries=1,
				loop=self.loop))
		self._dic = {}
		self.random_port = RANDOM_PORT


	async def go(self):
		self.log.info("новый запуск сокс")
		loc_port, ip, port, ipreal = await self.qu.get()
		bc = partial(self.handler, ip=ip, port=port, ipreal=ipreal)
		try:
			back = await asyncio.start_server(bc, self.server, loc_port)
			# после запуска передаем bc (кастомный partial "bc") обратно
			self._dic[ipreal] = [bc,back,loc_port]
		except (OSError, Exception) as exc:
			self.log.info(exc)
			self.log.info("не удалось запустить сервер на порт: %s", loc_port)
		self.qu.task_done()


	async def go_restart(self, loc_port, ip, port, ipreal):
		self.log.info("новый запуск сокс")
		bc = partial(self.handler, ip=ip, port=port, ipreal=ipreal)
		try:
			back = await asyncio.start_server(bc, self.server, loc_port)
			# после запуска передаем bc (кастомный partial "bc") обратно
			self._dic[ipreal] = [bc, back, loc_port]
		except (OSError, Exception) as exc:
			self.log.info(exc)
			self.log.info("не удалось запустить сервер на порт: %s", loc_port)
		self.qu.task_done()



	async def _restart_back(self):
		num = self.qu.qsize()
		self.log.info("востонавливаем бек всего (%s)", num)
		for _ in range(self.qu.qsize()):
			loc_port, ip, port, ipreal = await self.qu.get()
			bc = partial(self.handler, ip=ip, port=port, ipreal=ipreal)
			try:
				back = await asyncio.start_server(bc, self.server, loc_port)
				# после запуска передаем bc (кастомный partial "bc") обратно
				self._dic[ipreal] = [bc, back, loc_port]
			except (OSError, Exception) as exc:
				self.log.exception(exc)
				self.log.info("не удалось запустить сервер на порт: %s", loc_port)
		self.log.info("запустили %s", num)



	async def forwarder(self, reader, writer):
		try:
			while True:
				try:
					data = await reader.read(1024)
					if not data:
						break
				except ConnectionResetError:
					break
				writer.write(data)
				await writer.drain()
		except Exception as exc:
			pass
		finally:
			writer.close()



	async def sock_status(self, status, ip, port, ipreal):
		async with asyncpg.create_pool(DSN) as conn:
			try:
				await conn.execute(self.CHANGE_STATUS, status, ip, port, ipreal)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)



	async def sock_find(self, ipreal):
		async with self._pool.acquire() as conn:
			try:
				res = await conn.fetch(
					"SELECT ip, port, ipreal FROM bc_1 WHERE ipreal=$1 AND online=$2", ipreal, True)
				if not res:
					self.log.info("НЕТ ТАКОГО СОКСА, ИЛИ СОКС ОФЛАЙН ---> %s", ipreal)
					self.log.info("поиск по маске")
					res = await conn.fetch("SELECT ip, port, ipreal FROM bc_1 WHERE ipreal LIKE '{}.%'".format(
						".".join(ipreal.split('.')[:-1])))
					if len(res) > 0:
						return [res[0]['ip'], res[0]['port'], res[0]['ipreal']]
					else:
						self.log.info("поиск по маске вернул %s", len(res))
					return (None, None, None)
				else:
					self.log.info("%s ---> %s", ipreal, res[0]['ipreal'])
					return (res[0]['ip'], res[0]['port'], res[0]['ipreal'])
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			except Exception as exc:
				self.log.exception(exc)



	@retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type())
	async def check(self, ip, port, ipreal):
		socks5_addr = aiosocks.Socks5Addr(ip, port)
		try:
			reader, writer = await aiosocks.open_connection(
				proxy=socks5_addr, proxy_auth=None, dst=('185.235.245.17', 9999))
		except (aiosocks.errors.SocksError, ConnectionRefusedError):
			return "no"
		writer.write(b"GET / HTTP/1.1\r\n\r\n")
		data = await reader.read(1024)
		writer.close()
		if data:
			try:
				real = iprealre.findall(data.decode('latin1'))[0]
				if real:
					if real == ipreal:
						return real
					else:
						return "no"
				else:
					return "no"
			except Exception as exc:
				return "no"
		else:
			return "no"


	def stop_server(self, ipreal):
		try:
			self.log.info("остонавливаем сервер")
			self._dic[ipreal][1].close()
			loc_port = self._dic[ipreal][2]
			del self._dic[ipreal]
			self.random_port.put_nowait(loc_port)
			self.log.info("вернули порт %s обратно в пул", loc_port)
		except Exception as exc:
			self.log.exception(exc)



	async def report(self, ipreal, ip, port):
		try:
			self._dic[ipreal][0].keywords['ip'] = ip
			self._dic[ipreal][0].keywords['port'] = port
			self.log.info("сменили порт")
		except Exception as exc:
			self.log.exception(exc)


	async def handler(self, reader, writer, ip=None, port=None, ipreal=None):
		try:
			real = await self.check(ip, port, ipreal)
			if real == "no" or real == None:
				ip_new, port_new, real = await self.sock_find(ipreal)
				if ip_new != ip or port_new != port:
					if ip_new is None or port_new is None:
						writer.close()
						return
					self.log.info("сменили %s:%s (%s) на %s:%s (%s)", ip, port, ipreal, ip_new, port_new, real)
					await self.report(ipreal, ip_new, port_new)
					self.log.info("ARGS -> %s", self._dic[ipreal][0].keywords)
			elif real != ipreal:
				self.log.info("ip не совподают %s <> %s", ipreal, real)
				writer.close()
				return
			else:
				pass
		except RetryError:
			writer.close()
			return
		while True:
			try:
				dstreader, dstwriter = await asyncio.open_connection(ip, port)
			except Exception:
				writer.close()
				return
			tasks = [
				asyncio.ensure_future(self.forwarder(reader, dstwriter)),
				asyncio.ensure_future(self.forwarder(dstreader, writer)),
				]
			await asyncio.wait(tasks)
			break


	async def read_db_do_start(self):
		# читаем готовые связки из базы, для запуска бека
		async with self._pool.acquire() as conn:
			try:
				res = await conn.fetch(self.SQL)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			resp = [(i['loc_ip'],i['loc_port'],i['ip'],i['port'],i['ipreal']) \
				for i in res]
			return resp


	def run(self):
		self.log.info("run")
		self.log.info("проснулись и запускаемся")
		try:
			self,log.info("запуск серверов")
			self.loop.run_forever()
		except KeyboardInterrupt:
			pass
		finally:
			pass




class AsyncThreadDB(Thread):
	def __init__(self, th, url, type_list, list_port):
		Thread.__init__(self)
		self.loop = loop_db
		self.loop_back = loop_bc
		self.log = logging.getLogger(__name__)
		self.th = th
		self.name = "db"
		self.url = url
		self.dst = ('185.235.245.17', 9999)
		self.server = SERVER
		self.dsn = DSN
		self.sem = asyncio.BoundedSemaphore(100)
		self.lock = asyncio.Lock()
		self.sql = SQL
		self.sql_auth = SQL_AUTH
		self._pool = self.loop.run_until_complete(
			asyncpg.create_pool(
				dsn=self.dsn,
				max_size=5,
				min_size=2,
				max_queries=1,
				loop=self.loop))
		self.qu = QU_port_and_auth
		self._dic = []
		self.random_port = RANDOM_PORT
		self.ipreal_list = []
		self.ipreal_list_change = []
		self._type_list = type_list
		self.list_port = list_port



	async def check_auth(self, ip, port):
		# чекер с записью в базу
		async with self.sem:
			try:
				socks5_addr = aiosocks.Socks5Addr(ip, port)
				async with timeout(10):
					reader, writer = await aiosocks.open_connection(
						proxy=socks5_addr,  proxy_auth=None, dst=self.dst)
					writer.write(b"GET / HTTP/1.1\r\n\r\n")
					data = await reader.read(1024)
					try:
						ipreal = iprealre.findall(data.decode('latin1'))[0]
						await self._write_db_auth(ip, port, ipreal, True)
						writer.close()
					except Exception as exc:
						writer.close()
			except asyncio.TimeoutError:
				await self.change_status(False, ip, port)
			except aiosocks.errors.SocksConnectionError:
				await self.change_status(False, ip, port)
			except aiosocks.errors.SocksError:
				await self.change_status(False, ip, port)
			except ConnectionRefusedError:
				await self.change_status(False, ip, port)
			except Exception:
				await self.change_status(False, ip, port)


	@retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type())
	async def check_db(self, ip, port, ipreal):
		# чекер соксов из базы
		async with self.sem:
			try:
				socks5_addr = aiosocks.Socks5Addr(ip, port)
				async with timeout(10):
					reader, writer = await aiosocks.open_connection(
						proxy=socks5_addr,  proxy_auth=None, dst=self.dst)
					writer.write(b"GET / HTTP/1.1\r\n\r\n")
					data = await reader.read(1024)
					try:
						real = iprealre.findall(data.decode('latin1'))[0]
						if ipreal == real:
							await self.change_status_db(True, ip, port, ipreal)
						elif ".".join(real.split(".")[:-1]) == ".".join(ipreal.split(".")[:-1]):
							self.log.info("смена по маске %s на %s", ipreal, real)
							await self.change_status_db(True, ip, port, ipreal)
						else:
							self.log.info("ПРИ СКАНЕ БАЗЫ, сокс сменил ip с %s на %s", ipreal, real)
							await self.change_status_db(False, ip, port, ipreal)
						writer.close()
					except Exception as exc:
						writer.close()
			except asyncio.TimeoutError:
				await self.change_status_db(False, ip, port, ipreal)
			except aiosocks.errors.SocksConnectionError:
				await self.change_status_db(False, ip, port, ipreal)
			except aiosocks.errors.SocksError:
				await self.change_status_db(False, ip, port, ipreal)
			except ConnectionRefusedError:
				await self.change_status_db(False, ip, port, ipreal)
			except Exception:
				await self.change_status_db(False, ip, port, ipreal)


	
	async def wait_check(self, structs):
		self.log.info("НАЧАЛО ПРОВЕРКИ БАЗЫ")
		tasks = [self.loop.create_task(self.check_db(*obj)) for obj in structs]
		for task in asyncio.as_completed(tasks):
			try:
				await task
			except (asyncio.CancelledError, RetryError) as exc:
				self.log.exception(exc)
		self.log.info("ПРОВЕРКА БАЗЫ ЗАКОНЧЕНА")



	async def _del_db_auth(self, ip, port, ipreal):
		async with self._pool.acquire() as conn:
			try:
				await conn.execute(
					"DELETE  FROM bc_1 WHERE ip=$1 AND port=$2 AND ipreal=$3", ip, port, ipreal)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			except asyncpg.exceptions.UniqueViolationError as exc:
				self.log.exception(exc)
			except asyncio.CancelledError:
				log.info("CancelledError")
			except Exception as exc:
				self.log.exception(exc)



	async def check_auth_do_run_server(self, ip, port, ipreal):
		# чекер с записью в базу
		async with sem:
			try:
				socks5_addr = aiosocks.Socks5Addr(ip, port)
				async with timeout(10):
					reader, writer = await aiosocks.open_connection(
						proxy=socks5_addr,  proxy_auth=None, dst=self.dst)
					writer.write(b"GET / HTTP/1.1\r\n\r\n")
					data = await reader.read(1024)
					try:
						real = iprealre.findall(data.decode('latin1'))[0]
						if ipreal != real:
							self.log.info("сокс %s сменился на %s ", ipreal, real)
							self.log.info("удаляем")
							await self._del_db_auth(ip, port, ipreal)
						writer.close()
					except Exception as exc:
						writer.close()
			except asyncio.TimeoutError:
				await self._del_db_auth(ip, port, ipreal)
			except aiosocks.errors.SocksConnectionError:
				await self._del_db_auth(ip, port, ipreal)
			except aiosocks.errors.SocksError:
				await self._del_db_auth(ip, port, ipreal)
			except ConnectionRefusedError:
				await self._del_db_auth(ip, port, ipreal)
			except Exception as exc:
				await self._del_db_auth(ip, port, ipreal)



	async def change_status(self, status, ip, port):
		# меняем состоятия сокса на не активен
		# убираем сокс из листа (вывода)  
		async with self._pool.acquire() as con:
			try:
				await con.execute("UPDATE bc_1 SET online=$1 WHERE ip=$2 AND port=$3", status, ip, port)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)



	async def change_status_db(self, status, ip, port, ipreal):
		# меняем состоятия сокса на не активен
		async with self._pool.acquire() as con:
			try:
				await con.execute(
					"UPDATE bc_1 SET online=$1 WHERE ip=$2 AND port=$3 AND ipreal=$4", status, ip, port, ipreal)
				if not status:
					self.log.info("остонавливаем серве на %s:%s ---> %s", ip, port, ipreal)
					self.loop_back.call_soon_threadsafe(self.th.stop_server, ipreal)
					self.ipreal_list.remove('.'.join(ipreal.split('.')[:-1]))

			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			except asyncpg.exceptions.UndefinedFunctionError:
				self.log.info("ощибка формата записи %s: %s: %s", ip, port, ipreal)


	async def _write_db_auth(self, ip, port, ipreal, status):
		async with self._pool.acquire() as con:
			try:
				_ = ".".join(ipreal.split('.')[:-1])
				if _ not in self.ipreal_list:
					loc_port = await self.random_port.get()
					await con.execute(self.sql,
						self.server, loc_port, ip, port, ipreal, status, ip, port, status)
					async with self.lock:
						await self.qu.put((loc_port, ip, port, ipreal))
						self.ipreal_list.append(_)
						asyncio.run_coroutine_threadsafe(self.th.go(), self.loop_back)
						self.log.info("новый запуск:%s размер пула ----> %s", loc_port, self.random_port.qsize())
						await self.qu.join()
				else:
					try:
						await con.execute(
							"UPDATE bc_1 SET ip=$1, port=$2, online=$3 WHERE ipreal=$4", ip, port, status, ipreal)
					except Exception as exc:
						self.log.info("ошибка при обновление %s:%s --> %s", ip, port, ipreal)
						self.log.exception(exc)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			except asyncpg.exceptions.UniqueViolationError as exc:
				self.log.exception(exc)
			except asyncio.CancelledError:
				pass


	async def _read(self):
		# загружаем лист
		async with aiohttp.ClientSession() as session:
			async with session.get(self.url) as resp:
				data = await resp.text()
				return data.split()


	async def delete_socks(self):
		# при запуске чистить старые ip
		# которые офлайн
		async with self._pool.acquire() as con:
			try:
				res = await con.fetch("DELETE FROM bc_1 WHERE online=$1", False)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)

			loc_resp = [i['loc_port'] for i in res]
			return loc_resp


	async def read_in_db(self):
		# читаем список реальных ip из базы
		# для будуещих вычеслений при смене ip
		async with asyncpg.create_pool(DSN) as conn:
			try:
				res = await conn.fetch("SELECT ipreal FROM bc_1 WHERE online=$1", True)
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			sock = [".".join(i['ipreal'].split('.')[:-1]) for i in res]
			return sock


	async def read_db_do_write(self):
		# читаем готовые связки из базы, для запуска бека
		async with asyncpg.create_pool(DSN) as conn:
			try:
				res = await conn.fetch(
					"SELECT ip, port, ipreal FROM bc_1")
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			#  ip, port, ipreal, status, login, password
			resp = [(i['ip'],i['port'],i['ipreal']) \
				for i in res]
			return resp


	async def run_server_from_db(self):
		# читаем готовые связки из базы, для запуска бека
		async with asyncpg.create_pool(DSN) as conn:
			try:
				res = await conn.fetch(
					"SELECT loc_port, ip, port, ipreal FROM bc_1")
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			resp = [(i['loc_port'],i['ip'],i['port'],i['ipreal']) \
				for i in res]
			return resp


	async def _port(self):
		async with asyncpg.create_pool(DSN) as conn:
			try:
				res = await conn.fetch("SELECT loc_port FROM bc_1")
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except TooManyConnectionsError as exc:
				self.log.exception(exc)
			obj = [i['loc_port'] for i in res]
			return obj


	async def post_clean_run_server(self):
		lists_put_server = await self.run_server_from_db()
		for obj in lists_put_server:
			loc_port, ip, port, ipreal, login, password = obj
			await self.qu.put((loc_port, ip, port, ipreal, login, password))
			self.ipreal_list.append(ipreal)
			asyncio.run_coroutine_threadsafe(self.th.go(), self.loop_back)
			self.log.info("новый --> %s:%s ---> %s", self.server, loc_port, ipreal)


	async def _db_add_read_url(sef):
		async with asyncpg.create_pool(DSN) as conn:
			try:
				res = await conn.fetch("SELECT ip, port, ipreal FROM bc_1")
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except Exception as exc:
				self.log.exception(exc)
			obj = [(i['ip'],i['port'],i['ipreal']) for i in res]
			return obj


	async def _restart_back(self):
		async with self._pool.acquire() as conn:
			try:
				res = await conn.fetch("SELECT loc_port, ip, port, ipreal FROM bc_1")
			except ConnectionDoesNotExistError as exc:
				self.log.exception(exc)
			except Exception as exc:
				self.log.exception(exc)
			obj = [(i['loc_port'],i['ip'],i['port'],i['ipreal']) for i in res]
			for sock in obj:
				await self.qu.put(sock)


	def run(self):
		self.log.info("ЗАПУСК")
		data = self.loop.run_until_complete(self._read())

		resp = self.loop.run_until_complete(self.read_db_do_write())
		if resp:
			tasks_del = [self.loop.create_task(self.check_auth_do_run_server(*obj)) for obj in resp]
			completed, pending = self.loop.run_until_complete(asyncio.wait(tasks_del))
			if pending:
				for t in pending:
					try:
						t.cancel()
						self.log.info("отменили")
					except:
						pass
			self.log.info("базу почистили")
			self.ipreal_list = self.loop.run_until_complete(self.read_in_db())
			self.log.info("тут запуск из базы")
			self.loop.run_until_complete(self._restart_back())
			asyncio.run_coroutine_threadsafe(self.th._restart_back(), self.loop_back)
			self.log.info("бек востоновлен")


		loc = self.loop.run_until_complete(self._port())
		start, end = int(self.list_port[0]), int(self.list_port[1])
		[self.random_port.put_nowait(port) for port in range(start, end) if port not in loc]

		if self._type_list == "auth":
			response = [url for url in data if pattern.findall(url)]
			resp = []
			for obj in response:
				try:
					resp.append((obj.split(':')[0], int(obj.split(':')[1])))
				except Exception:
					resp.append((obj.split(';')[0].split(':')[0], int(obj.split(';')[0].split(':')[1])))
			
			if not resp:
				raise TypeError("лист пустой")
			
			self.log.info("всего: %s", len(resp))
			tasks = [self.loop.create_task(self.check_auth(*obj)) for obj in resp]
			self.log.info("старт")
			try:
				self.loop.run_until_complete(asyncio.gather(*tasks))
			except RuntimeError:
				self.log.info("ошибка времени выполнения")
				self.log.info(resp)

			
			while True:
				time.sleep(60*15)
				self.log.info("ЗАПУСК в ЦИКЛЕ")
				self.log.info("в списке %s", len(self.ipreal_list))
				self.log.info("свободных портов %s", self.random_port.qsize())
				try:
					data = self.loop.run_until_complete(self._read())
				except Exception:
					continue
				
				try:
					response = [pattern.search(ip).group() for ip in response] 
				except exc:
					self.log.exception(exc)
				resp = [(obj.split(':')[0], int(obj.split(':')[1])) for obj in response]

				
				self.log.info("ПРОВЕРКА ЛИСТА")
				self.log.info("всего: %s", len(set(resp)))
				tasks = [self.loop.create_task(self.check_auth(*obj)) for obj in resp]
				self.log.info("старт")
				try:
					self.loop.run_until_complete(asyncio.gather(*tasks))
				except RuntimeError:
					continue

				self.log.info("спим")



def main():
	args = argparse.ArgumentParser(description='бек', add_help=False)
	args.add_argument('-i', '--list', type=str)
	args.add_argument('-a', '--allow', type=str)
	args.add_argument('-t', '--type', type=str)
	args.add_argument('-p', '--port', action='append')
	arg = args.parse_args()

	bc = AsyncThreadBc()

	if arg.list and arg.list.startswith("http"):
		db = AsyncThreadDB(bc, arg.list, arg.type, arg.port)
	else:
		msg = "укажите url на сам бек лист\nпример: python back -t auth -i http://example.com/list.txt"
		log.info(msg)
	bc.start()
	db.start()
	db.join()


if __name__ == '__main__':
	main()



# нужно реализовать от базы к бк поток
# уведомления для того что первый запуск и
# то что в базу добавлены соксы 


# при проверки листа
# нужно брать из базы соксы и исключать те что есть в листе
# после сканить и смотреть кто поменял порт из связки


# 1 только один порт на один реальный ip
# 2 поток AsyncThreadDB обновляет ip реальный
#   и привязывает его к старому порту 
#   если бек сменил реальный ip

# 3 поток AsyncThreadBc при соединение
#   проверяет на равенство ip и тот что 
#   верну чекер при проверки
#   если это не так то запускаем выборку
#   из базы по этому ip и обновляем порт