import { BrowserCacheLocation, InteractionRequiredAuthError, PublicClientApplication, type AccountInfo, type AuthenticationResult } from "@azure/msal-browser";
import { DemoError, type DemoConfig } from "./config";
import { Diagnostics, scopes, summarizeToken } from "./diagnostics";

export class UserAuth {
  private readonly client: PublicClientApplication;
  private account: AccountInfo | null = null;
  private generation = 0;

  constructor(private readonly config: DemoConfig, private readonly diagnostics: Diagnostics) {
    this.client = new PublicClientApplication({
      auth: {
        clientId: config.clientId,
        authority: `https://login.microsoftonline.com/${config.tenantId}`,
        redirectUri: "http://localhost:5173/auth.html",
        postLogoutRedirectUri: "http://localhost:5173/auth.html",
      },
      cache: { cacheLocation: BrowserCacheLocation.SessionStorage },
    });
  }

  async initialize(): Promise<void> {
    await this.client.initialize();
    await this.client.handleRedirectPromise();
    this.account = this.client.getActiveAccount();
  }

  get signedIn(): boolean { return this.account !== null; }

  async signIn(): Promise<void> {
    this.generation++;
    const result = await this.client.loginPopup({ scopes, prompt: "select_account" });
    if (!result.account) throw new DemoError("Sign-in returned no user account. Sign in again.", "missing_account");
    this.account = result.account;
    this.client.setActiveAccount(result.account);
    this.inspect(result);
  }

  async getToken(forceRefresh = false): Promise<string> {
    if (!this.account) throw new DemoError("Sign in before loading the report.", "sign_in_required");
    const generation = this.generation;
    let result: AuthenticationResult;
    try {
      result = await this.client.acquireTokenSilent({ scopes, account: this.account, forceRefresh });
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        this.diagnostics.record("token", "error", { code: "interaction_required" });
        throw new DemoError("User interaction is required. Click Sign in again to renew consent/session, then reload. No background popup will be opened.", "interaction_required");
      }
      throw error;
    }
    if (generation !== this.generation) {
      throw new DemoError("The authentication session changed. Reload the report after sign-in completes.", "session_changed");
    }
    this.inspect(result);
    return result.accessToken;
  }

  async signOut(): Promise<void> {
    this.generation++;
    await this.client.logoutPopup({ account: this.account });
    this.account = null;
    this.client.setActiveAccount(null);
    this.diagnostics.setToken();
  }

  private inspect(result: AuthenticationResult): void {
    const summary = summarizeToken(result.accessToken, result.scopes, result.expiresOn, this.config.tenantId);
    this.diagnostics.setToken(summary);
    if (summary.missingRequiredScopes.length) {
      throw new DemoError(`Token lacks ${summary.missingRequiredScopes.join(", ")}. Add delegated Power BI permissions, grant consent and sign in again.`, "missing_scopes");
    }
    if (!result.accessToken || !result.expiresOn || result.expiresOn.getTime() <= Date.now()) {
      throw new DemoError("No unexpired Power BI access token was acquired. Sign in again.", "invalid_token");
    }
    if (summary.audienceCheck === "mismatch" || summary.tenantCheck === "mismatch") {
      throw new DemoError("Token claims do not match the configured Power BI audience/tenant. Check app configuration and sign in again.", "token_claim_mismatch");
    }
    this.diagnostics.record("token", "ok");
  }
}
