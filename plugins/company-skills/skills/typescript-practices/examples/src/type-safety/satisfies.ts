type Endpoint = { url: string } | { socket: string };

const endpoints = {
  api: { url: "https://api.example.com" },
  worker: { socket: "/run/worker.sock" },
} satisfies Record<string, Endpoint>;

export function apiUrl(): string {
  // Under a Record<string, Endpoint> annotation, this would not compile.
  return endpoints.api.url;
}
