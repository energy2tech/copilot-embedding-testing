export interface DemoConfig {
  tenantId: string;
  clientId: string;
  workspaceId: string;
  reportId: string;
}

export class DemoError extends Error {
  constructor(message: string, readonly code: string) {
    super(message);
    this.name = "DemoError";
  }
}

const fields = ["tenantId", "clientId", "workspaceId", "reportId"] as const;
const guid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseConfig(value: unknown): DemoConfig {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new DemoError("Configuration must be a JSON object.", "invalid_config");
  }
  const record: Record<string, unknown> = Object.fromEntries(Object.entries(value));
  if (Object.keys(record).some((key) => !fields.some((field) => field === key))) {
    throw new DemoError("Configuration accepts only tenantId, clientId, workspaceId, and reportId. Never add secrets.", "invalid_config");
  }
  for (const field of fields) {
    if (typeof record[field] !== "string" || !guid.test(record[field]) || /^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(record[field])) {
      throw new DemoError(`Set ${field} to a nonzero GUID in public/config.local.json.`, "invalid_config");
    }
  }
  return {
    tenantId: String(record.tenantId).toLowerCase(),
    clientId: String(record.clientId).toLowerCase(),
    workspaceId: String(record.workspaceId).toLowerCase(),
    reportId: String(record.reportId).toLowerCase(),
  };
}

export async function loadConfig(): Promise<DemoConfig> {
  if (window.location.origin !== "http://localhost:5173") {
    throw new DemoError("Open http://localhost:5173 so the origin matches the registered SPA redirect URI.", "invalid_origin");
  }
  const response = await fetch("/config.local.json", { cache: "no-store", signal: AbortSignal.timeout(30_000) });
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
    throw new DemoError("Copy public/config.example.json to public/config.local.json and fill in the four IDs, then refresh.", "missing_config");
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new DemoError("public/config.local.json is not valid JSON.", "invalid_config");
  }
  return parseConfig(value);
}
