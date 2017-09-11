#-*- coding:utf-8 -*-
#!/usr/bin/env python
import os
import zerorpc
import zmq
import zmq.auth
import gevent
from gevent.pool import Pool
import sys, os, time
from multiprocessing import Process


SECURE = False

pool = Pool(100)

base_dir = os.path.dirname(__file__)
keys_dir = os.path.join(base_dir, 'certificates')
public_keys_dir = os.path.join(base_dir, 'public_keys')
secret_keys_dir = os.path.join(base_dir, 'private_keys')


def black():
    urls = [
        'tcp://*.*.*.*:50001',
        'tcp://*.*.*.*:50001',
        'tcp://*.*.*.*:50001',
        'tcp://*.*.*.*:50001',
        'tcp://*.*.*.*:50001',
    ]

    client = zerorpc.Client(timeout=60*100,heartbeat=60*100)
    if SECURE:
        ctx = zerorpc.Context.get_instance()
        zmq_socket = client._events._socket

        print("установка безопасного соединения")
        # Нам нужны два сертификата, один для клиента и один для
        # сервер. Клиент должен знать открытый ключ сервера
        client_secret_file = os.path.join(secret_keys_dir, "client.key_secret")
        client_public, client_secret = zmq.auth.load_certificate(client_secret_file)
        zmq_socket.curve_secretkey = client_secret
        zmq_socket.curve_publickey = client_public

        server_public_file = os.path.join(public_keys_dir, "server.key")
        server_public, _ = zmq.auth.load_certificate(server_public_file)
    
        zmq_socket.curve_serverkey = server_public
        [zmq_socket.connect(url) for url in urls]
 
    else:
        [client.connect(url) for url in urls]

    return client

    
def main():
    client = black()
    blacklist = [x for x in Proxy.objects.values_list(
        'ipreal', flat=True).filter(checkers=True)]
    if blacklist:
        results = chunks(blacklist, 5)
        jobs = [gevent.spawn(client.dnsbl, res) for res in results]
        gevent.joinall(jobs)
    client.close()



if __name__ == "__main__":
    t = Process(target=main)
    t.start()