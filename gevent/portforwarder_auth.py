#-*-coding:utf-8 -*-
import sys
import os
import random
import logging
from struct import unpack, pack

import gevent
from gevent import select
from gevent.server import StreamServer
from gevent.socket import create_connection
from dns import resolver
from redis import Redis

from ._rev import IP2Location

obj = IP2Location.IP2Location()
obj.open("/home/john/proxyproject/pay/geo/geo.bin");

logging.basicConfig(
    filename='portforward_auth.log',
    format="%(levelname)-10s %(lineno)d %(asctime)s %(lineno)s %(message)s",
    level=logging.INFO
)

logging.getLogger(__name__)


class PortForwarder(StreamServer):
    def __init__(self, listener, dest, user, passwd, domain ,**kwargs):
        StreamServer.__init__(self, listener, **kwargs)
        self.dest = dest
        self.user = user
        self.passwd = passwd
        self.domain = domain
        self.geo = obj.get_all(dest[0])
        self.local_dns = False
        self.city = self.geo.city.decode("utf-8")
        self.country = self.geo.country_long.decode("utf-8")
        self.red = Redis(host="127.0.0.1",password='l1984loginn')
        
        try:
            iplist,citylist = eval(self.red.get(self.country))
        except TypeError:
            iplist = ['8.8.8.8', '8.8.4.4']
            
        total = [gevent.spawn(ping, ip) for ip in iplist[:10]]
        gevent.joinall(total)
        value = [x.value for x in total if x.value]
        
        if value:
            self._dns = [random.choice(value), random.choice(value)]
        else:
            self._dns = ['8.8.8.8','8.8.4.4']
        try:
            self.res = resolver.Resolver()
            self.res.nameservers = self._dns
            self.res.query(self.domain,"A")
        except Exception:
            pass


    def check_auth(self, data):
        ULEN = data[1:2]
        ULEN = unpack(">b",ULEN)[0]
        User = data[2:2+ULEN]
        PLEN = data[2+ULEN:3+ULEN]
        PLEN = unpack(">b",PLEN)[0]
        Pass = data[3+ULEN:3+ULEN+PLEN]
        if User.decode() == self.user and Pass.decode() == self.passwd:
            return True



    def handle(self, source, address):
        try:
            data = source.recv(1024)
        except ConnectionResetError:
            return
        if data == b"\x05\x01\x00":
            try:
                source.sendall(b'\x05\xff')
                source.close()
            except ConnectionRefusedError:
                pass
            return
        try:
            source.sendall(b'\x05\x02')
        except ConnectionResetError:
            return
        try:
            data = source.recv(1024)
        except ConnectionRefusedError:
            source.close()
            return
        if not data:
            return
        
        if self.check_auth(data):
            source.sendall(b"\x05\x00")
        else:
            source.sendall(b'\x05\xff')
            source.close()
            return
        try:
            dest = create_connection(self.dest, timeout=8)
        except (socket.timeout,ConnectionRefusedError, OSError):
            source.close()
            return
        dest.sendall(b"\x05\x01\x00")
        try:
            data = dest.recv(1024)
        except Exception:
            dest.close()
            return

        forwards = [
            gevent.spawn(forwarders, source, dest, self),
            gevent.spawn(forwarders, dest, source, self)
            ]
            
        gevent.joinall(forwards)

    def close(self):
        if self.closed:
            pass
        else:
            StreamServer.close(self)

def forwarders(source, dest, server):
    try:
        while True:
            try:
                data = source.recv(1024)
                if not data:
                    break
                dest.sendall(data)
            except socket.error:
                break
    finally:
        source.close()
        dest.close()
        server = None

def start(user, passwd, source, dest, domain):
    server = PortForwarder(source, dest, user, passwd, domain)
    server.serve_forever()


def main(source, dest, domain=None):
    user = "user"
    passwd = "passwd"
    server = PortForwarder(source, dest, user, passwd, domain)
    server.serve_forever()



if __name__ == '__main__':
    dest = ('24.72.191.90', 35923)
    source = '0.0.0.0:1026'
    domain = 'netservicos.com.br'
    main(source, dest, domain)

