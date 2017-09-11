#-*-coding:utf-8-*-
import zerorpc
import gevent
from gevent.pool import Pool
from gevent import socket
from daemonize import daemonize

pool = Pool(300)

BASE_PROVIDERS = [
	'sbl.spamhaus.org',
	'xbl.spamhaus.org',
	'css.spamhaus.org',
	'pbl.spamhaus.org',
	'cbl.abuseat.org',
	'bl.spamcop.net',
	'b.barracudacentral.org',]

class AsyncCheck(object):
    def __init__(self, ip=None, providers=[], timeout=2000):
        self.ip = ip
        self.providers = providers
        self.timeout = timeout
        self.socket = socket

    def build_query(self, provider):
        reverse = '.'.join(reversed(self.ip.split('.')))
        return '{reverse}.{provider}.'.format(reverse=reverse, provider=provider)

    def query(self, provider):
    	black = []
        proxy = {}
        try:
            result = socket.gethostbyname(self.build_query(provider))
            black.append(provider)
        except socket.gaierror as exc:
        	result = False

        if black:
            proxy[self.ip] = black

        return proxy

    def check(self):
        jobs = [gevent.spawn(self.query, provider) for provider in self.providers]
        gevent.joinall(jobs)
        j = [job.value for job in jobs if job.value]

        return j

def dnsbl_check(ip):
    backend = AsyncCheck(ip=ip, providers=BASE_PROVIDERS)
    return backend.check()

class AsyncRPC(object):

	def dnsbl(self, host):
		jobs = [pool.spawn(dnsbl_check,url) for url in host]
		gevent.joinall(jobs)
		j = [job.value for job in jobs]
		dicts = {}
		for i in j:
			for y in i:
				if dicts.get(y.keys()[0],False):
					val = dicts[y.keys()[0]]
					dicts[y.keys()[0]] = val + y.values()[0]
				else:
					dicts[y.keys()[0]] = y.values()[0]
		return dicts

if __name__ == '__main__':
	daemonize(stdout='/tmp/rpc.log',stderr='/tmp/rpcerror.log')
	s = zerorpc.Server(AsyncRPC())
	s.bind("tcp://0.0.0.0:4242")
	s.run()