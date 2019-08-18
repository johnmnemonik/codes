# encoding: utf-8
#!/usr/bin/env python
import sys
import os
import time
import gc
from multiprocessing import Process, current_process, cpu_count
import logging
import logging.handlers
import asyncio
import resource
import functools
from struct import unpack

import timeout_decorator

from daemonize import daemonize


sys.path.insert(0, os.path.dirname("../" + __file__))
sys.path.append('/home/john/proxyproject/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'proxyproject.settings'

import django
django.setup()

from client.models import IplistBack
from proxy.models import Proxy

logging.basicConfig(
    filename="portforward.log",
    format="%(levelname)-10s %(asctime)s %(message)s",
    level=logging.INFO
    )

log = logging.getLogger('forward')

# связь с реальным сервером,куда происходит проброс
class ForwardedConnection(asyncio.Protocol):
    def __init__(self, peer, ip=None):
        self.peer = peer
        self.transport = None
        self.buff = set()
        self.ip = set(ip) if ip else None

    # вызываеться когда происходит соединение
    def connection_made(self, transport):
        self.transport = transport

        if len(self.buff) > 0:
            self.transport.writelines(self.buff)
            self.buff = set()
    
    # при получении данных
    def data_received(self,data):
        self.peer.write(data)
        
        
    def connection_lost(self, exc):
        #****[закрыли]****"
        self.peer.close()

# Экземпляр PortForwarder будет создан для каждого клиента.
class PortForwarder(asyncio.Protocol):
    def __init__(self, dsthost, dstport, ip=None, portallow=None):
        self.dsthost = dsthost
        self.dstport = dstport
        self.ip = set(ip) if ip else None
        self.portallow = set(portallow) if portallow else None
    
    # 1 вызываеться когда происходит соединение к нам
    def connection_made(self, transport):
        #asyncio.sleep(0.1)
        peername = transport.get_extra_info('peername')
        sock = transport.get_extra_info('socket')
        
        if self.ip:
            if peername[0] not in self.ip:
                sock.send(b"\x05\xff")

        self.transport = transport
        loop = asyncio.get_event_loop()
        self.fcon = ForwardedConnection(self.transport, self.ip)
        #проброс на сервер
        asyncio.async(loop.create_connection(lambda: self.fcon, self.dsthost, self.dstport))

    # при получении данных от нас
    def data_received(self, data):
        if self.portallow:
            if data.startswith(b'\x05\x01\x00\x01'):
                if str(unpack('!BBBBBBBBH',data)[-1]) not in self.portallow:
                    self.connection_lost(None)
        
        if self.fcon.transport is None:
            self.fcon.buff.add(data)
        else:
            self.fcon.transport.write(data)
            
    def connection_lost(self, exc):
        try:
            self.fcon.transport.close()
            self.fcon.buff = set()
        except:
            pass



@timeout_decorator.timeout(60*15, use_signals=False)
def server_start(local_port, results, ipdos, portallow):
    loop = asyncio.get_event_loop()
    log.info("стартуем")

    ser = [functools.partial(PortForwarder, kw[0],kw[1], ipdos, portallow) for port,kw in zip(local_port, results)]
    coro = [loop.create_server(s,"0.0.0.0", port) for s,port in zip(ser,local_port)]
    asyncio.gather(*coro)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        sys.stderr.flush()
        loop.stop()
        raise SystemExit("exit")  
    except timeout_decorator.TimeoutError:
        sys.stderr.flush()
        log.exception("время кончилось")
        return
    finally:
        loop.stop()

def main():
    while True:
        try:
            local_port, results, ipdos, portallow = "func распаковывает порты/ip/ip доступа и портв доступа"
            if results:
                r1 = chunks(local_port, 4)
                r2 = chunks(results, 4)
                try:
                    servers = [Process(
                        target=server_start, args=(
                            k,v,ipdos,portallow)) for k,v in zip(r1,r2)]
                    for x in servers:
                        x.start()
                    for x in servers:
                        x.join()
                except Exception as e:
                    pass
            else:
                time.sleep(60*10)
                continue
        except timeout_decorator.timeout_decorator.TimeoutError as e:
            log.info("перезапуск")
            gc.collect()
            continue

if __name__ == '__main__':
    daemonize(stdout='/tmp/portforward.log',stderr='/tmp/portforwarderror.log')
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (100000, 100000))
    except Exception:
        pass

    main()
