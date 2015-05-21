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
from functools import partial
import threading
from queue import Queue
from datetime import datetime
from time import time
from lockfile import LockFile, locked

SERVER_URL = 'http://lets.developonbox.ru/mycroft'
PORT = 2400
CWD = os.path.abspath(os.path.split(sys.argv[0])[0])
LOCK = LockFile(os.path.join(CWD, 'build_agent.lock'))
mandrill_client = mandrill.Mandrill('UJbyuKjtdB1KnLcCPYJSBA')
loop = asyncio.get_event_loop()
agents = Queue()

connections = []
def broadcast(msg):
    for ws in connections:
        try:
            ws.send_str(json.dumps(msg))
        except Exception as e:
            print(e)


def getProjectsList():
    with open(os.path.join(CWD, 'projects.json'), 'r') as f:
        return json.load(f)


def makeLogURL(logfile):
    url = SERVER_URL + '/logs/' + '/'.join(logfile.split('/')[-3:])
    return url


def initProject(project):
    os.chdir(os.path.join(CWD, 'projects'))
    os.system('git clone %(url)s' % project)
    os.chdir(CWD)


def updateProject(project, run_id):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    logpath = os.path.join(CWD, 'logs', project['name'], run_id)
    if not os.path.isdir(logpath):
        os.makedirs(logpath)
    logfile = os.path.join(logpath, 'git_pull.log')
    cmd = 'git checkout %s > %s 2>&1' % (project['branch'], logfile)
    print(cmd)
    status = os.system(cmd)
    cmd = 'git pull > %s 2>&1' % logfile
    print(cmd)
    status = os.system(cmd)
    cmd = 'git log -n 5 >> %s  2>&1' % logfile
    print(cmd)
    status = os.system(cmd)
    os.chdir(CWD)
    return status, logfile


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


def runBuildStep(project, step, run_id):
    os.chdir(os.path.join(CWD, 'projects', project['name']))
    logpath = os.path.join(CWD, 'logs', project['name'], run_id)
    logfile = os.path.join(logpath, step['name'] + '.log')
    cmd = "%s > %s 2>&1" % (step['cmd'], logfile)
    print('Build step "%s": %s' % (step['name'], cmd))
    status = os.system(cmd)
    os.chdir(CWD)
    return status, logfile


def sendNotification(project, report, status):
    message = {
        'to': [{'email': watcher} for watcher in project['watchers']],
        'subject': 'Mycroft: %s run finished: %s' % (project['name'], status.upper()),
        'from_name': 'Mycroft',
        'from_email': 'averrin@gmail.com',
        'html': report

    }
    if status != 'success':
        message['to'].extend({'email': watcher} for watcher in project['fail_watchers'])
    status = mandrill_client.messages.send(message=message)
    print(status)


@locked(os.path.join(CWD, 'build_agent.lock'))
def processProject(project, hook_data=None):
    print(LOCK.is_locked())
    print('Starting process project: %s' % project['name'])
    report = 'Report (%s):<br>' % project['name']
    report += '%s<br>' % datetime.now()
    run_id = str(time())
    if hook_data is not None:
        report += 'Triggered by git event: <br>'
        report += 'New commit in repo: <strong>%s</strong> by %s<br> comment: "%s"<br>' % (
            hook_data['repository']['name'], hook_data['user_name'], hook_data['commits'][0]['message']
        )
    checkProjects()

    broadcast({'type': 'pre_pull', 'data': project, "description": "Update repository from git"})
    print('Update project')
    exit_code, logfile = updateProject(project, run_id)
    if not exit_code:
        status = 'success'
    else:
        status = 'fail'
    print('Status: %s' % status)
    broadcast({'type': 'pull', 'data': project, 'status': status, 'logfile': makeLogURL(logfile)})

    report += 'Pull from git: <span style="color:%s;font-weight:bold;">%s</span> [<a href="%s">log</a>]<br>' % (
        {'success': 'green', 'fail': 'red'}[status],
        status,
        makeLogURL(logfile)
    )
    if not exit_code:
        for step in project['build_steps']:
            broadcast({'type': 'pre_%s' % step['name'], 'data': project, "description": step['description']})
            exit_code, logfile = runBuildStep(project, step, run_id)
            if not exit_code:
                status = 'success'
            else:
                status = 'fail'
            print('Status: %s' % status)
            broadcast({'type': step['name'], 'data': project, 'status': status, 'logfile': makeLogURL(logfile)})
            report += '%s: <span style="color:%s;font-weight:bold;">%s</span> [<a href="%s">log</a>]<br>' % (
                step['description'],
                {'success': 'green', 'fail': 'red'}[status],
                status,
                makeLogURL(logfile)
            )
            if exit_code and ('stop_on_fail' in step and step['stop_on_fail']):
                print('Exit on fail')
                break
    report_path = os.path.join(os.path.split(logfile)[0], 'report.html')
    with open(report_path, 'w') as f:
        f.write('<!--' + status + '-->\n' + report)
    report += '<a href="%s">This report</a>' % makeLogURL(report_path)
    broadcast({'type': 'done', 'data': project, 'status': status, 'logfile': makeLogURL(report_path)})
    print('Done')
    sendNotification(project, report, status)


@aiohttp_jinja2.template('index.html')
def index(request):
    projects = getProjectsList()
    for project in projects:
        project['repo_url'] = project['url'].replace(':', '/').replace('git@', 'http://')
        project['builds'] = []
        logpath = os.path.join(CWD, 'logs', project['name'])
        if not os.path.isdir(logpath):
            continue
        builds = os.listdir(logpath)
        for build in builds:
            report_file = os.path.join(CWD, 'logs', project['name'], build, 'report.html')
            if os.path.isfile(report_file):
                with open(report_file, 'r') as rf:
                    status = rf.readline()[4:-4]
                project['builds'].append({
                    'timestamp': build,
                    'report': makeLogURL(report_file),
                    'name': '%s: <span style="color:%s;font-weight:bold;">%s</span>' % (
                        datetime.fromtimestamp(float(build)).strftime('%d.%m %H:%M'),
                        {'success': 'lightgreen', 'fail': 'coral'}[status],
                        status
                    )
                })
    return {'projects': projects}


@asyncio.coroutine
def run_project(request):
    if LOCK.is_locked():
        return web.Response(body=b'locked')
    project = request.match_info['project']
    print('Command to start %s' % project)
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        # loop.call_soon_threadsafe(partial(processProject, project[0]))
        t = threading.Thread(target=partial(processProject, project[0]))
        agents.put(t)
        t.start()
    return web.Response(body=b'success')


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
    host = request.headers['X-Real-IP']
    print('New ws connection: %s' % host)
    connections.append(ws)

    while True:
        msg = yield from ws.receive()
        print('Received data: %s' % msg.data)

        if msg.tp == web.MsgType.text:
            if msg.data == 'disconnect':
                break
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
    broadcast({'type': 'git', 'data': data, 'status': 'success'})
    project = list(filter(lambda x: x['name'] == data['repository']['name'], getProjectsList()))
    if project:
        # loop.call_soon_threadsafe(partial(processProject, project[0]))
        t = threading.Thread(target=partial(processProject, project[0], data))
        agents.put(t)
        t.start()
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
    app.router.add_static('/logs', os.path.join(CWD, 'logs'))

    srv = yield from loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    print("Server started at http://0.0.0.0:%s" % PORT)
    return srv

loop.run_until_complete(init(loop))
loop.run_forever()
loop.close()
