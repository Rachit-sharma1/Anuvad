import os
import sys
import time
import signal
import subprocess


def _popen(cmd, env=None):
    return subprocess.Popen(
        cmd,
        env=env,
        stdout=None,
        stderr=None,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def main():
    base_env = os.environ.copy()

    # Ensure the main app points to the local search service.
    base_env.setdefault("SEARCH_SERVICE_URL", "http://127.0.0.1:5001/search")

    # Search service process
    search_env = base_env.copy()
    search_env.setdefault("SEARCH_SERVICE_PORT", "5001")

    # Main Flask app process
    app_env = base_env.copy()
    # Make Flask explicitly load app.py
    app_env.setdefault("FLASK_APP", "app.py")
    app_env.setdefault("FLASK_RUN_HOST", "127.0.0.1")
    app_env.setdefault("FLASK_RUN_PORT", "5000")

    print("Starting search service on http://127.0.0.1:5001 ...")
    search_proc = _popen([sys.executable, os.path.join(os.path.dirname(__file__), "search_service.py")], env=search_env)

    # Small delay so the search service binds before the main app starts.
    time.sleep(1.0)

    print("Starting main app on http://127.0.0.1:5000 ...")
    app_proc = _popen([sys.executable, "-m", "flask", "run"], env=app_env)

    procs = [search_proc, app_proc]

    try:
        while True:
            for p in procs:
                code = p.poll()
                if code is not None:
                    raise RuntimeError(f"A service exited unexpectedly (pid={p.pid}, code={code}).")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for p in procs:
            try:
                if os.name == "nt":
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                    time.sleep(0.5)
                p.terminate()
            except Exception:
                pass
        time.sleep(1.0)
        for p in procs:
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
