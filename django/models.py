#-*-coding:utf-8 -*-
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.models import BaseUserManager

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, get_language
from django.utils.text import capfirst
from django.core.mail import send_mail, send_mass_mail
from django.utils.encoding import python_2_unicode_compatible
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils import timezone

from easy_thumbnails.fields import ThumbnailerImageField
from picklefield.fields import PickledObjectField

from prof.utils import validate_email, send_jabber

CHOICES_CLIENT = (
    ('jabber',_('Jabber')),
    ('email',_('Email')),
)

CHOICES_TYPE = (
    ('client',_(u'Покупатель')),
    ('vendor',_(u'Продавец'))
)

class UserManager(BaseUserManager):
    def create_user(self, email, jabber=None, client=None, **extra_fields):
        if not email or not jabber:
            raise ValueError(_(u'Пользователи должны иметь адрес электронной почты или jabber'))

        if email:
            if not validate_email(email):
                raise ValueError(_(u'Пользователи должны иметь правильный адрес почты или jabber'))
        else:
            if not validate_email(jabber):
                raise ValueError(_(u'Пользователи должны иметь правильный адрес почты или jabber'))

        if email:
            email = UserManager.normalize_email(email)

        if jabber:
            jabber = UserManager.normalize_email(email)

        if email:
            user = self.model(
                email=email,
                **extra_fields
                )
        elif jabber:
            user = self.model(
                email=jabber,
                **extra_fields
                )


        
        user.backend = 'prof.authBackend.AuthBackend'
        user.save(using=self._db)

        user.url = "id%s" % user.id
        user.save(update_fields=['url'])

        # Custom
        password = None

        if client:
            if client == 'jabber':
                password = gen_pass(user, client='jabber', send=True)
                user.client = True
                user.save(update_fields=['client'])
            
            else:
                password = gen_pass(user, client='email', send=True)
                user.client = False
                user.save(update_fields=['client'])

        # отправка уведомлений
        Notice.objects.create(
            body=_(u'Поздравления! Вы успешно зарегистрированы!'),
            sender=user,
            recipient=user)
        
        return user

    def create_superuser(self, password, email, **extra_fields):
        user = self.create_user(
            email=email,
            **extra_fields
        )
        user.is_active = True
        user.is_admin = True
        user.is_superuser = True
        user.set_password(password)
        user.save(using=self._db)
        return user

@python_2_unicode_compatible
class User(AbstractBaseUser, PermissionsMixin):
    objects = UserManager()
    jabber = models.CharField(_("Jabber"),
        max_length=70, unique=True, db_index=True, blank=True, null=True)
    email = models.CharField(_(u'email'),
        max_length=70, unique=True, db_index=True, blank=True, null=True)
    client = models.CharField(_(u"клиент"),choices=CHOICES_CLIENT, default='email', max_length=8)
    cv = models.CharField(_(u'Покупатель/Продавец'), choices=CHOICES_TYPE, default='vendor', max_length=6)

    avatar = ThumbnailerImageField(upload_to='img/avatar', blank=True,
        null=True, verbose_name=_(u"Аватарка"))#default='default/no_avatar.png'

    push_jabber = models.BooleanField(_("Jabber Увебомление"),default=True)
    push_email = models.BooleanField(_("Email Уведомление"),default=True)
    
    url = models.CharField(unique=True, blank=True, null=True, max_length=200,
        verbose_name=_(u'Адрес страницы'))
    
    balance = models.DecimalField(_(u'Баланс'), default=Decimal('0'),
        max_digits=10, decimal_places=2)

    is_active = models.BooleanField(_(u'Активный'), default=True)
    is_admin = models.BooleanField(_(u'Админ'), default=False)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    created = models.DateTimeField(_(u'Создан'), auto_now_add=True)

    language = models.CharField(_(u'Язык'), choices=settings.LANGUAGES,
                                default=get_language()[:2], max_length=2)

    dicts = PickledObjectField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _(u'Пользователь')
        verbose_name_plural = _(u'Пользователи')


    def get_full_name(self):
        return self.email

    def get_jabber(self):
        if self.client:
            return self.email
        return ''

    def get_short_name(self):
        return self.email

    def gen_mini_avatar(self):
        html = """
                <a href='%s'><img src='%s'
                width="100" 
                height="100"/>
                </a>""" % (
                    self.avatar.get_thumbnail({'size': (100, 100), 'crop': True}).url,
                    self.avatar.get_thumbnail({'size': (100, 100), 'crop': True}).url)

        return format_html(html)


    def __str__(self):
        return self.email

    @property
    def is_staff(self):
        return self.is_admin


    def thumbnail(self):
        return """<img border="0" alt="" src="%s" />""" % self.avatar.get_thumbnail(
            {'size': (40, 40), 'crop': True}).url

    def thumbnail30(self):
        return self.avatar.get_thumbnail({'size': (30, 30), 'crop': True}).url

    def thumbnail26(self):
        return self.avatar.get_thumbnail({'size': (26, 26), 'crop': True}).url

    def thumbnail48(self):
        return self.avatar.get_thumbnail({'size': (48, 48), 'crop': True}).url

    def thumbnail50(self):
        return self.avatar.get_thumbnail({'size': (50, 50), 'crop': True}).url

    def email_user(self, subject, message, from_email):
        if validate_email(self.email):
            send_mail(subject, message, from_email, [self.email])

    def jabber_user(self, message):
        send_jabber(message, jabber=[self.get_jabber()])


    def get_balance(self):
        if not self.balance:
            return 0
        
        if not (isinstance(self.balance, float) or isinstance(self.balance,Decimal)):
            return int(str(self.balance).rstrip('0').rstrip('.'))
        
        return int(self.balance)

    def give_money(self, **params_notice):
        Notice.objects.create(**params_notice)
        # TODO: нужно добавить оповещение на телефон
        return

    def take_money(self, **params_notice):    
        Notice.objects.create(**params_notice)
        return

    def gen_pswd(self):
        pswd = BaseUserManager().make_random_password()
        return pswd

    def get_name_split(self):
        try:
            return "{}".format(self.email.split("@")[0])
        except:
            return "{}".format(self.email)
            

def gen_pass(user, client=None, send=False):
    password = User.objects.make_random_password(
        length=8,
        allowed_chars='ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz123456789_$&'
    )

    user.set_password(password)
    user.save(update_fields=['password'])

    # send jabber
    if send:
        data = {
            'login': user.get_full_name(),
            'password': password
        }

        message = _(u'Вход для веб-сайта: login {} пароль: {}'.format(user.get_jabber(), password))

        if client == 'jabber':
            user.jabber_user(message=message)

        else:
            subject = render_to_string('activation_email_subject.txt', data)
            user.email_user(subject, message, settings.DEFAULT_FROM_EMAIL)


    return password

class EchoNiceManager(models.Manager):
    def echo(self, msg):
        [self.create(body=msg,sender=user,recipient=user) for user in User.objects.all()]

        return
        

@python_2_unicode_compatible
class Notice(models.Model):
    body = models.CharField(verbose_name=_(u'Сообщение'), max_length=2000, null=True)
    sender = models.ForeignKey(User, verbose_name=_(u'Отправитель'),related_name='notice_sender')
    recipient = models.ForeignKey(User, verbose_name=_(u'Получатель'),related_name='notice_recipient')
    created = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(verbose_name=_(u'Прочитано'), default=False)

    objects = models.Manager()
    echo = EchoNiceManager()

    class Meta:
        verbose_name = _(u'Уведомление')
        verbose_name_plural = _(u'Уведомление')
        ordering = ['-created']

    def __str__(self):
        return self.body


@python_2_unicode_compatible
class Echo(models.Model):
    text = models.CharField(_(u"Массовое уведомление"),
        max_length=2000, help_text=_(u"массовое уведомление пользователей, не более 2000 символов"))

    def __str__(self):
        return " ".join(self.text.split()[:10])

    def save(self, *args, **kwargs):
        Notice.echo.echo(self.text)
        super(Echo, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _(u"Массовое уведомление")
        verbose_name_plural = _(u"Массовое уведомление")