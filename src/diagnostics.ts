import { AuthError } from "@azure/msal-browser";
import { DemoError, type DemoConfig } from "./config";
import pkg from "../package.json";

export const requiredScopes = ["Report.Read.All", "MLModel.Execute.All"] as const;
export const powerBiResource = "https://analysis.windows.net/powerbi/api";
export const scopes = requiredScopes.map((scope) => `${powerBiResource}/${scope}`);

export type Phase = "configuration" | "sign-in" | "sign-out" | "token" | "metadata" | "embed" | "loaded" | "rendered" | "error" | "refresh";
export interface ErrorDetails {
  code?: string;
  httpStatus?: number;
  requestId?: string;
  activityId?: string;
  correlationId?: string;
}
interface Entry extends ErrorDetails {
  at: string;
  phase: Phase;
  outcome: "ok" | "error" | "start";
  copilot: boolean;
}
export interface TokenSummary {
  grantedRequiredScopes: string[];
  missingRequiredScopes: string[];
  expiresAt: string | null;
  audienceCheck: "match" | "mismatch" | "unavailable";
  tenantCheck: "match" | "mismatch" | "unavailable";
}

export function safeCode(value: unknown): string | undefined {
  return typeof value === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(value) ? value : undefined;
}

export function safeId(value: unknown): string | undefined {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value : undefined;
}

export function summarizeToken(accessToken: string, grantedScopes: string[], expiresOn: Date | null, tenantId: string): TokenSummary {
  const normalized = grantedScopes.map((scope) => scope.substring(scope.lastIndexOf("/") + 1).toLowerCase());
  const summary: TokenSummary = {
    grantedRequiredScopes: requiredScopes.filter((scope) => normalized.includes(scope.toLowerCase())),
    missingRequiredScopes: requiredScopes.filter((scope) => !normalized.includes(scope.toLowerCase())),
    expiresAt: expiresOn && Number.isFinite(expiresOn.getTime()) ? expiresOn.toISOString() : null,
    audienceCheck: "unavailable",
    tenantCheck: "unavailable",
  };
  // Access tokens may be opaque. Claim inspection is diagnostic only, not validation.
  const payload = accessToken.split(".")[1];
  if (!payload) return summary;
  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims: unknown = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")));
    if (claims && typeof claims === "object") {
      if ("aud" in claims && typeof claims.aud === "string") {
        summary.audienceCheck = [powerBiResource, "00000009-0000-0000-c000-000000000000"].includes(claims.aud.replace(/\/$/, "")) ? "match" : "mismatch";
      }
      if ("tid" in claims && typeof claims.tid === "string") {
        summary.tenantCheck = claims.tid.toLowerCase() === tenantId.toLowerCase() ? "match" : "mismatch";
      }
    }
  } catch {
    // Opaque or undecodable claims are explicitly reported as unavailable.
  }
  return summary;
}

export function describeError(error: unknown): { message: string; details: ErrorDetails } {
  if (error instanceof DemoError) return { message: error.message, details: { code: safeCode(error.code) } };
  if (error instanceof AuthError) {
    return {
      message: "Microsoft sign-in/token acquisition failed. Check the error code, Entra sign-in logs, redirect URI, delegated permissions and consent; then sign in again.",
      details: { code: safeCode(error.errorCode), correlationId: safeId(error.correlationId) },
    };
  }
  if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) {
    return { message: "The request timed out or was cancelled. Check connectivity and retry.", details: { code: error.name } };
  }
  return { message: "An operation failed. Check browser DevTools and the setup/troubleshooting guide; no raw error payload is exported.", details: { code: "unexpected_error" } };
}

export class Diagnostics {
  private events: Entry[] = [];
  private config?: DemoConfig;
  private token?: TokenSummary;
  copilot = true;
  onChange: () => void = () => {};

  setConfig(config: DemoConfig): void {
    this.config = { tenantId: config.tenantId, clientId: config.clientId, workspaceId: config.workspaceId, reportId: config.reportId };
    this.onChange();
  }

  setToken(summary?: TokenSummary): void {
    this.token = summary;
    this.onChange();
  }

  record(phase: Phase, outcome: Entry["outcome"], details: ErrorDetails = {}): void {
    this.events.push({
      at: new Date().toISOString(), phase, outcome, copilot: this.copilot,
      code: safeCode(details.code),
      httpStatus: Number.isInteger(details.httpStatus) && details.httpStatus! >= 100 && details.httpStatus! <= 599 ? details.httpStatus : undefined,
      requestId: safeId(details.requestId), activityId: safeId(details.activityId), correlationId: safeId(details.correlationId),
    });
    this.events = this.events.slice(-200);
    this.onChange();
  }

  snapshot(): string {
    return JSON.stringify({
      schemaVersion: 1, exportedAt: new Date().toISOString(),
      appVersion: pkg.version,
      libraries: pkg.dependencies,
      configuration: this.config, copilot: this.copilot,
      token: this.token, events: this.events,
      notice: "Claims are diagnostic, not validated. IDs are organizational metadata. SDK rendered does not verify Copilot. Cross-origin iframe requests are not captured.",
    }, null, 2);
  }
}
