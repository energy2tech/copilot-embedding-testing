import { describe, expect, it, vi, afterEach } from "vitest";
import { loadConfig, parseConfig } from "../src/config";
import { Diagnostics, describeError, powerBiResource, scopes, summarizeToken } from "../src/diagnostics";

export const config = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  clientId: "22222222-2222-4222-8222-222222222222",
  workspaceId: "33333333-3333-4333-8333-333333333333",
  reportId: "44444444-4444-4444-8444-444444444444",
};

afterEach(() => vi.unstubAllGlobals());

describe("configuration", () => {
  it("accepts exactly the four nonzero GUIDs", () => {
    expect(parseConfig(config)).toEqual(config);
    for (const value of [null, [], {}, { ...config, clientId: "placeholder" }, { ...config, tenantId: "00000000-0000-0000-0000-000000000000" }, { ...config, clientSecret: "do-not-store" }]) {
      expect(() => parseConfig(value)).toThrow();
    }
  });
  it("requires the registered origin", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost:9999" } });
    await expect(loadConfig()).rejects.toThrow("registered SPA redirect");
  });
  it("explains missing config even when Vite falls back to HTML", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost:5173" } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html></html>", { headers: { "Content-Type": "text/html" } })));
    await expect(loadConfig()).rejects.toThrow("Copy public/config.example.json");
  });
  it("reports malformed JSON", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost:5173" } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{", { headers: { "Content-Type": "application/json" } })));
    await expect(loadConfig()).rejects.toThrow("not valid JSON");
  });
});

describe("safe token diagnostics", () => {
  it("requests only Power BI report and Copilot scopes", () => {
    expect(scopes).toEqual([`${powerBiResource}/Report.Read.All`, `${powerBiResource}/MLModel.Execute.All`]);
  });
  it("reports missing Copilot consent", () => {
    expect(summarizeToken("opaque", ["Report.Read.All"], null, config.tenantId).missingRequiredScopes).toEqual(["MLModel.Execute.All"]);
  });
  it("handles opaque tokens without pretending claims were validated", () => {
    expect(summarizeToken("opaque", scopes, null, config.tenantId)).toMatchObject({
      audienceCheck: "unavailable", tenantCheck: "unavailable", missingRequiredScopes: [],
    });
  });
  it("summarizes claims without retaining raw token or user claims", () => {
    const payload = btoa(JSON.stringify({ aud: powerBiResource, tid: config.tenantId, upn: "private@example.com", name: "Private User" }));
    const token = `header.${payload}.signature`;
    const summary = summarizeToken(token, scopes, new Date("2030-01-01T00:00:00Z"), config.tenantId);
    expect(summary).toMatchObject({ audienceCheck: "match", tenantCheck: "match", missingRequiredScopes: [] });
    const diagnostics = new Diagnostics();
    diagnostics.setConfig(config);
    diagnostics.setToken(summary);
    diagnostics.record("error", "error", {
      code: token, requestId: "Authorization Bearer secret", activityId: config.reportId,
    });
    const snapshot = diagnostics.snapshot();
    expect(snapshot).not.toContain(token);
    expect(snapshot).not.toContain("private@example.com");
    expect(snapshot).not.toContain("Private User");
    expect(snapshot).not.toContain("Bearer secret");
    expect(JSON.parse(snapshot).events[0].activityId).toBe(config.reportId);
  });
  it("detects wrong audience/tenant and invalid claims", () => {
    const payload = btoa(JSON.stringify({ aud: "https://graph.microsoft.com", tid: config.clientId }));
    expect(summarizeToken(`h.${payload}.s`, scopes, null, config.tenantId)).toMatchObject({ audienceCheck: "mismatch", tenantCheck: "mismatch" });
    expect(summarizeToken("h.not-json.s", scopes, null, config.tenantId).audienceCheck).toBe("unavailable");
  });
  it("does not expose unknown raw exception messages", () => {
    const problem = describeError(new Error("Bearer secret-and-report-data"));
    expect(JSON.stringify(problem)).not.toContain("secret-and-report-data");
    expect(problem.details.code).toBe("unexpected_error");
  });
  it("bounds retained events", () => {
    const diagnostics = new Diagnostics();
    for (let i = 0; i < 250; i++) diagnostics.record("embed", "start");
    expect(JSON.parse(diagnostics.snapshot()).events).toHaveLength(200);
  });
});
