import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { api, errorText } from "../api/client";
import { date, mln, num, pct } from "../api/format";
import { axisCommon, Chart, type ChartTokens } from "../components/Chart";
import { PageHead } from "../components/Layout";
import { Badge, Card, DataTableToggle, EmptyState, ErrorBox, Loading, Metric } from "../components/ui";
import { ru } from "../copy/ru";
import { InvoiceDialog, InvoiceTable, type InvoiceRow } from "./Feed";

type A = {
  anchor: { id: number; name: string; industry: string; rating: string; points: number; pd: number; term_min: number; term_max: number; default_term_days: number; limit: number; supplier_sublimit: number };
  scoring: { points: number; rating: string; rules: { rule: string; points: number; value: string }[] };
  acceptances: InvoiceRow[];
  calendar: { date: string; amount: number; count: number; overdue: number }[];
  suppliers: { supplier_id: number; name: string; turnover: number; count: number; overdue: number }[];
  portfolio: { outstanding: number; share: number; limit: number; cap: number };
  anchor_cap: number;
};

export default function Anchor() {
  const list = useQuery({ queryKey: ["anchors"], queryFn: () => api<{ id: number; name: string; rating: string }[]>("/api/anchors") });
  const [aid, setAid] = useState(1);
  const q = useQuery({ queryKey: ["anchor", aid], queryFn: () => api<A>(`/api/anchors/${aid}`) });
  const [open, setOpen] = useState<number | null>(null);
  const d = q.data;
  return (
    <>
      <PageHead title={d ? d.anchor.name : "Якорь"} lead="Экран только для просмотра: акцепт якорь даёт в своём ЭДО (в прототипе — имитация). Здесь реестр акцептов, платежи на 90 дней, поставщики и доля в портфеле против лимита."
        right={list.data && (
          <label className="flex flex-col gap-1 text-small text-ink2">Якорь (вымышленный)
            <select className="input w-64" value={aid} onChange={(e) => setAid(Number(e.target.value))}>
              {list.data.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.rating}</option>)}
            </select>
          </label>
        )} />
      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!d ? <Card><Loading rows={6} /></Card> : (
        <div className="flex flex-col gap-6">
          <Card>
            <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
              <Metric label="Рейтинг якоря" value={d.anchor.rating} note={`${d.scoring.points} из 100 баллов · PD ${pct(d.anchor.pd, 1)}`} badge={<Badge kind="Гипотеза" source="Таблица баллов, без ML" />} />
              <Metric label="В портфеле платформы" value={mln(d.portfolio.outstanding)} note={`Лимит якоря ${mln(d.anchor.limit, 0)}`} />
              <Metric label="Доля в портфеле" value={pct(d.portfolio.share, 1)} tone={d.portfolio.share > d.anchor_cap ? "negative" : "default"} note={`Потолок ${pct(d.anchor_cap, 0)}`} />
              <Metric label="Срок оплаты" value={`${d.anchor.term_min}–${d.anchor.term_max}`} unit="дней" note={d.anchor.industry} />
            </div>
          </Card>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card title="Почему такой рейтинг" lead="Баллы суммируются до 100: A — от 80, B — от 55, C — от 35, D — ниже.">
              <ul className="flex flex-col gap-2 text-small">
                {d.scoring.rules.map((r) => <li key={r.rule} className="flex justify-between gap-3"><span className={r.points ? "" : "text-ink3"}>{r.rule}</span><span className="num shrink-0 font-semibold">+{r.points}</span></li>)}
              </ul>
            </Card>
            <Card title="Платежи на 90 дней" lead="Счета, по которым якорь должен заплатить финансирующей стороне.">
              {d.calendar.length === 0 ? <EmptyState title={ru.empty.calendar} /> : <CalChart rows={d.calendar} />}
            </Card>
          </div>
          <Card title="Поставщики якоря" lead="По обороту в демо-данных.">
            <div className="overflow-x-auto" tabIndex={0}>
              <table className="data-table dense">
                <thead><tr><th scope="col">Поставщик</th><th scope="col" className="r">Оборот</th><th scope="col" className="r">Счетов</th><th scope="col" className="r">С задержкой оплаты</th></tr></thead>
                <tbody>{d.suppliers.map((s) => <tr key={s.supplier_id}><td>{s.name}</td><td className="r num">{mln(s.turnover)}</td><td className="r num">{s.count}</td><td className="r num">{s.overdue}</td></tr>)}</tbody>
              </table>
            </div>
          </Card>
          <Card title="Реестр акцептов">
            {d.acceptances.length === 0 ? <EmptyState title="Акцептов пока нет." /> : <InvoiceTable items={d.acceptances.slice(0, 25)} onOpen={setOpen} compact />}
          </Card>
        </div>
      )}
      {open && <InvoiceDialog id={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function CalChart({ rows }: { rows: A["calendar"] }) {
  const option = useCallback((t: ChartTokens) => ({
    grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
    tooltip: { trigger: "axis", formatter: (p: { dataIndex: number }[]) => { const r = rows[p[0].dataIndex]; return `${date(r.date)}: <b>${mln(r.amount)}</b>, счетов ${r.count}${r.overdue ? `, просрочено ${r.overdue}` : ""}`; } },
    xAxis: { type: "category", data: rows.map((r) => date(r.date).slice(0, 5)), ...axisCommon(t), splitLine: { show: false } },
    yAxis: { type: "value", name: "₽ млн", ...axisCommon(t), axisLabel: { color: t.text2, formatter: (v: number) => num(v / 1e6) } },
    series: [{ type: "bar", barMaxWidth: 16, data: rows.map((r) => ({ value: r.amount, itemStyle: { color: r.overdue ? t.neg : t.accent, borderRadius: [4, 4, 0, 0] } })) }],
  }), [rows]);
  return <>
    <Chart option={option} height={240} label={`Платежи на 90 дней: ${rows.length} дат, всего ${mln(rows.reduce((s, r) => s + r.amount, 0))}`} />
    <DataTableToggle caption="Календарь платежей" head={["Дата", "₽ млн", "Счетов"]} rows={rows.map((r) => [date(r.date), num(r.amount / 1e6, 1), r.count])} />
  </>;
}
