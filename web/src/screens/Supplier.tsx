import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorText } from "../api/client";
import { days, mln, num, pct, rub } from "../api/format";
import { PageHead } from "../components/Layout";
import { Badge, Card, EmptyState, ErrorBox, Loading, Metric, Rail } from "../components/ui";
import { ru } from "../copy/ru";
import { InvoiceDialog, InvoiceTable, type InvoiceRow } from "./Feed";

type S = {
  supplier: { id: number; name: string; city: string; revenue_mln: number; auto_sell: boolean };
  links: { anchor_id: number; anchor: string; rating: string; limit: number; used: number; turnover_90d: number; limit_share: number; months_with_anchor: number; returns_share: number }[];
  offers: InvoiceRow[]; history: InvoiceRow[];
  compare: null | { invoice: string; amount: number; term_days: number; sell_cost: number; sell_payout: number; sell_eff_rate: number; sell_time: string; credit_cost: number; credit_rate: number; credit_time: string; difference: number; note: string };
  timeline: { number: string; accepted_at: string; funded_at: string; hours: number }[];
};

export default function Supplier() {
  const list = useQuery({ queryKey: ["suppliers"], queryFn: () => api<{ id: number; name: string }[]>("/api/suppliers") });
  const [sid, setSid] = useState(() => { try { return Number(localStorage.getItem("sl-supplier")) || 0; } catch { return 0; } });
  const current = sid || 0;
  const q = useQuery({ queryKey: ["supplier", current], queryFn: () => api<S>(`/api/suppliers/${current || list.data![0].id}`), enabled: !!list.data });
  const [open, setOpen] = useState<number | null>(null);
  const d = q.data;
  return (
    <>
      <PageHead title={d ? d.supplier.name : "Поставщик"} lead="Лимиты по якорям, открытые предложения и сколько стоит продать счёт сейчас по сравнению с кредитом."
        right={list.data && (
          <label className="flex flex-col gap-1 text-small text-ink2">Поставщик (вымышленный)
            <select className="input w-72" value={d?.supplier.id ?? ""} onChange={(e) => { setSid(Number(e.target.value)); try { localStorage.setItem("sl-supplier", e.target.value); } catch { /* */ } }}>
              {list.data.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        )} />
      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!d ? <Card><Loading rows={6} /></Card> : (
        <div className="flex flex-col gap-6">
          <Card title="Лимиты по якорям" lead="Лимит = min(доля × оборот с якорем за 90 дней, суб-лимит якоря). Скоринг поставщика влияет на лимит, а не на цену.">
            <ul className="grid gap-4 md:grid-cols-2">
              {d.links.map((l) => {
                const share = l.limit ? l.used / l.limit : 0;
                return (
                  <li key={l.anchor_id} className="panel flex flex-col gap-3">
                    <div className="flex items-center justify-between gap-2"><span className="font-semibold">{l.anchor}</span><span className="text-caption text-ink2">рейтинг {l.rating}</span></div>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="num text-[22px] font-semibold">{mln(l.used)}</span>
                      <span className="text-small text-ink2">из {mln(l.limit)}</span>
                    </div>
                    <div className="h-2 w-full rounded-full" style={{ background: "var(--primary-soft-2)" }} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)} aria-label={`Использовано ${pct(share, 0)} лимита`}>
                      <div className="h-2 rounded-full" style={{ width: `${Math.min(100, share * 100)}%`, background: share > 0.9 ? "var(--danger)" : "var(--primary)" }} />
                    </div>
                    <div className="text-caption text-ink3">Оборот за 90 дней {mln(l.turnover_90d)} · доля {pct(l.limit_share, 0)} · с якорем {l.months_with_anchor} мес. · возвраты {pct(l.returns_share, 1)}</div>
                  </li>
                );
              })}
            </ul>
          </Card>

          {d.compare && (
            <Card title="Ждать оплату и взять кредит или продать счёт сейчас" lead={`Счёт ${d.compare.invoice}: ${rub(d.compare.amount)}, срок ${days(d.compare.term_days)}.`}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="panel flex flex-col gap-2">
                  <div className="font-semibold">Продать счёт</div>
                  <Metric label="Дисконт" value={rub(d.compare.sell_cost)} note={`Эффективная ставка ${pct(d.compare.sell_eff_rate)}`} />
                  <div className="text-small text-ink2">Получите {rub(d.compare.sell_payout)} {d.compare.sell_time}. Без залога, долговая нагрузка не растёт.</div>
                </div>
                <div className="panel flex flex-col gap-2">
                  <div className="font-semibold">Взять кредит МСП на срок отсрочки</div>
                  <Metric label="Проценты" value={rub(d.compare.credit_cost)} note={<>Ставка {pct(d.compare.credit_rate, 1)} <Badge kind="Факт" source="Банк России, июнь 2026" /></>} />
                  <div className="text-small text-ink2">{d.compare.credit_time}.</div>
                </div>
              </div>
              <p className="mt-4 text-small">
                {d.compare.difference > 0 ? <>Продажа дороже кредита на <b className="num">{rub(d.compare.difference)}</b>.</> : <>Продажа дешевле кредита на <b className="num">{rub(-d.compare.difference)}</b>.</>} {d.compare.note}
              </p>
            </Card>
          )}

          <Card title="Открытые предложения">
            {d.offers.length === 0 ? <EmptyState title={ru.empty.offers} /> : <InvoiceTable items={d.offers} onOpen={setOpen} compact />}
          </Card>

          <Card title="От акцепта до денег" lead="Последние профинансированные счета: сколько часов прошло от акцепта якоря до зачисления.">
            {d.timeline.length === 0 ? <EmptyState title="Профинансированных счетов пока нет." /> : (
              <ul className="flex flex-col gap-3">
                {d.timeline.slice(0, 6).map((t) => (
                  <li key={t.number} className="grid items-center gap-2 md:grid-cols-[160px_1fr_80px]">
                    <span className="text-small font-medium">{t.number}</span>
                    <Rail label={`Счёт ${t.number}`} steps={[
                      { key: "a", state: "done", label: "Акцепт" },
                      { key: "f", state: "done", label: "Деньги" },
                    ]} />
                    <span className={`num text-right text-small font-semibold ${t.hours >= 24 ? "text-danger" : ""}`}>{num(t.hours, 1)} ч</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="История">
            {d.history.length === 0 ? <EmptyState title="Счетов пока нет." /> : <InvoiceTable items={d.history} onOpen={setOpen} compact />}
          </Card>
        </div>
      )}
      {open && <InvoiceDialog id={open} onClose={() => setOpen(null)} />}
    </>
  );
}
