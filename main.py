#!env python
# -*- coding: utf8 -*-

from bottle import *

WS_PORT = 2400
WEB_PORT = 2401


@route('/')
def index():
    return static_file('web/index.html', root='.')


run(port=WEB_PORT, reloader=True, host='0.0.0.0')
