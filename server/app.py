import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import auth, projects, files, products, recordings, documents, integrations, delivery, asr, sources,document_revisions,automation,project_catalog,workflow,activity,development,agent
from .db import Base, connect


def create_app(database_url=None, storage_dir=None, testing=False):
    from dotenv import load_dotenv
    if not testing:
        load_dotenv()
    root = Path(__file__).resolve().parents[1]
    directory = Path(storage_dir or os.getenv('STORAGE_DIR', str(root / 'data/files')))
    directory.mkdir(parents=True, exist_ok=True)
    url = database_url or os.getenv('DATABASE_URL', 'sqlite:///' + (root / 'data/platform.db').as_posix())
    engine, sessions = connect(url)

    @asynccontextmanager
    async def lifespan(app):
        if testing:
            Base.metadata.create_all(engine)
        else:
            from alembic import command
            from alembic.config import Config
            config=Config(str(root/'alembic.ini'))
            config.set_main_option('script_location',str(root/'migrations'))
            config.attributes['database_url']=url
            command.upgrade(config,'head')
            from .recording_imports import migrate_audio
            migrate_audio(app)
        import asyncio
        from contextlib import suppress
        sync_task=asyncio.create_task(sources.background_sync(app)) if not testing else None
        analysis_task=asyncio.create_task(automation.background_analysis(app)) if not testing else None
        discovery_task=asyncio.create_task(project_catalog.background_discovery(app)) if not testing else None
        development_task=asyncio.create_task(development.background_daily(app)) if not testing else None
        yield
        if development_task:
            development_task.cancel()
            with suppress(asyncio.CancelledError):await development_task
        if discovery_task:
            discovery_task.cancel()
            with suppress(asyncio.CancelledError):await discovery_task
        if analysis_task:
            analysis_task.cancel()
            with suppress(asyncio.CancelledError):await analysis_task
        if sync_task:
            sync_task.cancel()
            with suppress(asyncio.CancelledError):await sync_task
        engine.dispose()

    app = FastAPI(title='行序', lifespan=lifespan, docs_url='/api/docs' if testing else None, redoc_url=None)
    app.state.sessions = sessions
    app.state.storage = directory.resolve()
    app.state.testing = testing
    hosts = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    origins = set(os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8765,http://localhost:8765').split(','))

    @app.middleware('http')
    async def security(request: Request, call_next):
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in origins:
            return JSONResponse({'detail': '请求来源无效'}, status_code=403)
        try:
            response = await call_next(request)
        except Exception:
            logging.exception('Request failed: %s %s', request.method, request.url.path)
            if testing:
                raise
            return JSONResponse({'detail': '操作失败，请稍后重试'}, status_code=500)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return JSONResponse({'detail': '请检查填写内容', 'fields': ['.'.join(map(str, e['loc'][1:])) for e in exc.errors()]}, status_code=422)

    @app.exception_handler(StaleDataError)
    async def stale(request, exc):
        return JSONResponse({'detail': '内容已更新，请刷新后重试'}, status_code=409)

    @app.exception_handler(IntegrityError)
    async def integrity(request, exc):
        return JSONResponse({'detail': '记录冲突，请刷新后重试'}, status_code=409)

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    for module in (auth, projects, files, products, recordings, documents, integrations, delivery, asr, sources,document_revisions,automation,project_catalog,workflow,activity,development,agent):
        app.include_router(module.router)
    dist = root / 'web/dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='web')
    return app
