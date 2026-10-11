import { errorText } from "../api/client";
import { PageHead } from "../components/Layout";
import { Card, Chip, ErrorBox, Loading, Rail } from "../components/ui";
import { ru } from "../copy/ru";
import { useMeta } from "./Market";

const KIND_TONE: Record<string, "success" | "process" | "warning" | "neutral" | "danger"> = {
  "Работает": "success", "Мок": "process", "Синтетика": "neutral", "Гипотеза": "warning", "Факт": "success", "Нет": "danger",
};

export default function About() {
  const m = useMeta();
  return (
    <>
      <PageHead title={ru.about.title} lead="Что это за прототип, из каких слоёв состоит платформа и через какие ворота она должна пройти, прежде чем станет больше, чем демо." />
      {m.isError && <ErrorBox text={errorText(m.error)} onRetry={() => m.refetch()} />}
      {!m.data ? <Card><Loading rows={6} /></Card> : (
        <div className="flex flex-col gap-6">
          <Card title={ru.about.reality}>
            <div className="overflow-x-auto" tabIndex={0}>
              <table className="data-table">
                <thead><tr><th scope="col">Что</th><th scope="col">Статус</th><th scope="col">Комментарий</th></tr></thead>
                <tbody>{m.data.reality.map((r) => <tr key={r.what}><td>{r.what}</td><td><Chip tone={KIND_TONE[r.kind] ?? "neutral"}>{r.kind}</Chip></td><td className="text-ink2">{r.note}</td></tr>)}</tbody>
              </table>
            </div>
          </Card>

          <Card title={ru.about.layers} lead="Слой 7 «Риск и комплаенс» действует на всех остальных.">
            <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
              <ol className="flex flex-col gap-2">
                {m.data.layers.filter((l) => l.n < 7).reverse().map((l) => (
                  <li key={l.n} className="panel flex flex-wrap items-center gap-x-4 gap-y-1">
                    <span className="num w-6 text-h2 text-primary">{l.n}</span>
                    <span className="min-w-[200px] font-semibold">{l.name}</span>
                    <span className="grow text-small text-ink2">{l.items.join(", ")}</span>
                    <Chip tone={l.state === "работает" || l.state === "работает на моках" ? "success" : l.state === "мок" ? "process" : "warning"}>{l.state}</Chip>
                  </li>
                ))}
              </ol>
              {m.data.layers.filter((l) => l.n === 7).map((l) => (
                <div key={l.n} className="flex items-center rounded-panel border-2 border-dashed p-4 lg:w-56" style={{ borderColor: "var(--primary)" }}>
                  <div>
                    <div className="num text-h2 text-primary">7</div>
                    <div className="font-semibold">{l.name}</div>
                    <div className="text-small text-ink2">{l.items.join(", ")}</div>
                    <div className="mt-2"><Chip tone="process">{l.state}</Chip></div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card title={ru.about.roadmap} lead="Переход к следующей фазе — только после прохождения ворот. Метрики ворот 1 считаются на экране «Обзор платформы».">
            <Rail label={ru.about.roadmap} vertical steps={m.data.roadmap.map((r, i) => ({
              key: r.phase, state: i === 0 ? "current" : "todo",
              label: <span className="text-small">{r.phase} · {r.period}</span>,
              meta: <span className="text-small"><span className="text-ink">{r.scope}</span><br /><span className="text-ink2">{r.gate}</span></span>,
            }))} />
          </Card>

          <Card title="Схема сделки">
            <Rail label="Схема сделки" steps={[
              { key: "1", state: "done", label: "Онбординг", meta: "якорь приглашает поставщика, ЭДО, лимит" },
              { key: "2", state: "done", label: "УПД и акцепт", meta: "поставщик отгружает, якорь акцептует" },
              { key: "3", state: "done", label: "Предложение", meta: "цена по формуле, без ручных согласований" },
              { key: "4", state: "done", label: "Уступка и деньги", meta: "в течение суток" },
              { key: "5", state: "done", label: "Оплата якоря", meta: "напрямую финансирующей стороне, сверка" },
              { key: "6", state: "error", label: "Просрочка", meta: "напоминания, регресс, взыскание" },
            ]} />
            <p className="mt-4 max-w-[78ch] text-small text-ink2">
              Юридическое уточнение: в типовой конструкции ЦФА под дебиторку инвестор получает требование к эмитенту (фактору или SPV), а не к якорю.
              Риск якоря доходит до инвестора только через обеспечение или страхование. В прототипе эмитент модельный, доля страхового покрытия задаётся параметром.
            </p>
          </Card>
        </div>
      )}
    </>
  );
}
