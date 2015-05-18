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


connections = []
def broadcast(msg):
    for ws in connections:
        try:
            ws.send_str(json.dumps(msg))
        except Exception as e:
            print(e)


def getProjectsList():
    with open('projects.json', 'r') as f:
        return json.load(f)


def initProject(project):
    os.chdir(os.path.join(CWD, 'projects'))
    os.system('git clone %(url)s' % project)
    updateDeps(project)
    os.chdir(CWD)


def updateProject(project):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    os.system('git pull')
    os.chdir(CWD)


def buildProject(project):
    updateDeps(project)
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    status = os.system('./node_modules/gulp/bin/gulp.js build')
    os.chdir(CWD)
    return status


def testProject(project):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    broadcast({
        'type': 'info',
        'data': {
            'message': 'Starting tests'
        }
    })
    status = os.system('./node_modules/gulp/bin/gulp.js test')
    os.chdir(CWD)
    return status


def updateDeps(project):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    if os.path.isfile('package.json'):
        broadcast({
            'type': 'info',
            'data': {
                'message': 'Installing npm packages.'
            }
        })
        os.system('npm install')
    if os.path.isfile('bower.json'):
        broadcast({
            'type': 'info',
            'data': {
                'message': 'Installing bower packages.'
            }
        })
        os.system('bower install')
    os.chdir(CWD)


def checkProjects():
    projects = getProjectsList()
    for project in projects:
        if not os.path.isdir(os.path.join(CWD, 'projects', project['name'], '.git')):
            broadcast({
                'type': 'info',
                'data': {
                    'message': 'Init new repository: %s...' % project['name']
                }
            })
            initProject(project)
            broadcast({
                'type': 'info',
                'data': {
                    'message': 'Repository: %s successfully inited.' % project['name']
                }
            })


@asyncio.coroutine
def handle(request):
    path = request.match_info['path']
    print(path)
    if not path:
        fname = 'index.html'
    else:
        fname = path
    with open(os.path.join(CWD, 'web', fname), 'r') as f:
        text = f.read()
        return web.Response(body=text.encode('utf-8'), headers={'content-type': 'text/html'})


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
    project = data['repository']
    print(data)
    broadcast({'type': 'git', 'data': data})
    checkProjects()
    updateProject(project)
    broadcast({'type': 'pulled', 'data': data, 'status': 'success'})
    exit_code = testProject(project)
    if not exit_code:
        status = 'success'
    else:
        status = 'error'
    broadcast({'type': 'tested', 'data': data, 'status': status})
    if exit_code:
        return web.Response(body=b'')

    exit_code = buildProject(project)
    if not exit_code:
        status = 'success'
    else:
        status = 'error'
    broadcast({'type': 'built', 'data': data, 'status': 'success'})
    return web.Response(body=b'')


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/ws', wshandler)
    app.router.add_route('POST', '/hook', hook)
    app.router.add_route('GET', '/{path:.*}', handle)

    srv = yield from loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    print("Server started at http://0.0.0.0:%s" % PORT)
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

# run(port=WEB_PORT, reloader=True, host='0.0.0.0')
