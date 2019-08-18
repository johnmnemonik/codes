from settings import IP

sql_query = """
	SELECT p.ipreal FROM proxy_proxy as p, proxy_worker as w
	WHERE p.worker_id = w.id AND checkers = True AND w.ip = '%s';""" % IP

sql_write = "UPDATE proxy_proxy SET blacklist=$1 WHERE ipreal=$2"
