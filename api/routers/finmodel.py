from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from api import finmodel_meta
from api.schemas import FinRunIn
from engine import finmodel as fm

router = APIRouter(prefix="/api/finmodel", tags=["finmodel"])

ASSUMPTIONS = [
    "Фондирование считается на номинал счёта (консервативно).",
    "Налоговый убыток переносится полностью, без ограничения 50% базы.",
    "Нормы капитала упрощены: 10% от риска, который несёт организатор.",
    "В базе реализованные потери равны ожидаемым; дефолт якоря показан отдельно в стресс-тесте.",
    "Чувствительность к сроку приближённая: остаток пропорционален сроку.",
    "Экономику банка, оператора ЦФА и страховщика нужно подтвердить письмами о намерениях.",
    "Демо-счета и финансовая модель независимы: модель считается по своим параметрам и не агрегирует демо-счета.",
]


def build_params(body: FinRunIn) -> fm.FinParams:
    data = body.model_dump(exclude_none=True, exclude={"months", "weights_m"})
    p = fm.FinParams()
    try:
        p = p.with_overrides(**data)
        if body.weights_m is not None:
            w = list(p.weights)
            w[3] = tuple(body.weights_m)
            p = p.with_overrides(weights=w)
    except (ValueError, fm.FinModelError) as e:
        raise HTTPException(422, str(e)) from e
    return p


@router.get("/defaults")
def defaults():
    return {"params": finmodel_meta.defaults(), "assumptions": ASSUMPTIONS,
            "scenarios": fm.SCENARIO_NAMES, "price_modes": fm.PRICE_MODE_NAMES,
            "sources": fm.SOURCE_NAMES, "sensitivity_drivers": [
                {"key": k, "name": n, "low": float(lo), "high": float(hi), "note": note}
                for k, n, lo, hi, note in fm.SENS_DRIVERS]}


@router.post("/run")
def run_model(body: FinRunIn):
    p = build_params(body)
    try:
        res = fm.run(p)
    except fm.FinModelError as e:
        raise HTTPException(422, str(e)) from e
    if not body.months:
        res.pop("months")
    res["assumptions"] = ASSUMPTIONS
    res["label"] = "Гипотезы. Не прогноз."
    return fm.to_jsonable(res)


@router.get("/excel")
def excel() -> FileResponse:
    return FileResponse(finmodel_meta.BOOK, filename="SupplyLine_financial_model.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/excel")
def excel_with_params(body: FinRunIn) -> Response:
    p = build_params(body)
    data = finmodel_meta.export_xlsx(p)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="SupplyLine_model_current.xlsx"'})
