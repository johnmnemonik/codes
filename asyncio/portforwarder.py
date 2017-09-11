#coding:utf-8
from gevent.monkey import patch_all
patch_all()

from multiprocessing import Process, current_process, cpu_count
import resource
import socket
import logging
import sys
import signal
import gevent
import struct
import base64
from struct import pack, unpack
import os,sys
import time
import psycopg2 as ps
import requests

from gevent.pool import Pool
from gevent import select, socket
from gevent.server import StreamServer
from gevent.socket import create_connection, gethostbyname

from daemonize import daemonize

import logging
import logging.handlers

STATUS = b"\x00"
BUF_SIZE = 1024

sys.path.insert(0, os.path.dirname("../" + __file__))
sys.path.append('/home/john/proxyproject/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'proxyproject.settings'

 
class TlsSMTPHandler(logging.handlers.SMTPHandler):
    def emit(self, record):
        try:
            import smtplib
            import string
            try:
                from email.utils import formatdate
            except ImportError:
                formatdate = self.date_time
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port)
            msg = self.format(record)
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (
                            self.fromaddr,
                            string.join(self.toaddrs, ","),
                            self.getSubject(record),
                            formatdate(), msg)
            
            if self.username:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            smtp.quit()
        
        except (KeyboardInterrupt, SystemExit):
            raise
            
        except:
            self.handleError(record)
 
log = logging.getLogger('forward')

logging.basicConfig(
    filename="portforward.log",
    format="%(levelname)-10s %(asctime)s %(message)s",
    level=logging.INFO
    )
 
gm = TlsSMTPHandler(
    ("smtp.yandex.ru", 587), 
    'AntanasV@yandex.ru', 
    ['johnmnemonik.jm@gmail.com',''], 
    'ОШИБКА', 
    ('AntanasV@yandex.ru','im_who1984'))

gm.setLevel(logging.ERROR)
 
log.addHandler(gm)

import django
django.setup()

from client.models import IplistBack
from proxy.models import Proxy


def text(b):
    resp = int.from_bytes(b, byteorder='big', signed=False)
    return resp

def chunks(lst, count):
    """Группировка элементов последовательности по count элементов"""
    start = 0
    for i in range(count):
        stop = start + len(lst[i::count])
        yield lst[start:stop]
        start = stop

def iprw(ip):
    conn = ps.connect(dbname='django_db',host='217.23.7.73',user='john',password='password')
    cur = conn.cursor()
    
    try:
        sql = "INSERT INTO client_do (ip) VALUES (%s)"
        args_str = ','.join(cur.mogrify("(%s)", x) for x in ip)
        cur.execute("INSERT INTO client_do (ip) VALUES " + args_str)

        conn.commit()
    except Exception as exc:
        log.exception(exc)

    finally:
        cur.close()
        conn.close()




def results_ip_list_auth_type():
    try:
        conn = ps.connect(dbname='django_db',host='217.23.7.73',user='john',password='password')
        cur = conn.cursor()
        cur.execute("SELECT id,tp,usr,pswd,ip,port FROM proxy_proxyauth WHERE checkers = %s" % True)
        fetch = cur.fetchall()

        host_ip_and_port_and_user_pswd = set("{}://{}:{}@{}:{}".format(x[1],x[2],x[3],x[4],x[5]) for x in fetch)
    
    except Exception as exc:
        host_ip_and_port_and_user_pswd = None
        log.exception(exc)
    
    finally:
        cur.close()
        conn.close()
    
    return host_ip_and_port_and_user_pswd


class PortForwarder(StreamServer):
    "Главный класс наследуищий StreamServer"
    def __init__(self, listener, dest, ip, **kwargs):
        StreamServer.__init__(self, listener, **kwargs)
        self.dest = dest
        self.ip = set(ip) if ip else False

    def handle(self, source, address):
        """"
        хэндлер класса, который запускаеться при 
        любой попытки получить связя с сервером из вне
        """
        #address[0]
        try:
            # нужен список доступа по ip
            if self.ip:
                if address[0] not in self.ip:
                    source.send(b'\x05\xff')
                    return
            dest = create_connection(self.dest)
        except IOError as exc:
            #dest.close()
            return

        forwarders = (
            gevent.spawn(forward, source, dest, self),
            gevent.spawn(forward, dest, source, self)
        )

        
        gevent.joinall(forwarders)


    def close(self):
        if self.closed:
            sys.exit()
        else:
            StreamServer.close(self)


def forward(source, dest, server):
    "функция потока данных, запускаемая из класса выше"
    try:
        while True:
            try:
                data = source.recv(BUF_SIZE)

                if not data:
                    #dest.close()
                    break

                dest.sendall(data)

            except socket.error:
                break
                #dest.close()

    finally:
        source.close()
        dest.close()
        server = None


def start():
    dicts = []
    req = results_ip_list_auth_type()

    for i in req:
        if i.startswith('socks'):
            dicts.append(i)

    return dicts


def do_start_orm():
    try:
        i = IplistBack.objects.get(server='149.202.196.123')
    except IplistBack.DoesNotExist:
        log.info("список не обнаружен.......")
        return None, None, None
    except IplistBack.MultipleObjectsReturned:
        log.exception("модель имеет 2 записи")
        return None, None, None
    port = i.total()
    ipdos = i.ip
    try:
        ipdos = ipdos.split(' ')
    except AttributeError as exc:
        ipdos = None
    results = Proxy.objects.filter(i.dicts[0])
    count = results.count()
    s = min(len(port),count)
    ip_port = [(x.ip,int(x.port)) for x in results[:s]]
    port = port[:len(ip_port)]
    return port, ip_port, ipdos

def server_start(local_port, results, ipdos):
    with gevent.Timeout(60*20):
        try:
            log.info("генерация портов")                               
            servers = [PortForwarder('0.0.0.0:%s' % port, kw, ipdos) for port,kw in zip(local_port, results)]
            try:
                log.info("запуск")
                [server.start() for server in servers]
                gevent.wait()
            except gevent.socket.error as exc:
                #log.error("ошибка gevent.socket.error")
                #log.exception(exc)
                [server.stop() for server in servers]
            except KeyboardInterrupt:
                log.warning("прервано с клавиатуры")
                [server.stop() for server in servers]
                gevent.killall(servers)
        except gevent.Timeout:
            print("перезапуск сервера")
            [server.stop() for server in servers]
            gevent.sleep(10)
            return False


def deamon():
    while True:
        log.info("локальный порты ->local_port и удаленный ip/порт")
        local_port, results, ipdos = do_start_orm()

        if results:
            #распределяем на 5 ядер
            r1 = chunks(local_port, 5)
            r2 = chunks(results, 5)

            try:
                servers = [Process(target=server_start, args=(k,v,ipdos)) for k,v in zip(r1,r2)]
                [ser.start() for ser in servers]
                [ser.join() for ser in servers]
            except KeyboardInterrupt:
                [server.stop() for server in servers]


        else:
            log.info("спим 10 минуты")
            #спим 3 минуты
            time.sleep(60*10)
            continue
        

if __name__ == '__main__':
    log.info("запуск daemonize...")
    daemonize(stdout='/tmp/portforward.log',stderr='/tmp/portforwarderror.log')
    
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (65000, 100000))
    except:
        pass

    log.info("запуск deamon...")
    while True:
        try:
            deamon()
        except Exception as exc:
            print(exc)
            continue