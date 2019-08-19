sql5_write = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan, isp)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24, $25, $27)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$28, update=now();
	"""


update_geo = """
		UPDATE proxy_proxy
		SET 
		city=$1, country=$2,
		country_code=$3, lat=$4::float, 
		lon=$5::float, postal_code=$6,
		region=$7, domain=$8, 
		continent=$9, time_zone=$10,
		isp=$11, gmt=$12::float, time_region=$13
		WHERE ip=$14 AND ipreal=$15
	"""


sql5_write_isp = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan, isp)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24, $25, $26)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$27, update=now();
	"""




sql5_online_true = "UPDATE proxy_proxy \
			   SET checkers=$1::bool, update=now() \
			   WHERE ip=$2 AND port=$3 AND id=$4"



sql5_online_false = "UPDATE proxy_proxy \
			   SET checkers=$1::bool WHERE ip=$2 AND port=$3 AND id=$4"


sql4_write = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24,$25)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$26, update=now();
	"""


sql4_write_isp = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan, isp)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24, $25, $26)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$27, update=now();
	"""


sql4_online_true = "UPDATE proxy_proxy \
			   SET checkers=$1::bool, update=now(), anonymity=$2 \
			   WHERE ip=$3 AND port=$4 AND id=$5::integer"

sql4_online_false = "UPDATE proxy_proxy \
			   SET checkers=$1::bool, anonymity=$2 \
			   WHERE ip=$3 AND port=$4 AND id=$5::integer"

sql4_write_bp = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24,$25)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$26, update=now(), ipreal=$27, ip=$28;
	"""

sql4_write_bp_isp = """
		INSERT INTO proxy_proxy (
			worker_id, vendor_id, ip, port, ipreal,
			timeout, country, city, continent, country_code, 
			lat, lon, postal_code, region_code, time_zone,
			gmt, time_region, domain, region, typeproxy, 
			tp, anonymity, checkers, created, update, auth, scan, isp)
		VALUES (
				$1,$2,$3,$4,$5,
				$6::float,$7,$8,$9,$10,
				$11::float,$12::float,$13,$14,$15,
				$16::float,$17,$18,$19,$20,
				$21,$22,$23::bool, now(), now(), $24, $25, $26)
		ON CONFLICT (ipreal, vendor_id) DO UPDATE
			SET port=$27, update=now(), ipreal=$28, ip=$29;
	"""

sql4_write_bp_isp_new = """
		UPDATE proxy_proxy
		SET	ipreal=$1, isp=$2, country=$3, city=$4, continent=$5, 
			country_code=$6, lat=$7, lon=$8, postal_code=$9, update=now(),
		    time_zone=$10, gmt=$11, time_region=$12, domain=$13, region=$14,
		    anonymity=$15, checkers=$16
		WHERE ip=$17 AND port=$18 AND id=$19;  
		"""



sql4_online_bp_true = "UPDATE proxy_proxy \
			      SET checkers=$1::bool, update=now(), anonymity=$2, ipreal=$3\
			      WHERE ip=$4 AND port=$5 AND id=$6::integer"

sql4_online_bp_false = "UPDATE proxy_proxy \
			      SET checkers=$1::bool, anonymity=$2, ipreal=$3\
			      WHERE ip=$4 AND port=$5 AND id=$6::integer"



http_online_true = "UPDATE proxy_proxy \
			   SET checkers=$1::bool, update=now(), anonymity=$2 \
			   WHERE ip=$3 AND port=$4 AND id=$5"

http_online_false = "UPDATE proxy_proxy \
			   SET checkers=$1::bool, anonymity=$2 WHERE ip=$3 AND port=$4 AND id=$5"


__all__ = [
	'sql5_write', 'update_geo', 'sql5_write_isp', 
	'sql5_online_true', 'sql5_online_false', 'sql4_write', 
	'sql4_write_isp', 'sql4_online_true', 'sql4_online_false',
	'sql4_write_bp', 'sql4_write_bp_isp', 'sql4_write_bp_isp_new',
	'sql4_online_bp_true', 'sql4_online_bp_false', 'http_online_true', 
	'http_online_false'
	]