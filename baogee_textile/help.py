"""Help centre for the React app (/help): user manuals per role (baogee_textile/manuals/*.md, rendered here), and the
guides (A4 PDFs with screenshots, public/help — in git) and demo videos (public/downloads/videos — copied to each server
by hand, like on the sugarcane site), grouped by the stage of the work. Same pattern as sugarcane.api.v1.help.

Rebuild the guides and videos from the demo data:  apps/baogee_textile/scripts/help/README.md
"""
import os
import re

import frappe
from frappe import _

APP = os.path.dirname(__file__)
DIR = os.path.join(APP, "manuals")
PUBLIC = os.path.join(APP, "public")

# In the order the work flows. "manuals": shown at the top of those manuals. A video is listed only when its file is on this server.
GUIDES = [
	{"slug": "hr-payroll-overview", "stage": "Start here", "title": "HR & payroll — how the month flows", "kind": "Guide",
		"summary": "The whole system on one page: organisation, employees, punches to attendance, leave, advances and loans, and the monthly payroll — who does what and when.",
		"pdf": "help/hr-payroll-overview.pdf", "video": None, "roles": ["all"], "manuals": ["getting-started", "management"]},
	{"slug": "video-full-hr", "stage": "Start here", "title": "Full HR walk-through", "kind": "Video",
		"summary": "One pass through HR: the organisation tree and headcount, an employee's profile, biometric punches and attendance, leave, and an advance.",
		"pdf": None, "video": "01-Full-HR-walkthrough.mp4", "roles": ["all"], "manuals": ["getting-started", "hr-officer", "management"]},
	{"slug": "video-full-payroll", "stage": "Start here", "title": "Full payroll month — attendance to salary slip", "kind": "Video",
		"summary": "One payroll month end to end: salary structure, attendance, loan instalments and advance recovery, the payroll entry, salary slips and the loan ledger.",
		"pdf": None, "video": "02-Full-payroll-month.mp4", "roles": ["all"], "manuals": ["getting-started", "payroll-officer", "management"]},
	{"slug": "organisation", "stage": "HR — organisation & people", "title": "Organisation — divisions, departments, designations", "kind": "Guide",
		"summary": "Division → Department → Sub-department, codes and Urdu names, designations, headcount by level, and typing Urdu from an English keyboard.",
		"pdf": "help/organisation.pdf", "video": "03-Organisation-departments-designations.mp4",
		"roles": ["HR Manager", "HR User"], "manuals": ["hr-officer"]},
	{"slug": "employees", "stage": "HR — organisation & people", "title": "Employees — new employee, profile, photo", "kind": "Guide",
		"summary": "The employee list, a new employee on a full page (English and Urdu name, CNIC, job, pay), the passport photo from camera or file, and the profile's tabs and connections.",
		"pdf": "help/employees.pdf", "video": "04-Employees-new-employee-and-profile.mp4",
		"roles": ["HR Manager", "HR User"], "manuals": ["hr-officer"]},
	{"slug": "attendance", "stage": "Attendance & leave", "title": "Biometric punches, shifts and attendance", "kind": "Guide",
		"summary": "ZKTeco machines and the sync tool, attendance device IDs, check-ins, shifts with the 30-minute grace, roster, attendance and late marks.",
		"pdf": "help/attendance.pdf", "video": "05-Biometric-punches-shifts-attendance.mp4",
		"roles": ["HR Manager", "HR User", "Timekeeper"], "manuals": ["hr-officer", "timekeeper"]},
	{"slug": "leave", "stage": "Attendance & leave", "title": "Leave and holidays", "kind": "Guide",
		"summary": "Holiday lists, leave types and allocations, leave applications and approval, and the leave dashboard.",
		"pdf": "help/leave.pdf", "video": "06-Leave-and-holidays.mp4",
		"roles": ["HR Manager", "HR User", "Leave Approver"], "manuals": ["hr-officer", "timekeeper"]},
	{"slug": "advances-loans", "stage": "Advances & loans", "title": "Cash advances and salary loans", "kind": "Guide",
		"summary": "A cash advance or a salary loan on one page: eligibility, guarantor, approval, pay-out, the instalment schedule, recovery from salary and the loan ledger.",
		"pdf": "help/advances-loans.pdf", "video": "07-Advances-and-salary-loans.mp4",
		"roles": ["HR Manager", "HR User", "Accounts User", "Accounts Manager"], "manuals": ["hr-officer", "payroll-officer", "accounts"]},
	{"slug": "salary-structures", "stage": "Payroll", "title": "Salary components and structures", "kind": "Guide",
		"summary": "Earnings and deductions (allowances, overtime, EOBI, PF, advance and loan recovery), salary structures and assigning them to employees.",
		"pdf": "help/salary-structures.pdf", "video": "08-Salary-components-and-structures.mp4",
		"roles": ["HR Manager", "Payroll Officer"], "manuals": ["payroll-officer"]},
	{"slug": "payroll-run", "stage": "Payroll", "title": "Monthly payroll run", "kind": "Guide",
		"summary": "Before the run, the payroll entry, salary slips with attendance and deductions, additional salary, submitting and posting, and checking the result.",
		"pdf": "help/payroll-run.pdf", "video": "09-Monthly-payroll-run.mp4",
		"roles": ["HR Manager", "Payroll Officer", "Accounts Manager"], "manuals": ["payroll-officer", "accounts", "management"]},
]
EVERYONE = {"System Manager", "HR Manager"}


def _guides(mine: set, manual: str | None = None) -> list:
	out = []
	for g in GUIDES:
		if manual and manual not in g["manuals"]:
			continue
		if not ("all" in g["roles"] or EVERYONE & mine or set(g["roles"]) & mine or manual):
			continue
		pdf = g["pdf"] if g["pdf"] and os.path.exists(os.path.join(PUBLIC, g["pdf"])) else None
		video = g["video"] if g["video"] and os.path.exists(os.path.join(PUBLIC, "downloads", "videos", g["video"])) else None
		if not pdf and not video:
			continue
		out.append({**{k: g[k] for k in ("slug", "title", "kind", "summary", "roles")}, "stage": g.get("stage", "More"), "order": len(out) + 1,
			"pdf_url": f"/assets/baogee_textile/{pdf}" if pdf else None,
			"video_url": f"/assets/baogee_textile/downloads/videos/{video}" if video else None,
			"mine": bool(set(g["roles"]) & mine)})
	return out


def _read(slug):
	path = os.path.join(DIR, f"{slug}.md")
	if not re.fullmatch(r"[a-z0-9-]+", slug or "") or not os.path.exists(path):
		frappe.throw(_("No such manual"), frappe.DoesNotExistError)
	text = open(path, encoding="utf-8").read()
	meta, body = {}, text
	m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
	if m:
		body = text[m.end():]
		for line in m.group(1).splitlines():
			k, _sep, v = line.partition(":")
			meta[k.strip()] = v.strip()
	roles = {r.strip() for r in meta.get("roles", "").split(",") if r.strip()}
	return {"slug": slug, "title": meta.get("title") or slug, "roles": sorted(roles), "order": int(meta.get("order") or 99), "body": body}


def _allowed(m, mine):
	return "all" in m["roles"] or EVERYONE & mine or set(m["roles"]) & mine


@frappe.whitelist(methods=["GET"])
def manuals() -> list:
	mine = set(frappe.get_roles())
	out = []
	for f in sorted(os.listdir(DIR)):
		if f.endswith(".md"):
			m = _read(f[:-3])
			out.append({"slug": m["slug"], "title": m["title"], "roles": m["roles"], "order": m["order"], "mine": bool(set(m["roles"]) & mine),
				"allowed": bool(_allowed(m, mine))})
	return sorted([m for m in out if m["allowed"]], key=lambda m: (m["order"], m["title"]))


@frappe.whitelist(methods=["GET"])
def manual(slug: str) -> dict:
	m = _read(slug)
	if not _allowed(m, set(frappe.get_roles())):
		frappe.throw(_("This manual is for another role"), frappe.PermissionError)
	from frappe.utils import md_to_html

	return {"slug": m["slug"], "title": m["title"], "roles": m["roles"], "html": md_to_html(m["body"]),
		"guides": _guides(set(frappe.get_roles()), slug)}


@frappe.whitelist(methods=["GET"])
def guides() -> list:
	"""Guides (PDF) and videos for the signed-in person's roles; HR managers see all."""
	return _guides(set(frappe.get_roles()))
