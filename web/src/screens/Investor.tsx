import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorText, useDebounced } from "../api/client";
import { mln, num, pct } from "../api/format";
import { PageHead } from "../components/Layout";
import { Badge, Callout, Card, EmptyState, ErrorBox, Loading, Metric, SliderField } from "../components/ui";
import { ru } from "../copy/ru";

const MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const monthName = (m: string) => { const [y, mm] = m.split("-"); return `${MONTHS[Number(mm) - 1]} ${y}`; };

type I = {
  cover: number; tranches: { id: string; month: string; source: string; source_name: string; amount: number; count: number; outstanding: number; repaid: number; overdue: number; wavg_days: number; yield: number; net_yield: number; el: number; top_anchor: string; top_anchor_share: number; issuer: string }[];
  total_issued: number; outstanding: number; expected_loss: number; expected_loss_no_cover: number;
  concentration: { anchor: string; amount: number; share: number }[]; legal_note: string; anchor_cap: number;
};

export default function Investor() {
  const [cover, setCover] = useState(0);
  const dc = useDebounced(cover, 150);
  const q = useQuery({ queryKey: ["investor", dc], queryFn: () => api<I>(`/api/investor?cover=${dc}`), placeholderData: keepPreviousData });
  const d = q.data;
  return (
    <>
      <PageHead title="Портфель траншей" lead="Транши модельного SPV-эмитента, профинансированные внебалансовыми источниками: ЦФА, казначейства, синдикация." />
      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!d ? <Card><Loading rows={6} /></Card> : (
        <div className="flex flex-col gap-6">
          <Callout tone="warning" title="Требование к эмитенту, а не к якорю">{d.legal_note}</Callout>
          <Card>
            <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
              <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
                <Metric label="Выпущено" value={mln(d.total_issued)} />
                <Metric label="В обращении" value={mln(d.outstanding)} />
                <Metric label="Ожидаемые потери" value={mln(d.expected_loss, 2)} note={cover > 0 ? `без страхования ${mln(d.expected_loss_no_cover, 2)}` : "PD × LGD 60% × t/365"} />
                <Metric label="Доходность ЦФА" value={pct((d.tranches.find((t) => t.source === "cfa")?.net_yield) ?? 0.185)} note="KС + 4,5 п.п. минус стоимость страхования" badge={<Badge kind="Факт и гипотеза" source="≈18,5% в сделке Т-Банка, август 2026" />} />
              </div>
              <SliderField label="Страховое покрытие" badge={<Badge kind="Гипотеза" source="Тариф 1% годовых от застрахованной суммы" />} value={cover} onChange={setCover} min={0} max={0.8} step={0.05} scale={100} digits={0} unit="%" />
            </div>
          </Card>
          <Card title="Транши" lead="Эмитент всех траншей — модельный SPV. Группировка по месяцу выпуска и источнику; срок — средневзвешенный по номиналу.">
            {d.tranches.length === 0 ? <EmptyState title={ru.empty.tranches} /> : (
              <div className="overflow-x-auto" tabIndex={0}>
                <table className="data-table dense">
                  <thead><tr><th scope="col">Транш</th><th scope="col">Источник</th><th scope="col" className="r">Номинал</th><th scope="col" className="r">В обращении</th><th scope="col" className="r">Погашено</th><th scope="col" className="r">Просрочено</th><th scope="col" className="r">Срок, дн.</th><th scope="col" className="r">Доходность нетто</th><th scope="col">Крупнейший якорь</th></tr></thead>
                  <tbody>{d.tranches.map((t) => (
                    <tr key={t.id}>
                      <td className="font-medium whitespace-nowrap">{monthName(t.month)}</td>
                      <td>{t.source_name}</td>
                      <td className="r num">{mln(t.amount)}</td><td className="r num">{mln(t.outstanding)}</td><td className="r num">{mln(t.repaid)}</td>
                      <td className={`r num ${t.overdue ? "text-danger" : ""}`}>{mln(t.overdue)}</td>
                      <td className="r num">{num(t.wavg_days, 0)}</td><td className="r num">{pct(t.net_yield)}</td>
                      <td>{t.top_anchor} <span className="text-caption text-ink3">{pct(t.top_anchor_share, 0)}</span></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="Концентрация по якорям" lead={`Доля непогашенных траншей. Лимит в платформе: ${pct(d.anchor_cap, 0)} на якоря.`}>
            <ul className="flex flex-col gap-3">
              {d.concentration.map((c) => (
                <li key={c.anchor} className="grid items-center gap-3 md:grid-cols-[200px_1fr_120px]">
                  <span className="text-small font-medium">{c.anchor}</span>
                  <div className="h-2 rounded-full" style={{ background: "var(--primary-soft-2)" }} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(c.share * 100)} aria-label={`${c.anchor}: ${pct(c.share, 0)}`}>
                    <div className="h-2 rounded-full" style={{ width: `${c.share * 100}%`, background: c.share > d.anchor_cap ? "var(--danger)" : "var(--primary)" }} />
                    <div className="relative -mt-3 h-4 border-l-2" style={{ marginLeft: `${d.anchor_cap * 100}%`, borderColor: "var(--text-2)" }} title={`потолок ${pct(d.anchor_cap, 0)}`} />
                  </div>
                  <span className="num text-right text-small">{pct(c.share, 1)} · {mln(c.amount, 0)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-caption text-ink3">Вертикальная черта — потолок {pct(d.anchor_cap, 0)}; красная полоса правее неё — доля выше потолка. Внутри траншей концентрация может быть выше, чем в портфеле платформы.</p>
          </Card>
        </div>
      )}
    </>
  );
}
