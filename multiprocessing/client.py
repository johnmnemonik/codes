import os
import sys
import time
import logging

from multiprocessing.connection import Client, AuthenticationError
import socket
import django
import gevent

logging.basicConfig(
	filename='client.log',
	format="%(levelname)-10s %(lineno)d %(asctime)s %(message)s",
	level=logging.INFO
)

PASSWORD = b"passsword"

sys.path.insert(0, os.path.dirname("../" + __file__))
sys.path.append('/home/john/proxyproject')
os.environ['DJANGO_SETTINGS_MODULE'] = 'proxyproject.settings'

django.setup()
from vendor.models import Vendors, VendorsAuth
from proxy.models import Proxy, Worker, ProxyAuth
from prof.models import User
from vendor.utils import results_ip_list, chunks
from daemonize import daemonize



class ClientWorkerOnlineNoAuth:
	def __init__(self, typ, data, dataid, server):
		self.type = typ
		self.data = data
		self.dataid = dataid
		self.server = server

	def _botstrap(self):
		try:
			conn = Client((self.server, 65100), authkey=PASSWORD)
			logging.info("connection online AUTH {} sucess".format(self.server))
		except (AuthenticationError, socket.error, IOError):
			logging.info("connection online AUTH {} ERROR".format(self.server))
			return
		conn.send((self.type, self.data, self.dataid))
		logging.info("send data AUTH")
		conn.close()

	def run(self):
		self._botstrap()

class ClientWorkerOnlineAuth:
	def __init__(self, typ, data, dataid, server):
		self.type = typ
		self.data = data
		self.dataid = dataid
		self.server = server

	def _botstrap(self):
		try:
			conn = Client((self.server, 65100), authkey=PASSWORD)
			logging.info("connection online AUTH {} sucess".format(self.server))
		except (AuthenticationError, socket.error, IOError):
			logging.info("connection online AUTH {} ERROR".format(self.server))
			return
		conn.send((self.type, self.data, self.dataid))
		logging.info("send data AUTH")
		conn.close()

	def run(self):
		self._botstrap()

class ClientWorkerAuth:
	def __init__(self, typ, server, data, user_id):
		self.type = typ if typ else None
		self.server = server
		self.data = data
		self.user_id = user_id

	def _botstrap(self):
		if len(self.server.all()) >= 2:
			logging.info("server > 1")
			print(self.server)
			for srv in self.server.all():
				try:
					conn = Client((srv.ip, 65100), authkey=PASSWORD)
				except (AuthenticationError, socket.error, IOError):
					continue
				conn.send((self.type, self.server, self.data, self.user_id, srv.id))
				conn.close()
				break
		else:
			for srv in self.server.all():
				try:
					conn = Client((srv.ip, 65100), authkey=PASSWORD)
					logging.info("connection {} sucess".format(srv.ip))
				except AuthenticationError as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
				except socket.error as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
				except IOError as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
					
				conn.send((self.type, srv.ip, self.data, self.user_id, srv.id))
				conn.close()
				break
		
	def run(self):
		self._botstrap()

class ClientWorkerOnline:
	def __init__(self, typ, data, server):
		self.type = typ
		self.data = data
		self.server = server

	def _botstrap(self):
		
		try:
			conn = Client((self.server, 65100), authkey=PASSWORD)
			logging.info("connection online {} sucess".format(self.server))
		except (AuthenticationError, socket.error, IOError):
			logging.info("connection online {} ERROR".format(self.server))
			return

		conn.send((self.type, self.data))
		logging.info("send data")
		conn.close()

		
	def run(self):
		self._botstrap()

class ClientWorker:
	def __init__(self, typ, server, data, user_id):
		self.type = typ if typ else None
		self.server = server
		self.data = data
		self.user_id = user_id

	def _botstrap(self):
		if len(self.server.all()) >= 2:
			logging.info("server > 1")
			print(self.server)
			for srv in self.server.all():
				try:
					conn = Client((srv.ip, 65100), authkey=PASSWORD)
				except (AuthenticationError, socket.error, IOError):
					continue
				conn.send((self.type, self.server, self.data, self.user_id, srv.id))
				conn.close()
				break
		else:
			for srv in self.server.all():
				try:
					conn = Client((srv.ip, 65100), authkey=PASSWORD)
					logging.info("connection {} sucess".format(srv.ip))
				except AuthenticationError as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
				except socket.error as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
				except IOError as exc:
					logging.info("connection {} ERROR {}".format(srv.ip,exc))
					break
					
				conn.send((self.type, srv.ip, self.data, self.user_id, srv.id))
				conn.close()
		
	def run(self):
		self._botstrap()

def main():
	###checker
	v = Vendors.objects.all()
	data = [('dp', x.worker, x.link, x.user_id) for x in v if x.worker.all() \
		if x.typeproxy == 'dp' and not x.auth]

	lst = [ClientWorker(*r) for r in data]
	[x.run() for x in lst]
	###job
	
	works = Worker.objects.all()
	for ip in works:
		d = Proxy.objects.filter(worker__ip=ip.ip,auth=False)
		data = ["{}:{}".format(x.ip,x.port) for x in d]
		if data:
			if len(data) > 10000:
				datas = chunks(data, 4)
				for dt in datas:
					run = ClientWorkerOnline('online',dt, ip.ip)
					run.run()
			else:
				run = ClientWorkerOnline('online',data, ip.ip)
				run.run()


	#checker auth
	data = [('bp', x.worker, x.link, x.user_id) for x in v if x.worker.all() \
		if x.typeproxy == 'bp' if x.auth]

	lst = [ClientWorkerAuth(*r) for r in data]
	logging.info(data)
	[x.run() for x in lst]
	#job auth
	works = Worker.objects.all()
	for ip in works:
		d = Proxy.objects.filter(worker__ip=ip.ip,auth=True)
		data = ["{}://{}:{}@{}:{}".format(x.tp,x.usr,x.pswd,x.ip,x.port) for x in d]
		dataid = [x.id for x in d]
		if data:
			if len(data) > 10000:
				datas = chunks(data, 4)
				dataids = chunks(dataid, 4)
				for dt,s in zip(datas,dataids):
					run = ClientWorkerOnlineAuth('onlineauth',dt,s,ip.ip)
					run.run()
			else:
				run = ClientWorkerOnlineAuth('onlineauth',data,dataid,ip.ip)
				run.run()



if __name__ == '__main__':
	daemonize(stdout='/tmp/clien.log',stderr='/tmp/clienterror.log')
	while True:
		try:
			main()
		except Exception as exc:
			logging.exception(exc)
		time.sleep(60*15)