#!env python3
# -*- coding: utf8 -*-

from pprint import pprint
import json
import os
import sys
import shutil
import re

import envelopes
from functools import partial
import threading
from queue import Queue
from datetime import datetime
from time import time, sleep

from lockfile import LockFile, locked
import subprocess
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK, read

import asyncio
import websockets
from aiohttp import web
import urllib.parse as urlparse
import jinja2
import aiohttp_jinja2

from termcolor import colored
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import Terminal256Formatter

SERVER_URL = 'http://lets.developonbox.ru/mycroft'
FTP_URL = 'ftp://ftp.developonbox.ru/common/SCM/builds/html5/CI'
SMTP_SERVER = 'smtp.dev.zodiac.tv'
PORT = 2400
CWD = os.path.abspath(os.path.split(sys.argv[0])[0])
LOCK = LockFile(os.path.join(CWD, 'build_agent.lock'))
# на самом деле лок не обязателен, кажется, что я сделал так, чтобы сборки не мешали друг другу.
# Но, кажется, параллельно они все равно не выполняются, так что я вернул лок обратно
loop = asyncio.get_event_loop()
agents = Queue()

connections = []


def broadcast(msg):
    u"""Рассылка во все сокеты."""
    for ws in connections:
        try:
            ws.send_str(json.dumps(msg))
        except Exception as e:
            print(e)


def pprint(data):
    data = json.dumps(data, indent=4)
    data = highlight(data, JsonLexer(), Terminal256Formatter())
    print(data)


def getProjectsList():
    with open(os.path.join(CWD, 'projects.json'), 'r') as f:
        return json.load(f)


def makeLogURL(logfile):
    u"""Преобразование пути до файла лога в URL."""
    url = SERVER_URL + '/logs/' + '/'.join(logfile.split('/')[-4:])
    return url

def makeReportURL(logfile):
    url = SERVER_URL + '/view_report/logs/' + '/'.join(logfile.split('/')[-4:])
    return url

def getBuildId(project):
    return str(time())


def getProjectId(project):
    return project['name']


def getProjectGroup(project):
    return project['url'].split(':')[1].split('/')[0]


def getProjectPath(project):
    return os.path.join(CWD, 'projects', getProjectGroup(project), project['name'])


def getLogPath(project, run_id=None):
    path = os.path.join(CWD, 'logs', getProjectGroup(project), project['name'])
    if run_id is not None:
        path = os.path.join(path, run_id)
    return path


def getArtefactURL(project, run_id, ftp):
    name = '%s_%s.%s.tgz' % (getProjectGroup(project), project['name'], run_id)
    if not ftp:
        url = '%s/artefacts/%s' % (SERVER_URL, name)
        path = os.path.join(CWD, 'artefacts', name)
        if os.path.isfile(path):
            return url
    else:
        path = os.path.join(CWD, 'builds', getProjectGroup(project), project['name'], run_id)
        if not os.path.isdir(path):
            return None
        files = os.listdir(path)
        if len(files):
            name = files[0]
            url = '%s/%s/%s/%s/%s' % (FTP_URL, getProjectGroup(project), project['name'], run_id, name)
            return url

    return None


def initProject(project):
    group = getProjectGroup(project)
    try:
        os.system('mkdir -p %s/%s' % (CWD, group))
    except:
        pass
    os.system('cd %s/%s; git clone %s' % (os.path.join(CWD, 'projects'), group, project['url']))


def updateProject(project, run_id):
    logpath = getLogPath(project, run_id)
    if not os.path.isdir(logpath):
        os.makedirs(logpath)
    logfile = os.path.join(logpath, 'git_pull.log')
    cmd = 'cd %s; git checkout %s > %s 2>&1' % (
        getProjectPath(project), project['branch'], logfile
    )
    print(cmd)
    status = os.system(cmd)
    cmd = 'cd %s; git pull > %s 2>&1' % (getProjectPath(project), logfile)
    print(cmd)
    status = os.system(cmd)
    cmd = 'cd %s; git log -n 5 >> %s  2>&1' % (getProjectPath(project), logfile)
    print(cmd)
    status = os.system(cmd)
    return status, logfile


def checkProjects():
    u"""Проверка существования файлов проекта. Если он только добавлен."""
    projects = getProjectsList()
    for project in projects:
        if not os.path.isdir(os.path.join(getProjectPath(project), '.git')):
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


def runBuildStep(project, step, run_id, extra_env=None, processLog=None):
    details = []
    # переменные для использования в скриптах билд-степа
    export_var = {
        'run_id': run_id,
        'artefacts_path': os.path.join(CWD, 'artefacts'),
        'tgz_name': os.path.join(CWD, 'artefacts', '%s_%s.%s.tgz' % (getProjectGroup(project), project['name'], run_id)),
        'ftp_path': os.path.join(CWD, 'builds', getProjectGroup(project), project['name'], run_id)
    }

    logpath = getLogPath(project, run_id)
    # print('>>', logpath)
    logfile = os.path.join(logpath, step['name'] + '.log')
    env = os.environ.copy()
    if extra_env is not None:
        env.update(extra_env)
    env.update(export_var)
    print('Build step "%s": %s' % (colored(step['name'], 'blue', attrs=['bold']), step['cmd']))
    print('Logging to file: %s' % colored(logfile, 'magenta', attrs=['bold']))
    cmd = [step['cmd']]
    out = subprocess.PIPE
    try:
        p = subprocess.Popen(
            cmd, stdout=out, stderr=out, shell=True, env=env, cwd=getProjectPath(project)
        )
        with open(logfile, 'a') as lf:
            # реалтайм чтение логов. Тут бывают затыки
            while True:
                # err_line = p.stderr.readline()
                # err_line = b''
                raw_line = p.stdout.readline()
                line = raw_line.decode('utf8').strip()
                # err_line = err_line.decode('utf8').strip()
                if line:
                    broadcast({'type': 'log', 'data': {'name': project['name'], 'step': step['description'], 'line': line}})
                    if processLog is not None:
                        details.append(processLog(line, project, step, stderr=False))
                    lf.write(line + '\n')
                # if err_line:
                #     print('[%s]: %s' % (colored('stderr', 'red'), err_line))
                #     if processLog is not None:
                #         details.append(processLog(line, project, step, stderr=True))
                if not line:
                    break
                # else:
                    # print(line)
        # тесты иногда падают по таймауту, но не смотрел, завершаясь или нет. Если что, хвост проблемы в wait
        return p.wait(3), logfile, details
    except Exception as e:
        print(e)
        return 1, logfile, details


def sendNotification(project, report, status):
    u"""Отправка отчета почтой."""
    tos = [(watcher, watcher.split('@')[0]) for watcher in project['watchers']]
    if status != 'success':
        if project['fail_watchers'] and project['fail_watchers'] != [""]:
            tos.extend((watcher, watcher.split('@')[0]) for watcher in project['fail_watchers'])
    mail = envelopes.Envelope(
        from_addr=('mycroft@dev.zodiac.tv', 'Mycroft'),
        to_addr=tos,
        subject='Mycroft: %s run finished: %s' % (project['name'], status.upper()),
        html_body=report
    )
    print('Send to: %s' % ','.join(list([to[0] for to in tos])))
    status = mail.send(SMTP_SERVER, tls=True)
    print(status)


def getGitInfo(project):
    u"""Фетч текущего состояния локальной копии проекта. Выводится в дэшбоарде."""
    output = subprocess.check_output(
        ['cd %s; git log -n 1' % getProjectPath(project)],
        shell=True,
        universal_newlines=True
    )
    data = {}
    for line in output.split('\n'):
        if line.startswith('commit'):
            data['revision'] = line[7:]
        elif line.startswith('Author: '):
            data['author'] = line[8:]
        elif line.startswith('Date: '):
            data['date'] = line[6:].strip()
        elif line.strip():
            data['comment'] = line.strip()
    pprint(data)
    return data


def processTestLog(logline, project, step, stderr):
    u"""Парсинг отчета о прогоне тестов. Не ах, признаю."""
    if not stderr:
        test = re.match('.*PhantomJS.*\)[:]* (.*) (FAILED|SUCCESS)', logline)
        if test is not None:
            if test.group(2) == 'FAILED' and test.group(1).startswith('Exec'):
                return None
            else:
                desc = test.group(1).replace('[32m', '')
            h = {'test': desc, 'status': test.group(2)}
            # print(h)
            broadcast({'type': 'single_test', 'data': h, 'name': project['name']})
            return h
        else:
            error = re.match('.*PhantomJS.*\) ERROR.*', logline)
            if error:
                h = {'test': logline, 'status': 'ERROR'}
                broadcast({'type': 'single_test', 'data': h})
                return h
    return None


def processStep(step, project, run_id):
    u"""Сбор данных о результате прогона шага сборки."""
    if 'disabled' in step and step['disabled']:
        print('Step "%s" disabled. Skiping...' % colored(step['description'], 'blue', attrs=['bold']))
        return None, False
    broadcast({'type': 'pre_%s' % step['name'], 'data': project, "description": step['description']})
    history = {}
    d = datetime.now()
    pl = None
    if 'test' in step['name'] or 'test' in step['description']:
        pl = processTestLog  # пока в этом необходимости нет, но что-то меня тогда замкнуло
    exit_code, logfile, details = runBuildStep(project, step, run_id, processLog=pl)
    if not exit_code:
        status = 'success'
    else:
        status = 'fail'
    delta = datetime.now() - d
    history.update({
        'step': step['name'],
        'status': status,
        'time': delta.seconds,
        'logfile': logfile,
        'logURL': makeLogURL(logfile),
        'description': step['description'],
        'details': list(filter(lambda x: x is not None, details))
    })
    print('Status: %s' % colored(status, {'success': 'green', 'fail': 'red'}[status], attrs=['bold']))
    broadcast({'type': step['name'], 'data': project, 'status': status, 'logfile': makeLogURL(logfile)})
    if exit_code and ('stop_on_fail' in step and step['stop_on_fail']):
        print(colored('Exit on fail', 'red', attrs=['bold']))
        return history, True
    return history, False


@locked(os.path.join(CWD, 'build_agent.lock'))
def processProject(project, hook_data=None):
    u"""Обработка процесса сборки."""
    start_at = datetime.now()
    print('Starting process project: %s' % (colored(project['name'], 'blue', attrs=['bold'])))
    run_id = getBuildId(project)  # вероятно, следует заменить таймстамп на хэш коммита плюс что-нить.
    history = {'steps': [], 'run_id': run_id}
    checkProjects()

    broadcast({'type': 'pre_pull', 'data': project, "description": "Update repository from git"})
    print('Update project')
    d = datetime.now()
    exit_code, logfile = updateProject(project, run_id)
    if not exit_code:
        status = 'success'
    else:
        status = 'fail'
    delta = datetime.now() - d
    history['steps'].append({
        'step': 'update',
        'status': status,
        'time': delta.seconds,
        'logfile': logfile,
        'logURL': makeLogURL(logfile),
        'description': 'Pull from git'
    })
    print('Status: %s' % colored(status, {'success': 'green', 'fail': 'red'}[status], attrs=['bold']))
    broadcast({'type': 'pull', 'data': project, 'status': status, 'logfile': makeLogURL(logfile)})
    if not exit_code:
        for step in project['build_steps']:
            h, force_exit = processStep(step, project, run_id)
            status = h['status']
            if h is not None:
                history['steps'].append(h)
            if force_exit:
                break
    report_path = os.path.join(getLogPath(project, run_id), 'report.html')
    artefact_url = getArtefactURL(project, run_id, False)
    report_url = makeLogURL(report_path)
    broadcast({
        'type': 'done',
        'data': project,
        'status': status,
        'logfile': makeReportURL(report_path),
        'artefact': artefact_url,
        'ftp_artefact': getArtefactURL(project, run_id, True),
        'finish_at': datetime.now().strftime('%d.%m %H:%M')
    })
    print(colored('Done', 'green', attrs=['bold']))
    history['status'] = status
    json.dump(history, open(os.path.join(os.path.split(logfile)[0], 'history.json'), 'w'))
    template = jinja2.Template(open(os.path.join(CWD, 'report.html'), 'r').read())
    report = template.render({
        "project": project,
        "hook_data": hook_data,
        "history": history,
        "report_url": report_url,
        "artefact_url": artefact_url,
        'ftp_artefact': getArtefactURL(project, run_id, True),
        "status": status,
        "startAt": start_at
    })
    with open(report_path, 'w') as f:
        f.write(report)
    sendNotification(project, report, status)


def projects(request):
    _projects = getProjectsList()
    projects = []
    for project in _projects:
        project_info = getProjectInfo(project)
        if project_info is not None:
            projects.append(project_info)
        else:
            projects.append(project)
    return {'projects': projects}


def getProjectInfo(project):
    u"""Сбор информации о проекте, для вывода в веб."""
    project['repo_url'] = project['url'].replace(':', '/').replace('git@', 'http://')[:-4]
    project['builds'] = []
    logpath = getLogPath(project)
    if not os.path.isdir(logpath):
        return
    builds = os.listdir(logpath)
    for build in sorted(builds, reverse=True)[:10]:
        report_file = os.path.join(getLogPath(project), build, 'report.html')
        if os.path.isfile(report_file):
            history_file = os.path.join(os.path.split(report_file)[0], 'history.json')
            if os.path.isfile(history_file):
                history = json.load(open(history_file))
                failed = [
                    (
                        s['step'],
                        makeLogURL(s['logfile']) if 'logfile' in s else '',
                        s['details'] if 'details' in s else None
                    ) for s in filter(lambda x: x['status'] == 'fail', history['steps'])
                ]
                status = history['status']
            else:
                history = {}
                failed = []
                with open(report_file, 'r') as rf:
                    status = rf.readline()[4:-4]
            project['group'] = getProjectGroup(project)
            project['builds'].append({
                'timestamp': build,
                'history': history,
                'failed': failed,
                'report': makeReportURL(report_file),
                'name': '%s: <span class="%s">%s</span>' % (
                    datetime.fromtimestamp(float(build)).strftime('%d.%m %H:%M'),
                    status,
                    status
                )
            })
            if 'run_id' in history:
                project['artefact'] = getArtefactURL(project, history['run_id'], ftp=False)
                project['ftp_artefact'] = getArtefactURL(project, history['run_id'], ftp=True)
    return project


@aiohttp_jinja2.template('dashboard.html')
def dashboard(request):
    return projects(request)


@aiohttp_jinja2.template('table.html')
def index(request):
    return projects(request)


@aiohttp_jinja2.template('form.html')
def new_project(request):
    return {}


@aiohttp_jinja2.template('dashboard.html')
def view_project(request):
    project = request.match_info['project']
    print('Command to start %s' % project)
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        project = project[0]
    return {'projects': [getProjectInfo(project)]}


@aiohttp_jinja2.template('form.html')
def edit_project(request):
    project = request.match_info['project']
    print('Command to start %s' % project)
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        project = project[0]
    return {'project': project}


@aiohttp_jinja2.template('view_report.html')
def view_report(request):
    path = request.match_info['report_path']
    file_path = os.path.join(CWD, path)
    if os.path.isfile(file_path):
        content = open(file_path, 'r').read()
    else:
        content = 'No report found.'
    return {'path': path, 'content': content}

@asyncio.coroutine
def run_project(request):
    u"""Запуск сборки get-запросом."""
    if LOCK.is_locked():
        return web.Response(body=b'locked')
    project = request.match_info['project']
    print('Command to start %s' % project)
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        project = project[0]
        project['start_at'] = datetime.now().strftime('%d.%m %H:%M:%S')
        broadcast({'type': 'run', 'data': project, 'status': 'success'})
        t = threading.Thread(target=partial(processProject, project))
        agents.put(t)
        t.start()
    return web.Response(body=b'success')


@asyncio.coroutine
def static_handle(request):
    u"""Раздача статики."""
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


def sendGitInfo(msg, ws):
    u"""Отправка гит-инфы в сокет."""
    project = msg.data.split(':')[1]
    project = list(filter(lambda x: x['name'] == project, getProjectsList()))
    if project:
        project = project[0]
        project['git_info'] = getGitInfo(project)
        project['repo_url'] = project['url'].replace(':', '/').replace('git@', 'http://')[:-4]
        ws.send_str(json.dumps({
            'type': 'git_info',
            'data': project
        }))


def sendFullInfo(msg, ws):
    project = msg.data.split(':')[1]
    projects = getProjectsList()
    project = list(filter(lambda x: x['name'] == project, projects))
    pprint(project)
    if project:
        ws.send_str(json.dumps({
            'type': 'full_info',
            'data': project[0]
        }))


def deleteProject(msg, ws):
    project = msg.data.split(':')[1]
    projects = getProjectsList()
    project = list(filter(lambda x: x['name'] == project, projects))
    if project:
        projects.remove(project[0])
        with open(os.path.join(CWD, 'projects.json'), 'w') as f:
            json.dump(projects, f, indent=4)
        ws.send_str(json.dumps({
            'type': 'action',
            'status': 'success',
            'data': project[0]
        }))
    else:
        ws.send_str(json.dumps({
            'type': 'action',
            'status': 'fail',
            'data': {"name": msg.data.split(':')[1]}
        }))


def saveProject(msg, ws):
    project = msg.data[5:]
    project = json.loads(project)
    projects = getProjectsList()
    exists = list(filter(lambda x: x['name'] == project['name'], projects))
    if exists:
        i = projects.index(exists[0])
        projects[i] = project
    else:
        projects.append(project)
    with open(os.path.join(CWD, 'projects.json'), 'w') as f:
        json.dump(projects, f, indent=4)
    ws.send_str(json.dumps({
        'type': 'action',
        'status': 'success',
        'data': project
    }))


def releaseProject(msg, ws):
    u"""Запуск релизной команды."""
    project = msg.data.split(':')[1]
    projects = getProjectsList()
    project = list(filter(lambda x: x['name'] == project, projects))
    if project:
        project = project[0]
    else:
        ws.send_str(json.dumps({
            'type': 'release',
            'status': 'fail',
            'data': {
                'reason': 'No project with this name'
            }
        }))
    logpath = getLogPath(project)
    if not os.path.isdir(logpath):
        ws.send_str(json.dumps({
            'type': 'release',
            'status': 'fail',
            'data': {
                'reason': 'No builds'
            }
        }))
    builds = os.listdir(logpath)
    lastBuild = sorted(builds, reverse=True)[-1]
    step = {
        "name": "release",
        "description": "Deploy as release",
        "cmd": project['release_action']
    }
    print(lastBuild, step)
    runBuildStep(project, step, lastBuild, {'lastBuild': lastBuild})


@asyncio.coroutine
def wshandler(request):
    u"""Обработка web-сокетов."""
    ws = web.WebSocketResponse()
    ws.start(request)
    host = request.headers['X-Real-IP']
    print('New ws connection: %s' % colored(host, 'cyan'))
    connections.append(ws)

    while True:
        msg = yield from ws.receive()
        print('Received data: %s' % colored(msg.data, 'yellow'))

        if msg.tp == web.MsgType.text:
            if msg.data == 'disconnect':
                break
            elif msg.data.startswith('info:'):
                sendGitInfo(msg, ws)
            elif msg.data.startswith('fullinfo:'):
                sendFullInfo(msg, ws)
            elif msg.data.startswith('delete:'):
                deleteProject(msg, ws)
            elif msg.data.startswith('save:'):
                saveProject(msg, ws)
            elif msg.data.startswith('release:'):
                releaseProject(msg, ws)
            else:
                ws.send_str("Error 418: im a teapot")
        elif msg.tp == web.MsgType.binary:
            ws.send_bytes(msg.data)
        elif msg.tp == web.MsgType.close:
            break
    connections.remove(ws)
    return ws


@asyncio.coroutine
def hook(request):
    u"""Обработка хука от Гитлаба."""
    data = yield from request.json()
    pprint(data)
    print('Git hook: %s with comment: %s' % (data['repository']['name'], data['commits'][0]['message']))
    broadcast({'type': 'git', 'data': data, 'status': 'success'})
    projects = getProjectsList()
    project = list(filter(lambda x: x['name'] == data['repository']['name'], projects))
    if not project:
        for p in projects:
            if 'deps' in p and data['repository']['name'] in p['deps']:
                project = p
    else:
        project = project[0]
    if project:
        project['start_at'] = datetime.now().strftime('%d.%m %H:%M:%S')
        t = threading.Thread(target=partial(processProject, project, data))
        agents.put(t)
        t.start()
    return web.Response(body=b'')


@asyncio.coroutine
def init(loop):
    u"""Создание сервера."""
    app = web.Application(loop=loop)
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(os.path.join(CWD, 'web/html'))
    )
    app.router.add_route('GET', '/ws', wshandler)
    app.router.add_route('POST', '/hook', hook)
    app.router.add_route('GET', '/', index)
    app.router.add_route('GET', '/dashboard', dashboard)
    app.router.add_route('GET', '/new', new_project)
    app.router.add_route('GET', '/edit/{project}', edit_project)
    app.router.add_route('GET', '/view/{project}', view_project)
    app.router.add_route('GET', '/view_report/{report_path:.*}', view_report)
    # app.router.add_route('GET', '/static/{path:.*}', static_handle)
    app.router.add_route('GET', '/run/{project}', run_project)
    app.router.add_static('/static', os.path.join(CWD, 'web'))
    app.router.add_static('/logs', os.path.join(CWD, 'logs'))
    app.router.add_static('/artefacts', os.path.join(CWD, 'artefacts'))

    srv = yield from loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    print("Server started at http://0.0.0.0:%s" % PORT)
    return srv

if __name__ == '__main__':
    loop.run_until_complete(init(loop))
    loop.run_forever()
    loop.close()
