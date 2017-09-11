@login_required
def req_form(request):
    ts = TimeSet.objects.first()
    now = timezone.now()
    try:
        offset = now - datetime.timedelta(minutes=ts.offset)
    except AttributeError:
        offset = False

    if request.method == 'GET':
        form = ProxyModelForm(request.GET or None)
        if form.is_valid():
            bl = form.cleaned_data['blacklist']
            ip = form.cleaned_data['ip']
            country = form.cleaned_data['country']
            city = form.cleaned_data['city']
            continent = form.cleaned_data['continent']
            country_code = form.cleaned_data['country_code']
            postal_code = form.cleaned_data['postal_code']
            region_code = form.cleaned_data['region_code']
            time_zone = form.cleaned_data['time_zone']
            gmt = form.cleaned_data['gmt']

            qs = Q()
            if ip:
                ip = form.cleaned_data.pop('ip')
            #start country
            if country:
                country = [x.country for x in country]
                form.cleaned_data.pop('country')
            if bl:
                if country:
                    title = [x.title for x in bl]
                    form.cleaned_data.pop('blacklist')
                    [qs.add(Q(['%s' % k, v]),'AND') for k,v in form.cleaned_data.items() if v]
                    if offset:
                        coun = Proxy.objects.filter(qs, Q(blacklist__in=title) \
                            & Q(blacklist__icontains=title) & Q(update__gte=offset))
                    else:
                        if len(title) > 1:
                            q = Q()
                            [q.add(Q(['%s' % "blacklist__icontains", v]),'OR') for v in title]
                            coun = Proxy.objects.filter(qs,q,checkers=True,country__in=country)
                        else:
                            title = title[0]
                            coun = Proxy.objects.filter(
                                qs, checkers=True,country__in=country).filter(Q(
                                    blacklist__in=title) | Q(blacklist__icontains=title))
                else:
                    title = [x.title for x in bl]
                    form.cleaned_data.pop('blacklist')
                    [qs.add(Q(['%s' % k, v]),'AND') for k,v in form.cleaned_data.items() if v]
                    if offset:
                        coun = Proxy.objects.filter(qs, Q(blacklist__in=title) \
                            & Q(blacklist__icontains=title) & Q(update__gte=offset))
                    else:
                        if len(title) > 1:
                            q = Q()
                            [q.add(Q(['%s' % "blacklist__icontains", v]),'OR') for v in title]
                            coun = Proxy.objects.filter(qs,q,checkers=True)
                        else:
                            title = title[0]
                            coun = Proxy.objects.filter(
                                qs, checkers=True).filter(Q(
                                    blacklist__in=title) | Q(blacklist__icontains=title))
            else:
                if country:
                    [qs.add(Q(['%s' % k, v]),'AND') for k,v in form.cleaned_data.items() if v]
                    if offset:
                        if ip:
                            coun = Proxy.objects.filter(
                                qs,update__gte=offset,blacklist__isnull=True,ip__istartswith=ip)
                        else:
                            coun = Proxy.objects.filter(
                                qs,update__gte=offset,blacklist__isnull=True,country__in=country)
                    else:
                        if ip:
                            coun = Proxy.objects.filter(
                                qs,checkers=True,blacklist__isnull=True,ip__istartswith=ip)
                        else:
                            coun = Proxy.objects.filter(
                                qs,checkers=True,blacklist__isnull=True,country__in=country)
                else:
                    [qs.add(Q(['%s' % k, v]),'AND') for k,v in form.cleaned_data.items() if v]
                    if offset:
                        if ip:
                            coun = Proxy.objects.filter(
                                qs,update__gte=offset,blacklist__isnull=True,ip__istartswith=ip)
                        else:
                            coun = Proxy.objects.filter(
                                qs,update__gte=offset,blacklist__isnull=True)
                    else:
                        if ip:
                            coun = Proxy.objects.filter(
                                qs,checkers=True,blacklist__isnull=True,ip__istartswith=ip)
                        else:
                            coun = Proxy.objects.filter(
                                qs,checkers=True,blacklist__isnull=True)
            total = coun.count()
            paginator = Paginator(coun, 100)
            page = request.GET.get('page')
            GET_params = request.GET.copy()
            try:
                con = paginator.page(page)
            except PageNotAnInteger:
                con = paginator.page(1)
            except EmptyPage:
                con = paginator.page(paginator.num_pages)
            return render(request, "proxy/form.html",{
                "coun":con,"total":total,'GET_params':GET_params })
    else:
        form = ProxyModelForm()
    return render(request, "proxy/form.html",{"form":form})
