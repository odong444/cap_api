Starting Container
Traceback (most recent call last):
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 609, in spawn_worker
    worker.init_process()
    ~~~~~~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 134, in init_process
    self.load_wsgi()
    ~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 146, in load_wsgi
    self.wsgi = self.app.wsgi()
                ~~~~~~~~~~~~~^^
[2026-01-20 10:34:29 +0000] [1] [INFO] Starting gunicorn 21.2.0
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 67, in wsgi
[2026-01-20 10:34:29 +0000] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)
[2026-01-20 10:34:29 +0000] [1] [INFO] Using worker: sync
    self.callable = self.load()
[2026-01-20 10:34:29 +0000] [2] [INFO] Booting worker with pid: 2
                    ~~~~~~~~~^^
[2026-01-20 10:34:29 +0000] [2] [ERROR] Exception in worker process
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 58, in load
    return self.load_wsgiapp()
           ~~~~~~~~~~~~~~~~~^^
  File "<frozen importlib._bootstrap_external>", line 1087, in source_to_code
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/app/app.py", line 11
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                  ^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 48, in load_wsgiapp
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
    return util.import_app(self.app_uri)
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap_external>", line 1019, in exec_module
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/util.py", line 371, in import_app
  File "<frozen importlib._bootstrap_external>", line 1157, in get_code
    mod = importlib.import_module(module)
  File "/mise/installs/python/3.13.11/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: invalid decimal literal
[2026-01-20 10:34:29 +0000] [2] [INFO] Worker exiting (pid: 2)
[2026-01-20 10:34:29 +0000] [1] [ERROR] Worker (pid:2) exited with code 3
[2026-01-20 10:34:29 +0000] [1] [ERROR] Shutting down: Master
[2026-01-20 10:34:29 +0000] [1] [ERROR] Reason: Worker failed to boot.
    return self.load_wsgiapp()
           ~~~~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 609, in spawn_worker
    worker.init_process()
    ~~~~~~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 134, in init_process
    self.load_wsgi()
    ~~~~~~~~~~~~~~^^
[2026-01-20 10:34:30 +0000] [1] [INFO] Starting gunicorn 21.2.0
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 146, in load_wsgi
[2026-01-20 10:34:30 +0000] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)
    self.wsgi = self.app.wsgi()
[2026-01-20 10:34:30 +0000] [1] [INFO] Using worker: sync
                ~~~~~~~~~~~~~^^
[2026-01-20 10:34:30 +0000] [2] [INFO] Booting worker with pid: 2
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 67, in wsgi
    self.callable = self.load()
[2026-01-20 10:34:30 +0000] [2] [ERROR] Exception in worker process
                    ~~~~~~~~~^^
Traceback (most recent call last):
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 58, in load
    mod = importlib.import_module(module)
  File "/mise/installs/python/3.13.11/lib/python3.13/importlib/__init__.py", line 88, in import_module
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 48, in load_wsgiapp
    return _bootstrap._gcd_import(name[level:], package, level)
    return util.import_app(self.app_uri)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap_external>", line 1157, in get_code
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/util.py", line 371, in import_app
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1087, in source_to_code
  File "/app/app.py", line 11
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                  ^
  File "<frozen importlib._bootstrap_external>", line 1019, in exec_module
SyntaxError: invalid decimal literal
[2026-01-20 10:34:30 +0000] [2] [INFO] Worker exiting (pid: 2)
[2026-01-20 10:34:30 +0000] [1] [ERROR] Worker (pid:2) exited with code 3
[2026-01-20 10:34:30 +0000] [1] [ERROR] Shutting down: Master
[2026-01-20 10:34:30 +0000] [1] [ERROR] Reason: Worker failed to boot.
[2026-01-20 10:34:31 +0000] [1] [INFO] Starting gunicorn 21.2.0
[2026-01-20 10:34:31 +0000] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)
[2026-01-20 10:34:31 +0000] [1] [INFO] Using worker: sync
[2026-01-20 10:34:31 +0000] [2] [INFO] Booting worker with pid: 2
[2026-01-20 10:34:31 +0000] [2] [ERROR] Exception in worker process
    return self.load_wsgiapp()
Traceback (most recent call last):
           ~~~~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 609, in spawn_worker
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 48, in load_wsgiapp
    return util.import_app(self.app_uri)
    worker.init_process()
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/util.py", line 371, in import_app
    ~~~~~~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 134, in init_process
    self.load_wsgi()
    ~~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/workers/base.py", line 146, in load_wsgi
    self.wsgi = self.app.wsgi()
                ~~~~~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 67, in wsgi
    self.callable = self.load()
                    ~~~~~~~~~^^
  File "/app/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 58, in load
[2026-01-20 10:34:31 +0000] [2] [INFO] Worker exiting (pid: 2)
    mod = importlib.import_module(module)
  File "/mise/installs/python/3.13.11/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
