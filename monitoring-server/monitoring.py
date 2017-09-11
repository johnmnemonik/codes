#-*- coding:utf-8 -*-
import time
import psutil

def timeload(n):
	start = time.time()
	bytes_sent = psutil.net_io_counters(pernic=True)['eth0'].bytes_sent
	bytes_recv = psutil.net_io_counters(pernic=True)['eth0'].bytes_recv
	time.sleep(n)
	end = time.time()
	bytes_sent_f = psutil.net_io_counters(pernic=True)['eth0'].bytes_sent
	bytes_recv_f = psutil.net_io_counters(pernic=True)['eth0'].bytes_recv

	total_send = bytes_sent_f - bytes_sent
	total_recv = bytes_recv_f - bytes_recv
	return (total_send, total_recv)


def net():
	n = 5
	total_send,total_recv = timeload(n)
	t_s = total_send / 1024. / 1024 * 8 / n
	t_r = total_recv / 1024. / 1024 * 8 / n
	print("исходящий %0.3f Mb/s" % t_s)
	print("входящий %0.3f Mb/s" %t_r)
	load = psutil.cpu_percent(interval=1, percpu=True)
	total = sum(load) / psutil.cpu_count()
	print("общий % загрузки всех CPU {}".format(total))
	mem = psutil.virtual_memory()
	percent = mem.percent
	print("общий % загрузки ОЗУ {}".format(percent))

if __name__ == "__main__":
	net()