const defaultBackendOrigin = "http://127.0.0.1:8000";
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? "3000";

export const backendOrigin =
  process.env.STRATEGY_STUDIO_API_ORIGIN ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  defaultBackendOrigin;

export const frontendOrigin = `http://127.0.0.1:${frontendPort}`;

export function frontendApiUrl(path: string): string {
  return `${frontendOrigin}${path}`;
}

export function backendApiUrl(path: string): string {
  return `${backendOrigin}${path}`;
}
