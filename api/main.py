"""FastAPI-приложение SupplyLine. Единственный источник правды для расчётов: engine/*."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from api import content, sandbox
from api import services as sv
from api.routers import demo, finmodel, pricing
from db.models import SessionLocal, engine, init_db


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(600)
        await asyncio.to_thread(sandbox.cleanup)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = None
    if sandbox.ENABLED:
        # Шаблон сидируется в фоне: /api/health отвечает сразу, остальное API — 503 до готовности
        threading.Thread(target=sandbox.prepare_template, daemon=True).start()
        task = asyncio.create_task(_cleanup_loop())
    else:
        init_db()
        with SessionLocal() as s:
            if not inspect(engine).has_table("settings") or sv.get_setting(s, "now") is None:
                from db.seed import seed

                seed()
        sandbox.mark_ready()
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="SupplyLine API", version="0.1.0", lifespan=lifespan,
              description=content.DISCLAIMER + " Все расчёты выполняет engine/*.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin", "X-Frame-Options": "DENY"}
WAIT_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="3">
<title>SupplyLine</title><style>body{font:16px/1.5 system-ui,sans-serif;margin:0;display:grid;place-items:center;
min-height:100vh;background:#F7F8FA;color:#1B2230}@media(prefers-color-scheme:dark){body{background:#0F131A;
color:#E6E9EF}}</style></head><body><main><h1>Готовим демо, 10 секунд</h1>
<p>Генерируем синтетические счета. Страница обновится сама.</p></main></body></html>"""


def _json_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


@app.middleware("http")
async def sandbox_guard(request: Request, call_next) -> Response:
    path = request.url.path
    api = path.startswith("/api/")
    if path in ("/api/health", "/api/ready"):
        resp = await call_next(request)
    elif not sandbox.is_ready():
        resp = (_json_error(503, "warming_up", "Демо готовится: данные генерируются. Повторите через 10 секунд")
                if api else HTMLResponse(WAIT_PAGE, status_code=503))
    elif not sandbox.ENABLED or not api:
        resp = await call_next(request)
    else:
        sid = request.cookies.get(sandbox.COOKIE)
        fresh = not sandbox.valid_sid(sid)
        if fresh:
            sid = sandbox.new_sid()
        ip = request.client.host if request.client else "?"
        if int(request.headers.get("content-length") or 0) > sandbox.MAX_BODY:
            resp = _json_error(413, "too_large", "Слишком большой запрос: не больше 64 КБ")
        elif not sandbox.limiter.allow(sid) or not sandbox.ip_limiter.allow(ip):
            resp = _json_error(429, "rate_limited", "Слишком много запросов. Подождите минуту и повторите")
        else:
            request.state.sid = sid
            resp = await call_next(request)
        if fresh:
            resp.set_cookie(sandbox.COOKIE, sid, max_age=sandbox.TTL_SECONDS, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


@app.exception_handler(sv.ServiceError)
async def service_error(_: Request, exc: sv.ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content=jsonable_encoder({"code": exc.code, "message": exc.message, **exc.extra}))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errs = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": _ru(e)} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"code": "validation", "message": "Проверьте значения полей",
                                                  "errors": errs})


def _ru(e: dict) -> str:
    t = e.get("type", "")
    ctx = e.get("ctx") or {}
    if t in ("greater_than", "greater_than_equal"):
        return f"Должно быть не меньше {ctx.get('gt', ctx.get('ge'))}"
    if t in ("less_than", "less_than_equal"):
        return f"Должно быть не больше {ctx.get('lt', ctx.get('le'))}"
    if t == "literal_error":
        return f"Допустимые значения: {ctx.get('expected')}"
    if t == "value_error":
        return str(ctx.get("error", e.get("msg")))
    return e.get("msg", "Недопустимое значение")



@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/ready")
def ready():
    if sandbox.is_ready():
        return {"ready": True, "sandbox": sandbox.ENABLED}
    return JSONResponse(status_code=503, content={"ready": False, "error": sandbox.failed()})


@app.get("/api/meta")
def meta():
    return {"disclaimer": content.DISCLAIMER, "facts": content.FACTS, "checklist": content.CHECKLIST,
            "layers": content.LAYERS, "roadmap": content.ROADMAP, "reality": content.REALITY,
            "glossary": content.GLOSSARY, "facts_as_of": content.FACTS_AS_OF}


@app.post("/api/demo/reset")
def reset(request: Request):
    sid = getattr(request.state, "sid", None)
    if sandbox.ENABLED and sid:
        return sandbox.reset(sid)
    from db.seed import seed

    return seed()


app.include_router(pricing.router)
app.include_router(finmodel.router)
app.include_router(demo.router)

WEB = Path(__file__).resolve().parents[1] / "web" / "dist"
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = WEB / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
