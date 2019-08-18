from __future__ import absolute_import, unicode_literals
import datetime
import random
import time
import logging
from struct import pack, unpack
import json
import base64

from multiprocessing.connection import Client, AuthenticationError

import gevent
from gevent.socket import create_connection
from gevent import socket
import requests

from celery import shared_task, task
from celery.task.base import Task, PeriodicTask 
from celery.task.control import revoke
from celery.task.control import inspect
from celery.task.base import periodic_task
from celery.result import allow_join_result
from celery.utils import worker_direct
from celery.utils.log import get_task_logger
from celery.exceptions import TimeLimitExceeded, SoftTimeLimitExceeded

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

import netifaces

from proxy.models import Proxy
from client.models import Port
from pay.models import Refill, Purses
from prof.models import User
from client.models import Port
from folow_mony.models import HistoryMony
from ._rev import IP2Location

queues = settings.QUEUES


log = get_task_logger(__name__)

from bc.static_memory import trace



@task(name='test-logging')
@trace
def test():
    log.info("[ ********** > RUN < ********** ]")


# получаем ip сервера
def _get_ip_address():
    for interf in netifaces.interfaces():
        if not interf.startswith('lo'):
            address = netifaces.ifaddresses(interf)
            if netifaces.AF_INET in address:
                for addr in netifaces.ifaddresses(interf)[netifaces.AF_INET]:
                    return addr['addr']


# отправка уведомлений об ошибках
class SendEmailError(Task):
    name = 'отправка-почты'
    ignore_result = True

    def send_email_error(self, msg):
        if not isinstance(msg, str):
            log.info("не строка")
            return
        send_mail(
            'ERROR-TASKS',
            msg,
            settings.EMAIL_HOST_USER,
            settings.LIST_OF_EMAIL_RECIPIENTS,
            fail_silently=False,)

    def run(self, msg, *args, **kwargs):
        self.send_email_error(msg)



@task(name='ЗАПУСК-ПОШТУЧНОГО')
@trace
def forward(source, dest, user, password, type_proxy, userhttp=None, passwordhttp=None, dns=None):
    log.info("Запустили, %s", type_proxy)
    obj = (source, dest, user, password, type_proxy, userhttp, passwordhttp, dns)
    try:
        sock = Client(('localhost', 49151), authkey=b"password")
        sock.send(obj)
        ident = sock.recv()
        sock.close()
        return ident
    except AuthenticationError:
        raise AuthenticationError("Auth Error")
    except EOFError:
        sock.close()
        pass



@task(name='РЕСТАРТ-ПОШТУЧНОГО')
@trace
def restart(ident):
    obj = ('restart', "{}".format(ident))
    try:
        sock = Client(('localhost', 49151), authkey=b"password")
        sock.send(obj)
        ident = sock.recv()
        # TODO ident пишем в базу
        sock.close()
        return ident
    except AuthenticationError:
        raise AuthenticationError("Auth Error")
    except EOFError:
        sock.close()
        return


@task(name='СМЕНА-ПОРТОВ')
@trace
def report(ident, dest):
    obj = ('port', '{}'.format(ident), dest)
    try:
        sock = Client(('localhost', 49151), authkey=b"password")
        sock.send(obj)
        ident = sock.recv()
        # TODO пишем id в базу
        sock.close()
        return ident
    except AuthenticationError:
        raise AuthenticationError("Auth Error")
    except EOFError:
        sock.close()
        return
    except ConnectionRefusedError:
        raise ValueError("не удалось соедениться с бек сервером")


@task(name='ЗАВЕРШИТЬ')
@trace
def kill(ident):
    obj = ('kill', '{}'.format(ident))
    try:
        sock = Client(('localhost', 49151), authkey=b"password")
        sock.send(obj)
        data = sock.recv()
        sock.close()
        # TODO пишем id в базу
        return data
    except AuthenticationError:
        raise AuthenticationError("Auth Error")
    except EOFError:
        sock.close()
        return




@task(name='ПРОВЕРКА-СКОРОСТИ', default_retry_delay=60, max_retries=1, time_limit=120)
@trace
def check_speed(types, ip, port, user=None, password=None):
    speed = None
    if types == "https":
        types = "http"
    if types == "https_auth":
        types = "http"

    if user and password:
        proxies = {
            "http":"{}://{}:{}@{}:{}".format(types, user, password, ip, port),
        }
    else:
        proxies = {"http":"{}://{}:{}".format(types, ip, port)}
    
    num = 2
    url = settings.CHECKFILES
    while num:
        num -= 1
        try:
            start = time.time()
            s = requests.get(url,
                proxies=proxies, timeout=90)
            end = time.time()
            total = end - start
            size = int(s.headers.get('content-length'))
            s1 = size//total
            kb = round(s1/1024)
            mb = round(s1/1024/1024)

            if mb:
                speed = "{} Mb/s".format(mb)
            else:
                speed = "{} Kb/s".format(kb)
            break
        except Exception as exc:
            url = "http://asyncio.ru/static/archlinux-keyring-20171020-1-any.pkg.tar.xz"
            continue
    return speed


@task(name='ПРОВЕРКА-ОНЛАЙН')
@trace
def _online(ip, port, types, user=None, password=None):
    if types == "https":
        types = "http"
    
    if types == "https_auth":
        types = "http"
    
    if user and password:
        proxies = {
            "http":"{}://{}:{}@{}:{}".format(types, user, password, ip, port),
        }
    else:
        proxies = {
            "http":"{}://{}:{}".format(types, ip, port),
        }
    
    try:
        start = time.time()
        s = requests.get('http://{ip}:{port}'.format(
            ip=settings.CHECKERSERVER, port=settings.CHECKERSERVERPORT),proxies=proxies,timeout=60)
        status = True

    except Exception as exc:
        status = False

    return status


@task(name='СОЗДАНИЕ-ПОШТУЧНОГО-СВЯЗКА', default_retry_delay=60, max_retries=1, time_limit=120)
@trace
def backforward(portid, id, request):
    log.info("--- RUN backforward ---")
    User = get_user_model()

    userhttp, passhttp = None, None
    obj = Proxy.objects.get(id=id)
    worker = obj.worker.ip
    type_proxy = obj.tp
    user = request.user
    domain = obj.domain
    username = "{}".format(request.user.get_name_split())
    user = User.objects.get(id=user.id)

    username = user.get_name_split()
    passwd = request.user.gen_pswd()

    if type_proxy == 'https_auth':
        userhttp = obj.usr
        passhttp = obj.pswd

    al = [x.port for x in Port.objects.all()]

    while True:
        p = random.randint(10240, 15240)

        if str(p) not in al:
            break

    try:
        port = Port.objects.get(port=str(p))
    except Port.DoesNotExist:
        port = None

    if port:
        port.use = True
        port.password = passwd
        source = ('0.0.0.0', port.port)
        dest = (obj.ip, int(obj.port))
        ipreal = "{}:{}".format(obj.ip,obj.port)
        dns = port.dns

        task = forward.apply_async(args=(
                source, dest, username, passwd, type_proxy, userhttp, passhttp, dns), queue=worker)
        port.task = task.get()
        port.ipreal = ipreal
        port.worker = worker
        port.user = user
        port.use = True
        port.save()
    else:
        try:
            port = Port.objects.get(id=portid)
            source = ('0.0.0.0', p)
            dest = (obj.ip,int(obj.port))
            ipreal = "{}:{}".format(obj.ip,obj.port)
            dns = port.dns
            task = forward.apply_async(args=(
                source, dest, username, passwd, type_proxy, userhttp, passhttp, dns), queue=worker)

            port.task = task.get()
            port.port = p
            port.password = passwd
            port.ipreal = ipreal
            port.worker = worker
            port.user = user
            port.use = True
            port.save()
        except ConnectionRefusedError:
            raise TypeError("Error ConnectionRefusedError")
     




@task(name='СКАН-ПОРТОВ', default_retry_delay=60, max_retries=1, time_limit=120)
@trace
def _portopen(ip):
    status = []
    for port in [80, 8080, 3128]:
        try:
            s = create_connection((ip, port), timeout=4)
            status.append(str(port))
            s.close()
        except socket.error:
            continue
        except Exception:
            continue
    return status




@task(name='CHECK-SOCKS-FORWARD')
@trace
def checker_socks_forward(ipreal, user):
    """
    тут прпоисходит проверка почтучного сокса
    """
    if not ipreal:
        return "отправлен пустой ip"
    ip, port = ipreal.split(":")
    try:
        s = create_connection((ip,int(port)), timeout=10)
        s.send(b"\x05\x01\x00")
        data = s.recv(1024)
        if data.startswith(b"\x05\x00"):
            s.close()
            return
        elif data.startswith(b"\x05\x02"):
            status = [ipreal, user]
        else:
            s.close()
            return [ipreal, user]
    except socket.error:
        status = [ipreal, user]
    except Exception as exc:
        status = [ipreal, user]
    return status


class CheckOnlineSocks(Task):
    name = "ПРОВЕРКА-КУПЛЕННЫХ-СОКСОВ-ОНЛАЙН"


    @trace
    def _check_sock4(self, ipreal, user, timeout=10):
        ip = ipreal.split(":")[0]
        port = int(ipreal.split(":")[1])
        try:
            _sock = create_connection((ip, port), timeout=timeout)
            req = b'\x04\x01' + pack("!H", port) + socket.inet_aton(ip) + b'' + b'\x00'
            _sock.send(req)
            _ = _sock.recv(1024)
            if _[0] == 0x00 and _[1] == 0x5A or _[0] == 0x00 and _[1] == 0x5b:
                return
            else:
                status = [ipreal, user]
                return status
        except socket.error:
            status = [ipreal, user]
        except Exception:
            status = [ipreal, user]
        return status

    @trace
    def _check_sock5(self, ipreal, user, timeout=10):
        ip = ipreal.split(":")[0]
        port = int(ipreal.split(":")[1])
        try:
            _sock = create_connection((ip, port), timeout=timeout)
            _sock.send(b"\x05\x01\x00")
            _ = _sock.recv(1024)
            if _.startswith(b"\x05\x00"):
                return
            else:
                status = [ipreal, user]
                return status
        except socket.error:
            status = [ipreal, user]
        except Exception:
            status = [ipreal, user]
        return status


    @trace
    def _check_http(self, ipreal, user, timeout=10):
        ip = ipreal.split(":")[0]
        port = int(ipreal.split(":")[1])
        try:
            _sock = create_connection((ip, port), timeout=timeout)
            _header = "CONNECT {host}:{port} HTTP/1.1\r\n \
                       Host: {host}:{port}\r\n \
                       Proxy-Connection: Keep-Alive\r\n\r\n".format(host="185.235.245.17", port=9999)
            _sock.send(_header.encode('latin1'))
            _ = _sock.recv(1024)
            if _.startswith(b'HTTP/1.1 200') or _.startswith(b'HTTP/1.0 200'):
                return
            else:
                status = [ipreal, user]
                return status
        except socket.error:
            status = [ipreal, user]
        except Exception:
            status = [ipreal, status]
        return status




    def run(self, ipreal, user, type_proxy, *args, **kwargs):
        if type_proxy == "socks4":
            return self._check_sock4(ipreal, user)
        elif type_proxy == "socks5":
            return self._check_sock5(ipreal, user)
        elif type_proxy == "http":
            return self._check_http(ipreal, user)



@task(name='FUNC-FORWARD')
@trace
def func_forward(port_id, proxy_id):
    port = Port.objects.get(id=port_id)
    ident = port.task
    worker = port.worker
    try:
        task = restart.apply_async(args=(ident,),queue=worker)
        return "перезапустили"
    except Exception as exc:
        log.exception(exc)

    


class CheckForwardAndRestart(PeriodicTask):
    run_every = datetime.timedelta(minutes=30)
    name = "Проверка-и-перезапуск-купленных-соксов"
    soft_time_limit = 60*10
    queue = "185.235.245.4"
    ignore_result = False


    def _return_pay(self, user_id):
        """ тут возврат денег"""
        pass


    @trace
    def _sock_run_online(self):
        forwarders = [obj for obj in Port.objects.all()]
        try:
            total_jobs = [CheckOnlineSocks.apply_async(
                args=(sock.ipreal, sock.user.id, sock.socks.tp), queue=sock.worker) for sock in forwarders]
        except Exception as msg:
            msg = str(msg) + " строка 431"
            SendEmailError.apply_async(args=(msg,), queue=random.choice(queues))
            return
        error = []
        try:
            for c in total_jobs:
                with allow_join_result():
                    error.append(c.get())
        except Exception as msg:
            msg = str(msg) + " строка 433"
            SendEmailError.apply_async(args=(msg,), queue=random.choice(queues))
        list_replace_ip = [obj for obj in error if obj]
        return list_replace_ip


    @trace
    def _sock_check(self):
        list_replace_ip = self._sock_run_online()
        TOTAL = []
        if list_replace_ip:
            for _ in list_replace_ip:
                # ip -> iprea, user
                ipreal, user_id = _
                try:
                    port = Port.objects.get(ipreal=ipreal)
                    vendor_id = port.socks.vendor.id
                except Port.DoesNotExist:
                    continue
                try:
                    ip = port.socks.ipreal
                except AttributeError:
                    ip = ipreal.split(":")[0]
                if not ip:
                    TOTAL.append("пустой ip")
                    continue
                obj = Proxy.objects.filter(ipreal=ip, checkers=True, vendor_id=vendor_id)
                if obj:
                    proxy = random.choice(obj)
                    try:
                        worker = port.worker
                        dest = (proxy.ip, int(proxy.port))
                        ident = port.task
                        try:
                            report.apply_async(args=(ident, dest), queue=worker)
                        except:
                            return "Не удачная смена портов"
                        port.ipreal = "{}:{}".format(proxy.ip, proxy.port)
                        port.socks = proxy
                        port.online = True
                        port.save()

                        TOTAL.append("старый {_ip} новый {ip}:{port}".format(_ip=ipreal, ip=proxy.ip, port=proxy.port))
                        continue
                    except Exception as exc:
                        print(exc)
                        continue
                _ip_mix = ".".join(ipreal.split(":")[0].split(".")[:3])
                obj = Proxy.objects.filter(ip__startswith=_ip_mix, checkers=True, vendor_id=vendor_id)
                if obj:
                    proxy = random.choice(obj)
                    #тут перезапуск бек сокса на новый сокс
                    try:
                        worker = port.worker
                        dest = (proxy.ip, int(proxy.port))
                        ident = port.task
                        try:
                            report.apply_async(args=(ident, dest), queue=worker)
                        except Exception as exc:
                            return "Не удачная смена портов"
                        port.ipreal = "{}:{}".format(proxy.ip, proxy.port)
                        port.socks = proxy
                        port.online = True
                        port.save()

                        TOTAL.append("маска старый {_ip} новый {ip}:{port}".format(_ip=ipreal, ip=proxy.ip, port=proxy.port))
                        continue
                    except Exception as exc:
                        TOTAL.append(exc)
                        continue
                _ip_mix = ".".join(ipreal.split(":")[0].split(".")[:2])
                obj = Proxy.objects.filter(ip__startswith=_ip_mix, checkers=True, vendor_id=vendor_id)
                if obj:
                    proxy = random.choice(obj)
                    #тут перезапуск бек сокса на новый сокс
                    try:
                        worker = port.worker
                        dest = (proxy.ip, int(proxy.port))
                        ident = port.task
                        try:
                            report.apply_async(args=(ident, dest), queue=worker)
                        except:
                            return "Не удачная смена портов"
                        port.ipreal = "{}:{}".format(proxy.ip,proxy.port)
                        port.socks = proxy
                        port.online = True
                        port.save()

                        TOTAL.append("маска старый {_ip} новый {ip}:{port}".format( _ip=ip[0],ip=proxy.ip, port=proxy.port))
                        continue
                    except Exception as exc:
                        continue
                else:
                    #SendEmailError.apply_async(args=("else 503",), queue='185.235.245.4')
                    try:
                        port.online = False
                        port.save()
                        exists = True
                    except:
                        exists = False
                    if exists:
                        now = timezone.now()
                        offset = datetime.timedelta(hours=24)
                        if port.update + offset <= now:
                            port.delete()
                            TOTAL.append('socks удален'.format(ip[0]))

        else:
            return "Все СОКСЫ в рабочем состонии"
        return TOTAL


    def run(self, *args, **kwargs):
        try:
            result = self._sock_check()
            if isinstance(result, (list, tuple)):
                result = " ".join([str(x) for x in result])
        except (SoftTimeLimitExceeded, TimeLimitExceeded):
            msg = "не хватило времени на проверку"
            SendEmailError.apply_async(args=(msg,), queue=random.choice(queues))
            result = "error-time"
        return result




@periodic_task(
    name='ПРОВЕРКА-ОКОНЧАНИЯ-РАБОТЫ-СОКСА',
    run_every=datetime.timedelta(minutes=60),
    queue='185.235.245.4',
    time_limit=60*20)
@trace
def check_time():
    socks = []
    ports = Port.objects.all()
    for p in ports:
        if p.created + datetime.timedelta(days=int(p.term)) < timezone.now():
            p.delete()
            socks.append("socks {} delete".format(p.ipreal))
    return socks


def kurs_coin(bitcoin):
    """Проверка курса биткоин к USD
    """
    r = requests.get \
        ('http://preev.com/pulse/units:btc+usd/sources:bitfinex+bitstamp+btce')
    if r.status_code == 200:
        strs = json.loads(r.text)
        val = float(strs['btc']['usd']['bitfinex']['last'])
    else:
        r2 = requests.get("https://www.bitstamp.net/api/ticker/")
        strs2 = json.loads(r2.text)
        val = float(strs['last'])
    context = {}
    context['truck'] = val
    context['val'] = bitcoin * val


from celery.task.control import revoke

@task(name='CHECK-BITCOIN')
@trace
def check_bitcoin(user, purse, usd, bit):
    """Проверка кошелька на поступление денег
    """
    # try:
    User = get_user_model()
    
    t = 60*60*6
    while t > 0:
        r = requests.get \
                ('https://blockexplorer.com/api/addr/{}'.format(purse))
        if r.status_code == 200:
            strs = json.loads(r.text)
            total_received = float(strs['totalReceived'])
            total_sent = float(strs['totalSent'])
            tx = int(strs['unconfirmedTxApperances'])
            try:
                refill = Refill.objects.get(user_id=user, usd=usd, bit=bit, success=False)
                balance = total_received - refill.balance
            except Refill.DoesNotExist:
                return "Нет заявки"

            if tx == 0 and balance > 0:
                try:
                    #usd = kurs(balance)
                    r = requests.get \
                        ('http://preev.com/pulse/units:btc+usd/sources:bitfinex+bitstamp+btce')
                    if r.status_code == 200:
                        strs = json.loads(r.text)
                        val = float(strs['btc']['usd']['bitfinex']['last'])
                    else:
                        r2 = requests.get("https://www.bitstamp.net/api/ticker/")
                        strs2 = json.loads(r2.text)
                        val = int(strs['last'])
                    context = {}
                    context['truck'] = val
                    context['val'] = balance * val

                    refill.success = True
                    refill.save()
                    popoln = User.objects.get(id=user)
                    popoln.balance = int(context['val'])
                    popoln.save()
                    # Запись истории
                    history = HistoryMony()
                    history.user = request.user
                    history.purse = Purses.objects.get(client_id=user)
                    history.usd = popoln.balance
                    history.summ = context['val']
                    history.bitcoin = balance
                    history.popolnen = "1"
                    history.save()
                    return ("На счет зачисленно {}".format(context['val']))
                except:
                    return ("Ошибка сахронения")
            else:
                time.sleep(20*60)
                t -= 20*60
                continue
        else:
            time.sleep(20*60)
            t -= 20*60
            continue
    if t == 0:
        return "Время вышло, пополнений нет"
    else:
        return t