# Power BI Embedded Copilot test rig

A minimal local **user-owns-data** application for reproducing Copilot issues in an embedded Power BI report. It signs in a real user, uses that user's Power BI access token, and toggles the native Copilot button using Microsoft's documented URL opt-in.

**This is not app owns data. Do not supply a service principal secret, certificate, or embed token.** You need an Entra app registration (client ID), not service-principal authentication.

## What the demo tests

- Copilot starts **on**.
- The action bar is visible in both modes.
- On: the report embed URL includes `reportCopilotInEmbed=true`.
- Off: that opt-in parameter is removed.
- Changing the checkbox resets and re-embeds the report; temporary slicers/selections can reset.
- Both modes use the same user, report, delegated scopes, AAD token type, and action bar settings.
- "Report rendered" is not Copilot success. Open the native Copilot button and submit a prompt.
- The switch controls this embed experience only. It does not disable Copilot tenant-wide or form an authorization boundary.

The app does not create reports, models, capacities, app registrations, or tenant settings. It does not alter report data or automatically change customer permissions.

## Prerequisites

1. Node.js **22.12+** (Node 24 LTS recommended), npm, and a current Edge/Chrome browser.
2. A commercial-cloud Entra/Fabric tenant and an existing interactive Power BI report in a workspace. This demo does not target My Workspace, sovereign clouds, paginated reports, or guest/B2B authentication.
3. A user with report/workspace access and the Power BI license required for the workspace/capacity. Capacity does not automatically waive every user licensing requirement.
4. An eligible, active **paid Fabric F2+ or Power BI Premium P1+ capacity**, supported region, and applicable Copilot tenant/capacity settings enabled for the testing user. Trial capacity, Pro alone, and PPU alone are not sufficient Copilot capacity. Verify current requirements in the links below; do not assume an A-SKU qualifies.
5. Copilot working for the **same user and report in Power BI Service** is the best baseline. If it does not, resolve the environment/prerequisite issue before diagnosing embedding.
6. Permission to register/configure an Entra SPA and obtain the required delegated consent. Your organization's policies may require an administrator.

Copilot prompts can incur paid capacity usage. Use a nonsensitive test report where possible.

## 1. Register the Entra application

In the **Microsoft Entra admin center**:

1. Open **App registrations > New registration**.
2. Choose **Accounts in this organizational directory only**.
3. Under **Authentication**, add a **Single-page application (SPA)** redirect URI exactly:

   ```text
   http://localhost:5173/auth.html
   ```

   This is a static callback page, not the main application. Do not register it as a Web/confidential-client redirect. Do not enable implicit grant or create a client secret.

4. Under **API permissions > Add a permission > Power BI Service > Delegated permissions**, add:

   | Delegated permission | Why |
   | --- | --- |
   | `Report.Read.All` | Retrieve and view reports the signed-in user can access |
   | `MLModel.Execute.All` | Required by Microsoft's embedded Copilot documentation |

5. Obtain consent for both scopes under your organization's policies. Configuring permissions in the portal is not the same as obtaining those scopes in an issued token.
6. Record the **Directory (tenant) ID** and **Application (client) ID**.

No Microsoft Graph permission is required by this app. MSAL also uses standard OpenID Connect sign-in scopes.

`UserState.ReadWrite.All` is needed for full action-bar personalization, persistent filters and personal bookmarks. Those features are intentionally not enabled/requested here. Their permissions are separate from `MLModel.Execute.All`; do not confuse a request for those features with the failing Copilot request.

## 2. Configure the report

In Power BI Service, a workspace report URL normally contains:

```text
https://app.powerbi.com/groups/<workspaceId>/reports/<reportId>/...
```

Open PowerShell in the extracted demo directory:

```powershell
Copy-Item -LiteralPath .\public\config.example.json -Destination .\public\config.local.json
```

Edit `public/config.local.json`:

```json
{
  "tenantId": "YOUR-ENTRA-TENANT-GUID",
  "clientId": "YOUR-APPLICATION-CLIENT-GUID",
  "workspaceId": "YOUR-WORKSPACE-GUID",
  "reportId": "YOUR-REPORT-GUID"
}
```

Replace all four values with actual nonzero GUIDs. No other configuration fields are accepted. All four IDs are browser-visible configuration, not secrets, but still organizational metadata. Do not add passwords or tokens.

Each customer uses their own single-tenant app registration and report. No developer tenant values are needed or distributed.

## 3. Run locally

```powershell
npm ci
npm run dev
```

Open **http://localhost:5173** (not an IP address or another port), allow sign-in popups, and select **Sign in**.

The server is bound to localhost and fails if port 5173 is occupied instead of silently switching ports. Stop the other listener intentionally or choose a consistently updated origin/redirect in the source and Entra registration; do not change only the browser URL.

The app:

1. Signs in using MSAL authorization code flow with PKCE, with session-scoped browser caching.
2. Requests `https://analysis.windows.net/powerbi/api/Report.Read.All` and `https://analysis.windows.net/powerbi/api/MLModel.Execute.All`.
3. Checks granted required scopes and expiry. When readable, token audience/tenant claims provide diagnostic mismatch checks, not cryptographic validation.
4. Retrieves `embedUrl` using Power BI REST `GET /v1.0/myorg/groups/{workspaceId}/reports/{reportId}`.
5. Embeds with `models.TokenType.Aad`, the action bar visible, and the selected Copilot URL parameter.
6. Uses the SDK `accessTokenProvider` hook for silent token refresh. Refresh errors are shown, not hidden. If interaction is needed, click **Sign in again**, then reload if needed. No background popup is opened.

Use **Sign out** to reset the embedded report and end the MSAL session. This also affects your Microsoft sign-in session in the browser.

Do not deploy this diagnostic app publicly. Vite's public directory is served to the browser and copied into a production build, including local configuration. Build output is not the customer distribution package.

## 4. Controlled reproduction checklist

Use the same browser profile, user, tenant, and report throughout:

| Test | Action | Record |
| --- | --- | --- |
| Service baseline | Use **Open in Power BI**, open Copilot and submit a simple prompt | Whether button/pane/prompt works, UTC timestamp |
| Embedded on | Leave the checkbox on; open the native Copilot button and submit the same prompt | Button visible, pane opens, prompt succeeds or exact failure stage |
| Embedded off | Uncheck Copilot; wait for the new embed to render | Native Copilot button absent; action bar still visible; report still works |
| Embedded on again | Check Copilot and repeat prompt | Button returns and prompt succeeds, or reproducible failure |
| Reload / sign-out | Reload, then sign out | Only one report iframe; report removed at sign-out |

The app displays the **requested** Copilot mode. It cannot inspect cross-origin UI to assert that the button actually appeared/disappeared or that a prompt completed. Record those results manually.

If you change API permissions or consent, acquire a fresh token: sign out and sign in again. Editing the app registration does not modify a previously issued token. Compare both embed modes only after the scopes are correct.

## 5. Investigating a 401

### First distinguish the failing operation

- **Entra sign-in/token error**: redirect URI, SPA platform, consent, Conditional Access, tenant/account policy, or session issue. Check the displayed safe error code and Entra sign-in logs.
- **Report metadata HTTP 401**: verify Power BI audience, expiry, delegated token/scopes and tenant. This occurs before embedding.
- **Report metadata HTTP 403/404**: check report/workspace IDs and user access; permissions/metadata can be hidden as 404.
- **Report renders, Copilot fails**: confirm `MLModel.Execute.All` was actually granted in the acquired token. Then confirm tenant/capacity/region prerequisites and capture the specific iframe request.
- **Copilot button absent**: check the URL opt-in, visible action bar, prerequisites, and the same user's Service baseline. Missing UI is not itself evidence of a 401.

The diagnostics pane/export reports required granted/missing scopes, token expiry, audience/tenant check status, selected mode, versions, app events, and safe request IDs when exposed. Claims can be unavailable for opaque tokens. An unavailable claim is not proof of an invalid token.

### Capture the actual Copilot failure in Edge/Chrome

The app cannot intercept cross-origin iframe fetches, and SDK error events do not necessarily report a Copilot request failure.

1. Open **DevTools > Network** before reproducing. Enable **Preserve log**.
2. Clear previous requests, reload the report, open Copilot, and submit the test prompt.
3. Filter for **401** (for example `status-code:401`). Identify the request triggered by Copilot, not an unrelated action-bar or telemetry request.
4. Record the UTC timestamp, Copilot mode and failing stage, HTTP method, host and sanitized path (omit query strings containing sensitive data), status, safe response error code, and exposed request/activity/correlation IDs.
5. Compare against the same user/report in Service and, when possible, the customer's existing app.
6. Use **Export diagnostics** and review the JSON before attaching it to an approved support case.

Do **not** paste bearer/access/refresh/ID tokens, cookies, authorization headers, full request bodies, report data, or raw console payloads into issues or chat. Do not use third-party token inspection websites.

**HAR files can contain credentials and customer data**, even when browser export options remove some sensitive headers. The app does not create or upload HAR files. Only collect/share a reviewed and sanitized HAR through your organization's approved secure support process if required.

### Interpreting results

| Observation | Interpretation / next action |
| --- | --- |
| Copilot fails in Service too | Investigate eligibility, settings, permissions, session or service health first; not isolated to embed code |
| Required delegated scope missing | Correct consent/token acquisition and retest; this is an auth/configuration issue to resolve before escalation |
| This demo works but the customer's app fails | Compare token type/audience/scopes/expiry, embed URL/action bar, SDK versions, and browser/session behavior |
| Service works; minimal documented embed fails with correct scopes/prerequisites | Evidence for an embed-specific issue; collect request IDs and escalate for service investigation |
| Report works but Copilot request gets 401 | Basic report access alone is not proof that Copilot authorization is correct |

A reproducible 401 is **not by itself proof of a Power BI service defect**. Preserve the exact failing request and controlled comparison results.

## Diagnostics privacy

- No telemetry backend or upload destination is provided. Sign-in, metadata, report embedding and Copilot communicate with the required Microsoft services.
- App diagnostic JSON uses an allowlist, not raw error serialization. It excludes tokens, auth headers, account names/emails, report content, raw SDK messages and response bodies.
- IDs for tenant, app, workspace and report are included. Safe GUID request/activity/correlation IDs and bounded error codes may be included. Review these as organizational metadata.
- Error details that do not fit the safe format are omitted; use DevTools through an approved process when more detail is needed.
- Only the latest 200 app/SDK events are retained in memory. The snapshot is not a network trace, a complete security audit, or proof that Copilot answered.

## Tests and production build

```powershell
npm test
npm run build
```

Focused tests cover configuration, scopes, safe diagnostics, URL toggling, REST failure reporting, authentication errors, stale refresh/session handling, report cleanup and SDK refresh failures. The production build includes TypeScript checking. The SDK/MSAL bundle can trigger Vite's advisory chunk-size warning; this diagnostic app intentionally avoids extra routing/code-splitting complexity.

To smoke-test a build locally (stop the dev server first):

```powershell
npm run preview
```

Automated tests use mocks and do not authenticate to Power BI. **A real eligible tenant/user/report is required to verify the native Copilot button and prompt behavior.** Keep that live result separate from local tests/build results.

## Customer ZIP

```powershell
npm run package:demo
```

Creates `release/pbie-copilot-demo.zip` from an explicit file allowlist: source, tests, pinned lockfile, placeholder configuration and instructions. It excludes `config.local.json`, node_modules, dist, diagnostics, logs, HAR files, and other workspace files. No customer-specific configuration is included.

To choose another destination or intentionally replace the generated ZIP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1 -OutputPath C:\Temp\pbie-copilot-demo.zip -Force
```

Review the archive before sharing, especially if you have edited source files to contain customer values. Recipients extract it, configure their own app/report, and run `npm ci` followed by `npm run dev`. Internet access is required for dependency restore and Microsoft services. No cloud deployment is needed.

## Official references

- [Embedded action bar and Copilot: URL opt-in and MLModel.Execute.All](https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/embed-for-organization)
- [User-owns-data versus app-owns-data; AAD token type](https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/embedding-solutions)
- [Automatic access token refresh and null-on-failure contract](https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/refresh-token)
- [Copilot overview and current prerequisites](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction)
- [Copilot admin enablement](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-enable-power-bi)
- [Power BI Get Report In Group API](https://learn.microsoft.com/en-us/rest/api/power-bi/reports/get-report-in-group)
- [MSAL Browser initialization](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/initialization)
