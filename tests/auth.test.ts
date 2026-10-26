import { beforeEach, describe, expect, it, vi } from "vitest";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { UserAuth } from "../src/auth";
import { Diagnostics, scopes } from "../src/diagnostics";

const msal = vi.hoisted(() => ({
  initialize: vi.fn(), handleRedirectPromise: vi.fn(), getActiveAccount: vi.fn(),
  loginPopup: vi.fn(), setActiveAccount: vi.fn(), acquireTokenSilent: vi.fn(), logoutPopup: vi.fn(),
}));
vi.mock("@azure/msal-browser", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@azure/msal-browser")>();
  return { ...actual, PublicClientApplication: vi.fn(function () { return msal; }) };
});

const config = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  clientId: "22222222-2222-4222-8222-222222222222",
  workspaceId: "33333333-3333-4333-8333-333333333333",
  reportId: "44444444-4444-4444-8444-444444444444",
};
const account = { homeAccountId: "test-account" };
const result = () => ({ account, accessToken: "opaque-token", scopes, expiresOn: new Date(Date.now() + 3600_000) });

beforeEach(() => {
  vi.resetAllMocks();
  msal.getActiveAccount.mockReturnValue(account);
  msal.acquireTokenSilent.mockResolvedValue(result());
  msal.loginPopup.mockResolvedValue(result());
});

describe("delegated user authentication", () => {
  it("acquires an access token silently for the selected account", async () => {
    const auth = new UserAuth(config, new Diagnostics());
    await auth.initialize();
    expect(await auth.getToken()).toBe("opaque-token");
    expect(msal.acquireTokenSilent).toHaveBeenCalledWith({ scopes, account, forceRefresh: false });
    expect(msal.loginPopup).not.toHaveBeenCalled();
  });
  it("does not launch background popups when interaction is required", async () => {
    msal.acquireTokenSilent.mockRejectedValue(new InteractionRequiredAuthError("interaction_required"));
    const diagnostics = new Diagnostics();
    const auth = new UserAuth(config, diagnostics);
    await auth.initialize();
    await expect(auth.getToken()).rejects.toThrow("Click Sign in again");
    expect(msal.loginPopup).not.toHaveBeenCalled();
    expect(diagnostics.snapshot()).toContain("interaction_required");
  });
  it("surfaces denied consent and does not mark sign-in successful", async () => {
    msal.getActiveAccount.mockReturnValue(null);
    msal.loginPopup.mockRejectedValue(new Error("denied"));
    const auth = new UserAuth(config, new Diagnostics());
    await auth.initialize();
    await expect(auth.signIn()).rejects.toThrow("denied");
    expect(auth.signedIn).toBe(false);
  });
  it("rejects missing Copilot scope and expired tokens", async () => {
    const auth = new UserAuth(config, new Diagnostics());
    await auth.initialize();
    msal.acquireTokenSilent.mockResolvedValue({ ...result(), scopes: ["Report.Read.All"] });
    await expect(auth.getToken()).rejects.toThrow("MLModel.Execute.All");
    msal.acquireTokenSilent.mockResolvedValue({ ...result(), expiresOn: new Date(0) });
    await expect(auth.getToken()).rejects.toThrow("unexpired");
  });
  it("rejects late refresh after sign-out and clears token diagnostics", async () => {
    const diagnostics = new Diagnostics();
    const auth = new UserAuth(config, diagnostics);
    await auth.initialize();
    await auth.getToken();
    let complete!: (value: ReturnType<typeof result>) => void;
    msal.acquireTokenSilent.mockReturnValue(new Promise((resolve) => { complete = resolve; }));
    const pending = auth.getToken(true);
    await auth.signOut();
    complete(result());
    await expect(pending).rejects.toThrow("session changed");
    expect(auth.signedIn).toBe(false);
    expect(JSON.parse(diagnostics.snapshot()).token).toBeUndefined();
  });
});
