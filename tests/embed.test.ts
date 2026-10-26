import { beforeEach, describe, expect, it, vi } from "vitest";
import { UserAuth } from "../src/auth";
import { Diagnostics } from "../src/diagnostics";
import { copilotEmbedUrl, getReportUrl, ReportEmbed } from "../src/embed";

const sdk = vi.hoisted(() => ({
  configs: [] as unknown[], instances: [] as { on: ReturnType<typeof vi.fn>; off: ReturnType<typeof vi.fn> }[],
  reset: vi.fn(),
}));
vi.mock("powerbi-client", () => {
  class Report {
    on = vi.fn();
    off = vi.fn();
  }
  return {
    Report,
    factories: {},
    models: { TokenType: { Aad: 0 }, ViewMode: { View: 0 } },
    service: { Service: class {
      embed(_container: unknown, config: unknown) {
        sdk.configs.push(config);
        const report = new Report();
        sdk.instances.push(report);
        return report;
      }
      reset = sdk.reset;
    } },
  };
});

const config = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  clientId: "22222222-2222-4222-8222-222222222222",
  workspaceId: "33333333-3333-4333-8333-333333333333",
  reportId: "44444444-4444-4444-8444-444444444444",
};
const baseUrl = `https://app.powerbi.com/reportEmbed?reportId=${config.reportId}&groupId=${config.workspaceId}&custom=a%20b`;

beforeEach(() => {
  sdk.configs.length = 0;
  sdk.instances.length = 0;
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("Copilot URL opt-in", () => {
  it("sets exactly one on parameter and preserves other query values", () => {
    const url = new URL(copilotEmbedUrl(`${baseUrl}&reportCopilotInEmbed=false&reportCopilotInEmbed=true`, true));
    expect(url.searchParams.getAll("reportCopilotInEmbed")).toEqual(["true"]);
    expect(url.searchParams.get("custom")).toBe("a b");
    expect(url.searchParams.get("groupId")).toBe(config.workspaceId);
  });
  it("removes the opt-in for off mode", () => {
    const url = new URL(copilotEmbedUrl(`${baseUrl}&reportCopilotInEmbed=true`, false));
    expect(url.searchParams.has("reportCopilotInEmbed")).toBe(false);
    expect(url.searchParams.get("reportId")).toBe(config.reportId);
  });
  it("rejects non-Power-BI URLs", () => {
    for (const url of ["http://app.powerbi.com/reportEmbed", "https://example.com/reportEmbed", "https://app.powerbi.com/groups"]) {
      expect(() => copilotEmbedUrl(url, true)).toThrow();
    }
  });
});

describe("report metadata", () => {
  it("uses the user access token with Power BI REST", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ embedUrl: baseUrl })));
    vi.stubGlobal("fetch", fetcher);
    expect(await getReportUrl(config, "test-token", new Diagnostics())).toBe(baseUrl);
    expect(fetcher.mock.calls[0][0]).toContain(`/groups/${config.workspaceId}/reports/${config.reportId}`);
    expect(fetcher.mock.calls[0][1].headers.Authorization).toBe("Bearer test-token");
  });
  it("records REST 401 and exposed request ID without logging response bodies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("private-body", { status: 401, headers: { requestid: config.reportId } })));
    const diagnostics = new Diagnostics();
    await expect(getReportUrl(config, "secret-token", diagnostics)).rejects.toThrow("HTTP 401");
    const snapshot = diagnostics.snapshot();
    expect(snapshot).toContain('"httpStatus": 401');
    expect(snapshot).toContain(config.reportId);
    expect(snapshot).not.toContain("secret-token");
    expect(snapshot).not.toContain("private-body");
  });
});

describe("embed lifecycle", () => {
  it("keeps action bar and AAD auth constant, unregisters/reset old report, ignores late events", () => {
    const diagnostics = new Diagnostics();
    const status = vi.fn();
    const embed = new ReportEmbed({} as HTMLElement, diagnostics, status);
    const auth = new UserAuth(config, diagnostics);
    embed.load(config, baseUrl, "token", true, auth);
    const oldRendered = sdk.instances[0].on.mock.calls.find(([name]) => name === "rendered")![1];
    embed.load(config, baseUrl, "token", false, auth);
    expect(sdk.instances[0].off.mock.calls.map(([name]) => name)).toEqual(["loaded", "rendered", "error"]);
    expect(sdk.reset).toHaveBeenCalledTimes(1);
    oldRendered();
    expect(status).not.toHaveBeenCalled();
    for (const value of sdk.configs) {
      expect(value).toMatchObject({ tokenType: 0, settings: { bars: { actionBar: { visible: true } }, persistentFiltersEnabled: false, personalBookmarksEnabled: false } });
    }
    expect(sdk.configs[0]).toHaveProperty("embedUrl", copilotEmbedUrl(baseUrl, true));
    expect(sdk.configs[1]).toHaveProperty("embedUrl", copilotEmbedUrl(baseUrl, false));
  });
  it("surfaces refresh failure and returns null per SDK contract; rendered does not erase the error", async () => {
    const diagnostics = new Diagnostics();
    const status = vi.fn();
    const auth = new UserAuth(config, diagnostics);
    vi.spyOn(auth, "getToken").mockRejectedValue(new Error("sensitive-error"));
    const embed = new ReportEmbed({} as HTMLElement, diagnostics, status);
    embed.load(config, baseUrl, "token", true, auth);
    const value = sdk.configs[0] as { eventHooks: { accessTokenProvider: () => Promise<string | null> } };
    expect(await value.eventHooks.accessTokenProvider()).toBeNull();
    expect(status).toHaveBeenCalledWith(expect.any(String), true);
    const calls = status.mock.calls.length;
    sdk.instances[0].on.mock.calls.find(([name]) => name === "rendered")![1]();
    expect(status).toHaveBeenCalledTimes(calls);
    expect(diagnostics.snapshot()).not.toContain("sensitive-error");
  });
  it("does not return a refreshed token to a stale embed", async () => {
    const diagnostics = new Diagnostics();
    const auth = new UserAuth(config, diagnostics);
    let complete!: (token: string) => void;
    vi.spyOn(auth, "getToken").mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
    const embed = new ReportEmbed({} as HTMLElement, diagnostics, vi.fn());
    embed.load(config, baseUrl, "token", true, auth);
    const value = sdk.configs[0] as { eventHooks: { accessTokenProvider: () => Promise<string | null> } };
    const pending = value.eventHooks.accessTokenProvider();
    embed.reset();
    complete("renewed-token");
    expect(await pending).toBeNull();
  });
});
