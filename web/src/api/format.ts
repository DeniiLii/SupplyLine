// Форматирование чисел ru-RU: неразрывный пробел для тысяч, запятая, ₽, «млн», «млрд».
const NB = " ";

const nf = (min: number, max: number) =>
  new Intl.NumberFormat("ru-RU", { minimumFractionDigits: min, maximumFractionDigits: max });

export function num(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return nf(digits, digits).format(x).replace(/ /g, NB).replace("-", "−");
}

export function rub(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined) return "—";
  return `${num(x, digits)}${NB}₽`;
}

/** Рубли в млн с подписью единицы. */
export function mln(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return "—";
  return `${num(x / 1e6, digits)}${NB}млн${NB}₽`;
}

/** Величина уже в ₽ млн (финмодель). */
export function mlnM(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return "—";
  return `${num(x, digits)}${NB}млн${NB}₽`;
}

export function bln(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return "—";
  return `${num(x / 1e9, digits)}${NB}млрд${NB}₽`;
}

export function pct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined) return "—";
  return `${num(x * 100, digits)}%`;
}

export function pp(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined) return "—";
  return `${num(x * 100, digits)}${NB}п.п.`;
}

export function signed(s: string, x: number): string {
  return x > 0 ? `+${s}` : s;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })} ${d.toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function days(n: number): string {
  const m10 = n % 10;
  const m100 = n % 100;
  const w = m10 === 1 && m100 !== 11 ? "день" : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? "дня" : "дней";
  return `${n}${NB}${w}`;
}
