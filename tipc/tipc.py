import socket
import multiprocessing
import threading

'''
+ Адреса выражаются как (addr_type, v1, v2, v3 [, scope]);
+ где addr_type может быть одним из:
+ TIPC_ADDR_NAMESEQ, TIPC_ADDR_MCAST, TIPC_ADDR_NAME и TIPC_ADDR_ID;
+ и scope может быть одной из следующих:
+ TIPC_ZONE_SCOPE, TIPC_CLUSTER_SCOPE и TIPC_NODE_SCOPE.
+
+
+ Значение v1, v2 и v3 зависит от значения addr_type:
+
+ if addr_type - TIPC_ADDR_NAME:
+ v1 - тип сервера
+ v2 - это идентификатор порта
+ v3 игнорируется
+------------------------------------------------------
+ if addr_type - TIPC_ADDR_NAMESEQ или TIPC_ADDR_MCAST:
+ v1 - тип сервера
+ v2 - номер нижнего порта
+ v3 - номер верхнего порта
+------------------------------------------------------
+ if addr_type - TIPC_ADDR_ID:
+ v1 - узел
+ v2 является ссылкой
+ v3 игнорируется
+
+ Даже при игнорировании v3 должен присутствовать и быть целым числом.
'''


TIPC_STYPE = 2000 # указывает на группу / тип сервера
TIPC_LOWER = 200  # минимальный начало порта
TIPC_UPPER = 210  # максимальный конец порта

TIPC_STYPE_M = 3000


def server2():
	srv = socket.socket(socket.AF_TIPC, socket.SOCK_STREAM)
	srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	srvaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, 555, 0)
	srv.bind(srvaddr)
	srv.listen(5)
	cli, addr = srv.accept()
	while True:
		msg = cli.recv(1024)
		print(msg)
		if msg == b"end":
			cli.close()
			break
		print("сервер: ", msg)
		msg = msg.decode("latin-1").upper()
		cli.sendall(msg.encode("latin-1"))

	srv.close()


def client2():
	sock = socket.socket(socket.AF_TIPC, socket.SOCK_STREAM)
	#sendaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, TIPC_LOWER + int((TIPC_UPPER - TIPC_LOWER) / 2), 0)
	sendaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, 555, 0)
	print(sendaddr)
	sock.connect(sendaddr)
	sock.sendall(b"Hali-Gali")
	data = sock.recv(1024)
	print("клиент: ", data)
	sock.sendall(b"end")
	sock.close()


def server1():
	srv = socket.socket(socket.AF_TIPC, socket.SOCK_RDM)
	srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	srvaddr = (socket.TIPC_ADDR_NAMESEQ, TIPC_STYPE, TIPC_LOWER, TIPC_UPPER)
	srv.bind(srvaddr)
	while True:
		msg, recvaddr = srv.recvfrom(1024)
		if msg == b"end":
			break
		print("сервер: ", msg)
		msg = msg.decode("latin-1").upper()
		srv.sendto(msg.encode("latin-1"), recvaddr)

	srv.close()


def client1():
	sock = socket.socket(socket.AF_TIPC, socket.SOCK_RDM)
	#sendaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, TIPC_LOWER + int((TIPC_UPPER - TIPC_LOWER) / 2), 0)
	sendaddr = (socket.TIPC_ADDR_NAMESEQ, TIPC_STYPE_M, TIPC_LOWER, TIPC_UPPER, 0)
	sock.sendto(b"Hello", sendaddr)
	data, recvaddr = sock.recvfrom(1024)
	print("клиент: ", data)
	sock.sendto(b"end", recvaddr)
	#data = sock.recvfrom(1024)
	#sock.close()

	sock = socket.socket(socket.AF_TIPC, socket.SOCK_RDM)
	sendaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, TIPC_LOWER + int((TIPC_UPPER - TIPC_LOWER) / 2), 0)
	#sendaddr = (socket.TIPC_ADDR_NAME, TIPC_STYPE, TIPC_LOWER, TIPC_UPPER, 0)
	sock.sendto(b"Hi", sendaddr)
	data, recvaddr = sock.recvfrom(1024)
	print("клиент: ", data)
	sock.sendto(b"end", recvaddr)
	#data = sock.recvfrom(1024)
	sock.close()


def main2():
	srv = threading.Thread(target=server2)
	cli = threading.Thread(target=client2)
	srv.start()
	cli.start()
	srv.join()
	cli.join()


def main1():
	srv = threading.Thread(target=server1)
	cli = threading.Thread(target=client1)
	srv.start()
	cli.start()
	srv.join()
	cli.join()


if __name__ == '__main__':
	main1()
	#main2()

