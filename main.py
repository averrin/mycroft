#!env python3
# -*- coding: utf8 -*-

from bottle import *
from pprint import pprint
import json
import os
import sys
import shutil

import asyncio
import websockets
from aiohttp import web
import urllib.parse as urlparse

import threading
from queue import Queue

PORT = 2400

CWD = os.path.abspath(os.path.split(sys.argv[0])[0])
print(CWD)


def getProjectsList():
    with open('projects.json', 'r') as f:
        return json.load(f)


def initProject(project):
    os.chdir(os.path.join(CWD, 'projects'))
    os.system('git clone %(url)s' % project)
    os.chdir(CWD)


def updateProject(project):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    os.system('git pull')
    os.chdir(CWD)


def checkProjects():
    projects = getProjectsList()
    for project in projects:
        if not os.path.isdir(os.path.join(CWD, 'projects', project['name'], '.git')):
            initProject(project)


@asyncio.coroutine
def handle(request):
    with open(os.path.join(CWD, 'web/index.html'), 'r') as f:
        text = f.read()
        return web.Response(body=text.encode('utf-8'), headers={'content-type': 'text/html'})


connections = []
@asyncio.coroutine
def wshandler(request):
    ws = web.WebSocketResponse()
    ws.start(request)
    connections.append(ws)

    while True:
        msg = yield from ws.receive()
        print('Received data: %s' % msg.data)

        if msg.tp == web.MsgType.text:
            ws.send_str("Hello, {}".format(msg.data))
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.close:
            break
    connections.remove(ws)
    return ws


@asyncio.coroutine
def hook(request):
    os.chdir(CWD)
    data = yield from request.json()
    print(data)
    for ws in connections:
        ws.send_str(json.dumps({'type': 'git', 'data': data}))
    checkProjects()
    updateProject(data['repository'])
    for ws in connections:
        ws.send_str(json.dumps({'type': 'pulled', 'data': data, 'status': 'success'}))
    return web.Response(body=b'')


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/ws', wshandler)
    app.router.add_route('POST', '/hook', hook)
    app.router.add_route('GET', '/', handle)

    srv = yield from loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    print("Server started at http://0.0.0.0:%s" % PORT)
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

# run(port=WEB_PORT, reloader=True, host='0.0.0.0')
