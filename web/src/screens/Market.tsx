import { useQuery } from "@tanstack/react-query";
import { CircleDashed } from "lucide-react";
import { api, errorText } from "../api/client";
import { PageHead } from "../components/Layout";
import { Card, Chip, ErrorBox, Loading } from "../components/ui";
import { ru } from "../copy/ru";

export type Meta = {
  disclaimer: string;
  facts: { name: string; value: string; date: string; source: string; url: string; status: string; used_in: string; note?: string }[];
  checklist: { item: string; done: boolean }[];
  layers: { n: number; name: string; items: string[]; state: string }[];
  roadmap: { phase: string; period: string; scope: string; gate: string }[];
  reality: { what: string; kind: string; note: string }[];
  facts_as_of: string;
};

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/api/meta"), staleTime: Infinity });

const STATUS_TONE: Record<string, "success" | "warning" | "danger"> = { "Подтверждено": "success", "Неточно": "warning", "Не подтверждено": "danger", "Опровергнут": "danger" };

export default function Market() {
  const m = useMeta();
  return (
    <>
      <PageHead title={ru.market.title} lead={ru.market.lead} />
      {m.isError && <ErrorBox text={errorText(m.error)} onRetry={() => m.refetch()} />}
      {!m.data ? <Card><Loading rows={8} /></Card> : (
        <div className="grid gap-6 xl:grid-cols-12">
          <Card className="xl:col-span-8" title="Факты" lead={`Данные на ${m.data.facts_as_of}. «Неточно» — есть только пересказ или диапазон; «Не подтверждено» — первоисточник не найден.`}>
            <div className="hidden overflow-x-auto md:block" tabIndex={0}>
              <table className="data-table">
                <caption className="sr-only">Факты рынка</caption>
                <thead><tr>{Object.values(ru.market.columns).map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
                <tbody>
                  {m.data.facts.map((f) => (
                    <tr key={f.name}>
                      <td className="font-medium">{f.name}<div className="text-caption font-normal text-ink3">{f.used_in}</div></td>
                      <td>{f.value}{f.note && <div className="text-caption text-ink3">{f.note}</div>}</td>
                      <td className="text-small text-ink2">{f.date}</td>
                      <td className="text-small">{f.url ? <a href={f.url} target="_blank" rel="noreferrer noopener">{f.source}</a> : f.source}</td>
                      <td><Chip tone={STATUS_TONE[f.status] ?? "warning"}>{f.status}</Chip></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="flex flex-col gap-2 md:hidden">
              {m.data.facts.map((f) => (
                <li key={f.name} className="panel flex flex-col gap-1 text-small">
                  <div className="flex items-start justify-between gap-2"><span className="font-medium">{f.name}</span><Chip tone={STATUS_TONE[f.status] ?? "warning"}>{f.status}</Chip></div>
                  <div>{f.value}</div>
                  <div className="text-caption text-ink3">{f.date} · {f.source}</div>
                </li>
              ))}
            </ul>
          </Card>
          <div className="flex flex-col gap-6 xl:col-span-4">
            <Card title={ru.market.checklist}>
              <ul className="flex flex-col gap-3 text-small">
                {m.data.checklist.map((c) => (
                  <li key={c.item} className="flex gap-2"><CircleDashed size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden /><span>{c.item}<span className="sr-only"> — не проверено</span></span></li>
                ))}
              </ul>
            </Card>
            <Card title="Как читать статусы и бейджи">
              <dl className="flex flex-col gap-3 text-small">
                <div><dt className="font-medium">Подтверждено · Неточно · Не подтверждено · Опровергнут</dt><dd className="text-ink2">Статус проверки в таблице фактов: первоисточник открыт; есть только пересказ или диапазон; источник не найден; тезис оказался неверным.</dd></div>
                <div><dt className="font-medium">Факт</dt><dd className="text-ink2">Число из открытого источника с датой. Источник — в подсказке бейджа.</dd></div>
                <div><dt className="font-medium">Гипотеза</dt><dd className="text-ink2">Допущение автора. Его можно двигать в симуляторе и модели; проверяется интервью и письмами о намерениях.</dd></div>
                <div><dt className="font-medium">Факт и гипотеза</dt><dd className="text-ink2">Ориентир взят из факта, но перенесён на нашу схему с допущением (например, премия ЦФА к ключевой).</dd></div>
              </dl>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
