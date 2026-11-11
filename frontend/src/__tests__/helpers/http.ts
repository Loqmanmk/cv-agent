import type { Mock } from "vitest";

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function sentBody(fetchMock: Mock, path: string): unknown {
  const call = fetchMock.mock.calls.find(([url]) => (url as string).endsWith(path)) as
    [string, RequestInit] | undefined;
  return call ? JSON.parse(call[1].body as string) : undefined;
}
