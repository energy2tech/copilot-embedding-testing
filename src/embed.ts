import { factories, models, Report, service } from "powerbi-client";
import { UserAuth } from "./auth";
import { DemoError, type DemoConfig } from "./config";
import { Diagnostics, describeError } from "./diagnostics";

export function copilotEmbedUrl(embedUrl: string, enabled: boolean): string {
  const url = new URL(embedUrl);
  if (url.origin !== "https://app.powerbi.com" || url.pathname !== "/reportEmbed") {
    throw new DemoError("Expected a commercial-cloud Power BI report embed URL from the metadata API.", "invalid_embed_url");
  }
  url.searchParams.delete("reportCopilotInEmbed");
  if (enabled) url.searchParams.set("reportCopilotInEmbed", "true");
  return url.toString();
}

export async function getReportUrl(config: DemoConfig, accessToken: string, diagnostics: Diagnostics): Promise<string> {
  diagnostics.record("metadata", "start");
  const response = await fetch(`https://api.powerbi.com/v1.0/myorg/groups/${config.workspaceId}/reports/${config.reportId}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    diagnostics.record("metadata", "error", {
      httpStatus: response.status, code: "report_metadata_failed",
      requestId: response.headers.get("requestid") ?? undefined,
      activityId: response.headers.get("activityid") ?? undefined,
      correlationId: response.headers.get("x-ms-correlation-request-id") ?? undefined,
    });
    throw new DemoError(`Power BI report metadata returned HTTP ${response.status}. Check the Power BI token, Report.Read.All consent and user access to this workspace/report.`, "report_metadata_failed");
  }
  const body: unknown = await response.json();
  if (!body || typeof body !== "object" || !("embedUrl" in body) || typeof body.embedUrl !== "string") {
    throw new DemoError("Power BI did not return an embed URL for this report.", "missing_embed_url");
  }
  copilotEmbedUrl(body.embedUrl, true);
  diagnostics.record("metadata", "ok");
  return body.embedUrl;
}

export class ReportEmbed {
  private readonly sdk = new service.Service(factories.hpmFactory, factories.wpmpFactory, factories.routerFactory);
  private report?: Report;
  private generation = 0;

  constructor(
    private readonly container: HTMLElement,
    private readonly diagnostics: Diagnostics,
    private readonly status: (message: string, error?: boolean) => void,
  ) {}

  reset(): void {
    this.generation++;
    if (this.report) {
      for (const event of ["loaded", "rendered", "error"]) this.report.off(event);
      this.sdk.reset(this.container);
      this.report = undefined;
    }
  }

  load(config: DemoConfig, embedUrl: string, accessToken: string, copilot: boolean, auth: UserAuth): void {
    this.reset();
    const generation = this.generation;
    const current = () => generation === this.generation;
    let failed = false;
    const embedConfig: models.IReportEmbedConfiguration = {
      type: "report", id: config.reportId,
      embedUrl: copilotEmbedUrl(embedUrl, copilot),
      tokenType: models.TokenType.Aad, accessToken,
      viewMode: models.ViewMode.View,
      settings: {
        bars: { actionBar: { visible: true } },
        persistentFiltersEnabled: false,
        personalBookmarksEnabled: false,
      },
      eventHooks: {
        accessTokenProvider: async () => {
          if (!current()) return null;
          this.diagnostics.record("refresh", "start");
          try {
            const token = await auth.getToken(true);
            if (!current()) return null;
            this.diagnostics.record("refresh", "ok");
            return token;
          } catch (error) {
            if (current()) {
              const problem = describeError(error);
              failed = true;
              this.diagnostics.record("refresh", "error", problem.details);
              this.status(problem.message, true);
            }
            // The SDK contract requires null, not a thrown exception, on refresh failure.
            return null;
          }
        },
      },
    };
    this.diagnostics.record("embed", "start");
    const embedded = this.sdk.embed(this.container, embedConfig);
    if (!(embedded instanceof Report)) {
      this.sdk.reset(this.container);
      throw new DemoError("The SDK did not create a report instance.", "invalid_report_instance");
    }
    this.report = embedded;
    embedded.on("loaded", () => {
      if (!current()) return;
      this.diagnostics.record("loaded", "ok");
      if (failed) return;
      this.status(`Report loaded; Copilot requested ${copilot ? "on" : "off"}. Waiting for rendering.`);
    });
    embedded.on("rendered", () => {
      if (!current()) return;
      this.diagnostics.record("rendered", "ok");
      if (failed) return;
      this.status(`Report rendered; Copilot requested ${copilot ? "on" : "off"}. ${copilot ? "Open the native Copilot button and submit a prompt to verify." : "Verify the native Copilot button is absent."}`);
    });
    embedded.on("error", (event?: { detail?: models.IError }) => {
      if (!current()) return;
      failed = true;
      this.diagnostics.record("error", "error", {
        code: event?.detail?.errorCode,
        requestId: event?.detail?.technicalDetails?.requestId,
      });
      this.status("Power BI reported an embed error. Check diagnostic codes and DevTools for the failing request. SDK errors may not expose Copilot failures.", true);
    });
  }
}
