import asyncio
import aiodns
import asyncpg
import logging
import time

from async_timeout import timeout

from settings import DNS, DSN
from fields import sql_query, sql_write
from providers import BASE_PROVIDERS



logging.basicConfig(
        filename = "blocklist.log",
        format = '%(asctime)s - %(name)s - %(levelname)s -%(lineno)s - %(message)s',
        level = logging.INFO
        )


class AsyncDNSBLACK:
    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.resolver = aiodns.DNSResolver(DNS)
        self.log = logging.getLogger("workers")
        self.provider = BASE_PROVIDERS
        self.sem = asyncio.Semaphore(500)
        self.sql_write = sql_write
        self.sql_query = sql_query
        self.black = {}
        self.dsn = DSN
        self._pool = self._loop.run_until_complete(
            asyncpg.create_pool(
                dsn=self.dsn,
                max_size=10,
                min_size=5,
                max_queries=1,
                loop=self._loop))

        self.queue_block = asyncio.Queue()
        self.queue_no_block = asyncio.Queue()


    async def async_build_query(self, ip):
        resurces = []
        for host in self.provider:
            reverse = '.'.join(reversed(ip.split('.')))
            resurces.append('{reverse}.{host}'.format(reverse=reverse, host=host))
        return resurces


    def build_query(self, ip):
        resurces = []
        for host in self.provider:
            reverse = '.'.join(reversed(ip.split('.')))
            resurces.append('{reverse}.{host}'.format(reverse=reverse, host=host))
        return resurces


    async def _read_db(self):
        async with self._pool.acquire() as con:
            try:
                res = await con.fetch(self.sql_query)
                return res
            except Exception as exc:
                logging.exception(exc)


    async def _write_db(self, ipreal, black):
        async with self._pool.acquire() as con:
            try:
                await con.execute(self.sql_write, black, ipreal)
            except Exception as exc:
                logging.exception(exc)


    async def _write_db_many(self, sql, obj):
        async with self._pool.acquire() as con:
            try:
                await con.executemany(self.sql_write, obj)
            except ConnectionDoesNotExistError:
                logging.info("ошибка в бд в execute")
            except TooManyConnectionsError as exc:
                logging.exception(exc)
            except Exception as exc:
                logging.exception(exc)

    async def check(self, ip):
        values = []
        provider = await self.async_build_query(ip)
        async with self.sem:
            for i in provider:
                async with timeout(10):
                    try:
                        ips = await self.resolver.query(i, 'A')
                        values.append('.'.join(i.split('.')[4:]))
                    except aiodns.error.DNSError:
                        pass
                    except asyncio.TimeoutError as exc:
                        logging.exception(exc)
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        logging.info(ips)
                        logging.exception(exc)


        if values:
            black = " ".join(blk for blk in values)
            await self.queue_block.put((black, ip))


    async def _bootstrap(self, loop):
        data = await self._read_db()
        logging.info(len(data))
        data = [ip['ipreal'] for ip in data if ip['ipreal'] is not None]
        logging.info("всего на блек скан %s", len(data))
        tasks = [loop.create_task(self.check(ip)) for ip in data]
        for task in asyncio.as_completed(tasks):
            try:
                res = await task
            except asyncio.CancelledError:
                pass

        logging.info("всего в блек %s", self.queue_block.qsize())
        logging.info("запись")
        
        writer_block = []
        for i in range(self.queue_block.qsize()):
            writer_block.append(self.queue_block.get_nowait())
        await self._write_db_many(self.sql_write, writer_block)



    def run(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._bootstrap(loop))
        except asyncio.TimeoutError:
            logging.info('время вышло')
        finally:
            loop.run_until_complete(self._pool.close())


def main():
    block = AsyncDNSBLACK()
    block.run()
    del block


if __name__ == '__main__':
    while True:
        main()
        time.sleep(60*60)