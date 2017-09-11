import datetime
import json

from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from proxy.models import Proxy, TimeSet, CountryProxy, CityProxy



def ajax_continent(request):
	if request.method == 'GET':
		query = request.GET.get('term', '')
		if query:
			continent = [x.continent for x in Proxy.objects.filter(
				Q(checkers=True) & Q(continent__istartswith=query))]
			continent = list(set(continent))
		else:
			continent = ''
		data = json.dumps(continent)
		mimetype = 'application/json'
	else:
		data = 'fail'
		mimetype = 'application/json'
	return HttpResponse(data, mimetype)

def ajax_zone(request):
	if request.method == 'GET':
		query = request.GET.get('term', '')
		if query:
			time_zone = [x.time_zone for x in Proxy.objects.filter(
				Q(checkers=True) & Q(time_zone__icontains=query))]
			time_zone = list(set(time_zone))
		else:
			time_zone = ''
		data = json.dumps(time_zone)
		mimetype = 'application/json'
	else:
		data = 'fail'
		mimetype = 'application/json'
	return HttpResponse(data, mimetype)

def ajax_code_country(request):
	if request.method == 'GET':
		query = request.GET.get('term', '')
		if query:
			country_code = [x.country_code for x in Proxy.objects.filter(
				Q(checkers=True) & Q(country_code__istartswith=query))]
			country_code = list(set(country_code))
		else:
			country_code = ''
		data = json.dumps(country_code)
		mimetype = 'application/json'
	else:
		data = 'fail'
		mimetype = 'application/json'
	return HttpResponse(data, mimetype)


def ajax_code_postal(request):
	if request.method == 'GET':
		query = request.GET.get('term', '')
		if query:
			postal_code = [x.postal_code for x in Proxy.objects.filter(
				Q(checkers=True) & Q(postal_code__istartswith=query))]
			postal_code = list(set(postal_code))
		else:
			postal_code = ''
		data = json.dumps(postal_code)
		mimetype = 'application/json'
	else:
		data = 'fail'
		mimetype = 'application/json'
	return HttpResponse(data, mimetype)

#country list
def ajax_country(request):
	if request.is_ajax():
		country_id = request.GET.get('country', None)
		if country_id:
			country = CountryProxy.objects.get(id=int(country_id))
			data = Proxy.objects.filter(checkers=True,country=country.country)[:300]
			dicts = {x.id: [x.hidden_ip, x.country, x.city, \
				x.vendor.email, x.postal_code, x.gmt, x.blacklist, x.region_code]  for x in data}


			return HttpResponse(json.dumps(dicts))
		else:
			return HttpResponse(json.dumps({'error':'error'}))


#region list
def ajax_region(request):
	if request.is_ajax():
		country = request.GET.get('country', None)
		if country:
			country = CountryProxy.objects.get(id=int(country))
			data = Proxy.objects.filter(checkers=True, country__istartswith=country.country)[:300]

			dicts = {x.id: [x.id, x.hidden_ip, x.country, x.city, \
				x.vendor.email, x.postal_code, x.gmt, x.blacklist,x.region_code]  for x in data}

			return HttpResponse(json.dumps(dicts), content_type="txt/html")
	else:
		return HttpResponse("")

#city list
def ajax_city(request):
	if request.is_ajax():
		city = request.GET.get('country', None)
		if city:
			city = CountryProxy.objects.get(id=int(country))

			data = Proxy.objects.filter(checkers=True, country__istartswith=country.country)[:300]
			dicts = {x.id: [x.hidden_ip, x.country, x.city, \
				x.vendor.email, x.postal_code, x.gmt, x.blacklist, x.region_code]  for x in data}

			return HttpResponse(json.dumps(dicts))

		else:
			return HttpResponse(json.dumps({"error":"error"}))






def ajax_post_city(request):
	if request.is_ajax():
		country = request.GET.get('country', None)
		if country:
			city = Proxy.objects.get(id=int(country))

			data = Proxy.objects.filter(city=city.city)[:300]
			dicts = {x.id: [x.hidden_ip, x.country, x.city, \
				x.vendor.email, x.postal_code, x.gmt, x.blacklist]  for x in data}


			return HttpResponse(json.dumps(dicts))
	else:
		return HttpResponse("")



