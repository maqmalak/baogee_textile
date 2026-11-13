// Builds the A4 help guides (baogee_textile/public/help/<slug>.pdf) from live screenshots of the React app with the demo data,
// in the sugarcane guides' style (navy cover, amber accents, numbered sections, a screenshot under each step), light theme.
// It only opens pages, tabs and forms; it never saves anything.
//
//   cd apps/baogee_textile && DEMO_PWD=… NODE_PATH=../crm/node_modules node scripts/help/build_guides.js [slug …]
//
// Screens are taken as Administrator (DEMO_USER to change). BASE defaults to the local React dev server.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://baogee.localhost:5182";
const SYNC = process.env.SYNC || "http://127.0.0.1:8766";
const USER = process.env.DEMO_USER || "Administrator";
const PWD = process.env.DEMO_PWD;
const OUT = path.join(__dirname, "..", "..", "baogee_textile", "public", "help");
if (!PWD) { console.error("Set DEMO_PWD"); process.exit(1); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const enc = encodeURIComponent;

// demo records (baogee_textile.demo.loans_demo)
const LOAN = "HR-EAD-2026-00001", ADVANCE = "HR-EAD-2026-00007", DRAFT_LOAN = "HR-EAD-2026-00011";
const EMP = "HR-EMP-00001", SLIP = "Sal Slip/HR-EMP-00001/00001", PAYROLL = "HR-PRUN-2026-00001", STRUCTURE = "[DEMO] Basic Pay";
const DIVISION = "BLEACHING - BGT";

const clickText = (t) => async (p) => { await p.getByText(t, { exact: false }).first().click(); await sleep(1200); };
const clickBtn = (name) => async (p) => { await p.getByRole("button", { name, exact: false }).first().click(); await sleep(1200); };
const scrollTo = (t) => async (p) => {
  await p.getByText(t, { exact: false }).first().evaluate((el) => { el.scrollIntoView({ block: "start" }); window.scrollBy(0, -90); document.querySelector("main")?.scrollBy?.(0, -90); });
  await sleep(900);
};
const wheel = (px) => async (p) => { await p.mouse.wheel(0, px); await sleep(900); };

// sections: { h, intro?, steps?: [..], table?: [[..]], head?: [..], shots?: [[url, caption, action?]] }
const GUIDES = {
  "hr-payroll-overview": {
    title: "HR & payroll — how the month flows", kicker: "Start here",
    intro: "The whole system on one page: the organisation and its people, punches that become attendance, leave, advances and loans, and the monthly payroll that brings them together.",
    chips: [["Organisation", "Divisions, departments, designations"], ["People", "Employees, photo, Urdu name"], ["Attendance", "Biometric punches, shifts, leave"], ["Advances", "Cash advance, salary loan"], ["Payroll", "Slips, deductions, posting"]],
    who: "<b>HR officer</b> (people, attendance) · <b>Timekeeper</b> (machines) · <b>Payroll officer</b> (structures, run) · <b>Accounts</b> (pay-outs) · <b>Management</b>",
    sections: [
      { h: "The month, step by step", head: ["When", "Who", "What happens"], table: [
        ["Once", "HR officer", "Divisions, departments and sub-departments; designations; employees with their device ID, shift and salary structure."],
        ["Every day", "Machines → sync PC", "Every punch reaches the ERP as a check-in; attendance is marked from the shift with a 30-minute grace."],
        ["During the month", "HR · leave approvers", "Leave applications approved; missing punches corrected; advances and loans requested, approved and paid out."],
        ["Month end", "Payroll officer", "Payroll entry: salary slips from attendance, with loan instalments and advance recovery deducted."],
        ["After the run", "Accounts", "Slips submitted and posted; salaries paid; loan balances go down by the month's instalment."]] },
      { h: "Where you work", steps: ["The <b>Desktop</b> opens the apps: <b>HR</b>, <b>Payroll</b> and <b>Help &amp; Guides</b>.", "Each app's home page shows today's figures and every page as an icon, grouped like the sidebar."],
        shots: [["/hr", "HR home: today's attendance, headcount and every HR page."], ["/payroll", "Payroll home: the last run and every payroll page."]] },
      { h: "Rules that keep it right", steps: ["Payroll is based on attendance: a working day with no attendance counts as absent.", "An approved document (advance, leave, salary slip) can be cancelled, never edited.", "A salary loan outside the loan policy needs an HR Manager's override reason, kept on the loan.", "Punches already sent are never sent twice; employees are matched by their attendance device ID."] },
    ] },
  organisation: {
    title: "Organisation — divisions, departments, designations", kicker: "HR officer guide",
    intro: "The organisation has three levels — division, department and sub-department — each with a code and an Urdu name. Designations are the job titles. Both show live headcount.",
    chips: [["Division", "Top level"], ["Department", "Under a division"], ["Sub-department", "Under a department"], ["Designation", "Job title, Urdu"], ["Headcount", "Rolled up"]],
    who: "<b>HR Manager</b> · <b>HR User</b>",
    sections: [
      { h: "Departments and headcount", steps: ["Open <b>HR → Departments</b>. Each card shows the level, the parent, and the active headcount (male / female).", "The headcount tree at the top rolls the numbers up: a division counts everybody in its departments and sub-departments. Click a division to open it."],
        shots: [["/hr/departments", "Departments: headcount by division, cards for every department."]] },
      { h: "A department on a full page", steps: ["<b>New</b>, or <b>Edit</b> on a card, opens the full-page form: name, <b>Urdu name</b>, company, parent, code and level.", "Approvers: who approves leave, expense claims and shift requests for this department.", "The figures on the right are live: staff, male, female, and the sub-departments under it."],
        shots: [[`/hr/departments/${enc(DIVISION)}`, "A division: details, Urdu name, approvers and its departments."]] },
      { h: "Typing Urdu", steps: ["Click any <b>Urdu name</b> field and type with the English keyboard: each letter becomes the Urdu letter with the same sound.", "Shift gives the extra letters. A real Urdu keyboard (Windows or Android) also works."],
        head: ["Key", "Urdu", "Key", "Urdu", "Shift + key", "Urdu"],
        table: [["a", "<span dir=rtl>ا</span>", "s", "<span dir=rtl>س</span>", "T", "<span dir=rtl>ٹ</span>"], ["b", "<span dir=rtl>ب</span>", "m", "<span dir=rtl>م</span>", "D", "<span dir=rtl>ڈ</span>"],
          ["p", "<span dir=rtl>پ</span>", "n", "<span dir=rtl>ن</span>", "R", "<span dir=rtl>ڑ</span>"], ["t", "<span dir=rtl>ت</span>", "h", "<span dir=rtl>ہ</span>", "N", "<span dir=rtl>ں</span>"]],
        shots: [["/hr/departments/new", "New department: the Urdu name field types right to left."]] },
      { h: "Designations", steps: ["<b>HR → Designations</b>: every job title with its abbreviation, Urdu name and headcount.", "The form works like the department form."],
        shots: [["/hr/designations", "Designations with their headcount."]] },
    ] },
  employees: {
    title: "Employees — new employee, profile, photo", kicker: "HR officer guide",
    intro: "Register an employee on one page — name in English and Urdu, CNIC, job, device ID and pay — add a passport photo, then follow everything about them from their profile.",
    chips: [["Personal", "Name, Urdu, CNIC"], ["Photo", "Camera or file"], ["Job", "Department, shift"], ["Pay", "Basic, bank"], ["Profile", "Tabs, connections"]],
    who: "<b>HR Manager</b> · <b>HR User</b>",
    sections: [
      { h: "The employee list", steps: ["<b>HR → Employees</b>: cards or a table, search by name, code or CNIC, filter by department or status."],
        shots: [["/hr/employees", "Employees."]] },
      { h: "New employee", steps: ["<b>New employee</b> opens the full page. Required: first name, gender, date of birth, company, date of joining and status.", "<b>Full Name (Urdu)</b> types Urdu from the English keyboard. CNIC must look like 00000-0000000-0.", "<b>Attendance Device ID</b> is the employee's user number on the biometric machine — punches are matched by it.", "<b>Photo</b>: passport size. <i>Take photo</i> uses the camera; <i>Upload</i> picks a file."],
        shots: [["/hr/employees/new", "New employee: personal details beside the passport photo."], ["/hr/employees/new", "Job, contact and pay.", wheel(700)]] },
      { h: "The profile", steps: ["Save opens the employee's page: the photo, name in English and Urdu, and coloured links to department, designation and manager.", "All tabs are in one row: overview, job, pay, attendance, leave and the rest.", "<b>Connections</b> lists everything linked to the employee — attendance, leave, advances, salary slips — with <i>+ New</i> for each type. <b>Activity</b> shows every change."],
        shots: [[`/hr/employees/${EMP}`, "An employee's profile."], [`/hr/employees/${EMP}`, "Connections: everything linked to the employee.", clickText("Connections")]] },
    ] },
  attendance: {
    title: "Biometric punches, shifts and attendance", kicker: "Timekeeper guide",
    intro: "ZKTeco machines in the halls record every punch. The sync PC at the site sends them to the ERP as check-ins, and attendance is marked from each employee's shift.",
    chips: [["Machine", "User number"], ["Sync PC", "Every few minutes"], ["Check-ins", "IN / OUT"], ["Shift", "30-min grace"], ["Attendance", "Present, late"]],
    who: "<b>Timekeeper</b> · <b>HR User</b> · <b>HR Manager</b>",
    sections: [
      { h: "The sync tool", steps: ["The <b>Biometric Sync</b> tool runs on the site PC. It lists each machine (name, IP, port, serial) with <i>Test</i>.", "Each run reads the new punches from every machine and pushes them to the ERP. Punches already sent are skipped, so a run can be repeated safely."],
        shots: [[`${SYNC}/`, "The sync tool: machines and recent runs.", null, true]] },
      { h: "Check-ins", steps: ["<b>HR → Checkins</b>: every punch with the employee, time, IN / OUT and the machine's serial.", "A punch is matched to the employee whose <b>Attendance Device ID</b> equals the user number on the machine."],
        shots: [["/hr/checkins", "Check-ins from the two machines."]] },
      { h: "Shifts and grace", head: ["Shift", "Hours", "Grace"], table: [["General", "08:30 – 16:30", "Late after 30 min, early exit 30 min"], ["Shift A", "06:00 – 14:00", "30 min"], ["Shift B", "14:00 – 22:00", "30 min"], ["Shift C", "22:00 – 06:00", "30 min"]],
        steps: ["<b>Shift Types</b> holds the hours and grace periods; change grace in <b>HR Setup</b>.", "<b>Roster</b> shows who works which shift on each day."],
        shots: [["/hr/shift-types", "Shift types."], ["/hr/roster", "Roster."]] },
      { h: "Attendance", steps: ["<b>HR → Attendance</b>: present, absent, late, early exit and leave for any period, by department.", "Missing punches: an <b>Attendance Requests</b> entry from the employee, or the <b>Employee Attendance Tool</b>."],
        shots: [["/hr/attendance", "Attendance for the month."]] },
    ] },
  leave: {
    title: "Leave and holidays", kicker: "HR officer guide",
    intro: "Holidays for the year, leave days per employee, and leave applications approved by the department's leave approver.",
    chips: [["Holidays", "Sundays, public"], ["Leave types", "Casual, sick…"], ["Allocation", "Days per year"], ["Application", "Employee asks"], ["Approval", "Leave approver"]],
    who: "<b>HR User</b> · <b>Leave approvers</b>",
    sections: [
      { h: "Holiday list", steps: ["<b>Holiday Lists</b>: the year's weekly offs (Sunday) and public holidays.", "It is assigned to the company, so payroll and attendance know the working days."],
        shots: [["/hr/holiday-lists", "Holiday lists."]] },
      { h: "Leave types and allocations", steps: ["<b>Leave Types</b>: casual, sick, annual, compensatory, leave without pay.", "<b>Leave Allocations</b>: each employee's days per type for the period."],
        shots: [["/hr/leave-types", "Leave types."], ["/hr/leave-allocations", "Leave allocations."]] },
      { h: "Leave applications", steps: ["<b>Leave Applications → New</b>: employee, leave type, from and to dates, reason.", "The department's leave approver approves or rejects; approved leave shows on attendance and in payroll."],
        shots: [["/hr/leave-applications", "Leave applications."]] },
    ] },
  "advances-loans": {
    title: "Cash advances and salary loans", kicker: "HR & accounts guide",
    intro: "A cash advance is recovered in full from the next salary; a salary loan in equal monthly instalments. Both are requested, approved, paid out and recovered from salary on one page.",
    chips: [["Request", "Advance or loan"], ["Eligibility", "Loan policy"], ["Approve", "Submit"], ["Pay out", "Cash or bank"], ["Recover", "From salary"]],
    who: "<b>HR</b> (request, approve) · <b>Accounts</b> (pay out) · <b>Payroll</b> (recovery) · <b>HR Manager</b> (override)",
    sections: [
      { h: "The list", steps: ["<b>HR → Employee Advances</b>: every advance and loan, its amount, instalments, repaid and status.", "<b>New advance / loan</b> opens the full-page form."],
        shots: [["/hr/advances", "Employee advances and loans."]] },
      { h: "A new salary loan", steps: ["Choose <b>Salary loan</b> at the top (or <b>Cash advance</b>).", "Pick the employee and enter the amount and purpose. <b>Quick pick</b> 3, 6, 9 or 12 months shows the monthly amount for each.", "The coloured card shows the monthly instalment and the first and last deduction month; the <b>instalment schedule</b> below previews every month.", "Add a <b>guarantor</b>. The eligibility check lists every rule of the loan policy with ✓ or ✗."],
        shots: [[`/hr/advances/new?employee=${EMP}`, "New salary loan: amount, months and the live instalment.", async (p) => { await clickBtn("Salary loan")(p); await p.locator('[data-field="advance_amount"] input').first().click(); await sleep(300); await p.locator('[data-field="advance_amount"] input').first().fill("48000"); await p.keyboard.press("Tab"); await clickBtn("6 months")(p); await wheel(-2000)(p); }],
          [`/hr/advances/new?employee=${EMP}`, "The schedule preview and the eligibility check.", async (p) => { await clickBtn("Salary loan")(p); await p.locator('[data-field="advance_amount"] input').first().click(); await sleep(300); await p.locator('[data-field="advance_amount"] input').first().fill("48000"); await p.keyboard.press("Tab"); await clickBtn("6 months")(p); await scrollTo("Instalment schedule")(p); }]] },
      { h: "Approve and pay out", steps: ["<b>Approve</b> submits the loan. A loan outside the policy needs an HR Manager's <b>override reason</b>.", "<b>Pay out</b> (choose Cash, Cheque, Wire Transfer or Bank Draft) makes the payment entry.", "For a loan the instalments are set up in payroll at once; for a cash advance press <b>Recover from next salary</b>."],
        shots: [[`/hr/advances/${DRAFT_LOAN}`, "A loan request waiting for approval."]] },
      { h: "Recovery from salary", steps: ["The steps at the top show where it is: Request → Approved → Paid out → Instalments → Recovered.", "Each row of the schedule turns <b>Deducted</b> when that month's salary slip takes the instalment, with a link to the slip.", "A cash advance shows <b>Returned</b> when the salary has recovered it."],
        shots: [[`/hr/advances/${LOAN}`, "A paid loan: progress, money and the instalment."], [`/hr/advances/${LOAN}`, "October deducted from salary, five months scheduled.", scrollTo("Instalment schedule")], [`/hr/advances/${ADVANCE}`, "A cash advance recovered in full from October's salary."]] },
      { h: "Salary loans and the ledger", steps: ["<b>Salary Loans</b>: outstanding, deducted this month against last, disbursed, and the loan ledger per employee."],
        shots: [["/hr/loans", "Salary loans: summary and ledger."]] },
      { h: "The loan policy", head: ["Rule", "Now", "Set in"], table: [["Who may borrow", "Full-time, 12 months' service", "HR Settings → Salary Loans"], ["Maximum loan", "3 × average gross pay", "″"], ["Maximum instalment", "30% of average net pay", "″"], ["Maximum term", "12 months", "″"], ["Guarantor", "Always; 24 months' service, no own loan, backs ≤ 2", "″"]] },
    ] },
  "salary-structures": {
    title: "Salary components and structures", kicker: "Payroll officer guide",
    intro: "Every line of a salary slip is a salary component. A salary structure combines them into a formula, and each employee is assigned a structure with their monthly base.",
    chips: [["Earnings", "Basic, allowances"], ["Deductions", "EOBI, PF, loans"], ["Structure", "Formula"], ["Assignment", "Employee + base"], ["Accounts", "Per company"]],
    who: "<b>Payroll officer</b> · <b>HR Manager</b>",
    sections: [
      { h: "Salary components", head: ["Earnings", "Deductions", "Notes"], table: [["Basic, House Rent, Conveyance, Medical, Medical (Exempt), Utilities, Meal, Other Allowance", "EOBI, Provident Fund, Income Tax", "Each component posts to its account for the company"], ["Overtime, Arrear, Leave Encashment", "Attendance Deduction, Canteen, Other Deductions", "Entered monthly as Additional Salary"], ["—", "Advance Recovery, Loan Recovery", "Set up automatically from advances and loans"]],
        shots: [["/payroll/salary-components", "Salary components."]] },
      { h: "Salary structures", steps: ["<b>Salary Structures</b>: the earnings and deductions for a group of staff, with formulas such as <code>base</code> or <code>B * 0.45</code>.", "Submit the structure before assigning it."],
        shots: [["/payroll/salary-structures", "Salary structures."]] },
      { h: "Structure assignments", steps: ["<b>Structure Assignments</b>: employee, structure, <b>base</b> (monthly pay) and from date.", "Many employees at once: <b>Bulk Salary Structure Assignment</b>.", "No assignment = no salary slip, and loan instalments can't be set up."],
        shots: [["/payroll/salary-structure-assignments", "Salary structure assignments."]] },
    ] },
  "payroll-run": {
    title: "Monthly payroll run", kicker: "Payroll officer guide",
    intro: "At month end one payroll entry makes every salary slip from attendance, with allowances, statutory deductions, loan instalments and advance recovery, then posts it to the accounts.",
    chips: [["Check", "Attendance, leave"], ["Entry", "Month, accounts"], ["Slips", "Draft, check"], ["Submit", "Post to books"], ["Pay", "Bank entry"]],
    who: "<b>Payroll officer</b> · <b>Accounts Manager</b>",
    sections: [
      { h: "Before the run", steps: ["Attendance complete — payroll is <b>based on attendance</b>, and a day with no attendance counts as <b>absent</b>.", "Leave approved; overtime, arrears and other one-off amounts entered as <b>Additional Salary</b>.", "Advances and loans paid: their deductions are already scheduled."],
        shots: [["/payroll/additional-salary", "Additional salary: one-off and recurring amounts, including loan instalments."]] },
      { h: "The payroll entry", steps: ["<b>Payroll Entries → New</b>: company, start and end of the month, payroll payable account, cost centre and payment account.", "Get the employees and submit: salary slips are created as drafts.", "Then submit the salary slips: they become final and the payroll is posted."],
        shots: [["/payroll/entries", "Payroll entries."], [`/payroll/entries/${PAYROLL}`, "October's payroll entry."]] },
      { h: "Salary slips", steps: ["<b>Salary Slips</b>: one per employee — payment days, earnings, deductions and net pay.", "Loan Recovery and Advance Recovery appear as deductions, linked to the advance."],
        shots: [["/payroll/salary-slips", "Salary slips for October."], [`/payroll/salary-slips/${enc(SLIP)}`, "A salary slip with the loan instalment deducted."]] },
      { h: "After the run", steps: ["Make the bank entry when salaries are paid.", "<b>Salary Loans</b> shows the month's deductions and the new balances."],
        shots: [["/hr/loans", "Salary loans after October's payroll."]] },
    ] },
};

function html(slug, g, shots) {
  const chips = g.chips.map(([t, d], i) => `<div class="chip"><b>${i + 1} · ${t}</b><span>${d}</span></div>`).join("");
  let n = 0;
  const sections = g.sections.map((s, si) => {
    const steps = (s.steps || []).map((t, i) => `<li><span class="sn">${i + 1}</span><span>${t}</span></li>`).join("");
    const head = s.head || ["Step", "Who", "What happens"];
    const table = s.table ? `<table><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>${s.table.map((r) => `<tr>${r.map((c, i) => `<td>${i ? c : `<b>${c}</b>`}</td>`).join("")}</tr>`).join("")}</table>` : "";
    const imgs = (s.shots || []).map(() => { const sh = shots[n++]; return sh ? `<figure><img src="data:image/jpeg;base64,${sh.data}"><figcaption>${sh.caption}</figcaption></figure>` : ""; }).join("");
    return `<section><h2><span class="n">${si + 1}</span>${s.h}</h2>${s.intro ? `<p>${s.intro}</p>` : ""}${table}${steps ? `<ol>${steps}</ol>` : ""}${imgs}</section>`;
  }).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${g.title}</title><style>
  @page{size:A4;margin:14mm 14mm 16mm}
  body{font:10.5pt/1.5 Ubuntu,"Noto Sans",Arial,sans-serif;color:#1f2937;margin:0}
  .cover{background:#0f1b2d;color:#fff;border-radius:12px;padding:26px 26px 20px}
  .kick{font:700 8.5pt Ubuntu,Arial;letter-spacing:.16em;text-transform:uppercase;color:#f5a524}
  h1{font:700 26pt/1.1 Ubuntu,Arial,sans-serif;margin:10px 0 10px}
  .intro{color:#d6dbe4;font-size:10.5pt;margin:0 0 14px}
  .chips{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
  .chip{background:#fff;color:#1f2937;border-radius:8px;padding:8px 9px;font-size:8.5pt;line-height:1.35}
  .chip b{display:block;font-size:9pt;margin-bottom:2px;color:#0f1b2d}
  .who{margin-top:12px;font-size:9pt;color:#d6dbe4}.who b{color:#fff}
  h2{font:700 14pt Ubuntu,Arial,sans-serif;margin:22px 0 8px;padding-bottom:6px;border-bottom:2px solid #f5a524;display:flex;align-items:center;gap:10px;break-after:avoid}
  .n{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#f5a524;color:#fff;font:700 11pt Ubuntu,Arial}
  ol{list-style:none;margin:6px 0 10px;padding:0}li{display:flex;gap:9px;margin:5px 0;break-inside:avoid}
  .sn{flex:none;display:inline-grid;place-items:center;width:19px;height:19px;border-radius:50%;background:#15803d;color:#fff;font:700 8.5pt Ubuntu,Arial;margin-top:1px}
  table{width:100%;border-collapse:collapse;font-size:9.5pt;margin:6px 0 10px}th{background:#eef1f5;text-align:left;padding:6px 8px}td{border-top:1px solid #e3e7ee;padding:6px 8px;vertical-align:top}
  figure{margin:10px 0 14px;break-inside:avoid}img{width:100%;border:1px solid #d6dbe4;border-radius:8px}
  figcaption{font-size:8.5pt;color:#6b7280;margin-top:4px}
  code{background:#eef1f5;border-radius:4px;padding:0 4px;font-size:9pt}
  .foot{margin-top:18px;font-size:8pt;color:#8a93a3;border-top:1px solid #e3e7ee;padding-top:6px}
  </style></head><body>
  <div class="cover"><div class="kick">Bao Gee Textile · HR &amp; Payroll · ${g.kicker}</div><h1>${g.title}</h1><p class="intro">${g.intro}</p>
  <div class="chips">${chips}</div><div class="who">Who: ${g.who}</div></div>
  ${sections}
  <div class="foot">Screens in this guide are from the Bao Gee Textile HR &amp; Payroll app with demo data (${new Date().toLocaleDateString("en-GB", { month: "long", year: "numeric" })}). Names, amounts and dates are examples.</div>
  </body></html>`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const only = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true, args: ["--hide-scrollbars"] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", locale: "en-GB", deviceScaleFactor: 1 });
  // guides use the light theme (the app's default for a new visitor is dark)
  await ctx.addInitScript(() => { try { localStorage.setItem("micromax-theme", "light"); } catch { /* blocked */ } });
  const r = await ctx.request.post(`${BASE}/api/method/login`, { data: { usr: USER, pwd: PWD } });
  if (!r.ok()) throw new Error(`login: ${r.status()}`);
  const p = await ctx.newPage();
  const printer = await browser.newPage();
  let failed = 0;
  for (const [slug, g] of Object.entries(GUIDES)) {
    if (only.length && !only.includes(slug)) continue;
    const shots = [];
    try {
      for (const s of g.sections) for (const [url, caption, action, optional] of s.shots || []) {
        try {
          await p.goto(url.startsWith("http") ? url : `${BASE}${url}`, { waitUntil: "networkidle", timeout: 30000 });
          await sleep(1500);
          if (action) await action(p);
          await p.evaluate(() => document.activeElement && document.activeElement.blur && document.activeElement.blur());
          await sleep(300);
          shots.push({ caption, data: (await p.screenshot({ type: "jpeg", quality: 82 })).toString("base64") });
        } catch (e) {
          if (!optional) throw e;
          console.warn("  (skipped optional screen)", url, e.message.split("\n")[0]);
          shots.push(null);
        }
      }
      await printer.setContent(html(slug, g, shots), { waitUntil: "load" });
      await printer.pdf({ path: path.join(OUT, `${slug}.pdf`), format: "A4", printBackground: true, margin: { top: "14mm", bottom: "16mm", left: "14mm", right: "14mm" } });
      console.log("✓", slug, `${shots.filter(Boolean).length} screens`);
    } catch (e) {
      failed += 1;
      console.error("✗", slug, e.message.split("\n")[0]);
      await p.screenshot({ path: path.join(require("os").tmpdir(), `baogee-guide-${slug}-fail.png`) }).catch(() => {});
    }
  }
  await browser.close();
  process.exitCode = failed ? 1 : 0;
})();
