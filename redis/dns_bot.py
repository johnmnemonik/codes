#-*-coding:utf-8 -*-
from gevent import monkey
monkey.patch_all()

import re
from bs4 import BeautifulSoup as bs
import gevent
from gevent.pool import Pool
import requests
import pygeoip

geo = pygeoip.GeoIP('geo/GeoLiteCity.dat',flags=pygeoip.const.GEOIP_MEMORY_CACHE)

hostredis = 'localhost'
PSSWD = "password"

pool = Pool(50)

reg = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
url = 'https://public-dns.info/'


def parser(urls, red):
	page = requests.get(url + urls).text
	bsObj = bs(page)
	iplist = []
	citylist = []
	txt = [x.text for x in bsObj.findAll('tr',{'td':''})]
	dicts = {} 
	for i in txt:
		try:
			ip = re.search(reg, i).group()
		except AttributeError:
			continue
		try:
			city = geo.record_by_addr(ip)['city']
		except Exception as exc:
			city = ''
		try:
			country_name = geo.record_by_addr(ip)['country_name']
		except Exception:
			country_name = ''
		iplist.append(ip)
		citylist.append(city if city else '')
		
		if ip:
			dicts[ip] = [ip,country_name]

	red.set(country_name,[iplist,citylist])
	iplist, countrylist, citylist = [], [], []

def start(url=url):
	red = Redis(hostredis)
	req = requests.get(url).text
	bsObj = bs(req)
	links = [x.attrs['href'] for x in bsObj.findAll("a") if x.attrs['href'].endswith('.html')]
	jobs = [pool.spawn(parser, x, red) for x in links]
	gevent.joinall(jobs)
		

def main():
	start()

if __name__ == '__main__':
	main()