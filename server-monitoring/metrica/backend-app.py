import argparse
import asyncio
import json
import pickle
from asyncio import get_event_loop, gather, sleep, CancelledError
from random import randint, uniform
from datetime import datetime as dt
from datetime import timezone as tz
from contextlib import suppress
import psutil

import zmq, zmq.asyncio
from zmq.auth.asyncio import AsyncioAuthenticator

from signal import SIGINT

import netifaces
from hurry.filesize import size

from conf.settings import worker

# zmq.asyncio.install()  ￼
ctx = zmq.asyncio.Context()

lock = asyncio.Lock()

# получаем interface сервера
# _get_interface позже нужно 
# удалить, так как не используется. 

def _get_interface():
    for interf in netifaces.interfaces():
        if not interf.startswith('lo'):
            return interf


async def func_net_speed(num, loop):
    # мониторин скорости сети
    bytes_sent = psutil.net_io_counters().bytes_sent
    bytes_recv = psutil.net_io_counters().bytes_recv
    await sleep(num)
    total_send = (psutil.net_io_counters().bytes_sent - bytes_sent)
    total_recv = (psutil.net_io_counters().bytes_recv - bytes_recv)
    return (total_send, total_recv)


dic = {}
dic['scan_status'] = "---"
dic['scan_type']   = "---"
dic['scan_name']   = "---"
dic['scan_start']  = "---"
dic['scan_end']    = "---"
dic['scan_start_next'] = "---"


async def stats_reporter(loop):
    global dic
    p = psutil.Process()
    sock = ctx.socket(zmq.PUB)
    sock.setsockopt(zmq.LINGER, 1)
    sock.connect('tcp://localhost:5555')
    # suppress подавления исключения
    with suppress(CancelledError):
        while True:
            res = await func_net_speed(1, loop)
            await sock.send_json(dict(
                worker="127.0.0.1",
                timestamp=dt.now(tz=tz.utc).isoformat(),
                cpu=p.cpu_percent(),
                proc=__file__,
                mem=size(p.memory_full_info().rss),
                mem_int=p.memory_full_info().rss / 1024 / 1024,
                established=len([obj.status for obj in psutil.net_connections() if obj.status == 'ESTABLISHED']),
                ram=size(psutil.virtual_memory().active),
                bytes_send=res[0],
                bytes_recv=res[1],
                speed_send=size(res[0]),
                speed_recv=size(res[1]),
                scan_status=dic['scan_status'],
                scan_type=dic['scan_type'],
                scan_name=dic['scan_name'],
                scan_start=dic['scan_start'],
                scan_end=dic['scan_end'],
                scan_start_next=dic['scan_start_next']
            ))
            await sleep(3)
    sock.close()



async def echo_unix_server(reader, writer):
    global dic
    async with lock:
        while True:
            if reader.at_eof():
                print("exit")
                break
            data = await reader.read(65000)
            if data:
                dic = pickle.loads(data)
            if not data:
                break
        writer.close()



# тест на утечку памяти
# для вывода графика

async def main(args):
    leak = []
    with suppress(CancelledError):
        while True:
            sum(range(randint(1_000, 10_000_000)))
            await sleep(uniform(0, 1))
            leak += [0] * args.leak


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--color', type=str)
    parser.add_argument('--leak', type=int, default=0)
    args = parser.parse_args()
    loop = get_event_loop()
    loop.add_signal_handler(SIGINT, loop.call_soon, loop.stop)

    server = asyncio.start_unix_server(echo_unix_server, path="server.sock", loop=loop)
    unix = loop.run_until_complete(server)
    tasks = loop.run_until_complete(stats_reporter(loop))
    loop.run_forever()
    
    for t in asyncio.Task.all_tasks():
        t.cancel()
    loop.run_until_complete(tasks)
    ctx.term()