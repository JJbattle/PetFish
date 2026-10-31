"""Run exactly one Godot test, with a hard timeout and verified cleanup.

The point of this wrapper is that a test run can never be "started and
forgotten": every round records its own PID, is killed as a tree if it runs
past its timeout, and the wrapper refuses to start another round until that PID
is confirmed gone.  It never kills anything by image name, so the editor and the
user's own game are out of reach.

    python tools/testrun.py --timeout 180 --log tools/_debug/test_runs/x.log -- \
        godot --path game --rendering-driver opengl3 res://tests/clip_shot.tscn -- idle:0.5

Exit codes
    0..   the test's own exit code
    124   timed out, process tree killed, exit verified
    125   a previous round's process is still alive - refusing to start
    126   bad command line (nothing started)

Rules enforced here
    * engine options must come before the `--` separator; a `--rendering-driver`
      or `--path` after it is rejected instead of being silently fed to the
      scene (that is what used to make runs hang until the wrapper timed out)
    * the child gets its own process group, and only that group is killed
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, 'tools', '_debug', 'test_runs')
STATE = os.path.join(STATE_DIR, 'current.json')

ENGINE_OPTS = ('--rendering-driver', '--path', '--headless', '--resolution',
               '--quit-after', '--verbose', '--editor')


def _tasklist(pid):
    try:
        out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        out = ''
    return str(pid) in out


def _kill_tree(pid):
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                   capture_output=True, text=True)
    for _ in range(50):
        if not _tasklist(pid):
            return True
        time.sleep(0.1)
    return not _tasklist(pid)


def _parse():
    argv = sys.argv[1:]
    timeout = 180.0
    log = None
    cmd = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--':
            cmd = argv[i + 1:]
            break
        if a == '--timeout':
            i += 1
            timeout = float(argv[i])
        elif a == '--log':
            i += 1
            log = argv[i]
        else:
            sys.stderr.write('testrun: unknown option %s\n' % a)
            sys.exit(126)
        i += 1
    if not cmd:
        sys.stderr.write('testrun: no command after --\n')
        sys.exit(126)
    if '--' in cmd:
        sep = cmd.index('--')
        bad = [x for x in cmd[sep + 1:] if x in ENGINE_OPTS]
        if bad:
            sys.stderr.write(
                'testrun: engine option(s) %s appear after "--"; they would be '
                'passed to the scene. Put them before the separator.\n'
                % ', '.join(bad))
            sys.exit(126)
    return timeout, log, cmd


def main():
    timeout, log_path, cmd = _parse()
    os.makedirs(STATE_DIR, exist_ok=True)

    # -- refuse to run while a previous round is still alive -------------------
    if os.path.exists(STATE):
        try:
            prev = json.load(open(STATE, encoding='utf-8'))
        except (OSError, ValueError):
            prev = {}
        pid = int(prev.get('pid', 0) or 0)
        if pid and _tasklist(pid):
            sys.stderr.write(
                'testrun: previous round pid %d (%s) is still running - '
                'waiting is not allowed, cleaning it up first\n'
                % (pid, prev.get('cmd', '')))
            if not _kill_tree(pid):
                sys.stderr.write('testrun: could not kill pid %d; refusing\n' % pid)
                sys.exit(125)
            print('CLEANED leftover pid=%d gone=%s' % (pid, not _tasklist(pid)))
        os.remove(STATE)

    log_path = log_path or os.path.join(STATE_DIR, 'run.log')
    os.makedirs(os.path.dirname(log_path) or '.', exist_ok=True)
    log = open(log_path, 'w', encoding='utf-8', errors='replace')
    started = time.time()
    print('RUN  %s' % ' '.join(cmd))
    print('LOG  %s  timeout %.0fs' % (log_path, timeout))
    try:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    except OSError as exc:
        print('START FAILED: %s' % exc)
        sys.exit(126)
    json.dump({'pid': proc.pid, 'cmd': ' '.join(cmd), 'started': started},
              open(STATE, 'w', encoding='utf-8'))

    timed_out = False
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        print('TIMEOUT after %.0fs - killing pid %d tree' % (timeout, proc.pid))
        _kill_tree(proc.pid)
        try:
            code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            code = 124

    elapsed = time.time() - started
    gone = not _tasklist(proc.pid)
    log.close()
    if gone:
        os.remove(STATE)
    print('DONE pid=%d exit=%d elapsed=%.1fs timeout=%s process_gone=%s'
          % (proc.pid, 124 if timed_out else code, elapsed, timed_out, gone))
    tail = open(log_path, encoding='utf-8', errors='replace').read().splitlines()[-12:]
    for line in tail:
        print('  | %s' % line)
    if not gone:
        sys.stderr.write('testrun: pid %d still alive after cleanup\n' % proc.pid)
        sys.exit(125)
    sys.exit(124 if timed_out else code)


if __name__ == '__main__':
    main()
