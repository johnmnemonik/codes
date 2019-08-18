import datetime
import pytz


def gtm(tz):
	if not tz:
		return (None, None)
	try:
		local_tz = pytz.timezone(tz)
		now_utc = datetime.datetime.utcnow()
		now_utc = pytz.utc.localize(now_utc)
		local_time = now_utc.astimezone(local_tz)
		utcof = local_time.utcoffset()
		hours = utcof.total_seconds()//60//60
		return (hours, local_time)
	except Exception:
		return (None, None)
