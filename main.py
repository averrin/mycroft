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
import jinja2
import aiohttp_jinja2
import mandrill

PORT = 2400

CWD = os.path.abspath(os.path.split(sys.argv[0])[0])

mandrill_client = mandrill.Mandrill('UJbyuKjtdB1KnLcCPYJSBA')

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
    os.chdir(CWD)


def updateProject(project):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    os.system('git pull')
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


def runBuildStep(project, step):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    status = os.system(step['cmd'])
    os.chdir(CWD)
    return status


def sendNotification(project, report):
    message = {
        'to': [{'email': watcher} for watcher in project['watchers']],
        'subject': '%s run finished' % project['name'],
        'from_name': 'Mycroft',
        'from_email': 'averrin@gmail.com',
        'text': report

    }
    status = mandrill_client.messages.send(message=message)
    print(status)


def processProject(project):
    report = 'Report (%s):\n' % project['name']
    checkProjects()
    broadcast({'type': 'pre_pull', 'data': project, "description": "Update repository from git"})
    updateProject(project)
    broadcast({'type': 'pull', 'data': project, 'status': 'success'})
    report += 'Pull from git: success\n'
    for step in project['build_steps']:
        broadcast({'type': 'pre_%s' % step['name'], 'data': project, "description": step['description']})
        exit_code = runBuildStep(project, step)
        if not exit_code:
            status = 'success'
        else:
            status = 'error'
        broadcast({'type': step['name'], 'data': project, 'status': status})
        report += '%s: %s\n' % (step['description'], status)
        if exit_code and step['stop_on_fail']:
            break
    print('Done')
    sendNotification(project, report)
    return web.Response(body=b'')


@aiohttp_jinja2.template('index.html')
def index(request):
    return {'projects': getProjectsList()}


def run_project(request):
    project = request.match_info['project']
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        processProject(project[0])
    return web.Response(body=b'')


@asyncio.coroutine
def static_handle(request):
    path = request.match_info['path']
    headers = {'content-type': 'text/html'}
    types = {
        'css': 'text/css',
        'js': 'application/x-javascript'
    }
    ext = os.path.splitext(path)
    if ext in types:
        headers['content-type'] = types[ext]
    with open(os.path.join(CWD, 'web', path), 'r') as f:
        text = f.read()
        return web.Response(body=text.encode('utf-8'), headers=headers)


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
    print('Git hook: %s with comment: %s' % (data['repository']['name'], data['commits'][0]['message']))
    broadcast({'type': 'git', 'data': data})
    project = list(filter(lambda x: x['name'] == data['repository']['name'], getProjectsList()))
    if project:
        processProject(project[0])
    return web.Response(body=b'')


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    aiohttp_jinja2.setup(app,
        loader=jinja2.FileSystemLoader(os.path.join(CWD, 'web/html')))
    app.router.add_route('GET', '/ws', wshandler)
    app.router.add_route('POST', '/hook', hook)
    app.router.add_route('GET', '/', index)
    # app.router.add_route('GET', '/static/{path:.*}', static_handle)
    app.router.add_route('GET', '/run/{project}', run_project)
    app.router.add_static('/static', os.path.join(CWD, 'web'))

    srv = yield from loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    print("Server started at http://0.0.0.0:%s" % PORT)
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

# run(port=WEB_PORT, reloader=True, host='0.0.0.0')
