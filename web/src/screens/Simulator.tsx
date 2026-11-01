import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { api, errorText, useDebounced } from "../api/client";
import { days, num, pct, pp, rub } from "../api/format";
import { axisCommon, Chart, type ChartTokens } from "../components/Chart";
import { PageHead } from "../components/Layout";
import { Badge, Callout, Card, DataTableToggle, ErrorBox, Loading, Metric, Segmented, SliderField, Term } from "../components/ui";
import { ru } from "../copy/ru";

type Source = "bank" | "line" | "cfa" | "mix";
type Price = {
  r_total: number; r_total_formula: number; r_cap: number; capped: boolean; r_margin_effective: number; r_el: number;
  discount: number; payout: number; comp_funding: number; comp_loss: number; comp_opex: number; comp_margin: number;
  spread: number; spread_pct_cycle: number; eff_rate: number; msp_rate: number; cap_rate: number; cheaper_than_msp: boolean;
};
type Quote = {
  input: { r_fund: number; premium: number; pd: number };
  price: Price;
  waterfall: { key: string; label: string; amount: number; rate: number }[];
  compare: { msp_rate: number; msp_cost: number; overpay_vs_msp: number; factoring_low: number; factoring_high: number; cap_rate: number };
  verdict: { kind: string; title: string; text: string };
  parity_premium: number;
  premium_curve: { premium: number; eff_rate: number }[];
};

const PREMIUM: Record<Source, number> = { bank: 0.01, line: 0.025, cfa: 0.045, mix: 0.01975 };
const PD: Record<string, number> = { A: 0.005, B: 0.01, C: 0.02, D: 0.04 };

export default function Simulator() {
  const [p, setP] = useState({
    key_rate: 0.14, source: "bank" as Source, premium: 0.01, mode: 1 as 1 | 2, t_days: 45, face: 10_000_000,
    rating: "B", lgd: 0.6, cover: 0, r_opex: 0.012, r_margin: 0.024,
  });
  const set = useCallback(<K extends keyof typeof p>(k: K, v: (typeof p)[K]) => setP((x) => ({ ...x, [k]: v })), []);
  const dp = useDebounced(p, 150);
  const body = useMemo(() => {
    const { source, premium, ...rest } = dp;
    return source === "mix" ? { ...rest, source } : { ...rest, source, premium };
  }, [dp]);
  const q = useQuery({
    queryKey: ["quote", body],
    queryFn: () => api<Quote>("/api/pricing/quote", { method: "POST", json: body }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHead
        title={ru.simulator.title}
        lead={
          <>
            Цена <Term t="дисконт">дисконта</Term> считается по формуле от риска <Term t="якорь">якоря</Term>. Параметры с бейджем
            «Гипотеза» — допущения, их можно двигать.
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-12">
        <Card title={ru.simulator.params} className="order-2 lg:order-1 lg:col-span-4 lg:self-start">
          <div className="flex flex-col gap-5">
            <SliderField label={<Term t="KС">Ключевая ставка</Term>} badge={<Badge kind="Факт" source="Банк России: 14,00% с 27.07.2026, сохранена 11.09.2026" />}
              value={p.key_rate} onChange={(v) => set("key_rate", v)} min={0.05} max={0.25} step={0.0025} scale={100} digits={2} unit="%" />
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-small font-medium">{ru.simulator.source}</div>
              <Segmented<Source> label={ru.simulator.source} value={p.source} size="sm"
                onChange={(v) => setP((x) => ({ ...x, source: v, premium: PREMIUM[v] }))}
                options={[
                  { value: "bank", label: "Банк-партнёр", title: "KС + 0,5–1,0 п.п." },
                  { value: "line", label: "Кредитная линия", title: "KС + 2–3 п.п." },
                  { value: "cfa", label: "ЦФА", title: "KС + 3–5 п.п." },
                  { value: "mix", label: "Смешанная", title: "60/25/10/5" },
                ]} />
            </div>
            {p.source !== "mix" ? (
              <SliderField label={ru.simulator.premium}
                badge={<Badge kind={p.source === "cfa" ? "Факт и гипотеза" : "Гипотеза"} source={
                  p.source === "cfa" ? "≈18,5% в сделке Т-Банка, август 2026 → KС + 4,5 п.п.; диапазон 3–5" :
                  p.source === "line" ? "KС + 2–3 п.п. (Коммерсантъ, январь 2026)" : "RUONIA ≈ KС; банк: KС + 0,5–1,0 п.п."} />}
                value={p.premium} onChange={(v) => set("premium", v)} min={0} max={0.08} step={0.0025} scale={100} digits={2} unit="п.п." />
            ) : (
              <p className="text-caption text-ink2">Баланс 60% (KС + 1), ЦФА 25% (KС + 4,5), казначейства 10% (KС + 2), синдикация 5% (KС + 1): средняя премия 1,975 п.п. <Badge kind="Гипотеза" /></p>
            )}
            <div className="flex flex-col gap-2">
              <div className="text-small font-medium">{ru.simulator.priceMode}</div>
              <Segmented<"1" | "2"> label={ru.simulator.priceMode} value={String(p.mode) as "1" | "2"} size="sm"
                onChange={(v) => set("mode", Number(v) as 1 | 2)}
                options={[{ value: "1", label: ru.simulator.modeFormula }, { value: "2", label: ru.simulator.modeCap }]} />
              {p.mode === 2 && <p className="text-caption text-ink2">{ru.simulator.modeCapHint}</p>}
            </div>
            <SliderField label={ru.simulator.term} badge={<Badge kind="Гипотеза" source="Диапазон 14–90 дней" />}
              value={p.t_days} onChange={(v) => set("t_days", Math.round(v))} min={14} max={90} step={1} digits={0} unit="дн." />
            <SliderField label={ru.simulator.face} value={p.face} onChange={(v) => set("face", v)}
              min={500_000} max={40_000_000} step={100_000} scale={1e-6} digits={1} unit="млн ₽" />
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-small font-medium">{ru.simulator.rating} <Badge kind="Гипотеза" source="PD A 0,5% · B 1,0% · C 2,0% · D 4,0% годовых" /></div>
              <Segmented label={ru.simulator.rating} value={p.rating} size="sm" onChange={(v) => set("rating", v)}
                options={["A", "B", "C", "D"].map((r) => ({ value: r, label: `${r} · PD ${num(PD[r] * 100, 1)}%` }))} />
            </div>
            <SliderField label={<Term t="LGD" />} badge={<Badge kind="Гипотеза" />} value={p.lgd} onChange={(v) => set("lgd", v)}
              min={0} max={1} step={0.05} scale={100} digits={0} unit="%" />
            <SliderField label={ru.simulator.cover} badge={<Badge kind="Гипотеза" source="0–80%; в сделке Т-Банка дебиторка застрахована" />}
              value={p.cover} onChange={(v) => set("cover", v)} min={0} max={0.8} step={0.05} scale={100} digits={0} unit="%" />
            <SliderField label="Операционные издержки в цене" badge={<Badge kind="Гипотеза" />} value={p.r_opex}
              onChange={(v) => set("r_opex", v)} min={0} max={0.05} step={0.001} scale={100} digits={1} unit="%" />
            <SliderField label="Маржа платформы в цене" badge={<Badge kind="Гипотеза" />} value={p.r_margin}
              onChange={(v) => set("r_margin", v)} min={0} max={0.06} step={0.001} scale={100} digits={1} unit="%" />
          </div>
        </Card>

        <div className="order-1 flex flex-col gap-6 lg:order-2 lg:col-span-8">
          {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
          {!q.data ? (
            <Card><Loading rows={5} /></Card>
          ) : (
            <Result q={q.data} t={p.t_days} mode={p.mode} />
          )}
        </div>
      </div>
    </>
  );
}

function Result({ q, t, mode }: { q: Quote; t: number; mode: 1 | 2 }) {
  const pr = q.price;
  const above = !pr.cheaper_than_msp;
  return (
    <>
      <Card>
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
            <Metric big tone={above ? "default" : "accent"}
              label={<Term t="эффективная ставка">{ru.simulator.effRate}</Term>}
              value={pct(pr.eff_rate)}
              note={`Кредит МСП до 1 года: ${pct(q.compare.msp_rate, 1)} (Банк России, июнь 2026)`}
              how={<>D / (F − D) × 365 / t = {rub(pr.discount, 2)} / {rub(pr.payout, 2)} × 365 / {t}</>} />
            <Metric label={ru.simulator.payout} value={rub(pr.payout)} note={`через ${days(t)} вместо ожидания оплаты`}
              how="F − D: номинал минус дисконт" />
          </div>
          <Callout tone={above ? "warning" : "success"} title={q.verdict.title}>
            {q.verdict.text}
          </Callout>
          <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-4">
            <Metric label={<Term t="дисконт">{ru.simulator.discount}</Term>} value={rub(pr.discount)} how="D = F × r × t / 365, округление до копеек" />
            <Metric label={ru.simulator.rateOnFace} value={pct(pr.r_total)}
              how={pr.capped ? `Ограничена потолком: (МСП + 1 п.п.) / (1 + e·t/365) = ${pct(pr.r_cap)}` : "r = r_fund + r_EL + r_opex + r_margin"} />
            <Metric label={<Term t="спред">{ru.simulator.spread}</Term>} value={rub(pr.spread)}
              note={`${pct(pr.spread_pct_cycle, 3)} за цикл`} how="F × (r − r_fund) × t / 365" />
            <Metric label={mode === 2 ? ru.simulator.residualMargin : "Маржа в цене"} value={pp(pr.r_margin_effective)}
              tone={pr.r_margin_effective < 0 ? "negative" : "default"}
              note={pr.r_margin_effective < 0 ? "Отрицательная: цена не покрывает затраты" : "годовых"}
              how="r − r_fund − r_EL − r_opex" />
          </div>
        </div>
      </Card>

      <Card title={ru.simulator.waterfallTitle} lead="Фондирование, ожидаемые потери, издержки и маржа в сумме дают дисконт ровно (остаток округления — в марже).">
        <Waterfall q={q} />
      </Card>

      <Card title={ru.simulator.compareTitle} lead={ru.simulator.valueNote}>
        <CompareTable q={q} />
      </Card>

      <Card title={ru.simulator.curveTitle}
        lead={q.parity_premium >= 0 ? ru.simulator.curveParity(pp(q.parity_premium)) : ru.simulator.curveNever}>
        <Curve q={q} />
      </Card>
    </>
  );
}

function Waterfall({ q }: { q: Quote }) {
  const rows = q.waterfall;
  const D = q.price.discount;
  const option = useCallback((t: ChartTokens) => {
    let acc = 0;
    const base: number[] = [];
    const val: { value: number; itemStyle: { color: string } }[] = [];
    for (const r of rows) {
      const v = r.amount;
      base.push(v >= 0 ? acc : acc + v);
      val.push({ value: Math.abs(v), itemStyle: { color: r.key === "margin" ? (v < 0 ? t.neg : t.accent) : t.context } });
      acc += v;
    }
    base.push(0);
    val.push({ value: D, itemStyle: { color: t.accent } });
    const cats = [...rows.map((r) => r.label), "Дисконт D"];
    return {
      grid: { left: 8, right: 72, top: 8, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "item",
        formatter: (p: { dataIndex: number }) => {
          const i = p.dataIndex;
          if (i === rows.length) return `Дисконт D: <b>${rub(D, 2)}</b>`;
          const r = rows[i];
          return `${r.label}: <b>${rub(r.amount, 2)}</b><br/>Ставка: ${pct(r.rate)} годовых`;
        },
      },
      xAxis: { type: "value", ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => `${num(v / 1000)} тыс.` } },
      yAxis: { type: "category", inverse: true, data: cats, ...axisCommon(t), splitLine: { show: false } },
      series: [
        { type: "bar", stack: "w", data: base, itemStyle: { color: "transparent" }, emphasis: { disabled: true }, tooltip: { show: false }, barWidth: 22 },
        {
          type: "bar", stack: "w", data: val, barWidth: 22, itemStyle: { borderRadius: 4 },
          label: { show: true, position: "right", color: t.text, fontSize: 12, formatter: (p: { dataIndex: number }) =>
            p.dataIndex === rows.length ? rub(D) : rub(rows[p.dataIndex].amount) },
        },
      ],
    };
  }, [rows, D]);
  return (
    <>
      <Chart option={option} height={240} label={`Состав дисконта ${rub(D)}: фондирование ${rub(rows[0].amount)}, маржа ${rub(rows[3].amount)}`} />
      <DataTableToggle caption="Состав дисконта" head={["Компонент", "₽", "% годовых"]}
        rows={[...rows.map((r) => [r.label, rub(r.amount, 2), pct(r.rate)]), ["Дисконт D", rub(D, 2), pct(q.price.r_total)]]} />
    </>
  );
}

function CompareTable({ q }: { q: Quote }) {
  const pr = q.price;
  const rows = [
    { name: "SupplyLine, эффективная ставка", rate: pct(pr.eff_rate), badge: <Badge kind="Гипотеза" source="Расчёт по формуле при выбранных параметрах" />,
      note: "Деньги в течение суток после акцепта, без залога", strong: true },
    { name: ru.simulator.msp, rate: pct(q.compare.msp_rate, 1), badge: <Badge kind="Факт" source="Банк России, средневзвешенная ставка по рублёвым кредитам МСП до 1 года, июнь 2026" />,
      note: "Нужны одобрение, залог или поручительство" },
    { name: ru.simulator.factoring, rate: `${pct(q.compare.factoring_low, 1)} … ${pct(q.compare.factoring_high, 1)}`,
      badge: <Badge kind="Данные 2023 года" source="Вебинар крупного ритейлера для поставщиков, ноябрь 2023; открытого первоисточника нет" />, note: "При текущей KС" },
    { name: "Потолок рынка: кредит МСП + 1 п.п. за скорость", rate: pct(q.compare.cap_rate, 1), badge: <Badge kind="Гипотеза" source="Премия за скорость — проверяется интервью с поставщиками" />,
      note: "Сколько поставщик, по гипотезе, готов платить" },
  ];
  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto" tabIndex={0}>
        <table className="data-table">
          <caption className="sr-only">Сравнение стоимости денег для поставщика</caption>
          <thead><tr><th scope="col">Вариант</th><th scope="col" className="r">Ставка, % годовых</th><th scope="col">Происхождение</th><th scope="col">Условия</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name}>
                <td className={r.strong ? "font-semibold" : ""}>{r.name}</td>
                <td className="r num font-semibold">{r.rate}</td>
                <td>{r.badge}</td>
                <td className="text-ink2">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-small text-ink2">
        В рублях: дисконт {rub(pr.discount)} против {rub(q.compare.msp_cost)} процентов по кредиту МСП на ту же сумму и срок.
        {q.compare.overpay_vs_msp > 0 ? ` Переплата за скорость: ${rub(q.compare.overpay_vs_msp)}.` : ` Экономия: ${rub(-q.compare.overpay_vs_msp)}.`}
      </p>
    </div>
  );
}

function Curve({ q }: { q: Quote }) {
  const pts = q.premium_curve;
  const cur = q.input.premium;
  const msp = q.compare.msp_rate;
  const parity = q.parity_premium;
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 24, top: 28, bottom: 28, containLabel: true },
    tooltip: { trigger: "axis", formatter: (ps: { data: [number, number] }[]) =>
      `Премия ${num(ps[0].data[0], 2)} п.п.<br/>Эффективная ставка: <b>${num(ps[0].data[1], 2)}%</b>` },
    xAxis: { type: "value", name: "Премия фондирования к KС, п.п.", nameLocation: "middle", nameGap: 28, min: 0, max: 6, ...axisCommon(t),
      axisLabel: { color: t.text2, formatter: (v: number) => num(v, 0) } },
    yAxis: { type: "value", name: "% годовых", min: Math.floor(Math.min(msp * 100, pts[0].eff_rate * 100) - 1), ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v, 0) } },
    series: [{
      type: "line", showSymbol: false, lineStyle: { width: 2, color: t.accent }, itemStyle: { color: t.accent },
      data: pts.map((x) => [x.premium * 100, x.eff_rate * 100]),
      markLine: {
        symbol: "none", silent: true,
        label: { color: t.text2, fontSize: 12 },
        data: [
          { yAxis: msp * 100, lineStyle: { color: t.ref, type: "solid", width: 1 }, label: { formatter: `Кредит МСП ${num(msp * 100, 1)}%`, position: "insideEndTop" } },
          ...(parity >= 0 && parity <= 0.06 ? [{ xAxis: parity * 100, lineStyle: { color: t.ref, type: "solid", width: 1 }, label: { formatter: `паритет ${num(parity * 100, 2)} п.п.`, position: "insideEndTop" } }] : []),
        ],
      },
      markPoint: {
        symbol: "circle", symbolSize: 12, itemStyle: { color: t.accent, borderColor: t.surface, borderWidth: 2 },
        label: { show: true, position: "top", color: t.text, fontSize: 12, formatter: "текущая премия" },
        data: [{ coord: [cur * 100, (pts.find((x) => Math.abs(x.premium - cur) < 0.00126)?.eff_rate ?? q.price.eff_rate) * 100] }],
      },
    }],
  }), [pts, cur, msp, parity]);
  return (
    <>
      <Chart option={option} height={280}
        label={parity >= 0 ? `Эффективная ставка равна кредиту МСП при премии ${num(parity * 100, 2)} п.п.; при большей премии платформа дороже` :
          "Эффективная ставка выше кредита МСП при любой премии"} />
      <DataTableToggle caption="Эффективная ставка по премии" head={["Премия, п.п.", "Эффективная ставка, %"]}
        rows={pts.filter((_, i) => i % 2 === 0).map((x) => [num(x.premium * 100, 2), num(x.eff_rate * 100, 2)])} />
    </>
  );
}
