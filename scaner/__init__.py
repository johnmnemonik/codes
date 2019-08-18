#from socks5_geo import AsyncSock5
#from socks5_online import AsyncSock5Online

#from socks4_raw import AsyncSock4

from .example import func
from .fields import *
from .geo_parser import parser
from .geo_parser_bp import parser_bp
from .geo_parser_mixmand import parser_maxminddb
from .geo_parser_bp_mixmand import parser_online, parser_maxminddb_bp

from .geo_socks_no_scan import AsyncNoSock5

from .http_geo import AsyncHttpGeo
from .http_online import AsyncHttpOnline

from .socks4_geo import AsyncSock4Geo
from .socks4_geo_bp import AsyncSock4GeoBp
from .socks4_online import AsyncSock4Online
from .socks4_online_bp import AsyncSock4OnlineBp

from .socks5_geo import AsyncSock5Geo, do_start, _start_sock5, _start_sock5_online
from .socks5_geo_bp import AsyncSock5GeoBp
#from .socks5_online import AsyncSock5Online
from .socks5_online_bp import AsyncSock5OnlineBp

__all__ = [
	'func',
	fields.__all__,
	'farser',
	'parser_bp',
	parser_maxminddb,
	parser_online,
	parser_maxminddb_bp,
	AsyncNoSock5,
	AsyncHttpGeo,
	AsyncHttpOnline,
	AsyncSock4Geo,
	AsyncSock4GeoBp,
	AsyncSock4Online,
	
	AsyncSock5Geo,
	AsyncSock5GeoBp,
	AsyncSock5OnlineBp,
]


def sock5():
	res = do_start()
	for obj in res:
		_start_sock5(obj)

	_start_sock5_online()

