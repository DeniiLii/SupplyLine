import * as RDialog from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { PlayCircle, X } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, errorText } from "../api/client";
import { ru } from "../copy/ru";
import { setTourOpen } from "./tourState";
import { Spinner } from "./ui";

type Inv = { id: number; number: string; story: string | null; status: string; review_flag: boolean; status_reason: string | null };
type Ctx = { nav: (to: string) => void; soldId: number | null; setSoldId: (id: number) => void };
type Step = { title: string; text: string; go: (c: Ctx) => Promise<void>; run?: (c: Ctx) => Promise<string> };

async function bigInvoice(): Promise<Inv> {
  const r = await api<{ items: Inv[] }>("/api/invoices?limit=20");
  const big = r.items.find((i) => i.story === "concentration");
  if (!big) throw new Error(ru.tour.noBig);
  return big;
}

async function sellableOffer(): Promise<Inv> {
  const r = await api<{ items: Inv[] }>("/api/invoices?status=OFFERED&limit=100");
  for (const i of r.items.filter((x) => x.story === null && !x.review_flag && !x.status_reason).slice(0, 25)) {
    const full = await api<{ actions: { sell: boolean } }>(`/api/invoices/${i.id}`);
    if (full.actions.sell) return i;
  }
  throw new Error(ru.tour.noOffer);
}

function needSold(c: Ctx): number {
  if (c.soldId === null) throw new Error(ru.tour.needSold);
  return c.soldId;
}

function scrollToHeading(text: string) {
  // Экран грузится лениво: ждём заголовок до 3 секунд
  const t0 = Date.now();
  const tick = () => {
    const h = [...document.querySelectorAll("h2, h3")].find((x) => x.textContent?.startsWith(text));
    if (h) {
      // Отступ на липкую шапку, иначе она закрывает начало блока
      const top = h.getBoundingClientRect().top + window.scrollY - (document.querySelector("header")?.offsetHeight ?? 0) - 16;
      window.scrollTo({ top });
      // Графики выше грузятся лениво и сдвигают страницу: повторяем, пока раскладка не устоится
      if (Date.now() - t0 < 2500) setTimeout(tick, 400);
    } else if (Date.now() - t0 < 4000) setTimeout(tick, 150);
  };
  tick();
}

const S = ru.tour.steps;
const STEPS: Step[] = [
  { ...S[0], go: async (c) => c.nav("/simulator") },
  { ...S[1], go: async (c) => c.nav(`/feed/${(await bigInvoice()).id}`) },
  {
    ...S[2],
    go: async (c) => c.nav(`/feed/${(await sellableOffer()).id}`),
    run: async (c) => {
      const inv = await sellableOffer();
      await api(`/api/invoices/${inv.id}/sell`, { method: "POST" });
      c.setSoldId(inv.id);
      c.nav(`/feed/${inv.id}`);
      return ru.tour.sold(inv.number);
    },
  },
  {
    ...S[3],
    go: async (c) => c.nav(`/feed/${needSold(c)}`),
    run: async (c) => {
      const id = needSold(c);
      c.nav(`/feed/${id}`);
      try {
        await api(`/api/invoices/${id}/resell`, { method: "POST" });
        return ru.tour.resellPassed;
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) return ru.tour.resellBlocked;
        throw e;
      }
    },
  },
  {
    ...S[4],
    go: async (c) => c.nav(`/feed/${needSold(c)}`),
    run: async (c) => {
      const id = needSold(c);
      await api("/api/clock/advance", { method: "POST", json: { days: 1 } });
      await api(`/api/invoices/${id}/overdue`, { method: "POST" });
      c.nav(`/feed/${id}`);
      return ru.tour.overdue;
    },
  },
  {
    ...S[5],
    go: async (c) => c.nav("/feed"),
    run: async (c) => {
      const id = needSold(c);
      await api("/api/clock/advance", { method: "POST", json: { days: 30 } });
      c.nav(`/feed/${id}`);
      return ru.tour.regress;
    },
  },
  { ...S[6], go: async (c) => { c.nav("/model"); scrollToHeading(ru.model.stress); } },
  { ...S[7], go: async (c) => { c.nav("/overview"); scrollToHeading(ru.overview.gatesTitle); } },
];

export function TourButton() {
  const [open, setOpenState] = useState(false);
  const setOpen = (v: boolean) => {
    setOpenState(v);
    setTourOpen(v);
  };
  const [i, setI] = useState(0);
  const [soldId, setSoldId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const nav = useNavigate();
  const qc = useQueryClient();
  const trigger = useRef<HTMLButtonElement>(null);
  const step = STEPS[i];
  const ctx: Ctx = { nav, soldId, setSoldId };

  const act = async (fn: (c: Ctx) => Promise<string | void>) => {
    setBusy(true);
    setMsg(null);
    try {
      const text = await fn(ctx);
      await qc.invalidateQueries();
      if (text) setMsg({ tone: "ok", text });
    } catch (e) {
      setMsg({ tone: "err", text: e instanceof ApiError ? errorText(e) : e instanceof Error ? e.message : ru.errors.generic });
    } finally {
      setBusy(false);
    }
  };
  const goto = (n: number) => {
    setI(n);
    setMsg(null);
  };
  const start = () => {
    setOpen(true);
    if (i === 0) act(STEPS[0].go);
  };

  return (
    <RDialog.Root open={open} onOpenChange={setOpen} modal={false}>
      <RDialog.Trigger asChild>
        <button ref={trigger} className="btn btn-primary btn-sm" onClick={(e) => { e.preventDefault(); start(); }}>
          <PlayCircle size={16} aria-hidden />
          {ru.tour.button}
        </button>
      </RDialog.Trigger>
      <RDialog.Portal>
        <RDialog.Content
          data-tour
          aria-describedby="tour-text"
          // Панель не закрывается кликом по странице: посетитель работает с экраном и читает шаг
          onInteractOutside={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => { e.preventDefault(); trigger.current?.focus(); }}
          className="fixed inset-x-2 bottom-2 z-[60] max-h-[70vh] overflow-y-auto rounded-card border border-line bg-surface p-4 md:inset-x-auto md:bottom-4 md:right-4 md:w-[380px] md:p-5"
          style={{ pointerEvents: "auto", boxShadow: "0 0 0 1px var(--line)" }}
        >
          <div className="mb-2 flex items-start justify-between gap-3">
            <div>
              <div className="text-caption font-medium text-ink3" aria-live="polite">{ru.tour.progress(i + 1, STEPS.length)}</div>
              <RDialog.Title className="mt-0.5 text-h2">{step.title}</RDialog.Title>
            </div>
            <RDialog.Close className="btn btn-ghost btn-sm" aria-label={ru.tour.close}>
              <X size={18} />
            </RDialog.Close>
          </div>
          <ol className="mb-3 flex gap-1" aria-hidden>
            {STEPS.map((_, n) => (
              <li key={n} className="h-1 flex-1 rounded-full" style={{ background: n <= i ? "var(--primary)" : "var(--primary-soft-2)" }} />
            ))}
          </ol>
          <RDialog.Description id="tour-text" className="text-small text-ink2">{step.text}</RDialog.Description>
          {msg && (
            <p role={msg.tone === "err" ? "alert" : "status"} className="mt-3 rounded-control px-3 py-2 text-small"
              style={msg.tone === "err" ? { background: "var(--danger-bg)", color: "var(--danger)" } : { background: "var(--success-bg)", color: "var(--success)" }}>
              {msg.text}
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => act(step.go)}>{ru.tour.go}</button>
            {step.run && (
              <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => act(step.run!)}>
                {busy && <Spinner />}{ru.tour.run}
              </button>
            )}
            <span className="ml-auto flex gap-2">
              <button className="btn btn-ghost btn-sm" disabled={i === 0 || busy} onClick={() => goto(i - 1)}>{ru.tour.back}</button>
              {i < STEPS.length - 1
                ? <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => { goto(i + 1); act(STEPS[i + 1].go); }}>{ru.tour.next}</button>
                : <button className="btn btn-primary btn-sm" onClick={() => { setOpen(false); goto(0); }}>{ru.tour.finish}</button>}
            </span>
          </div>
          <p className="mt-3 text-caption text-ink3">{step.run ? ru.tour.keys : ru.tour.keysShort}</p>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}
