// Records the help centre's videos — walk-throughs of the real screens with captions and a visible cursor, light theme —
// from the demo data, then turns each into an MP4 in baogee_textile/public/downloads/videos (copy to each server by hand,
// like the sugarcane videos). They open, point, preview and type into forms, but never save: the data is left as it is.
//
//   cd apps/baogee_textile && DEMO_PWD=… NODE_PATH=../crm/node_modules node scripts/help/record_videos.js [number …]
//
// Needs a Python with imageio-ffmpeg (VIDEO_PY, default ~/.cache/micromax-videos/venv/bin/python) for the MP4.
const { chromium } = require("playwright-core");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://baogee.localhost:5182";
const SYNC = process.env.SYNC || "http://127.0.0.1:8766";
const USER = process.env.DEMO_USER || "Administrator";
const PWD = process.env.DEMO_PWD;
const OUT = path.join(__dirname, "..", "..", "baogee_textile", "public", "downloads", "videos");
const TMP = path.join(require("os").tmpdir(), "baogee-help-frames");
const W = 1440, H = 900;
const VIDEO_PY = process.env.VIDEO_PY || path.join(require("os").homedir(), ".cache/micromax-videos/venv/bin/python");
if (!PWD) { console.error("Set DEMO_PWD"); process.exit(1); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const enc = encodeURIComponent;

const LOAN = "HR-EAD-2026-00001", ADVANCE = "HR-EAD-2026-00007", DRAFT_LOAN = "HR-EAD-2026-00011";
const EMP = "HR-EMP-00001", SLIP = "Sal Slip/HR-EMP-00001/00001", PAYROLL = "HR-PRUN-2026-00001", DIVISION = "BLEACHING - BGT";

const OVERLAY = `
(() => {
  if (window.__ov) return; window.__ov = 1;
  try { localStorage.setItem('micromax-theme', 'light'); } catch (e) {}
  const css = document.createElement('style');
  css.textContent = \`
  #vv-cap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:2147483646;max-width:1100px;min-width:520px;
    background:rgba(15,27,45,.95);color:#fff;border:1px solid rgba(245,165,36,.7);border-radius:16px;padding:14px 22px 14px 18px;
    font:500 19px/1.35 Ubuntu,"Noto Sans",Arial,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.3);pointer-events:none;display:flex;gap:14px;align-items:center}
  #vv-cap b{display:block;color:#f5a524;font-size:13px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:2px}
  #vv-cap .n{flex:none;width:38px;height:38px;border-radius:50%;background:#f5a524;color:#fff;display:grid;place-items:center;font:700 17px Ubuntu,Arial}
  #vv-cap:empty{display:none}
  #vv-cur{position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;pointer-events:none;
    background:rgba(245,165,36,.35);border:2px solid #f5a524;transition:transform .12s}
  #vv-cur.dn{transform:scale(.65);background:rgba(245,165,36,.75)}\`;
  const mount = () => {
    if (!document.body) return setTimeout(mount, 30);
    document.head.appendChild(css);
    const cap = document.createElement('div'); cap.id = 'vv-cap'; document.body.appendChild(cap);
    const cur = document.createElement('div'); cur.id = 'vv-cur'; document.body.appendChild(cur);
    const c = sessionStorage.getItem('vv-cap'); if (c) cap.innerHTML = c;
    const p = sessionStorage.getItem('vv-xy'); if (p) { const [x, y] = p.split(','); cur.style.left = x + 'px'; cur.style.top = y + 'px'; }
    addEventListener('mousemove', (e) => { cur.style.left = e.clientX + 'px'; cur.style.top = e.clientY + 'px'; sessionStorage.setItem('vv-xy', e.clientX + ',' + e.clientY); }, true);
    addEventListener('mousedown', () => cur.classList.add('dn'), true);
    addEventListener('mouseup', () => cur.classList.remove('dn'), true);
  };
  mount();
})();`;

let page, ctx, n = 0;
async function caption(who, text, top = false) {
  n += 1;
  const html = `<span class="n">${n}</span><span><b>${who}</b>${text}</span>`;
  await page.evaluate(([h, t]) => {
    sessionStorage.setItem("vv-cap", h); const c = document.getElementById("vv-cap");
    if (c) { c.innerHTML = h; c.style.top = t ? "70px" : ""; c.style.bottom = t ? "auto" : ""; }
  }, [html, top]).catch(() => {});
  await sleep(3900);
}
async function noCaption() {
  await page.evaluate(() => { sessionStorage.removeItem("vv-cap"); const c = document.getElementById("vv-cap"); if (c) c.innerHTML = ""; }).catch(() => {});
}
async function pointAt(loc) {
  loc = loc.first();
  await loc.waitFor({ state: "visible", timeout: 15000 });
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (b) await page.mouse.move(b.x + Math.min(b.width / 2, 160), b.y + b.height / 2, { steps: 20 });
  await sleep(500);
}
async function click(loc, after = 1200) { await pointAt(loc); await loc.first().click(); await sleep(after); }
async function type(loc, text) { await pointAt(loc); await loc.first().click(); await sleep(250); await loc.first().pressSequentially(String(text), { delay: 70 }); await sleep(400); }
async function go(url) { await noCaption(); await page.goto(url.startsWith("http") ? url : `${BASE}${url}`, { waitUntil: "networkidle" }); await sleep(1500); }
async function scroll(px) { await page.mouse.move(W / 2, H / 2, { steps: 8 }); await page.mouse.wheel(0, px); await sleep(1300); }
async function scrollTo(t) {
  await page.getByText(t, { exact: false }).first().evaluate((el) => { el.scrollIntoView({ block: "start", behavior: "smooth" }); });
  await sleep(900); await page.mouse.wheel(0, -90); await sleep(700);
}
const btn = (name) => page.getByRole("button", { name, exact: false });
const text = (t) => page.getByText(t, { exact: false });
const field = (f) => page.locator(`[data-field="${f}"] input, [data-field="${f}"] textarea`);
async function card(title, sub, ms = 3600) {
  await noCaption();
  await page.setContent(`<html><body style="margin:0;height:100vh;display:grid;place-items:center;background:radial-gradient(1200px 600px at 30% 20%,#1b2d48,#0f1b2d 60%);
    font-family:Ubuntu,'Noto Sans',Arial,sans-serif;color:#fff"><div style="text-align:center;max-width:1050px;padding:40px">
    <div style="font:700 15px Ubuntu,Arial;letter-spacing:.25em;color:#f5a524;text-transform:uppercase">Bao Gee Textile · HR &amp; Payroll · Help centre</div>
    <h1 style="font-size:56px;margin:18px 0 14px;line-height:1.1">${title}</h1>
    <div style="height:4px;width:120px;margin:0 auto 22px;border-radius:4px;background:#f5a524"></div>
    <p style="font:400 24px/1.45 Ubuntu,Arial;color:#d6dbe4;margin:0">${sub}</p></div></body></html>`);
  await sleep(ms);
}
const end = (t) => card("That's it", `${t}<br><br><span style="font-size:18px;color:#94a3b8">Demo data · more in Help &amp; Guides</span>`, 4200);
const HR = "HR officer", TK = "Timekeeper", PO = "Payroll officer", AC = "Accounts";

// the scenes, reused by the full walk-throughs
const S = {
  organisation: async () => {
    await go("/hr/departments"); await caption(HR, "Departments: the headcount tree rolls staff up by division, department and sub-department");
    await scroll(500); await caption(HR, "Every department as a card: its level, parent and active headcount, male and female");
    await go(`/hr/departments/${enc(DIVISION)}`); await caption(HR, "A division on a full page: name, Urdu name, code, level and its approvers");
    await go("/hr/designations"); await caption(HR, "Designations: every job title with its Urdu name and headcount");
  },
  urdu: async () => {
    await go("/hr/departments/new"); await caption(HR, "New department: the Urdu name field types Urdu from the English keyboard");
    await type(field("mm_urdu_name"), "rNgayi"); await caption(HR, "Letters by sound — r ر, Shift+N ں, g گ, a ا, y ے — no Urdu keyboard needed. This demo does not save");
  },
  employee: async () => {
    await go("/hr/employees"); await caption(HR, "Employees: search by name, code or CNIC, filter by department");
    await go("/hr/employees/new"); await caption(HR, "New employee on one page: English and Urdu name, CNIC, gender, date of birth, and the passport photo");
    await type(field("first_name"), "Imran"); await type(field("mm_urdu_name"), "amran");
    await scroll(650); await caption(HR, "Job: department, designation, code, shift — and the Attendance Device ID, the user number on the biometric machine");
    await caption(HR, "Pay: basic salary, salary mode and bank. Create employee saves it — this demo does not");
    await go(`/hr/employees/${EMP}`); await caption(HR, "The profile: photo, Urdu name, coloured links to department, designation and manager");
    await click(text("Connections")); await caption(HR, "Connections: attendance, leave, advances and salary slips linked to the employee");
  },
  attendance: async () => {
    await go(`${SYNC}/`).catch(() => {}); await caption(TK, "The Biometric Sync tool on the site PC: each ZKTeco machine, Test, and the history of runs");
    await caption(TK, "Every run reads the new punches and pushes them to the ERP; punches already sent are skipped");
    await go("/hr/checkins"); await caption(TK, "Checkins: every punch with the employee, time, IN or OUT, and the machine");
    await go("/hr/shift-types"); await caption(TK, "Shifts: General 08:30–16:30, A, B and C — late entry and early exit after a 30-minute grace");
    await go("/hr/roster"); await caption(TK, "Roster: who works which shift on each day");
    await go("/hr/attendance"); await caption(HR, "Attendance: present, absent, late and leave for any period, by department");
  },
  leave: async () => {
    await go("/hr/holiday-lists"); await caption(HR, "Holiday list: Sundays and public holidays, assigned to the company");
    await go("/hr/leave-allocations"); await caption(HR, "Leave allocations: each employee's days per leave type");
    await go("/hr/leave-applications"); await caption(HR, "Leave applications: approved by the department's leave approver");
  },
  advanceNew: async () => {
    await go("/hr/advances"); await caption(HR, "Employee advances: every cash advance and salary loan, its instalments, repaid and status");
    await go(`/hr/advances/new?employee=${EMP}`); await caption(HR, "New advance or loan: choose the type at the top");
    await click(btn("Salary loan")); await caption(HR, "A salary loan is recovered in equal monthly instalments from salary");
    await type(field("advance_amount"), "48000"); await page.keyboard.press("Tab"); await sleep(600);
    await click(btn("6 months")); await caption(HR, "Quick pick 6 months: Rs 8,000 a month — the card shows the first and last deduction");
    await scrollTo("Instalment schedule"); await caption(HR, "The instalment schedule previews every month and the balance after it", true);
    await scrollTo("eligible"); await caption(HR, "The eligibility check: every rule of the loan policy with ✓ or ✗. An HR Manager can override with a reason", true);
    await caption(HR, "Save draft or Approve. This demo does not save", true);
  },
  advanceRecovery: async () => {
    await go(`/hr/advances/${DRAFT_LOAN}`); await caption(HR, "A loan request waiting for approval: Approve, then Accounts pays it out");
    await go(`/hr/advances/${LOAN}`); await caption(AC, "Paid out in cash on 3 October: the instalments were set up in payroll at once");
    await scrollTo("Instalment schedule"); await caption(PO, "October: Rs 10,000 deducted by the salary slip. Five months scheduled", true);
    await go(`/hr/advances/${ADVANCE}`); await caption(PO, "A cash advance: recovered in full from October's salary — status Returned");
    await go("/hr/loans"); await caption(PO, "Salary loans: outstanding, deducted this month against last, and the loan ledger");
  },
  structures: async () => {
    await go("/payroll/salary-components"); await caption(PO, "Salary components: earnings and deductions, each posting to its account");
    await go("/payroll/salary-structures"); await caption(PO, "Salary structures: the formula for a group of staff, e.g. Basic = base");
    await go("/payroll/salary-structure-assignments"); await caption(PO, "Assignments: each employee's structure, monthly base and start date");
  },
  payroll: async () => {
    await go("/payroll/additional-salary"); await caption(PO, "Additional salary: overtime, arrears — and the loan instalments and advance recovery");
    await go("/payroll/entries"); await caption(PO, "Payroll entries: one per month");
    await go(`/payroll/entries/${PAYROLL}`); await caption(PO, "October's payroll: the month, accounts and employees — slips created, then submitted and posted");
    await go("/payroll/salary-slips"); await caption(PO, "Salary slips: payment days from attendance, earnings, deductions and net pay");
    await go(`/payroll/salary-slips/${enc(SLIP)}`); await caption(PO, "One slip: Basic earned, Loan Recovery Rs 10,000 deducted, net pay");
    await scroll(500); await caption(PO, "Submitting posts the payroll: the loan's balance drops by the instalment");
  },
};

const VIDEOS = {
  "01-Full-HR-walkthrough": async () => {
    await card("Full HR walk-through", "Organisation, employees, punches and attendance, leave, and an advance");
    await S.organisation(); await S.employee(); await S.attendance(); await S.leave(); await S.advanceNew();
    await end("That is HR from the organisation to an employee's loan.");
  },
  "02-Full-payroll-month": async () => {
    await card("Full payroll month", "Structures, attendance, loans and advances, the payroll entry and the salary slips");
    await S.structures();
    await go("/hr/attendance"); await caption(PO, "Payroll is based on attendance: a working day with no attendance counts as absent");
    await S.advanceRecovery(); await S.payroll();
    await end("Next month the payroll entry takes the next instalment automatically.");
  },
  "03-Organisation-departments-designations": async () => {
    await card("Organisation", "Divisions, departments, sub-departments, designations and Urdu names"); await S.organisation(); await S.urdu();
    await end("Headcount updates as employees join, move and leave.");
  },
  "04-Employees-new-employee-and-profile": async () => {
    await card("Employees", "A new employee on one page, the passport photo, and the profile"); await S.employee();
    await end("Set the Attendance Device ID so the employee's punches are matched.");
  },
  "05-Biometric-punches-shifts-attendance": async () => {
    await card("Biometric attendance", "Machines, the sync tool, check-ins, shifts and attendance"); await S.attendance();
    await end("Check yesterday's punches every morning.");
  },
  "06-Leave-and-holidays": async () => {
    await card("Leave and holidays", "Holiday list, allocations and applications"); await S.leave();
    await end("Approved leave shows on attendance and in payroll.");
  },
  "07-Advances-and-salary-loans": async () => {
    await card("Advances and salary loans", "Request, eligibility, approval, pay-out and recovery from salary"); await S.advanceNew(); await S.advanceRecovery();
    await end("Each instalment is taken by that month's salary slip.");
  },
  "08-Salary-components-and-structures": async () => {
    await card("Salary structures", "Components, structures and assignments"); await S.structures();
    await end("No assignment, no salary slip — assign a structure to every employee.");
  },
  "09-Monthly-payroll-run": async () => {
    await card("Monthly payroll run", "Additional salary, the payroll entry, salary slips and posting"); await S.payroll();
    await end("Salary loans shows the month's deductions and the new balances.");
  },
};

async function record(name, fn) {
  const dir = path.join(TMP, name);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const frames = [];
  await page.setContent("<body style=\"margin:0;background:#0f1b2d\"></body>");
  const cdp = await ctx.newCDPSession(page);
  cdp.on("Page.screencastFrame", (f) => {
    const file = path.join(dir, `${String(frames.length).padStart(6, "0")}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ file, t: f.metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const tick = setInterval(() => page.evaluate(() => { const c = document.getElementById("vv-cur"); if (c) c.style.opacity = c.style.opacity === "0.99" ? "1" : "0.99"; }).catch(() => {}), 120);
  n = 0;
  try { await fn(); } finally {
    clearInterval(tick);
    await cdp.send("Page.stopScreencast").catch(() => {});
    await cdp.detach().catch(() => {});
  }
  fs.writeFileSync(path.join(dir, "frames.json"), JSON.stringify(frames));
  execFileSync(VIDEO_PY, [path.join(__dirname, "build_video.py"), dir, path.join(OUT, `${name}.mp4`)], { stdio: "inherit" });
  fs.rmSync(dir, { recursive: true, force: true });
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const only = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true, args: ["--hide-scrollbars"] });
  ctx = await browser.newContext({ viewport: { width: W, height: H }, colorScheme: "light", locale: "en-GB" });
  await ctx.addInitScript(OVERLAY);
  const r = await ctx.request.post(`${BASE}/api/method/login`, { data: { usr: USER, pwd: PWD } });
  if (!r.ok()) throw new Error(`login: ${r.status()}`);
  page = await ctx.newPage();
  let failed = 0;
  for (const [name, fn] of Object.entries(VIDEOS)) {
    if (only.length && !only.some((o) => name.startsWith(o))) continue;
    try { await record(name, fn); console.log("✓", name); } catch (e) {
      failed += 1; console.error("✗", name, e.message.split("\n")[0]);
      await page.screenshot({ path: path.join(require("os").tmpdir(), `baogee-video-${name}-fail.png`) }).catch(() => {});
    }
  }
  await browser.close();
  process.exitCode = failed ? 1 : 0;
})();
