"""
Production-Ready Multi-Worker Launcher for Vertex Construction & PCCC
Automatically configures Gunicorn + Uvicorn Workers for Linux / Cloud Servers
and Multi-process Uvicorn for Windows Server to maximize High Concurrency.
"""
import os
import sys
import platform
import multiprocessing
import argparse
from app.config import settings

def parse_args():
    parser = argparse.ArgumentParser(description="Khởi chạy hệ thống Vertex Quote Automation (Multi-Worker)")
    parser.add_argument("--host", type=str, default=settings.HOST, help="Host binding (Default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Port binding (Default: 8000)")
    parser.add_argument("--workers", type=int, default=None, help="Số lượng worker processes (Mặc định: 2x CPU cores)")
    parser.add_argument("--dev", action="store_true", help="Chạy chế độ Development với Auto-reload")
    return parser.parse_args()


def main():
    args = parse_args()
    host = os.environ.get("HOST", args.host)
    port = int(os.environ.get("PORT", args.port))
    cpu_count = multiprocessing.cpu_count()
    
    # Calculate optimal worker count
    if args.workers:
        workers = args.workers
    else:
        env_workers = os.environ.get("WEB_CONCURRENCY")
        if env_workers:
            workers = int(env_workers)
        else:
            workers = max(2, min(cpu_count * 2, 8))

    is_windows = platform.system() == "Windows"

    print("=" * 65)
    print("  🚀 VERTEX CONSTRUCTION & PCCC - HIGH CONCURRENCY ENGINE")
    print(f"  🏢 System: {platform.system()} ({platform.machine()}) | CPU Cores: {cpu_count}")
    print(f"  ⚡ Workers: {workers} processes | Mode: {'Development (Reload)' if args.dev else 'Production'}")
    print(f"  🌐 Endpoint: http://{host}:{port}")
    print(f"  🔒 Security: Rate Limiting & OWASP Headers Active")
    print("=" * 65)

    if args.dev:
        # Development mode with auto-reload
        import uvicorn
        uvicorn.run("main:app", host=host, port=port, reload=True)
    else:
        if is_windows:
            # On Windows: run multi-process Uvicorn
            import uvicorn
            uvicorn.run("main:app", host=host, port=port, workers=workers, access_log=True)
        else:
            # On Linux / Cloud / Docker: run Gunicorn with Uvicorn workers
            from gunicorn.app.base import BaseApplication

            class GunicornApp(BaseApplication):
                def __init__(self, app_uri, options=None):
                    self.options = options or {}
                    self.app_uri = app_uri
                    super().__init__()

                def load_config(self):
                    for key, value in self.options.items():
                        self.cfg.set(key.lower(), value)

                def load(self):
                    import importlib
                    module_name, app_name = self.app_uri.split(":")
                    module = importlib.import_module(module_name)
                    return getattr(module, app_name)

            options = {
                "bind": f"{host}:{port}",
                "workers": workers,
                "worker_class": "uvicorn.workers.UvicornWorker",
                "timeout": 120,
                "keepalive": 5,
                "accesslog": "-",
                "errorlog": "-",
                "max_requests": 10000,
                "max_requests_jitter": 500
            }
            GunicornApp("main:app", options).run()


if __name__ == "__main__":
    main()
