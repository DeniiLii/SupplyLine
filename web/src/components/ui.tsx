import * as RSlider from "@radix-ui/react-slider";
import * as RSwitch from "@radix-ui/react-switch";
import * as RToggle from "@radix-ui/react-toggle-group";
import * as RTooltip from "@radix-ui/react-tooltip";
import * as RDialog from "@radix-ui/react-dialog";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Info,
  Loader2,
  OctagonAlert,
  RotateCcw,
  ShieldX,
  X,
} from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { glossary, ru } from "../copy/ru";
import { num } from "../api/format";

/* ---------------------------------------------------------------- бейдж происхождения */

export type BadgeKind = "Факт" | "Гипотеза" | "Факт и гипотеза" | "Факт / гипотеза" | "Факт / допущение" | "Допущение" | "Данные 2023 года" | string;

export function Badge({ kind, source }: { kind: BadgeKind; source?: string }) {
  const fact = kind.startsWith("Факт") && !kind.includes("гипотез");
  const mixed = kind.includes("гипотез") && kind.startsWith("Факт");
  const style = fact
    ? { color: "var(--badge-fact)", background: "var(--badge-fact-bg)" }
    : mixed
      ? { color: "var(--primary)", background: "var(--primary-soft)" }
      : { color: "var(--badge-hyp)", background: "var(--badge-hyp-bg)" };
  const label = kind === "Факт / гипотеза" ? "Факт и гипотеза" : kind;
  const body = (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 text-caption font-medium"
      style={{ ...style, minHeight: 22 }}
      tabIndex={source ? 0 : undefined}
      aria-label={source ? `${label}. Источник: ${source}` : label}
    >
      {fact ? <Check size={12} aria-hidden /> : <CircleDashed size={12} aria-hidden />}
      {label}
    </span>
  );
  if (!source) return body;
  return <Tip text={source}>{body}</Tip>;
}

/* ---------------------------------------------------------------- подсказки */

export function Tip({ text, children }: { text: ReactNode; children: ReactNode }) {
  return (
    <RTooltip.Root delayDuration={150}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded-panel border border-line bg-surface px-3 py-2 text-caption text-ink"
          style={{ boxShadow: "0 4px 16px rgba(20,27,45,.12)" }}
        >
          {text}
          <RTooltip.Arrow style={{ fill: "var(--surface)" }} />
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  );
}

/** Термин с объяснением при первом появлении. */
export function Term({ t, children }: { t: keyof typeof glossary | string; children?: ReactNode }) {
  const text = glossary[t] ?? "";
  return (
    <Tip text={text}>
      <span className="hint-term" tabIndex={0}>
        {children ?? t}
      </span>
    </Tip>
  );
}

export function HowCalculated({ children }: { children: ReactNode }) {
  return (
    <Tip text={children}>
      <button type="button" className="-my-[13px] inline-flex min-h-[44px] items-center gap-1 self-start text-caption text-ink3 hover:text-link" aria-label={ru.howCalculated}>
        <Info size={14} aria-hidden /> {ru.howCalculated}
      </button>
    </Tip>
  );
}

/* ---------------------------------------------------------------- плитка показателя */

export function Metric({
  label,
  value,
  unit,
  note,
  how,
  tone = "default",
  big = false,
  badge,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  note?: ReactNode;
  how?: ReactNode;
  tone?: "default" | "negative" | "positive" | "accent";
  big?: boolean;
  badge?: ReactNode;
}) {
  const color = tone === "negative" ? "var(--danger)" : tone === "positive" ? "var(--success)" : tone === "accent" ? "var(--primary)" : "var(--text)";
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex items-center gap-2 text-small text-ink2">
        <span>{label}</span>
        {badge}
      </div>
      <div className={`flex flex-wrap items-baseline gap-x-1 font-semibold ${big ? "text-[30px] leading-[38px] sm:text-display" : "text-[24px] leading-[32px] sm:text-[28px] sm:leading-[36px]"}`} style={{ color, letterSpacing: "-0.02em" }}>
        <span className="num">{value}</span>
        {unit && <span className="text-body font-normal tracking-normal text-ink2">{unit}</span>}
      </div>
      {note && <div className="text-caption text-ink3">{note}</div>}
      {how && <HowCalculated>{how}</HowCalculated>}
    </div>
  );
}

/* ---------------------------------------------------------------- карточка */

export function Card({
  title,
  lead,
  actions,
  children,
  className = "",
  id,
}: {
  title?: ReactNode;
  lead?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  const hid = useId();
  return (
    <section className={`card ${className}`} aria-labelledby={title ? hid : undefined} id={id}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 id={hid} className="text-h2">
                {title}
              </h2>
            )}
            {lead && <p className="mt-1 max-w-[72ch] text-small text-ink2">{lead}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/* ---------------------------------------------------------------- ползунок с вводом */

export function SliderField({
  label,
  value,
  onChange,
  min,
  max,
  step,
  scale = 1,
  digits = 1,
  unit,
  badge,
}: {
  label: ReactNode;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  /** отображаемое = value × scale (например, доля → проценты) */
  scale?: number;
  digits?: number;
  unit: string;
  badge?: ReactNode;
}) {
  const id = useId();
  const [text, setText] = useState(num(value * scale, digits));
  const [err, setErr] = useState<string | null>(null);
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setText(num(value * scale, digits));
  }, [value, scale, digits]);
  const commit = (s: string) => {
    const v = Number(s.replace(/\s| /g, "").replace(",", ".").replace("−", "-"));
    if (Number.isNaN(v)) {
      setErr("Введите число");
      return;
    }
    const raw = v / scale;
    if (raw < min || raw > max) {
      setErr(`От ${num(min * scale, digits)} до ${num(max * scale, digits)} ${unit}`);
      return;
    }
    setErr(null);
    onChange(raw);
  };
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={id} id={`${id}-label`} className="flex items-center gap-2 text-small font-medium">
          {label}
          {badge}
        </label>
        <div className="flex items-center gap-1">
          <input
            id={id}
            className="input num w-[92px] text-right"
            style={{ minHeight: 36 }}
            inputMode="decimal"
            value={text}
            aria-invalid={!!err}
            aria-describedby={err ? `${id}-err` : undefined}
            onFocus={() => (focused.current = true)}
            onChange={(e) => {
              setText(e.target.value);
              commit(e.target.value);
            }}
            onBlur={() => {
              focused.current = false;
              if (!err) setText(num(value * scale, digits));
            }}
          />
          <span className="w-12 text-caption text-ink2">{unit}</span>
        </div>
      </div>
      <RSlider.Root
        className="relative flex h-6 w-full touch-none select-none items-center"
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={(v) => {
          setErr(null);
          onChange(v[0]);
        }}
      >
        <RSlider.Track className="relative h-1 grow rounded-full" style={{ background: "var(--primary-soft-2)" }}>
          <RSlider.Range className="absolute h-full rounded-full" style={{ background: "var(--primary)" }} />
        </RSlider.Track>
        <RSlider.Thumb
          className="block h-5 w-5 rounded-full border-2 bg-surface"
          style={{ borderColor: "var(--primary)" }}
          aria-labelledby={`${id}-label`}
          aria-valuetext={`${num(value * scale, digits)} ${unit}`}
        />
      </RSlider.Root>
      {err && (
        <div id={`${id}-err`} className="text-caption text-danger" role="alert">
          {err}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- сегменты и переключатель */

export function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
  size = "md",
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode; title?: string }[];
  size?: "sm" | "md";
}) {
  return (
    <RToggle.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as T)}
      aria-label={label}
      className="inline-flex flex-wrap gap-1 rounded-control border border-line bg-sunken p-1"
    >
      {options.map((o) => (
        <RToggle.Item
          key={o.value}
          value={o.value}
          title={o.title}
          className={`rounded-[9px] px-3 font-medium text-ink2 transition-colors hover:text-ink data-[state=on]:bg-surface data-[state=on]:text-primary ${
            size === "sm" ? "min-h-[32px] text-caption" : "min-h-[36px] text-small"
          }`}
        >
          <span className="inline-flex items-center gap-1">
            {value === o.value && <Check size={14} aria-hidden />}
            {o.label}
          </span>
        </RToggle.Item>
      ))}
    </RToggle.Root>
  );
}

export function Switch({ label, checked, onChange, hint }: { label: ReactNode; checked: boolean; onChange: (v: boolean) => void; hint?: ReactNode }) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <RSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onChange}
        className="relative mt-0.5 h-6 w-10 shrink-0 rounded-full border transition-colors"
        style={{ background: checked ? "var(--primary)" : "var(--neutral-bg)", borderColor: checked ? "var(--primary)" : "var(--border-strong)" }}
      >
        <RSwitch.Thumb
          className="block h-[18px] w-[18px] translate-x-[2px] rounded-full transition-transform data-[state=checked]:translate-x-[18px]"
          style={{ background: checked ? "var(--on-primary)" : "var(--text-2)" }}
        />
      </RSwitch.Root>
      <label htmlFor={id} className="text-small">
        {label}
        {hint && <div className="text-caption text-ink3">{hint}</div>}
      </label>
    </div>
  );
}

/* ---------------------------------------------------------------- статусы */

type Tone = "neutral" | "success" | "warning" | "danger" | "process";
const STATUS_TONE: Record<string, Tone> = {
  DRAFT: "neutral",
  UPD_VERIFIED: "process",
  ACCEPTED: "process",
  OFFERED: "process",
  SOLD: "process",
  FUNDED: "success",
  REPAID: "success",
  REJECTED: "danger",
  EXPIRED: "neutral",
  OVERDUE: "warning",
  REGRESS: "danger",
  RECOVERED: "success",
  WRITTEN_OFF: "danger",
};

export function toneStyle(t: Tone) {
  switch (t) {
    case "success":
      return { color: "var(--success)", background: "var(--success-bg)" };
    case "warning":
      return { color: "var(--warning)", background: "var(--warning-bg)" };
    case "danger":
      return { color: "var(--danger)", background: "var(--danger-bg)" };
    case "process":
      return { color: "var(--primary)", background: "var(--primary-soft)" };
    default:
      return { color: "var(--neutral)", background: "var(--neutral-bg)" };
  }
}

function ToneIcon({ t }: { t: Tone }) {
  const p = { size: 13, "aria-hidden": true } as const;
  if (t === "success") return <CheckCircle2 {...p} />;
  if (t === "warning") return <AlertTriangle {...p} />;
  if (t === "danger") return <OctagonAlert {...p} />;
  if (t === "process") return <Clock3 {...p} />;
  return <CircleDashed {...p} />;
}

export function StatusChip({ status, label, review }: { status: string; label: string; review?: boolean }) {
  const t: Tone = review ? "warning" : (STATUS_TONE[status] ?? "neutral");
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 text-caption font-medium" style={{ ...toneStyle(t), minHeight: 24 }}>
      <ToneIcon t={t} />
      {review ? ru.feed.reviewFlag : label}
    </span>
  );
}

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 text-caption font-medium" style={{ ...toneStyle(tone), minHeight: 24 }}>
      <ToneIcon t={tone} />
      {children}
    </span>
  );
}

export function Callout({ tone, title, children }: { tone: Tone; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex gap-3 rounded-panel border p-3" style={{ ...toneStyle(tone), borderColor: "currentColor" }} role={tone === "danger" ? "alert" : "note"}>
      <span className="mt-0.5 shrink-0">
        <ToneIcon t={tone} />
      </span>
      <div className="min-w-0 text-small">
        <div className="font-semibold">{title}</div>
        {children && <div className="mt-0.5 text-ink">{children}</div>}
      </div>
    </div>
  );
}

/** Проверка: ок / нет / не применимо — всегда иконка + слово. */
export function CheckMark({ ok, label }: { ok: boolean | null | undefined; label: string }) {
  const t: Tone = ok === true ? "success" : ok === false ? "danger" : "neutral";
  const word = ok === true ? "да" : ok === false ? "нет" : "ещё нет";
  return (
    <span className="inline-flex items-center gap-1 text-caption" style={{ color: toneStyle(t).color }} title={`${label}: ${word}`}>
      {ok === true ? <Check size={14} aria-hidden /> : ok === false ? <ShieldX size={14} aria-hidden /> : <CircleDashed size={14} aria-hidden />}
      <span className="sr-only">
        {label}: {word}
      </span>
    </span>
  );
}

/* ---------------------------------------------------------------- линия с узлами */

export type RailStep = { key: string; label: ReactNode; state: "done" | "current" | "todo" | "error"; meta?: ReactNode };

export function Rail({ steps, label, vertical = false }: { steps: RailStep[]; label: string; vertical?: boolean }) {
  return (
    <ol aria-label={label} className={`relative flex ${vertical ? "flex-col gap-4" : "flex-row flex-wrap gap-y-4"}`}>
      {steps.map((s, i) => {
        const color =
          s.state === "error" ? "var(--danger)" : s.state === "todo" ? "var(--border-strong)" : "var(--primary)";
        const lineColor = steps[i + 1] && steps[i + 1].state !== "todo" ? "var(--primary)" : "var(--border)";
        return (
          <li
            key={s.key}
            aria-current={s.state === "current" ? "step" : undefined}
            className={`relative flex ${vertical ? "flex-row items-start gap-3" : "min-w-[96px] flex-1 flex-col gap-2"}`}
          >
            <div className={`flex items-center ${vertical ? "flex-col self-stretch" : "w-full"}`}>
              <span
                className="z-[1] block shrink-0 rounded-full"
                style={{
                  width: 14,
                  height: 14,
                  border: `2.5px solid ${color}`,
                  background: s.state === "done" || s.state === "error" ? color : "var(--surface)",
                  transition: "background var(--dur) var(--ease)",
                }}
                aria-hidden
              />
              {i < steps.length - 1 && (
                <span
                  aria-hidden
                  className={vertical ? "mt-1 w-[2px] grow" : "ml-1 h-[2px] grow"}
                  style={{ background: lineColor, minHeight: vertical ? 16 : undefined }}
                />
              )}
            </div>
            <div className={`text-caption ${vertical ? "" : "pr-2"}`}>
              <div className={`font-medium ${s.state === "todo" ? "text-ink3" : s.state === "error" ? "text-danger" : "text-ink"}`}>
                {s.label}
                <span className="sr-only">
                  {s.state === "done" ? " — пройдено" : s.state === "current" ? " — текущий этап" : s.state === "error" ? " — ошибка" : " — впереди"}
                </span>
              </div>
              {s.meta && <div className="text-ink3">{s.meta}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ---------------------------------------------------------------- состояния */

export function Skeleton({ h = 20, w = "100%", className = "" }: { h?: number; w?: number | string; className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} style={{ height: h, width: w }} />;
}

export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label={ru.loading}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} h={i === 0 ? 36 : 18} w={i === 0 ? "40%" : `${90 - i * 12}%`} />
      ))}
      <span className="sr-only">{ru.loading}</span>
    </div>
  );
}

export function EmptyState({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-panel border border-dashed border-line p-6 text-small text-ink2">
      <div>{title}</div>
      {action}
    </div>
  );
}

export function ErrorBox({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-panel border p-4 text-small" style={toneStyle("danger")} role="alert">
      <OctagonAlert size={16} aria-hidden />
      <span className="grow">{text}</span>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry}>
          <RotateCcw size={14} aria-hidden />
          {ru.retry}
        </button>
      )}
    </div>
  );
}

export function Spinner() {
  return <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden />;
}

/* ---------------------------------------------------------------- тосты */

type ToastT = { id: number; tone: "success" | "danger" | "warning"; text: string };
const ToastCtx = createContext<(tone: ToastT["tone"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastT[]>([]);
  const push = useCallback((tone: ToastT["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, tone, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 6000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(420px,calc(100vw-32px))] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.tone === "danger" ? "alert" : "status"}
            className="pointer-events-auto flex items-start gap-3 rounded-panel border bg-surface p-3 text-small"
            style={{ borderColor: toneStyle(t.tone).color, boxShadow: "0 6px 24px rgba(20,27,45,.14)" }}
          >
            <span style={{ color: toneStyle(t.tone).color }} className="mt-0.5">
              <ToneIcon t={t.tone} />
            </span>
            <span className="grow">{t.text}</span>
            <button className="text-ink3 hover:text-ink" onClick={() => setItems((x) => x.filter((y) => y.id !== t.id))} aria-label="Закрыть уведомление">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/* ---------------------------------------------------------------- диалог */

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-40" style={{ background: "rgba(11,18,34,.45)" }} />
        <RDialog.Content
          onKeyDown={(e) => {
            // Подсказка Radix внутри диалога может оставить свой слой и перехватывать Esc
            if (e.key === "Escape" && !document.querySelector("[role=tooltip]")) onOpenChange(false);
          }}
          className={`fixed inset-x-0 bottom-0 z-50 max-h-[92vh] overflow-y-auto rounded-t-card border border-line bg-surface p-5 md:inset-auto md:left-1/2 md:top-[5vh] md:-translate-x-1/2 md:rounded-card md:p-6 ${
            wide ? "md:w-[min(1080px,94vw)]" : "md:w-[min(560px,94vw)]"
          }`}
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RDialog.Title className="text-h2">{title}</RDialog.Title>
              {description ? (
                <RDialog.Description className="mt-1 text-small text-ink2">{description}</RDialog.Description>
              ) : (
                <RDialog.Description className="sr-only">{typeof title === "string" ? title : "Диалог"}</RDialog.Description>
              )}
            </div>
            <RDialog.Close className="btn btn-ghost btn-sm" aria-label="Закрыть">
              <X size={18} />
            </RDialog.Close>
          </div>
          {children}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}

/* ---------------------------------------------------------------- таблица данных под графиком */

export function DataTableToggle({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button className="btn btn-ghost btn-sm" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? ru.hideTable : ru.dataTable}
      </button>
      {open && (
        <div className="mt-2 max-h-80 overflow-auto rounded-panel border border-line" tabIndex={0}>
          <table className="data-table dense">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr>
                {head.map((h, i) => (
                  <th key={h} scope="col" className={i ? "r" : ""}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j} className={j ? "r num" : ""}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
