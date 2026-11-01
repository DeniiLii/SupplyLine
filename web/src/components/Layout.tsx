import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Menu, Monitor, Moon, RotateCcw, Sun, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { dateTime } from "../api/format";
import { ru } from "../copy/ru";
import { useTheme } from "./theme";
import { TourButton } from "./Tour";
import { Dialog, Spinner, Tip, useToast } from "./ui";

export type Role = "supplier" | "anchor" | "investor" | "organizer";

export const ROLE_MENU: Record<Role, { to: string; label: string }[]> = {
  supplier: [
    { to: "/supplier", label: ru.nav.supplier },
    { to: "/feed", label: ru.nav.feed },
    { to: "/simulator", label: ru.nav.simulator },
  ],
  anchor: [
    { to: "/anchor", label: ru.nav.anchor },
    { to: "/feed", label: ru.nav.feed },
  ],
  investor: [
    { to: "/investor", label: ru.nav.investor },
    { to: "/model", label: ru.nav.model },
  ],
  organizer: [
    { to: "/simulator", label: ru.nav.simulator },
    { to: "/feed", label: ru.nav.feed },
    { to: "/overview", label: ru.nav.overview },
    { to: "/model", label: ru.nav.model },
  ],
};
const COMMON = [
  { to: "/market", label: ru.nav.market },
  { to: "/about", label: ru.nav.about },
];

function roleFor(path: string, current: Role): Role {
  if (ROLE_MENU[current].some((m) => path.startsWith(m.to))) return current;
  const found = (Object.keys(ROLE_MENU) as Role[]).find((r) => ROLE_MENU[r].some((m) => path.startsWith(m.to)));
  return found ?? current;
}

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2" aria-label="SupplyLine">
      <svg width="34" height="14" viewBox="0 0 34 14" aria-hidden>
        <path d="M1 7h32" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="10" cy="7" r="5" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2.5" />
      </svg>
      <span className="text-[18px] font-semibold tracking-[-0.01em] text-ink">SupplyLine</span>
    </span>
  );
}

type State = { now: string; scenario: string };

function Clock() {
  const qc = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const st = useQuery({ queryKey: ["state"], queryFn: () => api<State>("/api/state") });
  const adv = useMutation({
    mutationFn: (days: number) => api<{ transitions: number }>("/api/clock/advance", { method: "POST", json: { days } }),
    onSuccess: (r) => {
      qc.invalidateQueries();
      toast("success", ru.clock.moved(r.transitions));
    },
    onError: (e) => toast("danger", errorText(e)),
  });
  const reset = useMutation({
    mutationFn: () => api("/api/demo/reset", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries();
      setConfirm(false);
      toast("success", ru.clock.resetDone);
    },
    onError: (e) => toast("danger", errorText(e)),
  });
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label={ru.clock.label}>
      <Tip text={ru.clock.hint}>
        <span className="inline-flex items-center gap-2 text-small" tabIndex={0}>
          <CalendarClock size={16} className="text-ink2" aria-hidden />
          <span className="text-ink2">{ru.clock.label}</span>
          <span className="num font-semibold" aria-live="polite">
            {st.data ? dateTime(st.data.now) : "…"}
          </span>
        </span>
      </Tip>
      <div className="flex gap-1">
        {[1, 7, 30].map((d) => (
          <button key={d} className="btn btn-secondary btn-sm" disabled={adv.isPending} onClick={() => adv.mutate(d)}>
            {adv.isPending && adv.variables === d ? <Spinner /> : null}
            {d === 1 ? ru.clock.plus1 : d === 7 ? ru.clock.plus7 : ru.clock.plus30}
          </button>
        ))}
        <button className="btn btn-ghost btn-sm debug-only" onClick={() => setConfirm(true)} aria-label={ru.clock.reset} title={ru.clock.reset}>
          <RotateCcw size={16} aria-hidden />
        </button>
      </div>
      <Dialog open={confirm} onOpenChange={setConfirm} title={ru.clock.resetConfirmTitle} description={ru.clock.resetConfirmText}>
        <div className="flex flex-wrap justify-end gap-2">
          <button className="btn btn-secondary" onClick={() => setConfirm(false)}>
            {ru.clock.resetKeep}
          </button>
          <button className="btn btn-danger" disabled={reset.isPending} onClick={() => reset.mutate()}>
            {reset.isPending && <Spinner />}
            {ru.clock.reset}
          </button>
        </div>
      </Dialog>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const nav = useNavigate();
  const { theme, setTheme, presentation, setPresentation } = useTheme();
  const [role, setRole] = useState<Role>(() => {
    try {
      return (localStorage.getItem("sl-role") as Role) || "organizer";
    } catch {
      return "organizer";
    }
  });
  const [open, setOpen] = useState(false);
  const effective = roleFor(loc.pathname, role);
  useEffect(() => {
    if (effective !== role) setRole(effective);
  }, [effective, role]);
  useEffect(() => {
    try {
      localStorage.setItem("sl-role", role);
    } catch {
      /* нет хранилища */
    }
  }, [role]);
  useEffect(() => setOpen(false), [loc.pathname]);

  const changeRole = (r: Role) => {
    setRole(r);
    nav(ROLE_MENU[r][0].to);
  };
  const links = [...ROLE_MENU[role], ...COMMON];

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2">
        Перейти к содержимому
      </a>
      <div role="note" className="border-b border-line text-caption" style={{ background: "var(--warning-bg)", color: "var(--warning)" }}>
        <div className="container-page py-1.5">{ru.demoBanner}</div>
      </div>
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="container-page flex min-h-[64px] flex-wrap items-center gap-x-6 gap-y-2 py-2">
          <NavLink to="/" className="shrink-0 rounded-control" aria-label="SupplyLine, на главную">
            <Wordmark />
          </NavLink>
          <div className="flex items-center gap-2">
            <label htmlFor="role" className="text-small text-ink2">
              {ru.roleSwitch}
            </label>
            <select
              id="role"
              className="input w-auto py-0 font-medium"
              style={{ minHeight: 40 }}
              value={role}
              onChange={(e) => changeRole(e.target.value as Role)}
            >
              {(Object.keys(ru.roles) as Role[]).map((r) => (
                <option key={r} value={r}>
                  {ru.roles[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="ml-auto hidden items-center gap-3 lg:flex">
            <TourButton />
            <Clock />
          </div>
          <div className="flex items-center gap-1 lg:ml-0 ml-auto">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={theme === "light" ? ru.theme.dark : ru.theme.light}
              title={theme === "light" ? ru.theme.dark : ru.theme.light}
            >
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <button
              className="btn btn-ghost btn-sm"
              aria-pressed={presentation}
              onClick={() => setPresentation(!presentation)}
              aria-label={ru.presentation}
              title={ru.presentation}
            >
              <Monitor size={18} />
            </button>
            <button className="btn btn-ghost btn-sm md:hidden" aria-expanded={open} aria-controls="role-nav" onClick={() => setOpen(!open)} aria-label="Меню">
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        <nav id="role-nav" aria-label={`Меню роли «${ru.roles[role]}»`} className={`${open ? "block" : "hidden"} border-t border-line md:block`}>
          <ul className="container-page flex flex-col gap-1 py-2 md:flex-row md:flex-wrap md:gap-1 md:py-0">
            {links.map((l, i) => (
              <li key={l.to} className={i === ROLE_MENU[role].length ? "md:ml-auto" : ""}>
                <NavLink
                  to={l.to}
                  className={({ isActive }) =>
                    `flex min-h-[44px] items-center border-b-2 px-3 text-small font-medium transition-colors ${
                      isActive ? "border-primary text-primary" : "border-transparent text-ink2 hover:text-ink"
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="container-page flex flex-wrap items-center gap-3 border-t border-line py-2 lg:hidden">
          <Clock />
          <TourButton />
        </div>
      </header>
      <main id="main" className="container-page py-6 md:py-8">
        {children}
      </main>
      <footer className="container-page pb-10 text-caption text-ink3">
        {ru.demoBanner} Все компании вымышлены. Параметры с бейджем «Гипотеза» — допущения автора.
      </footer>
    </div>
  );
}

export function PageHead({ title, lead, right }: { title: string; lead?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-h1">{title}</h1>
        {lead && <p className="mt-2 max-w-[78ch] text-body text-ink2">{lead}</p>}
      </div>
      {right}
    </div>
  );
}
