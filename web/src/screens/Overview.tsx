import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api, errorText } from "../api/client";
import { mln, num, pct } from "../api/format";
import { axisCommon, Chart, type ChartTokens } from "../components/Chart";
import { PageHead } from "../components/Layout";
import { Badge, Card, Chip, DataTableToggle, ErrorBox, Loading, Metric, Segmented, useToast } from "../components/ui";
import { ru } from "../copy/ru";

type Ov = {
  now: string; scenario: string;
  kpi: { turnover_total: number; turnover_30d: number; outstanding: number; spread_30d: number; overdue30_share: number; overdue30_amount: number; off_balance_share: number; fraud_losses: number; duplicates_blocked: number; invoices_visible: number };
  turnover_by_month: { month: string; amount: number }[];
  by_anchor: { anchor_id: number; name: string; rating: string; outstanding: number; share: number; limit: number; cap: number }[];
  by_source: { source: string; name: string; amount: number; on_balance: boolean }[];
  funnel: { stage: string; label: string; count: number }[];
  gates: { key: string; label: string; value: number; unit: string; target: string; ok: boolean; gate: number; note?: string }[];
  program_size: number; anchor_cap: number;
};
type St = { scenario: string; scenarios: Record<string, { name: string; rate: number; off_balance: number }> };

const SRC_ORDER = ["bank", "line", "cfa", "treasury", "syndication"];
const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

export function gateValue(g: Ov["gates"][number]) {
  if (g.unit === "share") return pct(g.value, 1);
  if (g.unit === "hours") return `${num(g.value, 1)} ч`;
  if (g.unit === "rub") return `${num(g.value)} ₽`;
  return String(g.value);
}

export default function Overview() {
  const qc = useQueryClient();
  const toast = useToast();
  const ov = useQuery({ queryKey: ["overview"], queryFn: () => api<Ov>("/api/overview") });
  const st = useQuery({ queryKey: ["state"], queryFn: () => api<St>("/api/state") });
  const setSc = useMutation({
    mutationFn: (scenario: string) => api("/api/settings", { method: "PUT", json: { scenario } }),
    onSuccess: () => { qc.invalidateQueries(); toast("success", "Сценарий фондирования изменён: новые предложения считаются по нему"); },
    onError: (e) => toast("danger", errorText(e)),
  });
  const d = ov.data;
  return (
    <>
      <PageHead title={ru.overview.title} lead={ru.overview.lead}
        right={st.data && (
          <div className="flex flex-col gap-1">
            <span className="text-small text-ink2">{ru.overview.scenario} <Badge kind="Гипотеза" source="Премии: банк KС+1; линия KС+2,5; ЦФА KС+4,5; казначейства KС+2; синдикация KС+1" /></span>
            <Segmented label={ru.overview.scenario} value={st.data.scenario} onChange={(v) => setSc.mutate(v)} size="sm"
              options={Object.entries(st.data.scenarios).map(([k, v]) => ({ value: k, label: `${k} · ${v.name}`, title: `r_fund ${pct(v.rate)}, вне баланса ${pct(v.off_balance, 0)}` }))} />
          </div>
        )} />
      {ov.isError && <ErrorBox text={errorText(ov.error)} onRetry={() => ov.refetch()} />}
      {!d ? <Card><Loading rows={6} /></Card> : (
        <div className="flex flex-col gap-6">
          <Card>
            <div className="grid grid-cols-2 gap-x-6 gap-y-6 md:grid-cols-3 xl:grid-cols-6">
              <Metric label={ru.overview.turnover} value={mln(d.kpi.turnover_30d)} how="Сумма номиналов счетов, профинансированных за последние 30 дней виртуального времени" />
              <Metric label={ru.overview.outstanding} value={mln(d.kpi.outstanding)} how="Номинал профинансированных и ещё не оплаченных счетов (включая просрочку)" />
              <Metric label={ru.overview.spread} value={mln(d.kpi.spread_30d, 2)} how="Σ F × (r − r_fund) × t / 365 по счетам за 30 дней" />
              <Metric label={ru.overview.overdue} value={pct(d.kpi.overdue30_share, 1)} tone={d.kpi.overdue30_share > 0.02 ? "negative" : "default"} note={mln(d.kpi.overdue30_amount)} how="Номинал счетов с просрочкой 30+ дней / средства в работе" />
              <Metric label={ru.overview.offBalance} value={pct(d.kpi.off_balance_share, 1)} how="Доля средств в работе, профинансированных ЦФА, казначействами и синдикацией" />
              <Metric label={ru.overview.fraud} value={`${num(d.kpi.fraud_losses)} ₽`} note={`Заблокировано двойных продаж: ${d.kpi.duplicates_blocked}`} how="Реестр требований блокирует повторную уступку до выплаты денег" />
            </div>
          </Card>

          <Card title={ru.overview.gatesTitle} lead="Перейти к фазе 1 (ЦФА и внешние инвесторы) можно, когда эти показатели в норме. Считаются по демо-портфелю.">
            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {d.gates.map((g) => (
                <li key={g.key} className="panel flex flex-col gap-2">
                  <div className="text-small text-ink2">{g.label}</div>
                  <div className="num text-[24px] font-semibold leading-8">{gateValue(g)}</div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip tone={g.ok ? "success" : "warning"}>{g.ok ? "в норме" : "не достигнуто"}</Chip>
                    <span className="text-caption text-ink3">цель {g.target}</span>
                  </div>
                  {g.note && <div className="text-caption text-ink3">{g.note}</div>}
                </li>
              ))}
            </ul>
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card title={ru.overview.byMonth} lead="По дате выплаты поставщику. Текущий месяц неполный."><MonthChart d={d} /></Card>
            <Card title={ru.overview.byAnchor} lead={`База концентрации — больше из портфеля и плана программы (${mln(d.program_size, 0)}).`}><AnchorChart d={d} /></Card>
            <Card title={ru.overview.bySource} lead="Доли средств в работе по источникам. Новые счета распределяются по весам выбранного сценария; старые остаются у своих источников до погашения."><SourceChart d={d} /></Card>
            <Card title={ru.overview.funnel} lead="Сколько счетов дошли хотя бы до этапа."><FunnelChart d={d} /></Card>
          </div>
        </div>
      )}
    </>
  );
}

function monthLabel(m: string) {
  const [y, mm] = m.split("-");
  return `${MONTHS[Number(mm) - 1]} ${y.slice(2)}`;
}

function MonthChart({ d }: { d: Ov }) {
  const rows = d.turnover_by_month;
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
    tooltip: { trigger: "axis", formatter: (p: { dataIndex: number }[]) => `${monthLabel(rows[p[0].dataIndex].month)}: <b>${mln(rows[p[0].dataIndex].amount)}</b>` },
    xAxis: { type: "category", data: rows.map((r) => monthLabel(r.month)), ...axisCommon(t), splitLine: { show: false } },
    yAxis: { type: "value", name: "₽ млн", ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v / 1e6) } },
    series: [{ type: "bar", barMaxWidth: 24, itemStyle: { color: t.accent, borderRadius: [4, 4, 0, 0] }, data: rows.map((r) => r.amount),
      label: { show: true, position: "top", color: t.text2, fontSize: 11, formatter: (p: { dataIndex: number }) => (p.dataIndex === rows.length - 1 ? num(rows[p.dataIndex].amount / 1e6) : "") } }],
  }), [rows]);
  return <>
    <Chart option={option} height={260} label={`Оборот по месяцам, последний месяц ${rows.length ? mln(rows[rows.length - 1].amount) : "—"}`} />
    <DataTableToggle caption="Оборот по месяцам" head={["Месяц", "Оборот, ₽ млн"]} rows={rows.map((r) => [monthLabel(r.month), num(r.amount / 1e6, 1)])} />
  </>;
}

function AnchorChart({ d }: { d: Ov }) {
  const rows = d.by_anchor;
  const cap = d.anchor_cap;
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 56, top: 28, bottom: 8, containLabel: true },
    tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => { const r = rows[p.dataIndex]; return `${r.name} (рейтинг ${r.rating})<br/>${mln(r.outstanding)} · ${pct(r.share, 1)} базы<br/>Лимит якоря ${mln(r.limit, 0)}`; } },
    xAxis: { type: "value", max: Math.max(0.3, ...rows.map((r) => r.share)) * 1.1, ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => `${num(v * 100)}%` } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => `${r.name} · ${r.rating}`), ...axisCommon(t), splitLine: { show: false } },
    series: [{
      type: "bar", barWidth: 20, data: rows.map((r) => ({ value: r.share, itemStyle: { color: r.share > cap ? t.neg : t.accent, borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: "right", color: t.text, fontSize: 12, formatter: (p: { value: number }) => pct(p.value, 1) },
      markLine: { symbol: "none", silent: true, lineStyle: { color: t.ref, type: "solid" }, label: { color: t.text2, formatter: `потолок ${pct(cap, 0)}`, position: "start", distance: 4 }, data: [{ xAxis: cap }] },
    }],
  }), [rows, cap]);
  return <>
    <Chart option={option} height={240} label={`Крупнейший якорь ${rows[0]?.name}: ${pct(rows[0]?.share ?? 0, 1)} при потолке ${pct(cap, 0)}`} />
    <DataTableToggle caption="Портфель по якорям" head={["Якорь", "В работе, ₽ млн", "Доля базы", "Лимит, ₽ млн"]} rows={rows.map((r) => [r.name, num(r.outstanding / 1e6, 1), pct(r.share, 1), num(r.limit / 1e6)])} />
  </>;
}

function SourceChart({ d }: { d: Ov }) {
  const rows = [...d.by_source].sort((a, b) => SRC_ORDER.indexOf(a.source) - SRC_ORDER.indexOf(b.source));
  const total = rows.reduce((s, r) => s + r.amount, 0) || 1;
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    legend: { bottom: 0, textStyle: { color: t.text2 }, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
    tooltip: { trigger: "item", formatter: (p: { seriesName: string; value: number }) => `${p.seriesName}: <b>${pct(p.value, 1)}</b>` },
    xAxis: { type: "value", max: 1, show: false },
    yAxis: { type: "category", data: ["Портфель"], show: false },
    series: rows.map((r) => ({
      name: `${r.name}${r.on_balance ? " (баланс)" : ""} — ${pct(r.amount / total, 0)}`, type: "bar", stack: "s", barWidth: 28,
      itemStyle: { color: t.cat[SRC_ORDER.indexOf(r.source)], borderColor: t.surface, borderWidth: 2 },
      data: [r.amount / total],
      label: { show: false },
    })),
  }), [rows, total]);
  return <>
    <Chart option={option} height={140} label={`Структура фондирования: ${rows.map((r) => `${r.name} ${pct(r.amount / total, 0)}`).join(", ")}`} />
    <DataTableToggle caption="Структура фондирования" head={["Источник", "₽ млн", "Доля"]} rows={rows.map((r) => [r.name, num(r.amount / 1e6, 1), pct(r.amount / total, 1)])} />
  </>;
}

function FunnelChart({ d }: { d: Ov }) {
  const rows = d.funnel;
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: "item", formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].label}: <b>${rows[p.dataIndex].count}</b>` },
    xAxis: { type: "value", show: false },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => r.label), ...axisCommon(t), splitLine: { show: false } },
    series: [{ type: "bar", barWidth: 20, itemStyle: { color: t.accent, borderRadius: [0, 4, 4, 0] }, data: rows.map((r) => r.count),
      label: { show: true, position: "right", color: t.text, fontSize: 12 } }],
  }), [rows]);
  return <>
    <Chart option={option} height={260} label={`Воронка: ${rows[0]?.count} счетов создано, ${rows[rows.length - 1]?.count} оплачено якорем`} />
    <DataTableToggle caption="Воронка счетов" head={["Этап", "Счетов"]} rows={rows.map((r) => [r.label, r.count])} />
  </>;
}
