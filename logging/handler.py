import logging
from hand import SMTPHandler
 
log = logging.getLogger('forward')

logging.basicConfig(
    filename="portforward.log",
    format="%(levelname)-10s %(asctime)s %(message)s",
    level=logging.INFO
    )
 
handler = SMTPHandler(
    ("smtp.yandex.ru", 587), 
    'AntanasV@yandex.ru', 
    ['johnmnemonik.jm@gmail.com',''], 
    'ОШИБКА', 
    ('AntanasV@yandex.ru','passwdord'))

handler.setLevel(logging.ERROR)
 
log.addHandler(handler)

logging.exception("ошибка на почту")