#!/home/john/.venv/bin/python 
import asyncio
import aiohttp
import aiofiles

from aiohttp.web import Application, Response, StreamResponse, run_app

async def index(request):
    peername = request.transport.get_extra_info('peername')
    if peername is not None:
        host, port = peername
    return Response(body=bytes('{0}'.format(host),'utf8'))

async def filesresp(request):
    response = StreamResponse()
    response.enable_chunked_encoding()
    response.content_type = 'application/octet-stream'
    response.start(request)
    async with aiofiles.open("files.zip",mode="rb") as f:
        content = await f.read()
        response.write(content)
        await response.drain()


async def metainfo(request):
    try:
        ip = request.transport.get_extra_info('peername')[0]
        rem = request.headers['X-Forwarded-For']
    except Exception:
        ip = request.transport.get_extra_info('peername')[0]
        rem = False

    if rem:
        return Response(body=bytes('{0} anonymity half'.format(ip),'utf8'))
    
    return Response(body=bytes('{0} full anonymity'.format(ip),'utf8'))


async def detail(request):
    try:
        return Response(text=str(request.headers['X-Forwarded-For']))
    except Exception:
        text = '{0} full anonymity'.format(request.transport.get_extra_info('peername')[0])
        return Response(text=text)



_app = Application()
_app.router.add_route('GET','/',index)
_app.router.add_route('GET','/metainfo',metainfo)
_app.router.add_route('GET','/full', detail)
_app.router.add_route('GET','/files',filesresp)
_app.router.add_static('/static','media/')