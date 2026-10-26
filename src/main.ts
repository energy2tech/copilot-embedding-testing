import { UserAuth } from "./auth";
import { loadConfig, type DemoConfig } from "./config";
import { Diagnostics, describeError, type Phase } from "./diagnostics";
import { getReportUrl, ReportEmbed } from "./embed";
import "./style.css";

function element<T extends HTMLElement>(id: string, type: { new(): T }): T {
  const node = document.getElementById(id);
  if (!(node instanceof type)) throw new Error(`Missing UI element: ${id}`);
  return node;
}

const signIn = element("sign-in", HTMLButtonElement);
const signOut = element("sign-out", HTMLButtonElement);
const reload = element("reload", HTMLButtonElement);
const toggle = element("copilot", HTMLInputElement);
const serviceLink = element("service-link", HTMLAnchorElement);
const statusLine = element("status", HTMLParagraphElement);
const diagnosticText = element("diagnostics", HTMLPreElement);
const diagnostics = new Diagnostics();
const status = (message: string, error = false) => {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", error);
};
const report = new ReportEmbed(element("report", HTMLElement), diagnostics, status);
let config: DemoConfig | undefined;
let auth: UserAuth | undefined;
let busy = false;
let activeMode = true;

diagnostics.onChange = () => { diagnosticText.textContent = diagnostics.snapshot(); };
diagnostics.onChange();

function controls(): void {
  signIn.disabled = busy || !auth;
  signIn.textContent = auth?.signedIn ? "Sign in again" : "Sign in";
  signOut.disabled = busy || !auth?.signedIn;
  reload.disabled = busy || !auth?.signedIn;
  toggle.disabled = busy || !auth?.signedIn;
}

async function run(phase: Phase, action: () => Promise<void>): Promise<void> {
  if (busy) return;
  busy = true;
  controls();
  diagnostics.record(phase, "start");
  try {
    await action();
  } catch (error) {
    const problem = describeError(error);
    diagnostics.record(phase, "error", problem.details);
    status(problem.message, true);
  } finally {
    busy = false;
    controls();
  }
}

async function loadReport(): Promise<void> {
  if (!auth || !config) return;
  report.reset();
  diagnostics.copilot = toggle.checked;
  activeMode = toggle.checked;
  status("Acquiring a delegated Power BI token...");
  const token = await auth.getToken();
  status("Retrieving report metadata...");
  const embedUrl = await getReportUrl(config, token, diagnostics);
  status(`Embedding report with Copilot requested ${activeMode ? "on" : "off"}...`);
  report.load(config, embedUrl, token, activeMode, auth);
}

signIn.addEventListener("click", () => void run("sign-in", async () => {
  report.reset();
  status("Sign in and consent in the Microsoft popup...");
  await auth!.signIn();
  diagnostics.record("sign-in", "ok");
  await loadReport();
}));
signOut.addEventListener("click", () => void run("sign-out", async () => {
  report.reset();
  status("Signing out...");
  await auth!.signOut();
  diagnostics.record("sign-out", "ok");
  status("Signed out. Sign in to test again.");
}));
reload.addEventListener("click", () => void run("embed", loadReport));
toggle.addEventListener("change", () => {
  if (busy) { toggle.checked = activeMode; return; }
  void run("embed", loadReport);
});
element("export", HTMLButtonElement).addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([diagnostics.snapshot()], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `diagnostics-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

void run("configuration", async () => {
  config = await loadConfig();
  diagnostics.setConfig(config);
  auth = new UserAuth(config, diagnostics);
  await auth.initialize();
  serviceLink.href = `https://app.powerbi.com/groups/${config.workspaceId}/reports/${config.reportId}?ctid=${config.tenantId}`;
  serviceLink.hidden = false;
  diagnostics.record("configuration", "ok");
  if (auth.signedIn) await loadReport();
  else status("Ready. Sign in with a user who can access this Power BI report.");
});
