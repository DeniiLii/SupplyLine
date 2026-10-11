import { useEffect, useState } from "react";
import { ru } from "../copy/ru";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: Record<string, unknown>,
  ) {
    super(typeof body.message === "string" ? body.message : `Ошибка ${status}`);
  }
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(path, {
      ...rest,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, { message: ru.errors.network });
  }
  if (!res.ok) {
    let body: Record<string, unknown> = {};
    try {
      body = await res.json();
    } catch {
      /* пустое тело */
    }
    if (typeof body.detail === "string" && !body.message) body.message = body.detail;
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}

/** Текст ошибки для пользователя: что случилось, почему и что сделать. */
export function errorText(e: unknown): string {
  if (!(e instanceof ApiError)) return ru.errors.generic;
  if (e.status === 0) return ru.errors.network;
  if (e.status === 409 && e.body.claim_key) return ru.errors.duplicate;
  if (e.status === 422 && typeof e.body.rule === "string") return ru.errors.limit(e.body.rule);
  if (e.status === 503) return ru.errors.payment;
  if (e.status === 422 && e.body.code === "validation") return ru.errors.validation;
  return e.message || ru.errors.generic;
}

/** Значение с задержкой: для ползунков (150 мс). */
export function useDebounced<T>(value: T, ms = 150): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
