"""FastAPI-приложение SupplyLine. Единственный источник правды для расчётов: engine/*."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from api import content
from api import services as sv
from api.routers import demo, finmodel, pricing
from db.models import SessionLocal, engine, init_db

app = FastAPI(title="SupplyLine API", version="0.1.0",
              description=content.DISCLAIMER + " Все расчёты выполняет engine/*.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


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


@app.on_event("startup")
def _startup() -> None:
    init_db()
    with SessionLocal() as s:
        if not inspect(engine).has_table("settings") or sv.get_setting(s, "now") is None:
            from db.seed import seed

            seed()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    return {"disclaimer": content.DISCLAIMER, "facts": content.FACTS, "checklist": content.CHECKLIST,
            "layers": content.LAYERS, "roadmap": content.ROADMAP, "reality": content.REALITY,
            "glossary": content.GLOSSARY, "facts_as_of": "11.10.2026"}


@app.post("/api/demo/reset")
def reset():
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
