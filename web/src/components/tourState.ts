import { useSyncExternalStore } from "react";

/** Открыт ли тур. Пока открыт, карточки-диалоги не модальные: панель тура остаётся доступной. */
let open = false;
const listeners = new Set<() => void>();

export function setTourOpen(v: boolean) {
  open = v;
  listeners.forEach((l) => l());
}

export function useTourOpen(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => open,
  );
}
