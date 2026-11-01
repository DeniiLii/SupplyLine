import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { api, errorText } from "../api/client";
import { mlnM, num, pct } from "../api/format";
import { axisCommon, Chart, type ChartTokens } from "../components/Chart";
import { Callout, Card, Chip, DataTableToggle, ErrorBox, Loading } from "../components/ui";
import { ru } from "../copy/ru";

type Preset = {
  key: string; name: string; note: string; payback_month: number | null; cum_np_5y: number; eq_need_peak: number;
  np5: number; eff5: number; msp_rate: number; cap_rate: number; position: string; above_cap: boolean;
  stress_share: number; stress_covered: boolean; cum_np: number[];
};
type Levers = { presets: Preset[]; label: string };

const MAX_LINES = 3;
const POS_TONE: Record<string, "success" | "warning" | "danger"> = {
  "дешевле кредита МСП": "success", "дороже кредита, в пределах премии": "warning", "выше потолка рынка": "danger",
};

/** Рычаги окупаемости: пресеты параметров той же модели. Все числа — из /api/finmodel/levers. */
export function LeversCard() {
  const q = useQuery({ queryKey: ["levers"], queryFn: () => api<Levers>("/api/finmodel/levers"), staleTime: Infinity });
  const [sel, setSel] = useState<string[]>(["base", "t60", "m35"]);
  const toggle = (k: string) =>
    setSel((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : cur.length >= MAX_LINES ? [...cur.slice(1), k] : [...cur, k]));

  return (
    <Card title={ru.levers.title} lead={<>{ru.levers.lead} <Chip tone="warning">{q.data?.label ?? ru.levers.hypothesis}</Chip></>}>
      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!q.data ? <Loading rows={6} /> : <Body d={q.data} sel={sel} toggle={toggle} />}
    </Card>
  );
}

function Body({ d, sel, toggle }: { d: Levers; sel: string[]; toggle: (k: string) => void }) {
  const above = d.presets.filter((p) => sel.includes(p.key) && p.above_cap);
  const cap = d.presets[0]?.cap_rate ?? 0;
  return (
    <div className="flex flex-col gap-5">
      <div role="group" aria-label={ru.levers.pick} className="flex flex-wrap gap-2">
        {d.presets.map((p) => (
          <button key={p.key} type="button" className={`btn btn-sm ${sel.includes(p.key) ? "btn-secondary" : "btn-ghost"}`}
            aria-pressed={sel.includes(p.key)} onClick={() => toggle(p.key)} title={p.note}>
            {p.name}
          </button>
        ))}
        <span className="self-center text-caption text-ink3">{ru.levers.pickNote(MAX_LINES)}</span>
      </div>

      {above.length > 0 && (
        <Callout tone="warning" title={ru.levers.aboveCapTitle}>
          {ru.levers.aboveCap(above.map((p) => `${p.name} ${pct(p.eff5)}`).join(", "), pct(cap, 1))}
        </Callout>
      )}

      <div className="overflow-x-auto" tabIndex={0}>
        <table className="data-table dense">
          <caption className="sr-only">{ru.levers.title}</caption>
          <thead><tr>
            <th scope="col">Пресет</th><th scope="col" className="r">Окупаемость</th><th scope="col" className="r">Накопленная ЧП, 5 лет</th>
            <th scope="col" className="r">Пик капитала</th><th scope="col" className="r">ЧП 5-го года</th><th scope="col" className="r">Ставка поставщика, Г5</th>
            <th scope="col">Позиция цены</th><th scope="col">Стресс: дефолт якоря</th>
          </tr></thead>
          <tbody>
            {d.presets.map((p) => (
              <tr key={p.key} aria-selected={sel.includes(p.key)} style={sel.includes(p.key) ? { background: "var(--primary-soft)" } : undefined}>
                <th scope="row" className="text-left" style={{ position: "static", background: "transparent" }}>
                  <div className="font-medium">{p.name}</div><div className="text-caption text-ink3">{p.note}</div>
                </th>
                <td className="r num">{p.payback_month ? `месяц ${p.payback_month}` : "нет"}</td>
                <td className={`r num ${p.cum_np_5y < 0 ? "text-danger" : ""}`}>{mlnM(p.cum_np_5y)}</td>
                <td className="r num">{mlnM(p.eq_need_peak)}</td>
                <td className={`r num ${p.np5 < 0 ? "text-danger" : ""}`}>{mlnM(p.np5)}</td>
                <td className="r num">{pct(p.eff5)}</td>
                <td><Chip tone={POS_TONE[p.position] ?? "warning"}>{p.position}</Chip></td>
                <td><Chip tone={p.stress_covered ? "success" : "danger"}>{p.stress_covered ? "покрыт" : "не покрыт"} при {pct(p.stress_share, 0)}</Chip></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-caption text-ink3">{ru.levers.tableNote(pct(d.presets[0]?.msp_rate ?? 0, 1), pct(cap, 1))}</p>

      <div>
        <h3 className="mb-2 text-small font-semibold">{ru.levers.chartTitle}</h3>
        <CumLines presets={d.presets} sel={sel} />
      </div>
    </div>
  );
}

function CumLines({ presets, sel }: { presets: Preset[]; sel: string[] }) {
  // Цвет закреплён за пресетом (слот по порядку в списке), выбор не перекрашивает линии
  const shown = presets.map((p, i) => ({ ...p, slot: i })).filter((p) => sel.includes(p.key));
  const months = presets[0]?.cum_np.map((_, i) => i + 1) ?? [];
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 120, top: 56, bottom: 28, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: t.text2 }, data: shown.map((p) => p.name) },
    tooltip: { trigger: "axis", valueFormatter: (v: number) => mlnM(v) },
    xAxis: { type: "category", data: months, name: "месяц", nameLocation: "middle", nameGap: 26, ...axisCommon(t), splitLine: { show: false },
      axisLabel: { color: t.text2, interval: 11 } },
    yAxis: { type: "value", name: "₽ млн", ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v) } },
    series: shown.map((p, j) => ({
      name: p.name, type: "line", data: p.cum_np, showSymbol: false,
      lineStyle: { width: 2, color: t.cat[p.slot % t.cat.length] }, itemStyle: { color: t.cat[p.slot % t.cat.length] },
      endLabel: { show: true, color: t.text, fontSize: 12, formatter: () => `${p.name}: ${num(p.cum_np[59], 0)}` },
      ...(j === 0 ? { markLine: { symbol: "none", silent: true, lineStyle: { color: t.ref, type: "solid", width: 1 }, label: { show: false }, data: [{ yAxis: 0 }] } } : {}),
    })),
  }), [shown, months]);
  const label = shown.length
    ? `Накопленная чистая прибыль к месяцу 60: ${shown.map((p) => `${p.name} ${mlnM(p.cum_np[59])}`).join("; ")}`
    : ru.levers.empty;
  return <>
    {shown.length ? <Chart option={option} height={300} label={label} /> : <p className="text-small text-ink2">{ru.levers.empty}</p>}
    <DataTableToggle caption={ru.levers.chartTitle} head={["Месяц", ...shown.map((p) => `${p.name}, ₽ млн`)]}
      rows={months.filter((m) => m % 6 === 0 || m === 1).map((m) => [m, ...shown.map((p) => num(p.cum_np[m - 1], 1))])} />
  </>;
}
