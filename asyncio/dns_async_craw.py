import asyncio
import aiohttp
import _thread as thread
import datetime
import pickle
import sys

from aiohttp.client_exceptions import ClientConnectorError

import aioredis
from async_timeout import timeout
import aiodns

import re
import smtplib

import maxminddb
from bs4 import BeautifulSoup as bs

import asyncio


from tqdm import tqdm


_city    = maxminddb.open_database('geo/maxminddb/city.mmdb', mode=maxminddb.MODE_MEMORY)
_isp     = maxminddb.open_database('geo/maxminddb/isp.mmdb', mode=maxminddb.MODE_MEMORY)
_domain  = maxminddb.open_database('geo/maxminddb/domain.mmdb', mode=maxminddb.MODE_MEMORY)
_country = maxminddb.open_database('geo/maxminddb/country.mmdb', mode=maxminddb.MODE_MEMORY)


HOST     = '127.0.0.1'
PASSWORD = "l1984login"

from email.message import EmailMessage
from email.mime.text import MIMEText

from smtplib import SMTP_SSL as SMTP

DEBUG = False

def send_email(text):
	msg = MIMEText(text, 'plain')
	msg['Subject'] = "Ошибка DNS парсинг"
	me = 'johnmnemonik.jm@gmail.com'
	msg['To'] = me
	frm = "antanasv@yandex.ru"

	try:
		conn = SMTP('smtp.yandex.ru')
		if DEBUG:
			conn.set_debuglevel(True)
		conn.login('antanasv@yandex.ru', 'password')
		try:
			conn.sendmail(frm, me, msg.as_string())
		finally:
			conn.close()

	except Exception as exc:
		print("ERROR!!!")
		print(exc)


class AsyncDNS:
	def __init__(self):
		self._country_futer = None
		self._city_futer = None
		self._isp_futer = None
		self.local = 'en'
		self.pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
		self.url = 'https://public-dns.info'
		self._url_redis = 'redis://:l1984loginn@127.0.0.1:6379/0'
		self._city = _city
		self._isp = _isp
		self._dic = {}
		self._resp_url = []
		self._red_pool = None
		self._loop = asyncio.get_event_loop()
		self._sem = asyncio.BoundedSemaphore(100)
		self._total_dns = {}
		self.resolver = aiodns.DNSResolver()
		self.domain = 'google.com'

	
	async def create_pool(self, loop):
		self._red_pool = await aioredis.create_pool(
			self._url_redis,
			minsize=5,maxsize=10,loop=loop)
		

	async def _red_write(self, key, value):
		await self._red_pool.execute('set', key, str(value)) 


	async def _pars(self, raw):
		bsObj = bs(raw, "html.parser")
		txt = [x.text for x in bsObj.findAll('tr',{'td':''})]
		return txt


	async def _get_country(self, ip):
		fut = self._loop.run_in_executor(None, self._city.get, ip)
		country = await fut


		try:
			country = country.get('country').get('names').get(self.local)
		except:
			return
		return country


	async def _dns_check(self, k, v):
		for dns in v:
			self.resolver.nameservers = [dns]
			try:
				async with timeout(7):
					old = await self.resolver.query(self.domain, 'A')
					print(k, dns, "работает")
					if self._total_dns.get(k, None):
						self._total_dns[k].append(dns)
					else:
						self._total_dns[k] = [dns]
			except (aiodns.error.DNSError, asyncio.TimeoutError):
				pass
			except Exception as exc:
				print(exc)


	async def _country_search(self, txt):
		for i in txt:
			try:
				ip = self.pattern.findall(i)[0]
			except (AttributeError, IndexError):
				continue
			country = await self._get_country(ip)
			if self._dic.get(country):
				self._dic[country].append(ip)
			else:
				self._dic[country] = [ip]


	async def crawler(self, link):
		async with self._sem:
			async with aiohttp.ClientSession() as session:
				try:
					async with session.get(self.url + link) as resp:
						if resp.status == 200:
							text = await resp.text()
							txt = await self._pars(text)
							await self._country_search(txt)
						elif resp.status == 503:
							self._resp_url.append(link)
						else:
							print("Ошибка %s урла" % (self.url + link))
							print(resp.status)
				except ClientConnectorError:
					msg = "ошибка соединение %s" % datetime.datetime.now()
					send_email(msg)


	async def _do_start(self):
		try:
			async with timeout(60):
				async with aiohttp.ClientSession() as session:
					async with session.get(self.url) as resp:
						if resp.status == 200:
							data = await resp.text()
							return data
		except asyncio.TimeoutError:
			import sys
			msg = "время вышло %s сервер не доступен" % datetime.datetime.now()
			send_email(msg)
			sys.exit(msg)


	def _bootstrap(self):
		loop = asyncio.get_event_loop()
		loop.run_until_complete(self.create_pool(loop))
		req = loop.run_until_complete(self._do_start())

		print("парсинг")

		bsObj = bs(req, "html.parser")
		links = [x.attrs['href'] for x in bsObj.findAll("a") if x.attrs['href'].endswith('.html')]

		tasks = [self.crawler(link) for link in links]
		loop.run_until_complete(asyncio.gather(*tasks))
		
		print("всего стран: ", len(self._dic.keys()))

		if self._resp_url:
			print("Всего на повтор: %s" % len(self._resp_url))
			links = self._resp_url
			self._resp_url = []
			print("--> ", len(links), len(self._resp_url))
			tasks = [self.crawler(link) for link in links]
			loop.run_until_complete(asyncio.gather(*tasks))

		if self._resp_url:
			print("Всего: %s" % len(self._resp_url))
			if len(self._resp_url) > 1:
				msg = "не добавлены страны %s" % " ".join(self._resp_url)
			else:
				msg = "не добавлены страны %s" % self._resp_url
			thread.start_new(send_email, (msg,))

		else:
			msg = "все страны добавлены > %s" % self._resp_url
			print(msg)
			thread.start_new(send_email, (msg,))

		tasks = [self._dns_check(k, v) for k,v in self._dic.items()]
		loop.run_until_complete(asyncio.gather(*tasks))

		with open("check_dns.bin", "wb") as f:
			pickle.dump(self._total_dns, f)


		tasks_red_write = [self._red_write(key, val) for key, val in self._total_dns.items()]
		loop.run_until_complete(asyncio.gather(*tasks_red_write))
		self._red_pool.close()
		loop.run_until_complete(self._red_pool.wait_closed())
		loop.close()


	def run(self):
		self._bootstrap()


def main():
	craw = AsyncDNS()
	craw.run()



if __name__ == '__main__':
	main()
