from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from api.schemas import QuoteIn
from engine import pricing

router = APIRouter(prefix="/api/pricing", tags=["pricing"])
D = Decimal


@router.get("/defaults")
def defaults():
    return {
        "params": [
            {"key": "key_rate", "label": "Ключевая ставка", "value": 0.14, "badge": "Факт",
             "source": "Банк России: 14,00% с 27.07.2026, сохранена 11.09.2026"},
            {"key": "premium_bank", "label": "Премия: банк-партнёр", "value": 0.01, "badge": "Гипотеза",
             "source": "KС + 0,5–1,0 п.п.; RUONIA ≈ KС"},
            {"key": "premium_line", "label": "Премия: кредитная линия фактору", "value": 0.025, "badge": "Гипотеза",
             "source": "KС + 2–3 п.п. (Коммерсантъ, январь 2026)"},
            {"key": "premium_cfa", "label": "Премия: ЦФА для инвесторов", "value": 0.045, "badge": "Факт и гипотеза",
             "source": "≈18,5% в сделке Т-Банка, август 2026; диапазон 3–5 п.п."},
            {"key": "pd", "label": "PD якоря A / B / C / D", "value": [0.005, 0.01, 0.02, 0.04], "badge": "Гипотеза",
             "source": "Внутренняя шкала"},
            {"key": "lgd", "label": "LGD", "value": 0.6, "badge": "Гипотеза", "source": "Допущение автора"},
            {"key": "cover", "label": "Страховое покрытие", "value": 0.0, "badge": "Гипотеза", "source": "0–80%"},
            {"key": "r_opex", "label": "r_opex", "value": 0.012, "badge": "Гипотеза", "source": "Компонент цены"},
            {"key": "r_margin", "label": "r_margin", "value": 0.024, "badge": "Гипотеза", "source": "Компонент цены"},
            {"key": "t_days", "label": "Срок", "value": 45, "badge": "Гипотеза", "source": "Диапазон 14–90 дней"},
            {"key": "msp_rate", "label": "Кредит МСП до 1 года", "value": 0.18, "badge": "Факт",
             "source": "Банк России, июнь 2026"},
            {"key": "factoring", "label": "Факторинг в программе крупного ритейлера", "value": [0.02, 0.07],
             "badge": "Факт", "source": "Вебинар X5, ноябрь 2023 (данные 2023 года)"},
        ],
        "sources": {k: {"name": v["name"], "premium": float(v["premium"]), "on_balance": v["on_balance"],
                        "badge": v["badge"], "range": [float(x) for x in v["range"]]}
                    for k, v in pricing.FUNDING_SOURCES.items()},
        "ratings": {k: float(v) for k, v in pricing.RATING_PD.items()},
    }


@router.post("/quote")
def quote(q: QuoteIn):
    if q.source == "mix":
        prem = {k: v["premium"] for k, v in pricing.FUNDING_SOURCES.items()}
        r_fund = pricing.r_fund_blended(q.weights, q.key_rate, prem)
        premium = r_fund - q.key_rate
    else:
        premium = q.premium if q.premium is not None else pricing.FUNDING_SOURCES[q.source]["premium"]
        r_fund = q.key_rate + premium
    pd = q.pd if q.pd is not None else pricing.RATING_PD[q.rating]
    p = pricing.price(pricing.PriceInput(face=q.face, t_days=q.t_days, r_fund=r_fund, pd=pd, lgd=q.lgd,
                                         cover=q.cover, r_opex=q.r_opex, r_margin=q.r_margin, mode=q.mode,
                                         msp_rate=q.msp_rate))
    max_prem = pricing.max_premium_for_msp_parity(q.key_rate, pd, q.lgd, q.cover, q.r_opex, q.r_margin,
                                                  q.t_days, q.msp_rate)
    k = D(q.t_days) / D(365)
    msp_cost = (q.face - p.discount) * q.msp_rate * k
    fact_lo, fact_hi = (q.key_rate + x for x in pricing.FACTORING_RANGE)
    diff_pp = (p.eff_rate - q.msp_rate) * 100
    if p.eff_rate > q.msp_rate:
        verdict = {
            "kind": "more_expensive",
            "title": f"Дороже кредита МСП на {_pp(diff_pp)}",
            "text": "При фондировании около ключевой ставки дисконт не ниже краткосрочного кредита. "
                    "Поставщик платит за скорость: деньги в течение суток после акцепта, без залога и без "
                    "кредитного лимита банка на поставщика.",
        }
    else:
        verdict = {
            "kind": "cheaper",
            "title": f"Не дороже кредита МСП (разница {_pp(diff_pp)})",
            "text": "При этих параметрах эффективная ставка не выше средней ставки по кредитам МСП до 1 года.",
        }
    return {
        "input": {"r_fund": r_fund, "premium": premium, "pd": pd},
        "price": p.as_dict(),
        "waterfall": [
            {"key": "funding", "label": "Фондирование", "amount": p.comp_funding, "rate": r_fund},
            {"key": "loss", "label": "Ожидаемые потери", "amount": p.comp_loss, "rate": p.r_el},
            {"key": "opex", "label": "Операционные издержки", "amount": p.comp_opex, "rate": q.r_opex},
            {"key": "margin", "label": "Маржа платформы", "amount": p.comp_margin, "rate": p.r_margin_effective},
        ],
        "compare": {
            "msp_rate": q.msp_rate,
            "msp_cost": msp_cost.quantize(D("0.01")),
            "overpay_vs_msp": (p.discount - msp_cost).quantize(D("0.01")),
            "factoring_low": fact_lo, "factoring_high": fact_hi,
            "factoring_label": "Факторинг в программе крупного ритейлера: KС + 2…7% (данные 2023 года)",
            "cap_rate": q.msp_rate + pricing.SPEED_PREMIUM,
        },
        "verdict": verdict,
        "parity_premium": max_prem,
        "premium_curve": pricing.premium_curve(q.key_rate, pd, q.lgd, q.cover, q.r_opex, q.r_margin, q.t_days),
    }


def _pp(x: Decimal) -> str:
    return f"{abs(x):.2f}".replace(".", ",") + " п.п."
