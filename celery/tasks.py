from __future__ import absolute_import, unicode_literals
import datetime
import random
import time
from struct import pack, unpack

import gevent
import requests

from celery import shared_task, task
from celery.task.control import revoke
from celery.task.control import inspect
from celery.task.base import periodic_task 
#from celery.task.base import task
from django.contrib.auth import get_user_model

from pay.portforwarder_auth import start
from proxy.models import Proxy
from client.models import Task, Port

from celery.utils import worker_direct

from gevent.socket import create_connection
from gevent import socket


User = get_user_model()

@task
def forward(user, passwd, source, dest, domain):
	start(user, passwd, source, dest, domain)


@task
def backforward(request, id):
	obj = Proxy.objects.get(id=id)
	worker = obj.worker.ip
	user = request.user
	domain = obj.domain
	username = u"{}".format(request.user.get_name_split())
	user = User.objects.get(id=user.id)
	passwd = request.user.gen_pswd()

	al = [x.port for x in Port.objects.all()]

	while True:
		p = random.randint(1024,65000)
		
		if str(p) not in al:
			break

	try:
		port = Port.objects.get(port=str(p))
	except Port.DoesNotExist:
		port = None

	if port:
		port.use = True
		port.password = passwd

		source = "0.0.0.0:{}".format(port.port)
		dest = (obj.ip,int(obj.port))
		ipreal = "{}:{}".format(obj.ip,obj.port)
		
		task = forward.apply_async(args=(username,passwd,source,dest, domain),queue=worker)
		port.task = task.id
		port.ipreal = ipreal
		port.worker = worker
		port.save()
		port.user.add(user)

	else:
		port = Port(use=True,password=passwd, port=p)
		source = "0.0.0.0:{}".format(p)
		dest = (obj.ip,int(obj.port))
		ipreal = "{}:{}".format(obj.ip,obj.port)
		
		task = forward.apply_async(args=(username,passwd,source,dest, domain),queue=worker)
		port.task = task.id
		port.ipreal = ipreal
		port.worker = worker
		port.save()
		port.user.add(user)


@task
def _online(ip, port, user=None, password=None):
	try:
		status = None
		s = create_connection((ip,int(port)), timeout=10)
		s.send(b"\x05\x01\x00")
		data = s.recv(1024)
		if data.startswith(b"\x05\x00"):
			data = b"\x05\x01\x00\x01" + socket.inet_aton('217.23.2.235') + pack("!H", 9999)
			s.send(data)
			data = s.recv(1024)
			s.send(b"GET / HTTP/1.1\r\n\r\n")
			data = s.recv(1024)
			s.close()
			status = True
		elif data.startswith(b"\x05\x02"):
			pass
		else:
			s.close()
	except socket.error:
		pass
	return status


@task
def _portopen(ip):
	status = []
	for port in [80, 8080, 3128]:
		try:
			s = create_connection((ip, port), timeout=10)
			status.append(str(port))
			s.close()
		except socket.error:
			continue
		except Exception:
			continue
	return status


@task(default_retry_delay=100, max_retries=2, time_limit=200)
def checker_socks_forward(ipreal):
	"""
	тут прпоисходит проверка почтучного сокса
	"""
	ip, port = ipreal.split(":")
	try:
		status = ipreal
		s = create_connection((ip,int(port)), timeout=10)
		s.send(b"\x05\x01\x00")
		data = s.recv(1024)
		if data.startswith(b"\x05\x00"):
			data = b"\x05\x01\x00\x01" + socket.inet_aton('ip address') + pack("!H", 9999)
			s.send(data)
			data = s.recv(1024)
			s.send(b"GET / HTTP/1.1\r\n\r\n")
			data = s.recv(1024)
			s.close()
			status = False
		elif data.startswith(b"\x05\x02"):
			status = ipreal
		else:
			s.close()
	except socket.error:
		status = ipreal
	except Exception as exc:
		status = ipreal
		return status
	return status

@task
def func_forward(port_id, proxy_id):
	port = Port.objects.get(id=port_id)
	proxy = Proxy.objects.get(id=proxy_id)
	revoke(port.task, terminate=True)
	# тут запускаем новый бек
	worker = port.worker
	user = port.user.all()[0]
	username = user.get_name_split()
	passwd = port.password
	domain = proxy.domain
	source = "0.0.0.0:{}".format(port.port)
	dest = (proxy.ip,int(proxy.port))
	task = forward.apply_async(args=(username,passwd,source,dest, domain),queue=worker)

	port.task = task.id
	port.ipreal = "{}:{}".format(proxy.ip,proxy.port)
	port.save()
	return "Удачтно одновлен {ip} {task}".format(ip=port.ipreal, task=task.id)
	
	
from celery.result import allow_join_result

@periodic_task(run_every=datetime.timedelta(minutes=30),time_limit=180, max_retries=2)
def forward_check_and_restart():
	forward = [obj for obj in Port.objects.all()]
	#тут проверка всех купленых соксов
	total_jobs = [checker_socks_forward.apply_async(args=(fw.ipreal,),queue=fw.worker) for fw in forward]

	error = []

	for c in total_jobs:
		with allow_join_result():
			error.append(c.get())

	list_replace_ip = [ip for ip in error if ip]

	if list_replace_ip:
		for ip in list_replace_ip:
			_ip = ip.split(":")[0]
			obj = Proxy.objects.filter(ip__startswith=_ip,checkers=True,)
			if obj:
				proxy = random.choice(obj)
				#тут перезапуск бек сокса на новый сокс
				try:
					port = Port.objects.get(ipreal=ip)
				except:
					return "ОШИБКА {}".format(ip)
				func_forward.delay(port.id, proxy.id)
				return("ОТЛИЧНАЯ ЗАМЕНА ПОРТОВ {}".format(ip))
			else:
				_ip = ".".join(ip.split(":")[0].split(".")[:3])
				obj = Proxy.objects.filter(ip__startswith=_ip,checkers=True,)
				if obj:
					proxy = random.choice(obj)
					#тут перезапуск бек сокса на новый сокс
					try:
						port = Port.objects.get(ipreal=ip)
					except:
						return "ОШИБКА {}".format(ip)
					func_forward.delay(port.id, proxy.id)
					return("ОТЛИЧНАЯ ЗАМЕНА ПОРТОВ МАСКА 3 {}".format(ip))
				else:
					return "Geo"
					#тогда выбераем сокс по гео
					

	else:
		return "Все ok"