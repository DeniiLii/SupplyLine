import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { api, errorText, useDebounced } from "../api/client";
import { mlnM, num, pct, pp } from "../api/format";
import { axisCommon, Chart, type ChartTokens } from "../components/Chart";
import { PageHead } from "../components/Layout";
import { Badge, Callout, Card, Chip, DataTableToggle, ErrorBox, Loading, Metric, Segmented, SliderField, Tip, useToast } from "../components/ui";
import { ru } from "../copy/ru";
import { LeversCard } from "./Levers";

type Year = { year: number; turnover: number; avg_bal: number; bal_end: number; income: number; fund_net: number; el_borne: number; ins: number; cfa_fee: number; var_opex: number; fix_opex: number; pbt: number; tax: number; np: number; cum_np: number; capital_avg: number; r_app: number; eff: number; w_on: number; borne: number; margin: number; breakeven_turnover: number | null; rorc: number; nim: number; econ: number };
type Month = { month: number; cum_np: number; eq_need: number; np: number; capital: number };
type Matrix = { scenario: string; mode: number; pbt: number[]; np5: number; cum_np5: number; eff5: number; eff_minus_msp5: number; margin5: number; breakeven5: number | null; eq_need: number; verdict: string };
type Unit = { scenario: string; mode: number; r: number; eff: number; D: number; recv: number; fund: number; el: number; opex: number; margin: number; margin_per_1000: number; overpay: number; position: string };
type Sens = { base_pbt: number; rows: { key: string; name: string; low: number; high: number; note: string; delta_low: number; delta_high: number; range: number }[] };
type Stress = { month: number; year: number; bal: number; share: number; exposure: number; gross: number; borne: number; loss: number; capital: number; coverage: number; el_year: number; max_share: number; eq_need_peak: number; eq_need_with_event: number; shares: number[]; lgds: number[]; grid: number[][]; grid_cap: number[][]; by_month: { month: number; bal: number; capital: number; loss: number; coverage: number }[]; covered: boolean };
type Run = {
  scenario: string; mode: number; years: Year[]; months: Month[]; matrix: Matrix[]; kpis: { eq_need_peak: number; eq_need_peak_month: number; first_positive_np_month: number | null; sustained_positive_month: number | null; payback_month: number | null; cum_np_bottom: number; cum_np_bottom_month: number; cum_np_5y: number; tax_5y: number; breakeven_turnover_y5: number | null; breakeven_share_y5: number | null };
  unit: { selected: Unit; all: Unit[] }; sensitivity: Sens; stress: Stress; warnings: { code: string; level: string; text: string; detail: string }[];
  checks: { name: string; ok: boolean }[]; assumptions: string[]; cap_credit: number; label: string;
};

const SC_NAMES: Record<string, string> = { A: "A · Банк-партнёр", B: "B · Кредитная линия", C: "C · ЦФА", M: "M · Смешанная" };

export default function Model() {
  const toast = useToast();
  const [s, setS] = useState({ scenario: "M", price_mode: 1, ks_scenario: 1, ks_pass_through: 1, t_days: 45 });
  const ds = useDebounced(s, 150);
  const q = useQuery({ queryKey: ["finmodel", ds], queryFn: () => api<Run>("/api/finmodel/run", { method: "POST", json: ds }), placeholderData: keepPreviousData });
  const d = q.data;
  // Лимит концентрации платформы (настройка) и стресс-тест при этой доле якоря
  const stq = useQuery({ queryKey: ["state"], queryFn: () => api<{ anchor_cap: number }>("/api/state") });
  const cap = stq.data?.anchor_cap;
  const pq = useQuery({
    queryKey: ["finmodel-cap", ds, cap], enabled: cap !== undefined, placeholderData: keepPreviousData,
    queryFn: () => api<Run>("/api/finmodel/run", { method: "POST", json: { ...ds, stress_share: cap, months: false } }),
  });
  const isBase = s.scenario === "M" && s.price_mode === 1 && s.ks_scenario === 1 && s.ks_pass_through === 1 && s.t_days === 45;

  const downloadCurrent = async () => {
    try {
      const r = await fetch("/api/finmodel/excel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s) });
      if (!r.ok) throw new Error();
      const b = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = "SupplyLine_model_current.xlsx";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      toast("danger", ru.errors.generic);
    }
  };

  return (
    <>
      <PageHead title={ru.model.title}
        lead={<>{ru.model.lead} <Chip tone="warning">{ru.modelLabel}</Chip></>}
        right={<div className="flex flex-wrap gap-2">
          <a className="btn btn-secondary" href="/api/finmodel/excel" download><Download size={16} aria-hidden />{ru.model.download}</a>
          <button className="btn btn-ghost" onClick={downloadCurrent}>{ru.model.downloadCurrent}</button>
        </div>} />

      <Card className="mb-6">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          <Ctrl label="Сценарий фондирования" badge={<Badge kind="Гипотеза" source="A 100% баланс · B 100% кредитная линия · C 100% ЦФА · M 60/25/10/5 с рампой внебаланса 0/80/100%" />}>
            <Segmented size="sm" label="Сценарий фондирования" value={s.scenario} onChange={(v) => setS({ ...s, scenario: v })}
              options={["A", "B", "C", "M"].map((k) => ({ value: k, label: k, title: SC_NAMES[k] }))} />
          </Ctrl>
          <Ctrl label="Режим цены">
            <Segmented size="sm" label="Режим цены" value={String(s.price_mode)} onChange={(v) => setS({ ...s, price_mode: Number(v) })}
              options={[{ value: "1", label: "По формуле" }, { value: "2", label: "С потолком" }]} />
          </Ctrl>
          <Ctrl label="Сценарий KС" badge={<Badge kind="Гипотеза" source="1: 14% весь горизонт · 2: 11,5/10/9/8,5/8,5% · 3: 17%" />}>
            <Segmented size="sm" label="Сценарий KС" value={String(s.ks_scenario)} onChange={(v) => setS({ ...s, ks_scenario: Number(v) })}
              options={[{ value: "1", label: "14%" }, { value: "2", label: "Смягчение" }, { value: "3", label: "Шок +3" }]} />
          </Ctrl>
          <Ctrl label="Перенос KС в цену">
            <Segmented size="sm" label="Перенос KС в цену" value={String(s.ks_pass_through)} onChange={(v) => setS({ ...s, ks_pass_through: Number(v) })}
              options={[{ value: "1", label: "Плавающий дисконт" }, { value: "2", label: "Цена фиксирована" }]} />
          </Ctrl>
          <SliderField label="Срок финансирования" badge={<Badge kind="Гипотеза" />} value={s.t_days} onChange={(v) => setS({ ...s, t_days: Math.round(v) })} min={14} max={90} step={1} digits={0} unit="дн." />
        </div>
        {!isBase && <button className="btn btn-ghost btn-sm mt-3" onClick={() => setS({ scenario: "M", price_mode: 1, ks_scenario: 1, ks_pass_through: 1, t_days: 45 })}>Вернуть базовый вариант (M, по формуле, KС 14%, 45 дней)</button>}
      </Card>

      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!d ? <Card><Loading rows={8} /></Card> : <Body d={d} platform={pq.data?.stress} cap={cap} />}
    </>
  );
}

function Ctrl({ label, badge, children }: { label: string; badge?: React.ReactNode; children: React.ReactNode }) {
  return <div className="flex flex-col gap-2"><div className="flex items-center gap-2 text-small font-medium">{label}{badge}</div>{children}</div>;
}

function Body({ d, platform, cap }: { d: Run; platform?: Stress; cap?: number }) {
  const y5 = d.years[4];
  const k = d.kpis;
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="grid grid-cols-2 gap-x-6 gap-y-6 lg:grid-cols-4">
          <Metric big label="Прибыль до налога, 5-й год" value={num(y5.pbt, 1)} unit="млн ₽" tone={y5.pbt < 0 ? "negative" : "default"}
            how="Σ по месяцам Г5: доход − фондирование нетто − потери − страхование − комиссия ЦФА − переменные и постоянные расходы" />
          <Metric big label="Накопленная чистая прибыль за 5 лет" value={num(k.cum_np_5y, 1)} unit="млн ₽" tone={k.cum_np_5y < 0 ? "negative" : "default"}
            note={`Дно ${mlnM(k.cum_np_bottom)} в месяце ${k.cum_np_bottom_month}; окупаемость в горизонте: ${k.payback_month ? `месяц ${k.payback_month}` : "нет"}`}
            how="Σ ЧП за 60 месяцев; налог по накопленной прибыли, убыток переносится полностью" />
          <Metric big label="Нужен собственный капитал" value={num(k.eq_need_peak, 0)} unit="млн ₽"
            note={`Пик в месяце ${k.eq_need_peak_month}`} how="max по месяцам (капитал под риск − накопленная ЧП); капитал = 10% × доля риска организатора × средний остаток" />
          <Metric big label="Оборот безубыточности, 5-й год" value={k.breakeven_turnover_y5 === null ? "н/д" : num(k.breakeven_turnover_y5, 0)} unit={k.breakeven_turnover_y5 === null ? undefined : "млн ₽ в год"}
            note={k.breakeven_share_y5 === null ? "Безубыточность недостижима: вклад на ₽1 оборота ≤ 0" : `${pct(k.breakeven_share_y5, 0)} оборота Г5`}
            how="Постоянные расходы Г5 / вклад на ₽1 оборота при стационарном остатке (оборот × t/365)" />
        </div>
        <p className="mt-4 text-small text-ink2">
          Первый месяц с прибылью: {k.first_positive_np_month ?? "нет"}; устойчиво положительна с месяца {k.sustained_positive_month ?? "— (не в горизонте)"}. Налог за 5 лет: {mlnM(k.tax_5y)}.
        </p>
      </Card>

      {d.warnings.length > 0 && (
        <section aria-label={ru.model.warnings} className="grid gap-3 md:grid-cols-2">
          {d.warnings.map((w) => <Callout key={w.code} tone={w.level === "danger" ? "danger" : "warning"} title={w.text}>{w.detail}</Callout>)}
        </section>
      )}

      <LeversCard />

      <Card title="Цена и конкурентоспособность" lead={ru.model.priceSummary}>
        <PriceTable d={d} />
      </Card>

      <Card title={ru.model.pnl} lead="₽ млн; Г1…Г5 — годы модели. Потоки — сумма по месяцам; средний остаток и капитал — среднее за год.">
        <PnL years={d.years} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title={ru.model.cumTitle} lead="Помесячно, 60 месяцев с 01.01.2027 (дата условная)."><CumChart months={d.months} field="cum_np" /></Card>
        <Card title={ru.model.capTitle} lead="Капитал под риск минус накопленная ЧП. Отдельный график, а не вторая ось."><CumChart months={d.months} field="eq_need" /></Card>
      </div>

      <Card title={ru.model.matrix} lead="ПДН — прибыль до налога, ЧП — чистая прибыль, ₽ млн. Налог в этих вариантах равен 0, поэтому ЧП = ПДН.">
        <MatrixTable m={d.matrix} cap={d.cap_credit} sel={`${d.scenario}${d.mode}`} />
      </Card>

      <Card title={ru.model.tornado} lead={`${ru.model.tornadoNote} База ПДН Г5 = ${mlnM(d.sensitivity.base_pbt)}.`}>
        <Tornado s={d.sensitivity} />
      </Card>

      <Card title={ru.model.stress} lead="Валовые потери = доля якоря × остаток × LGD × (1 − покрытие); организатор несёт свою долю риска.">
        <StressBlock st={d.stress} platform={platform} cap={cap} />
      </Card>

      <Card title={ru.model.unit} lead="₽ тыс. Переплата — дисконт минус проценты по кредиту МСП на полученную сумму за тот же срок.">
        <UnitTable rows={d.unit.all} />
      </Card>

      <Card title={ru.model.assumptions}>
        <ul className="list-disc space-y-1 pl-5 text-small text-ink2">{d.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
        <p className="mt-3 text-caption text-ink3 debug-only">Контрольные тождества движка: {d.checks.filter((c) => c.ok).length} из {d.checks.length} выполнены.</p>
      </Card>
    </div>
  );
}

function PriceTable({ d }: { d: Run }) {
  const rows = d.matrix;
  return (
    <div className="overflow-x-auto" tabIndex={0}>
      <table className="data-table">
        <caption className="sr-only">Эффективная ставка Г5 по сценариям</caption>
        <thead><tr><th scope="col">Сценарий</th><th scope="col" className="r">Цена по формуле, эфф.</th><th scope="col" className="r">С потолком, эфф.</th><th scope="col" className="r">ПДН Г5 с потолком</th><th scope="col">Положение цены по формуле</th></tr></thead>
        <tbody>
          {["A", "B", "C", "M"].map((sc) => {
            const f = rows.find((r) => r.scenario === sc && r.mode === 1)!;
            const c = rows.find((r) => r.scenario === sc && r.mode === 2)!;
            return (
              <tr key={sc}>
                <td className="font-medium">{SC_NAMES[sc]}</td>
                <td className="r num">{pct(f.eff5)}</td>
                <td className="r num">{pct(c.eff5)}</td>
                <td className={`r num font-medium ${c.np5 < 0 ? "text-danger" : ""}`}>{num(c.pbt[4], 1)}</td>
                <td>{f.eff5 > d.cap_credit ? <Chip tone="warning">выше потолка {pct(d.cap_credit, 1)}</Chip> : <Chip tone="success">в пределах потолка</Chip>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-caption text-ink3">Кредит МСП до 1 года 18,0% <Badge kind="Факт" source="Банк России, июнь 2026" />; потолок = кредит + 1 п.п. за скорость <Badge kind="Гипотеза" />.</p>
    </div>
  );
}

function PnL({ years }: { years: Year[] }) {
  const rows: [string, (y: Year) => string, string?][] = [
    ["Оборот", (y) => num(y.turnover, 0)],
    ["Средняя задолженность", (y) => num(y.avg_bal, 1)],
    ["Остаток на конец года", (y) => num(y.bal_end, 1)],
    ["Доход (дисконт)", (y) => num(y.income, 1)],
    ["Фондирование нетто", (y) => num(-y.fund_net, 1)],
    ["Потери на организаторе", (y) => num(-y.el_borne, 1)],
    ["Комиссия оператора ЦФА", (y) => num(-y.cfa_fee, 1)],
    ["Переменные расходы", (y) => num(-y.var_opex, 1)],
    ["Постоянные расходы", (y) => num(-y.fix_opex, 1)],
    ["Прибыль до налога", (y) => num(y.pbt, 1), "b"],
    ["Налог", (y) => num(-y.tax, 1)],
    ["Чистая прибыль", (y) => num(y.np, 1), "b"],
    ["Накопленная ЧП", (y) => num(y.cum_np, 1), "b"],
    ["Капитал под риск, среднее", (y) => num(y.capital_avg, 1)],
    ["Цена r", (y) => pct(y.r_app)],
    ["Эффективная ставка поставщика", (y) => pct(y.eff)],
    ["Доля на балансе", (y) => pct(y.w_on, 1)],
    ["Доля риска организатора", (y) => pct(y.borne, 1)],
    ["Оборот безубыточности", (y) => (y.breakeven_turnover === null ? "н/д" : num(y.breakeven_turnover, 0))],
  ];
  return (
    <div className="max-h-[520px] overflow-auto" tabIndex={0} role="region" aria-label="Таблица P&L, прокручивается">
      <table className="data-table dense">
        <caption className="sr-only">Прибыль и убыток по годам</caption>
        <thead><tr><th scope="col">Показатель, ₽ млн</th>{years.map((y) => <th key={y.year} scope="col" className="r">Г{y.year}</th>)}</tr></thead>
        <tbody>
          {rows.map(([name, f, b]) => (
            <tr key={name}>
              <th scope="row" className={`text-left font-normal ${b ? "font-semibold text-ink" : "text-ink2"}`} style={{ position: "static", background: "transparent", fontSize: 14 }}>{name}</th>
              {years.map((y) => {
                const v = f(y);
                return <td key={y.year} className={`r num ${b ? "font-semibold" : ""} ${b && v.startsWith("−") ? "text-danger" : ""}`}>{v}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CumChart({ months, field }: { months: Month[]; field: "cum_np" | "eq_need" }) {
  const option = useCallback((t: ChartTokens) => {
    const vals = months.map((m) => m[field]);
    const ext = field === "cum_np" ? vals.indexOf(Math.min(...vals)) : vals.indexOf(Math.max(...vals));
    return {
      grid: { left: 8, right: 24, top: 28, bottom: 28, containLabel: true },
      tooltip: { trigger: "axis", formatter: (p: { dataIndex: number }[]) => `Месяц ${months[p[0].dataIndex].month}: <b>${mlnM(vals[p[0].dataIndex])}</b>` },
      xAxis: { type: "category", data: months.map((m) => m.month), name: "месяц", nameLocation: "middle", nameGap: 26, ...axisCommon(t), splitLine: { show: false },
        axisLabel: { color: t.text2, interval: 11 } },
      yAxis: { type: "value", name: "₽ млн", ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v) } },
      series: [{
        type: "line", data: vals, showSymbol: false, lineStyle: { width: 2, color: t.accent }, itemStyle: { color: t.accent },
        areaStyle: { color: t.accent, opacity: 0.08 },
        markLine: { symbol: "none", silent: true, lineStyle: { color: t.ref, type: "solid", width: 1 }, label: { show: false }, data: [{ yAxis: 0 }] },
        markPoint: {
          symbol: "circle", symbolSize: 10, itemStyle: { color: t.accent, borderColor: t.surface, borderWidth: 2 },
          label: { show: true, color: t.text, fontSize: 12 },
          data: [
            { name: "ext", xAxis: ext, yAxis: vals[ext], label: { position: field === "cum_np" ? "bottom" : ext === months.length - 1 ? "left" : "top", formatter: `${num(vals[ext], 0)} (мес. ${ext + 1})` } },
            ...(ext !== months.length - 1 ? [{ name: "end", xAxis: months.length - 1, yAxis: vals[months.length - 1], label: { position: "left", formatter: `${num(vals[months.length - 1], 0)} (мес. 60)` } }] : []),
          ],
        },
      }],
    };
  }, [months, field]);
  const last = months[months.length - 1]?.[field] ?? 0;
  return <>
    <Chart option={option} height={280} label={field === "cum_np" ? `Накопленная чистая прибыль к месяцу 60: ${mlnM(last)}` : `Потребность в капитале к месяцу 60: ${mlnM(last)}`} />
    <DataTableToggle caption={field === "cum_np" ? "Накопленная ЧП" : "Потребность в капитале"} head={["Месяц", "₽ млн"]} rows={months.filter((m) => m.month % 6 === 0 || m.month === 1).map((m) => [m.month, num(m[field], 1)])} />
  </>;
}

function MatrixTable({ m, cap, sel }: { m: Matrix[]; cap: number; sel: string }) {
  return (
    <div className="overflow-x-auto" tabIndex={0}>
      <table className="data-table dense">
        <caption className="sr-only">Матрица сценариев и режимов цены</caption>
        <thead>
          <tr>
            <th scope="col">Сценарий</th><th scope="col">Цена</th>
            {[1, 2, 3, 4, 5].map((y) => <th key={y} scope="col" className="r">ПДН Г{y}</th>)}
            <th scope="col" className="r">Накопл. ЧП</th><th scope="col" className="r">Эфф. ставка Г5</th><th scope="col" className="r">Маржа Г5</th>
            <th scope="col" className="r">Безубыточность, ₽ млн</th><th scope="col" className="r">Капитал, ₽ млн</th>
          </tr>
        </thead>
        <tbody>
          {m.map((r) => (
            <tr key={`${r.scenario}${r.mode}`} aria-selected={`${r.scenario}${r.mode}` === sel}>
              <td className="font-medium">{r.scenario}</td>
              <td>{r.mode === 1 ? "формула" : "потолок"}</td>
              {r.pbt.map((v, i) => <td key={i} className={`r num ${v < 0 ? "text-danger" : ""}`}>{num(v, 1)}</td>)}
              <td className={`r num font-medium ${r.cum_np5 < 0 ? "text-danger" : ""}`}>{num(r.cum_np5, 1)}</td>
              <td className="r num"><Tip text={`Кредит МСП 18,0%; потолок ${pct(cap, 1)}; разница ${pp(r.eff_minus_msp5)}`}><span tabIndex={0}>{pct(r.eff5)}</span></Tip></td>
              <td className={`r num ${r.margin5 < 0 ? "text-danger" : ""}`}>{pct(r.margin5)}</td>
              <td className="r num">{r.breakeven5 === null ? "н/д" : num(r.breakeven5, 0)}</td>
              <td className="r num">{num(r.eq_need, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-caption text-ink3">Выбранный вариант подсвечен. «н/д» — вклад на ₽1 оборота не положителен: безубыточность недостижима.</p>
    </div>
  );
}

function Tornado({ s }: { s: Sens }) {
  const rows = useMemo(() => [...s.rows].sort((a, b) => a.range - b.range), [s]);
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 48, top: 8, bottom: 28, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p: { dataIndex: number }[]) => {
      const r = rows[p[0].dataIndex];
      return `<b>${r.name}</b><br/>${r.note}<br/>Низкий кейс: ${num(r.delta_low, 1)} млн ₽<br/>Высокий кейс: ${num(r.delta_high, 1)} млн ₽`;
    } },
    xAxis: { type: "value", name: "Δ ПДН Г5, ₽ млн", nameLocation: "middle", nameGap: 26, ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v) } },
    yAxis: { type: "category", data: rows.map((r) => r.name), ...axisCommon(t), splitLine: { show: false }, axisLabel: { color: t.text2, width: 260, overflow: "truncate", margin: 44 } },
    series: [
      { name: "Низкий кейс", type: "bar", stack: "t", barWidth: 16, data: rows.map((r) => ({ value: r.delta_low, itemStyle: { color: r.delta_low >= 0 ? t.pos : t.neg, borderRadius: r.delta_low >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
          label: { show: Math.abs(r.delta_low) >= 0.05, position: r.delta_low >= 0 ? "right" : "left", color: t.text2, fontSize: 11, formatter: (r.delta_low > 0 ? "+" : "") + num(r.delta_low, 0) } })) },
      { name: "Высокий кейс", type: "bar", stack: "t2", barGap: "-100%", barWidth: 16, data: rows.map((r) => ({ value: r.delta_high, itemStyle: { color: r.delta_high >= 0 ? t.pos : t.neg, borderRadius: r.delta_high >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
          label: { show: Math.abs(r.delta_high) >= 0.05, position: r.delta_high >= 0 ? "right" : "left", color: t.text2, fontSize: 11, formatter: (r.delta_high > 0 ? "+" : "") + num(r.delta_high, 0) } })) },
    ],
  }), [rows]);
  const top = [...s.rows].sort((a, b) => b.range - a.range);
  return <>
    <Chart option={option} height={420} label={`Сильнее всего ПДН Г5 двигают: ${top.slice(0, 3).map((r) => `${r.name.toLowerCase()} (±${num(r.range / 2, 0)})`).join(", ")}`} />
    <p className="mt-2 text-caption text-ink3">Вправо и «+» — прибыль растёт, влево и «−» — падает; цвет дублирует знак.</p>
    <DataTableToggle caption="Чувствительность ПДН Г5" head={["Драйвер", "Низкий", "Высокий", "Δ низкий", "Δ высокий"]}
      rows={top.map((r) => [r.name, num(r.low, 2), num(r.high, 2), num(r.delta_low, 1), num(r.delta_high, 1)])} />
  </>;
}

function StressBlock({ st, platform, cap }: { st: Stress; platform?: Stress; cap?: number }) {
  const [view, setView] = useState<"rub" | "cap">("rub");
  const capSafe = cap !== undefined && cap <= st.max_share && (platform?.covered ?? true);
  return (
    <div className="flex flex-col gap-6">
      {platform && cap !== undefined && (
        <section aria-label="Стресс-тест: книга и платформа" className="grid gap-3 md:grid-cols-2">
          <Callout tone={st.covered ? "success" : "danger"}
            title={`Книга Excel, доля якоря ${pct(st.share, 0)}: ${st.covered ? "капитал покрывает дефолт" : "капитал не покрывает дефолт"}`}>
            Потери {mlnM(st.loss)} против капитала {mlnM(st.capital)} (покрытие {num(st.coverage, 2)}×). Безопасная доля {pct(st.max_share, 1)}.
          </Callout>
          <Callout tone={capSafe ? "success" : "danger"}
            title={capSafe ? `Капитал покрывает дефолт якоря при лимите ${pct(cap, 0)}` : `Лимит платформы ${pct(cap, 0)} выше безопасной доли ${pct(st.max_share, 1)}`}>
            Лимит в платформе: {pct(cap, 0)}. Потери {mlnM(platform.loss)} против капитала {mlnM(platform.capital)} (покрытие {num(platform.coverage, 2)}×).
          </Callout>
        </section>
      )}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 lg:grid-cols-4">
        <Metric label={`Потери организатора, месяц ${st.month}`} value={num(st.loss, 0)} unit="млн ₽" tone="negative"
          how={`${pct(st.share, 0)} × ${num(st.bal, 1)} × LGD × доля риска ${pct(st.borne, 0)}`} />
        <Metric label="Капитал под риск в этом месяце" value={num(st.capital, 0)} unit="млн ₽" note={`Покрытие ${num(st.coverage, 2)}×`} />
        <Metric label="Безопасная доля якоря" value={pct(st.max_share, 1)} note="при которой капитал покрывает потерю" how="капитал / (остаток × LGD × (1 − покрытие) × доля риска)" />
        <Metric label="Пик капитала с событием" value={num(st.eq_need_with_event, 0)} unit="млн ₽" note={`без события ${num(st.eq_need_peak, 0)}`} />
      </div>
      {!st.covered && <Callout tone="warning" title={`При доле ${pct(st.share, 0)} капитал под риск не покрывает дефолт якоря`}>
        Помогают лимит концентрации ниже {pct(st.max_share, 1)}, страхование требований и дополнительный капитал. Ожидаемые потери года, заложенные в цену: {mlnM(st.el_year)}. Сетка ниже — для доли книги {pct(st.share, 0)}.
      </Callout>}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-small font-semibold">Потери организатора: доля якоря × LGD, месяц {st.month}</h3>
          <Segmented size="sm" label="Единицы сетки" value={view} onChange={setView} options={[{ value: "rub", label: "₽ млн" }, { value: "cap", label: "Доля капитала" }]} />
        </div>
        <div className="overflow-x-auto" tabIndex={0}>
          <table className="data-table dense">
            <caption className="sr-only">Сетка стресса</caption>
            <thead><tr><th scope="col">Доля якоря \ LGD</th>{st.lgds.map((l) => <th key={l} scope="col" className="r">{pct(l, 0)}</th>)}</tr></thead>
            <tbody>
              {st.shares.map((sh, i) => (
                <tr key={sh}>
                  <th scope="row" className="text-left font-medium" style={{ position: "static", background: "transparent" }}>{pct(sh, 0)}</th>
                  {st.lgds.map((_, j) => {
                    const capShare = st.grid_cap[i][j];
                    const over = capShare > 1;
                    const a = Math.min(capShare / 2.6, 1);
                    return (
                      <td key={j} className="r num" style={{ background: `color-mix(in srgb, var(--danger-bg) ${Math.round(a * 100)}%, var(--surface))`, color: over ? "var(--danger)" : undefined, fontWeight: over ? 600 : 400 }}>
                        {over && <span aria-hidden>▲ </span>}{view === "rub" ? num(st.grid[i][j], 0) : `${num(capShare * 100, 0)}%`}
                        {over && <span className="sr-only"> — больше капитала</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-caption text-ink3">▲ и красный текст — потеря больше капитала под риск.</p>
      </div>
      <div>
        <h3 className="mb-2 text-small font-semibold">Событие в разные месяцы (доля {pct(st.share, 0)}, LGD 60%)</h3>
        <div className="overflow-x-auto" tabIndex={0}>
          <table className="data-table dense">
            <thead><tr><th scope="col">Месяц</th><th scope="col" className="r">Остаток</th><th scope="col" className="r">Капитал</th><th scope="col" className="r">Потери</th><th scope="col" className="r">Покрытие</th></tr></thead>
            <tbody>{st.by_month.map((r) => <tr key={r.month}><td>{r.month}</td><td className="r num">{num(r.bal, 0)}</td><td className="r num">{num(r.capital, 0)}</td><td className="r num">{num(r.loss, 0)}</td><td className={`r num ${r.coverage < 1 ? "text-danger" : ""}`}>{num(r.coverage, 2)}×</td></tr>)}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function UnitTable({ rows }: { rows: Unit[] }) {
  return (
    <div className="overflow-x-auto" tabIndex={0}>
      <table className="data-table dense">
        <caption className="sr-only">Юнит-экономика счёта</caption>
        <thead><tr>
          <th scope="col">Сценарий</th><th scope="col">Цена</th><th scope="col" className="r">r</th><th scope="col" className="r">Эфф. ставка</th><th scope="col" className="r">D</th>
          <th scope="col" className="r">Получает поставщик</th><th scope="col" className="r">Фондирование</th><th scope="col" className="r">Потери</th><th scope="col" className="r">Издержки</th>
          <th scope="col" className="r">Маржа</th><th scope="col" className="r">Маржа на ₽1000</th><th scope="col" className="r">Переплата против МСП</th>
        </tr></thead>
        <tbody>
          {rows.map((u) => (
            <tr key={`${u.scenario}${u.mode}`}>
              <td className="font-medium">{u.scenario}</td><td>{u.mode === 1 ? "формула" : "потолок"}</td>
              <td className="r num">{pct(u.r)}</td><td className="r num">{pct(u.eff)}</td><td className="r num">{num(u.D, 2)}</td>
              <td className="r num">{num(u.recv, 2)}</td><td className="r num">{num(u.fund, 2)}</td><td className="r num">{num(u.el, 2)}</td><td className="r num">{num(u.opex, 2)}</td>
              <td className={`r num font-medium ${u.margin < 0 ? "text-danger" : ""}`}>{num(u.margin, 2)}</td>
              <td className={`r num ${u.margin_per_1000 < 0 ? "text-danger" : ""}`}>{num(u.margin_per_1000, 2)}</td>
              <td className="r num">{num(u.overpay, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
