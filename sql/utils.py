#-*-coding:utf-8 -*-
import os
import time
import datetime
import logging

from django.utils import timezone
import psycopg2 as ps
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import TransactionRollbackError


logging.basicConfig(format = u'%(filename)s[STRING:%(lineno)d]# %(levelname)-8s \
		[%(asctime)s]  %(message)s',level = logging.DEBUG, filename = u'/home/john/proxy.log')



def black_save_old(dicts):
	conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
	
	with conn:
		with conn.cursor() as cur:
			val = [(v,k) for k,v in dicts.items()]
			sql = "UPDATE proxy_proxy SET blacklist=%s WHERE ip = %s"

			args_str = ','.join(cur.mogrify("(%s)", x) for x in val)
			cur.execute("INSERT INTO client_do (ip) VALUES " + args_str)

			cur.executemany(sql,val)
	

	conn.close()

def black_save(dicts):
	conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
	cur = conn.cursor()
	val = set([(v,k) for k,v in dicts.items()])


	try:
		while True:
			try:
				t1 = time.time()
				cur.executemany("UPDATE proxy_proxy SET blacklist=(%s) WHERE ip = (%s)", val);
				print("{}".format(time.time() - t1))
				cur.close()
				break

			except TransactionRollbackError as exc:
				print("deadlock прошло {} сек, с момента запуска".format(time.time() - t1))
				conn.rollback()
				time.sleep(30)
				continue
	
	except KeyboardInterrupt:
		conn.close()
	
	finally:
		conn.commit()
		conn.close()

def del_db_orm():
	delta = timezone.now() - datetime.timedelta(minutes=120)
	objall = Proxy.objects.filter(
			checkers=False,created__lte=delta)
	while True:
		try:
			objall.delete()
			break
		except:
			time.sleep(60*2)
			continue
	objall = Proxy.objects.filter(checkers=False,created__isnull=True)
	
	while True:
		try:
			objall.delete()
			break
		except:
			time.sleep(60*2)
			continue



def del_db():
	conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
	delta = timezone.now() - datetime.timedelta(minutes=120)
	s1 = 0
	s2 = 0

	with conn:
		with conn.cursor() as cur:

			msg = "DELETE FROM proxy_proxy WHERE checkers = %s AND update <= '%s'" % (False,delta)
			while True:
				try:
					cur.execute(msg)
					s1 = cur.rowcount
					break
				except TransactionRollbackError:
					conn.rollback()
					continue
			
			msg = """
			DELETE FROM proxy_proxy WHERE
			checkers = %s AND created <= '%s' 
			AND update IS NULL;""" % (False,delta)
			
			while True:
				try:
					cur.execute(msg)
					s2 = cur.rowcount
					break

				except TransactionRollbackError:
					conn.rollback()
					continue
		
	conn.close()
	return (s1, s2)

def del_dubli():
	sql = """
		DELETE FROM proxy_proxy WHERE id NOT in (
		SELECT MIN(id) FROM proxy_proxy 
		GROUP BY ipreal)
		"""
	conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
	cur = conn.cursor()
	conn.commit()
	try:
		cur.execute(sql)
	except Exception as exc:
		pass
	finally:
		cur.close()
		conn.commit()


def del_db_auth():
	conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
	
	with conn:
		with conn.cursor() as cur:

			while True:
				try:
					cur.execute("DELETE FROM proxy_proxyauth WHERE checkers = %s" % False)
					s1 = cur.rowcount
					break
				
				except TransactionRollbackError:
					conn.rollback()
					continue
		
	conn.close()
	return s1



def ipwrite(iplist):
    try:
        conn = ps.connect(dbname='*********',host='*******',user='*****',password='*****')
        conn.autocommit = True
        cur = conn.cursor()
        
        args_str = ','.join(cur.mogrify("%s", x) for x in iplisst)

        #супер быстро 80000 за 3 сек.
        cur.execute("DELETE FROM client_do WHERE ip in (" + args_str + ")")


        #conn.commit()
        
    except Exception as exc:
        log.exception(exc)

    finally:
        cur.close()
        conn.close()