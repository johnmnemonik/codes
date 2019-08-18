import asyncio
from aiohttp import web
import asyncpg
from aiohttp_cache import cache, setup_cache

sql_auth     = "SELECT * FROM bc_auth WHERE online=True"
sql_ident    = "SELECT * FROM bc_ident WHERE online=True"
sql_ident_1  = "SELECT * FROM bc_ident_1 WHERE online=True"
sql_ident_2  = "SELECT * FROM bc_ident_2 WHERE online=True"
sql 		 = "SELECT * FROM bc WHERE online=True" 
sql_1 		 = "SELECT * FROM bc_1 WHERE online=True"
sql_2 		 = "SELECT * FROM bc_2 WHERE online=True"
sql_full 	 = "SELECT * FROM bc_1"
sql_full_two = "SELECT * FROM bc_2"


class ListSocks5(web.View):
	async def get(self):
		return web.Response(text="".join([x for x in open('_ip.txt', 'rt')]))
 


#@cache(expires=60*3)
async def handle_auth(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_auth)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)


#@cache(expires=60*3)
async def handle(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)


#@cache(expires=60*3)
async def handle_bc_1(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_1)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)

#@cache(expires=60*3)
async def handle_bc_2(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_2)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)


#@cache(expires=60*3)
async def handle_bc_full(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_full)
			res = " ".join(["{}:{}\t {}\t{}\n".format(x['loc_ip'],x['loc_port'],x['ipreal'],x['online']) for x in result])
			return web.Response(text=res)


#@cache(expires=60*3)
async def handle_bc_two(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_full_two)
			res = " ".join(["{}:{}\t {}\t{}\n".format(x['loc_ip'],x['loc_port'],x['ipreal'],x['online']) for x in result])
			return web.Response(text=res)


#@cache(expires=60*3)
async def handle_ident(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_ident)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)

#@cache(expires=60*3)
async def handle_ident_1(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_ident_1)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)


async def handle_ident_2(request):
	pool = request.app['pool']
	async with pool.acquire() as connection:
		async with connection.transaction():
			result = await connection.fetch(sql_ident_2)
			res = " ".join(["{}:{}\t {}\n".format(x['loc_ip'],x['loc_port'],x['ipreal']) for x in result])
			return web.Response(text=res)





async def init_app():
	app = web.Application()
	app['pool'] = await asyncpg.create_pool(
		database='proj', host='localhost', user='john', password='loginn')
	#setup_cache(app)

	app.router.add_route('GET', '/bcsocks5list.txt', handle)
	app.router.add_route('GET', '/bcauths.txt', handle_auth)
	app.router.add_route("GET", "/_ip.txt", ListSocks5)
	app.router.add_route("GET", "/ident.txt", handle_ident)
	app.router.add_route("GET", "/ident1.txt", handle_ident_1)
	app.router.add_route("GET", "/ident2.txt", handle_ident_2)
	app.router.add_route("GET", "/qwertyuikjhgfds.txt", handle_bc_1)
	app.router.add_route("GET", "/2w3e4r5tyuijnhbgvfd.txt", handle_bc_2)
	app.router.add_route("GET", "/bac1_full.txt", handle_bc_full)
	app.router.add_route("GET", "/bac2_two.txt", handle_bc_two)
	return app


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	app = loop.run_until_complete(init_app())
	web.run_app(app, host='0.0.0.0', port=40135)