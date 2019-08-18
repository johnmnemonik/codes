#-*-coding:utf-8-*-
import os
import time

import gevent
from gevent import socket
from gevent.pool import Pool
from gevent.queue import Queue

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
import zerorpc
import logging


logging.basicConfig(
        filename = "workers.log",
        format = '%(asctime)s - %(name)s - %(levelname)s -%(lineno)s - %(message)s',
        level = logging.INFO
        )

logger = logging.getLogger("workers")



from blk import AsyncCheck, dnsbl_check, dnsbl_check_auth, BASE_PROVIDERS as providers
from daemonize import daemonize
from utils import black_save, black_save_auth

SECURE = False

base_dir = os.path.dirname(__file__)
keys_dir = os.path.join(base_dir, 'certificates')
public_keys_dir = os.path.join(base_dir, 'public_keys')
secret_keys_dir = os.path.join(base_dir, 'private_keys')


pool = Pool(100)

def build_query(ip, provider):
    reverse = '.'.join(reversed(ip.split('.')))
    return '{reverse}.{provider}.'.format(reverse=reverse, provider=provider)

def optimizator_auth(j):
    dicts = {}
    for i in j:
        for x in i:
            if dicts.get(x.keys()[0],False):
                val = dicts[x.keys()[0]]
                dicts[x.keys()[0]] = val + x.values()[0]
            else:
                dicts[x.keys()[0]] = x.values()[0]
    
    val = [{k:" ".join(v)} for k,v in dicts.items()]
    dicts = {}
    for x in val:
        dicts.update(x)

    return dicts

def optimizator(j):
    dicts = {}
    for i in j:
        for x in i:
            try:
                if dicts.get(list(x.keys())[0],False):
                    val = dicts[list(x.keys())[0]]
                    dicts[list(x.keys())[0]] = val + list(x.values())[0]
                else:
                    dicts[list(x.keys())[0]] = list(x.values())[0]
            except TypeError as ex:
                logger.info(ex)
    val = [{k:" ".join(v)} for k,v in dicts.items()]
    dicts = {}
    for x in val:
        dicts.update(x)

    return dicts

def query(ip, provider):
    black = []
    proxy = {}
    try:
        result = socket.gethostbyname(build_query(ip,provider))
        black.append(provider)
    except socket.gaierror as exc:
        result = False

    if black:
        proxy[ip] = black

    return proxy

def check(ip):
    jobs = [pool.spawn(query, ip, provider) for provider in providers]
    gevent.joinall(jobs)
    j = [job.value for job in jobs if job.value]
    return j

class Worker(object):
    """Главный класс воркеров"""
    def dnsbl(self, host):
        logger.info('запуск')
        jobs = [pool.spawn(dnsbl_check,url) for url in host]
        gevent.joinall(jobs)
        j = [job.value for job in jobs]
        dicts = optimizator(j)
        logger.info("запись db")
        black_save(dicts)
        logger.info("END")


    def ping(self):
        print("PONG")
        return "PONG {}".format("10")

def run_server():
    srv = zerorpc.Server(Worker(),heartbeat=60*100)
    if SECURE:
        ctx = zerorpc.Context.get_instance()
        auth = ThreadAuthenticator(ctx)
        auth.start()

        # доступ с определынных ip'ов
        auth.allow('0.0.0.0')

        # Скажите аутентификатору использовать сертификат из каталога
        auth.configure_curve(domain='*', location=public_keys_dir)
        zmq_socket = srv._events._socket

        server_secret_file = os.path.join(secret_keys_dir, "server.key_secret")
        server_public, server_secret = zmq.auth.load_certificate(server_secret_file)

        zmq_socket.curve_secretkey = server_secret
        zmq_socket.curve_publickey = server_public
        zmq_socket.curve_server = True

    srv.bind('tcp://0.0.0.0:50001')

    try:
        logger.info("RUN")
        srv.run()
    
    except KeyboardInterrupt:
        srv.stop()


    except Exception as exc:
        logger.extension(exc)

if __name__ == '__main__':
    while True:
        try:
            run_server()
        except Exception as exc:
            logger.exception(exc)
            continue