type HttpOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

export class HttpError extends Error {
  constructor(public response: Response) {
    super(`HTTP ${response.status}`);
    this.name = "HttpError";
  }
}

export const isHttpStatus = (err: unknown, code: number): boolean =>
  err instanceof HttpError && err.response.status === code;

export async function http<T>(url: string, options: HttpOptions = {}): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: options.body ? { "content-type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  };
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new HttpError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
