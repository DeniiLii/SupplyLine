import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, errorText, useDebounced } from "../api/client";
import { date, dateTime, days, pct, rub } from "../api/format";
import { PageHead } from "../components/Layout";
import {
  Badge, Callout, Card, CheckMark, Dialog, EmptyState, ErrorBox, Loading, Rail, Spinner, StatusChip, Term, Tip, useToast,
  type RailStep,
} from "../components/ui";
import { ru } from "../copy/ru";

export type InvoiceRow = {
  id: number; number: string; anchor: string; anchor_rating: string; anchor_id: number; supplier: string; supplier_id: number;
  upd_no: string; upd_date: string; amount: number; term_days: number; due_date: string; status: string; status_label: string;
  status_reason: string | null; funding_source: string | null; review_flag: boolean; review_reason: string | null;
  checks: { upd: boolean | null; acceptance: boolean | null; registry: boolean; limits: boolean | null };
  r_total: number | null; discount: number | null; payout: number | null; accepted_at: string | null; funded_at: string | null;
  repaid_at: string | null; overdue_since: string | null; story: string | null; created_at: string;
};
type Full = InvoiceRow & {
  price: { r_total: number; discount: number; payout: number; comp_funding: number; comp_loss: number; comp_opex: number; comp_margin: number; eff_rate: number; spread: number; r_el: number; capped: boolean };
  why: { anchor_rating: string; anchor_points: number; pd: number; rules: { rule: string; points: number; value: string }[]; funding_scenario: string; funding_scenario_name: string; key_rate: number; r_fund: number; note: string };
  limit_checks: { rule: string; ok: boolean; used: number; limit: number; detail: string }[];
  claim_key: string;
  events: { ts: string; kind: string; level: string; message: string }[];
  actions: { sell: boolean; resell: boolean; overdue: boolean };
};
type List = { total: number; items: InvoiceRow[]; status_counts: Record<string, number>; labels: Record<string, string> };

const FILTERS: { key: string; label: string; statuses?: string[] }[] = [
  { key: "all", label: ru.feed.all },
  { key: "offers", label: "Предложения", statuses: ["OFFERED", "ACCEPTED"] },
  { key: "funded", label: "Профинансированы", statuses: ["SOLD", "FUNDED"] },
  { key: "overdue", label: "Просрочка и регресс", statuses: ["OVERDUE", "REGRESS"] },
  { key: "closed", label: "Закрыты", statuses: ["REPAID", "RECOVERED"] },
  { key: "rejected", label: "Отклонены и истекли", statuses: ["REJECTED", "EXPIRED"] },
];

export default function Feed() {
  const { id } = useParams();
  const nav = useNavigate();
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const dq = useDebounced(q, 250);
  const f = FILTERS.find((x) => x.key === filter)!;
  const params = new URLSearchParams({ limit: "40", offset: String(page * 40) });
  f.statuses?.forEach((s) => params.append("status", s));
  if (dq) params.set("q", dq);
  const list = useQuery({ queryKey: ["invoices", filter, dq, page], queryFn: () => api<List>(`/api/invoices?${params}`), placeholderData: keepPreviousData });

  return (
    <>
      <PageHead title={ru.feed.title} lead={<>Синтетические счета пяти вымышленных якорей. Продажа возможна только при совпадении <Term t="УПД" /> в <Term t="ЭДО" />, <Term t="акцепт">акцепта</Term> якоря и отсутствии требования в <Term t="реестр">реестре</Term>.</>} />
      <Card>
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div role="tablist" aria-label="Фильтр по статусу" className="flex flex-wrap gap-1">
            {FILTERS.map((x) => {
              const n = x.statuses ? x.statuses.reduce((s, k) => s + (list.data?.status_counts[k] ?? 0), 0) : Object.values(list.data?.status_counts ?? {}).reduce((a, b) => a + b, 0);
              return (
                <button key={x.key} role="tab" aria-selected={filter === x.key} onClick={() => { setFilter(x.key); setPage(0); }}
                  className={`min-h-[36px] rounded-full border px-3 text-small font-medium ${filter === x.key ? "border-primary bg-primary-soft text-primary" : "border-line text-ink2 hover:text-ink"}`}>
                  {x.label} <span className="num text-ink3">{list.data ? n : ""}</span>
                </button>
              );
            })}
          </div>
          <label className="relative block lg:w-80">
            <span className="sr-only">{ru.feed.search}</span>
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink3" aria-hidden />
            <input className="input pl-9" placeholder={ru.feed.search} value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          </label>
        </div>
        {list.isError && <ErrorBox text={errorText(list.error)} onRetry={() => list.refetch()} />}
        {!list.data ? <Loading rows={8} /> : list.data.items.length === 0 ? <EmptyState title={ru.feed.empty} /> : (
          <>
            <InvoiceTable items={list.data.items} onOpen={(i) => nav(`/feed/${i}`)} />
            <div className="mt-4 flex items-center justify-between gap-3 text-small text-ink2">
              <span className="num">{page * 40 + 1}–{Math.min((page + 1) * 40, list.data.total)} из {list.data.total}</span>
              <div className="flex gap-2">
                <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Назад</button>
                <button className="btn btn-secondary btn-sm" disabled={(page + 1) * 40 >= list.data.total} onClick={() => setPage(page + 1)}>Дальше</button>
              </div>
            </div>
          </>
        )}
      </Card>
      {id && <InvoiceDialog id={Number(id)} onClose={() => nav("/feed")} />}
    </>
  );
}

export function InvoiceTable({ items, onOpen, compact = false }: { items: InvoiceRow[]; onOpen: (id: number) => void; compact?: boolean }) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block" tabIndex={0}>
        <table className={`data-table ${compact ? "dense" : ""}`}>
          <caption className="sr-only">Счета</caption>
          <thead>
            <tr>
              <th scope="col">{ru.feed.columns.number}</th>
              <th scope="col">{ru.feed.columns.supplier}</th>
              {!compact && <th scope="col">{ru.feed.columns.anchor}</th>}
              <th scope="col" className="r">{ru.feed.columns.amount}</th>
              <th scope="col" className="r">{ru.feed.columns.term}</th>
              <th scope="col">{ru.feed.columns.checks}</th>
              <th scope="col">{ru.feed.columns.status}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id} data-clickable="true" tabIndex={0} onClick={() => onOpen(i.id)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen(i.id))}
                aria-label={`Счёт ${i.number}, ${rub(i.amount)}, ${i.status_label}. Открыть карточку`}>
                <td>
                  <div className="font-medium">{i.number}</div>
                  <div className="text-caption text-ink3">УПД {i.upd_no} от {date(i.upd_date)}</div>
                </td>
                <td className="max-w-[220px] truncate">{i.supplier}</td>
                {!compact && <td><span className="whitespace-nowrap">{i.anchor}</span> <span className="text-caption text-ink3">· {i.anchor_rating}</span></td>}
                <td className="r num font-medium">{rub(i.amount)}</td>
                <td className="r num">{days(i.term_days)}</td>
                <td><Checks i={i} /></td>
                <td>
                  <div className="flex flex-col items-start gap-1">
                    <StatusChip status={i.status} label={i.status_label} review={i.review_flag} />
                    {i.story === "concentration" && <span className="text-caption text-ink3">крупный счёт</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col gap-2 md:hidden">
        {items.map((i) => (
          <li key={i.id}>
            <button className="panel flex w-full flex-col gap-2 text-left" onClick={() => onOpen(i.id)}>
              <div className="flex w-full items-start justify-between gap-2">
                <div>
                  <div className="font-medium">{i.number}</div>
                  <div className="text-caption text-ink3">{i.supplier}</div>
                </div>
                <div className="num font-semibold">{rub(i.amount)}</div>
              </div>
              <div className="flex w-full flex-wrap items-center justify-between gap-2">
                <StatusChip status={i.status} label={i.status_label} review={i.review_flag} />
                <span className="text-caption text-ink2">{i.anchor} · {days(i.term_days)}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function Checks({ i }: { i: InvoiceRow }) {
  return (
    <span className="inline-flex items-center gap-2">
      <CheckMark ok={i.checks.upd} label={ru.feed.checks.upd} />
      <CheckMark ok={i.checks.acceptance} label={ru.feed.checks.acceptance} />
      <CheckMark ok={i.checks.registry ? true : null} label={ru.feed.checks.registry} />
      <CheckMark ok={i.status_reason?.includes("правило") ? false : i.checks.registry ? true : null} label={ru.feed.checks.limits} />
    </span>
  );
}

const PATH = [
  ["DRAFT", "Черновик"], ["UPD_VERIFIED", "УПД в ЭДО"], ["ACCEPTED", "Акцепт"], ["OFFERED", "Предложение"],
  ["SOLD", "Уступка"], ["FUNDED", "Деньги"], ["REPAID", "Оплата якоря"],
] as const;

function railFor(inv: Full): RailStep[] {
  const order = PATH.map((x) => x[0] as string);
  const st = inv.status;
  let idx = order.indexOf(st);
  let errAt = -1;
  if (st === "REJECTED") { idx = inv.accepted_at ? 3 : inv.checks.upd === false ? 0 : 1; errAt = idx + 1; }
  if (st === "EXPIRED") { idx = 3; errAt = 4; }
  if (["OVERDUE", "REGRESS", "RECOVERED", "WRITTEN_OFF"].includes(st)) { idx = 5; errAt = 6; }
  const meta: Record<string, string | undefined> = {
    ACCEPTED: inv.accepted_at ? dateTime(inv.accepted_at) : undefined,
    FUNDED: inv.funded_at ? dateTime(inv.funded_at) : undefined,
    REPAID: inv.repaid_at ? dateTime(inv.repaid_at) : `срок ${date(inv.due_date)}`,
  };
  return PATH.map(([k, label], i) => ({
    key: k, label: i === errAt && st !== "EXPIRED" && st !== "REJECTED" ? (st === "OVERDUE" ? "Просрочка" : st === "REGRESS" ? "Регресс" : st === "RECOVERED" ? "Взыскано по регрессу" : "Списано") : i === errAt ? (st === "EXPIRED" ? "Истекло" : "Отклонён") : label,
    state: i === errAt ? (st === "RECOVERED" ? "done" : "error") : i < idx ? "done" : i === idx ? (st === "REPAID" ? "done" : "current") : "todo",
    meta: meta[k],
  }));
}

export function InvoiceDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [blocked, setBlocked] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["invoice", id], queryFn: () => api<Full>(`/api/invoices/${id}`) });
  const act = useMutation({
    mutationFn: (a: "sell" | "resell" | "overdue") => api<Full>(`/api/invoices/${id}/${a}`, { method: "POST" }),
    onSuccess: (_d, a) => {
      qc.invalidateQueries();
      setBlocked(null);
      toast("success", a === "sell" ? ru.feed.sold : a === "overdue" ? ru.feed.overdueDone : "Готово");
    },
    onError: (e) => {
      qc.invalidateQueries();
      const txt = errorText(e);
      if (e instanceof ApiError && (e.status === 409 || e.status === 422)) setBlocked(txt);
      toast("danger", txt);
    },
  });
  const inv = q.data;
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()} wide title={inv ? `Счёт ${inv.number}` : "Счёт"}
      description={inv ? `${inv.supplier} → ${inv.anchor} · ${rub(inv.amount)} · срок ${days(inv.term_days)}` : undefined}>
      {q.isError && <ErrorBox text={errorText(q.error)} onRetry={() => q.refetch()} />}
      {!inv ? <Loading rows={6} /> : (
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-3">
            <StatusChip status={inv.status} label={inv.status_label} review={inv.review_flag} />
            {inv.funding_source && <span className="text-caption text-ink2">Фондирование: {SOURCE_NAMES[inv.funding_source] ?? inv.funding_source}</span>}
          </div>
          <div className="hidden md:block"><Rail label={ru.feed.path} steps={railFor(inv)} /></div>
          <div className="md:hidden"><Rail label={ru.feed.path} steps={railFor(inv)} vertical /></div>
          {inv.review_flag && <Callout tone="warning" title="Счёт на ручной проверке">{inv.review_reason}</Callout>}
          {inv.status_reason && <Callout tone={inv.status_reason.includes("правило") ? "warning" : "danger"} title="Почему счёт не продан">{inv.status_reason}</Callout>}
          {blocked && <Callout tone="danger" title="Действие заблокировано">{blocked}</Callout>}

          <div className="grid gap-6 lg:grid-cols-2">
            <section aria-labelledby="offer-h" className="panel">
              <h3 id="offer-h" className="mb-3 text-small font-semibold">{ru.feed.offer}{inv.status !== "OFFERED" && inv.status !== "ACCEPTED" ? " (зафиксировано при продаже)" : ""}</h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-small">
                <dt className="text-ink2">Ставка дисконта</dt><dd className="num text-right font-medium">{pct(inv.price.r_total)}</dd>
                <dt className="text-ink2"><Term t="эффективная ставка">Эффективная ставка</Term></dt><dd className="num text-right font-medium">{pct(inv.price.eff_rate)}</dd>
                <dt className="text-ink2"><Term t="дисконт">Дисконт</Term></dt><dd className="num text-right">{rub(inv.price.discount, 2)}</dd>
                <dt className="text-ink2">Поставщик получит</dt><dd className="num text-right text-[18px] font-semibold text-primary">{rub(inv.price.payout, 2)}</dd>
                <dt className="col-span-2 mt-2 border-t border-line pt-2 text-caption text-ink3">Состав дисконта</dt>
                <dt className="text-ink2">Фондирование</dt><dd className="num text-right">{rub(inv.price.comp_funding, 2)}</dd>
                <dt className="text-ink2">Ожидаемые потери</dt><dd className="num text-right">{rub(inv.price.comp_loss, 2)}</dd>
                <dt className="text-ink2">Издержки</dt><dd className="num text-right">{rub(inv.price.comp_opex, 2)}</dd>
                <dt className="text-ink2">Маржа платформы</dt><dd className="num text-right">{rub(inv.price.comp_margin, 2)}</dd>
              </dl>
            </section>
            <section aria-labelledby="why-h" className="panel">
              <h3 id="why-h" className="mb-1 text-small font-semibold">{ru.feed.why}</h3>
              <p className="mb-3 text-caption text-ink2">{inv.why.note}</p>
              <div className="mb-2 text-small">Рейтинг якоря <b>{inv.why.anchor_rating}</b> ({inv.why.anchor_points} из 100 баллов) → <Term t="PD" /> {pct(inv.why.pd, 1)} <Badge kind="Гипотеза" source="Таблица баллов скоринга, без ML" /></div>
              <ul className="mb-3 flex flex-col gap-1 text-caption">
                {inv.why.rules.map((r) => (
                  <li key={r.rule} className="flex justify-between gap-3"><span className={r.points ? "" : "text-ink3"}>{r.rule}</span><span className="num shrink-0 font-medium">+{r.points}</span></li>
                ))}
              </ul>
              <div className="text-caption text-ink2">Фондирование: сценарий {inv.why.funding_scenario} «{inv.why.funding_scenario_name}», KС {pct(inv.why.key_rate)} → r_fund {pct(inv.why.r_fund)}</div>
            </section>
          </div>

          <section aria-labelledby="lim-h">
            <h3 id="lim-h" className="mb-2 text-small font-semibold">{ru.feed.limits}</h3>
            <div className="overflow-x-auto" tabIndex={0}>
              <table className="data-table dense">
                <thead><tr><th scope="col">Правило</th><th scope="col" className="r">С учётом счёта</th><th scope="col" className="r">Лимит</th><th scope="col">Итог</th></tr></thead>
                <tbody>
                  {inv.limit_checks.map((c) => (
                    <tr key={c.rule}>
                      <td><Tip text={c.detail}><span className="hint-term" tabIndex={0}>{c.rule}</span></Tip></td>
                      <td className="r num">{rub(c.used)}</td>
                      <td className="r num">{rub(c.limit)}</td>
                      <td><CheckMark ok={c.ok} label={c.rule} /> <span className="text-caption">{c.ok ? "в пределах" : "превышен"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={!inv.actions.sell || act.isPending} onClick={() => act.mutate("sell")}>
              {act.isPending && act.variables === "sell" && <Spinner />}{ru.feed.sell}
            </button>
            <Tip text={ru.feed.resellHint}>
              <button className="btn btn-secondary" disabled={!inv.actions.resell || act.isPending} onClick={() => act.mutate("resell")}>
                <ShieldAlert size={16} aria-hidden />{ru.feed.resell}
              </button>
            </Tip>
            <button className="btn btn-danger" disabled={!inv.actions.overdue || act.isPending} onClick={() => act.mutate("overdue")}>{ru.feed.overdue}</button>
          </div>

          <section aria-labelledby="key-h" className="text-caption">
            <h3 id="key-h" className="mb-1 font-semibold">{ru.feed.claimKey}</h3>
            <code className="block break-all rounded-panel bg-sunken p-2 font-mono text-ink2">{inv.claim_key}</code>
            <p className="mt-1 text-ink3">SHA-256 от якоря, поставщика, номера и даты УПД, суммы в копейках. Уникальный индекс в БД.</p>
          </section>

          <section aria-labelledby="ev-h">
            <h3 id="ev-h" className="mb-2 text-small font-semibold">{ru.feed.history}</h3>
            <ol className="flex flex-col gap-1 text-caption">
              {inv.events.map((e, i) => (
                <li key={i} className="flex gap-3"><span className="num w-24 shrink-0 text-ink3">{dateTime(e.ts)}</span><span className={e.level === "danger" ? "text-danger" : e.level === "warning" ? "text-warning" : ""}>{e.message}</span></li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </Dialog>
  );
}

export const SOURCE_NAMES: Record<string, string> = {
  bank: "Банк-партнёр (баланс)", line: "Кредитная линия", cfa: "ЦФА для инвесторов", treasury: "Казначейства корпораций", syndication: "Синдикация",
};
