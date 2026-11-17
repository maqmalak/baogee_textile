"""One-time import of the old HR site's history (baogeetextile.pk, "Bao Gee Dyeing"): employees, attendance with time in /
out (also as check-ins), absent and leave days, and the half-monthly salary sheets.

The data is read in the browser from the old site (signed-in session) and saved as two JSON files:
- baogee_legacy_attendance.json: {"rows": [[docId, accountId, account, attendanceDate, timeIn, timeOut, worked, duty, ot], …]}
- baogee_legacy_hr.json: {"employeeList", "dailyWagerList", "Employee", "DailyWagers", "Salary", "Leave", "Absent",
  "absentList", "OT", "AdvanceDetail"} — the old site's own records, as its Recall / GetAll endpoints return them.

    bench --site baogee execute baogee_textile.importers.legacy.run --kwargs "{'folder': '/home/…/Downloads', 'dry_run': 1}"

Matching: the old site's employee code (codeUNI) is this site's employee_number. Its employee id is kept in
Employee.mm_legacy_id and links the attendance (accountId), leave (employeeId) and salary (code) records.

- Employees: matched by old employee id, then by code (a code shared by several people, e.g. DP/DGM/OPR-1000, also
  needs the name to match). Existing employees only get blank fields filled (placeholder joining / birth dates from the
  masters sheet are replaced). Missing old-site employees are created, Left with a leaving date if they left.
  Missing dates follow the owner's rules and are noted in Employee.mm_import_remarks:
    joining date  → 1st of the first salary month (attendance earlier than that moves it back to the first attendance)
    leaving date  → last day of the last salary month (for staff who left)
    date of birth → 18 years before the first salary month
  Gender is not on the old site: new employees get Male / Female from the name list below and stay mm_placeholder_data.
  Device codes reused by the old site go to working staff first; a clash is left blank and noted.
- Attendance: one record per employee per day (Present, or Half Day under 4 hours), with in / out time, working hours,
  duty hours and overtime; two check-ins (IN, OUT) linked to it, skip_auto_attendance set. Bulk-inserted, submitted,
  named ATT-OLD-… / CKIN-OLD-…; an existing record for that employee and day is left alone.
- Absent days → Attendance Absent; leave periods → Attendance On Leave (no leave type: the old site has none).
- Salary history → payroll: salary structures "BGT Half-Monthly" (Bimonthly) and "BGT Monthly", one assignment per
  employee (latest basic), one Payroll Entry per old period (HR-PRUN-OLD-…) and a submitted Salary Slip per employee
  (Sal Slip/<employee>/OLD-…) with Basic, Overtime, Advance / Loan / Other / OT Advance deductions exactly as the old
  sheet. The raw line is kept as a Legacy Salary Sheet linked both ways. No accounting entries for past periods.
  Advances, loans and overtime detail come later from the owner's Excel.

Re-running is safe: everything is matched or skipped. undo() removes everything except the employees.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

import frappe
from frappe.utils import cint, flt, getdate, now_datetime

COMPANY = "Bao Gee Textile"
FEMALE = {"AMNA", "IQRA", "NIDA", "MOMNA", "VANEEZA", "AYESHA", "FATIMA", "SANA", "SADIA", "MARIA", "ZAINAB", "KIRAN", "RABIA",
	"SAIMA", "NAZIA", "SHAZIA", "HINA", "MEHAK", "AQSA", "ALIZA", "ANAM", "ASMA", "BUSHRA", "FARAH", "HUMA", "IRAM", "JAVERIA",
	"KHADIJA", "LAIBA", "MAHNOOR", "NOOR", "RIDA", "SAMINA", "SHAMIM", "SOBIA", "TAHIRA", "UZMA", "YASMIN", "ZARA", "ZUBAIDA"}
DEVICE = "OLD-SITE"


def _load(folder, name):
	path = os.path.join(os.path.expanduser(folder), name)
	if not os.path.exists(path):
		frappe.throw(f"{path} not found")
	return json.load(open(path, encoding="utf-8"))


def _s(v):
	return " ".join(str(v or "").split())


def _date(v):
	v = _s(v)
	if not v or v in ("N/A", "0001-01-01"):
		return None
	for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%d/%m/%Y", "%d-%m-%Y"):
		try:
			d = datetime.strptime(v[:19], fmt).date()
			return d if 1900 < d.year <= 2100 else None
		except ValueError:
			continue
	return None


def _time(v):
	"""'26-10-26 08:00:00 AM' → datetime."""
	v = _s(v)
	for fmt in ("%d-%m-%y %I:%M:%S %p", "%d-%m-%Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
		try:
			return datetime.strptime(v, fmt)
		except ValueError:
			continue
	return None


def _employment_type(nature):
	"""Old site's employment nature -> Employment Type (Permanent with or without overtime)."""
	n = _s(nature).lower()
	if not n.startswith("permanent"):
		return None
	return "Permanent (no OT)" if "not allowed" in n else "Permanent (OT allowed)"


def _phone(v):
	"""Digits only (Pakistani mobile, e.g. 03046616376); anything that isn't 10–13 digits is dropped."""
	digits = re.sub(r"\D", "", _s(v))
	return digits if 10 <= len(digits) <= 13 else None


def _blood(v):
	"""'A+ve' → 'A+'."""
	v = _s(v).upper().replace("VE", "").replace("POSITIVE", "+").replace("NEGATIVE", "-").replace(" ", "")
	return v if v in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-") else None


def _shift(e, cache):
	"""Old shift (time in / out) → Shift Type with the same hours; created if none (e.g. '12 Hours' 08:00–20:00)."""
	tin, tout = _s(e.get("timeIn"))[11:16], _s(e.get("timeOut"))[11:16]
	if not (tin and tout):
		return None
	key = (tin, tout)
	if key not in cache:
		hit = frappe.db.get_value("Shift Type", {"start_time": tin + ":00", "end_time": tout + ":00"})
		if not hit:
			label = _s(e.get("shift")).title() or "Shift"
			hit = f"{label} ({tin}-{tout})"
			if not frappe.db.exists("Shift Type", hit):
				frappe.get_doc({"doctype": "Shift Type", "name": hit, "__newname": hit, "start_time": tin + ":00",
					"end_time": tout + ":00"}).insert(ignore_permissions=True)
		cache[key] = hit
	return cache[key]


def _gender(name):
	return "Female" if _s(name).split(" ")[0].upper() in FEMALE else "Male"


# ------------------------------------------------------------------ employees
def _department_lookup():
	"""(division, department, sub) of an old-site employee → this site's Department.

	First from the employees already here (the masters sheet came from the old site, so the paths are the same), then by
	the sub-department / department / division name under the right parent."""
	by_path = {}
	for e in frappe.get_all("Employee", {"company": COMPANY, "department": ["is", "set"]}, ["employee_number", "department"]):
		by_path.setdefault("code:" + _s(e.employee_number).upper(), e.department)
	import re
	depts = frappe.get_all("Department", {"company": COMPANY}, ["name", "department_name", "mm_level", "parent_department"])
	base = lambda t: re.sub(r"\s*\([^)]*\)\s*$", "", _s(t).upper())  # "DRYING (BLEACHING)" → "DRYING"  # noqa: E731
	children = defaultdict(list)
	for d in depts:
		children[d.parent_department].append(d)

	def child(parent, label):
		hits = [d.name for d in children.get(parent, []) if base(d.department_name) == label or _s(d.department_name).upper() == label]
		return hits[0] if len(hits) == 1 else None

	def find(div, dept, sub):
		div, dept, sub = (_s(x).upper() for x in (div, dept, sub))
		node = next((d.name for d in depts if d.mm_level == "Division" and base(d.department_name) == div), None)
		if not node:  # daily wagers have only a sub-department: take it when the name is unique
			label = sub or dept
			hits = [d.name for d in depts if label and (base(d.department_name) == label or _s(d.department_name).upper() == label)]
			return hits[0] if len(hits) == 1 else None
		for label in (dept, sub):
			if not label or label == base(frappe.db.get_value("Department", node, "department_name") or ""):
				continue  # a level named like its parent was merged into it
			nxt = child(node, label)
			if not nxt:
				break
			node = nxt
		return node

	return by_path, find


def _designation(name, cache):
	name = _s(name).title() if name else ""
	if not name:
		return None
	key = name.upper()
	if key not in cache:
		hit = frappe.db.get_value("Designation", {"designation_name": name}) or next(
			(d for d in frappe.get_all("Designation", pluck="name") if d.upper() == key), None)
		if not hit:
			hit = frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True).name
		cache[key] = hit
	return cache[key]


def _month_start(d):
	return d.replace(day=1)


def _month_end(d):
	return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _years_before(d, n):
	try:
		return d.replace(year=d.year - n)
	except ValueError:  # 29 Feb
		return d.replace(year=d.year - n, day=28)


def _salary_span(hr):
	"""legacy employee id → (first period start, last period end) of its salary lines."""
	span = {}
	for r in hr.get("Salary", []):
		lid, f, t = (r or {}).get("employeeDetailId"), _date((r or {}).get("fromDate")), _date((r or {}).get("toDate"))
		if lid and f and t:
			a, b = span.get(lid, (f, t))
			span[lid] = (min(a, f), max(b, t))
	return span


def _dates(e, first_att, last_att, span):
	"""Joining, leaving and birth dates for an old-site employee, and a remark for every date that had to be assumed."""
	lid, remarks = e.get("id"), []
	first_sal, last_sal = span.get(lid, (None, None))
	fmt = lambda d: f"{d:%b %Y}"  # noqa: E731
	doj = _date(e.get("doj"))
	if not doj:
		if first_sal:
			doj = _month_start(first_sal)
			remarks.append(f"Joining date missing on old site: set to 1st of first salary month ({fmt(first_sal)}).")
		elif first_att.get(lid):
			doj = _month_start(first_att[lid])
			remarks.append(f"Joining date missing on old site and no salary: set to 1st of first attendance month ({fmt(doj)}).")
		else:
			doj = getdate("2024-10-01")
			remarks.append("Joining date missing on old site, no salary or attendance: set to 1 Oct 2024 (start of old-site history).")
	if first_att.get(lid) and first_att[lid] < doj:
		remarks.append(f"Joining date {doj:%d-%m-%Y} moved back to first attendance {first_att[lid]:%d-%m-%Y}.")
		doj = first_att[lid]
	status = _s(e.get("status")).upper()
	left = status == "LEFT" or (e.get("isActive") is False and status != "WORKING")
	dol = _date(e.get("dol")) if left else None
	if left and not dol:
		if last_sal:
			dol = _month_end(last_sal)
			remarks.append(f"Leaving date missing on old site: set to last day of last salary month ({fmt(last_sal)}).")
		elif last_att.get(lid):
			dol = _month_end(last_att[lid])
			remarks.append(f"Leaving date missing on old site and no salary: set to last day of last attendance month ({fmt(dol)}).")
		else:
			dol = _month_end(doj)
			remarks.append("Leaving date missing on old site, no salary or attendance: set to last day of joining month.")
	if dol and dol < doj:
		dol = doj
	dob = _date(e.get("dob"))
	if dob and dob > _years_before(doj, 14):
		remarks.append(f"Date of birth on old site ({dob:%d-%m-%Y}) is not possible for joining {doj:%d-%m-%Y}: replaced.")
		dob = None
	if not dob:
		base = _month_start(first_sal) if first_sal else doj
		dob = _years_before(base, 18)
		what = "first salary month" if first_sal else "joining month (no salary)"
		remarks.append(f"Date of birth missing on old site: set to 18 years before {what} ({fmt(base)}).")
	return doj, dol, dob, left, remarks


def import_employees(hr, first_att, last_att, span, dry_run, log, plan):
	"""Upsert every old-site employee (and daily wager). Returns {legacy id: employee name}.

	Existing employees (matched by code) only get their blank fields filled; joining / birth dates from the masters sheet
	were placeholders, so on a placeholder employee those are replaced. New employees are created (Left with a leaving
	date if they left). Every assumed date is noted in mm_import_remarks."""
	recs = {e["id"]: e for e in hr.get("Employee", []) if e and e.get("id")}
	daily_ids = {e["id"] for e in hr.get("DailyWagers", []) + hr.get("dailyWagerList", []) if e and e.get("id")}
	for e in hr.get("DailyWagers", []):
		if e and e.get("id") and e["id"] not in recs:
			recs[e["id"]] = {**e, "nature": e.get("nature") or "Daily Wager"}
	for e in hr.get("employeeList", []) + hr.get("dailyWagerList", []):  # list rows for anyone whose detail failed
		recs.setdefault(e["id"], e)
	by_path, find_dept = _department_lookup()
	desig_cache = {}
	existing = {_s(r.employee_number).upper(): r for r in frappe.get_all("Employee", {"company": COMPANY},
		["name", "employee_number", "mm_legacy_id", "employee_name"])}
	code_count = defaultdict(int)
	for e in recs.values():
		code_count[_s(e.get("codeUNI")).upper()] += 1
	by_legacy = {r.mm_legacy_id: r.name for r in existing.values() if r.mm_legacy_id}
	for etype in ("Daily Wager", "Permanent (OT allowed)", "Permanent (no OT)"):
		if not frappe.db.exists("Employment Type", etype):
			frappe.get_doc({"doctype": "Employment Type", "employee_type_name": etype}).insert(ignore_permissions=True)
	stats = defaultdict(int)
	mapping, shift_cache = {}, {}
	used_devices = {str(d): n for n, d in frappe.get_all("Employee", {"attendance_device_id": ["is", "set"]},
		["name", "attendance_device_id"], as_list=1)}
	working_first = sorted(recs.items(), key=lambda kv: (_s(kv[1].get("status")).upper() != "WORKING", -cint(kv[0])))
	for lid, e in working_first:
		code = _s(e.get("codeUNI")).upper()
		full = _s(e.get("name"))
		row = existing.get(code) if code else None
		if row and code_count[code] > 1 and _s(row.employee_name).upper() != full.upper():
			row = None  # a code shared by several people on the old site (e.g. DP/DGM/OPR-1000): only match on the name too
		name = by_legacy.get(lid) or (row.name if row else None)
		doj, dol, dob, left, remarks = _dates(e, first_att, last_att, span)
		values = {
			"mm_legacy_id": lid, "mm_father_name": _s(e.get("fatherName")).title() or None,
			"attendance_device_id": str(e["deviceCode"]) if e.get("deviceCode") else None,
			"cnic": _s(e.get("cnic")) if len(_s(e.get("cnic"))) >= 13 else None,
			"mm_basic_salary": flt(e.get("basicSalary")) or None, "mm_urdu_name": _s(e.get("nameUrdu")) or None,
			"cell_number": _phone(e.get("contact1")), "current_address": _s(e.get("address1")) or None,
			"employment_type": "Daily Wager" if "Daily" in _s(e.get("nature")) or lid in daily_ids else _employment_type(e.get("nature")),
			"date_of_joining": doj, "date_of_birth": dob,
			"blood_group": _blood(e.get("bloodGroup")), "permanent_address": _s(e.get("address2")) or None,
			"emergency_phone_number": _phone(e.get("contact2")),
			"salary_mode": {"CASH": "Cash", "BANK": "Bank"}.get(_s(e.get("paymentType")).upper()),
			"default_shift": _shift(e, shift_cache),
			"mm_father_name_urdu": _s(e.get("fatherNameUrdu")) or None, "mm_gross_salary": flt(e.get("grossSalary")) or None,
			"mm_city": _s(e.get("city")).title() or None, "mm_province": _s(e.get("province")).title() or None,
			"mm_qualification": _s(e.get("qualification")) or None, "mm_experience": _s(e.get("experience")) or None,
			"mm_old_site_remarks": _s(e.get("remarks"))[:140] or None,
		}
		dev = values["attendance_device_id"]
		if dev and used_devices.get(dev) not in (None, name):
			remarks.append(f"Old-site device code {dev} is already used by another employee: left blank.")
			values["attendance_device_id"] = None
		if name:
			doc = frappe.get_doc("Employee", name)
			fill = {k: v for k, v in values.items() if v not in (None, "") and not doc.get(k)}
			if fill.get("attendance_device_id"):
				used_devices[fill["attendance_device_id"]] = name
			if doc.mm_placeholder_data:  # masters-sheet dates were placeholders
				for k in ("date_of_joining", "date_of_birth"):
					if getdate(doc.get(k)) != values[k]:
						fill[k] = values[k]
			if not doc.department:
				dept = by_path.get("code:" + code) or find_dept(e.get("division"), e.get("department"), e.get("subDepartment"))
				if dept:
					fill["department"] = dept
			if not doc.designation and e.get("designation"):
				fill["designation"] = _designation(e.get("designation"), desig_cache)
			note = [r for r in remarks if ("Joining" in r and "date_of_joining" in fill) or ("birth" in r and "date_of_birth" in fill)]
			note += [r for r in remarks if "device code" in r and not doc.attendance_device_id]
			if note:
				old = _s(doc.mm_import_remarks)
				fill["mm_import_remarks"] = "\n".join(([doc.mm_import_remarks] if old else []) + [n for n in note if n not in old])
				stats["remarks"] += 1
			if fill:
				stats["updated"] += 1
				if not dry_run:
					doc.db_set(fill, update_modified=False)
			else:
				stats["unchanged"] += 1
			plan[name] = {"name": doc.employee_name, "department": fill.get("department") or doc.department,
				"designation": fill.get("designation") or doc.designation, "doj": getdate(fill.get("date_of_joining") or doc.date_of_joining)}
			mapping[lid] = name
			continue
		if not full:
			stats["skipped_no_name"] += 1
			continue
		first_name, _sp, rest = full.partition(" ")
		dept = by_path.get("code:" + code) or find_dept(e.get("division"), e.get("department"), e.get("subDepartment"))
		desig = _designation(e.get("designation") or ("Daily Wager" if lid in daily_ids else None), desig_cache)
		doc = frappe.get_doc({
			"doctype": "Employee", "company": COMPANY, "first_name": first_name.title(), "last_name": rest.title() or None,
			"employee_number": (code if code_count[code] == 1 and code not in existing else f"{code}/{lid}") if code else f"OLD-{lid}", "gender": _gender(full),
			"status": "Left" if left else "Active", "relieving_date": dol if left else None,
			"department": dept, "designation": desig, "mm_placeholder_data": 1,
			"mm_import_remarks": "\n".join(remarks + ["Gender not on old site: guessed from the first name."]),
			**{k: v for k, v in values.items() if v is not None},
		})
		stats["created_left" if left else "created"] += 1
		if remarks:
			stats["remarks"] += 1
		if not dry_run:
			doc.flags.ignore_mandatory = True
			try:
				doc.insert(ignore_permissions=True)
			except Exception as exc:
				frappe.clear_messages()
				stats["failed"] += 1
				log.append(f"employee {lid} {full} not created: {exc}")
				continue
			key = doc.name
		else:
			key = f"(new {lid}) {full}"
		if values["attendance_device_id"]:
			used_devices[values["attendance_device_id"]] = key
		mapping[lid] = key
		plan[key] = {"name": full.title(), "department": dept, "designation": desig, "doj": doj}
	log.append(f"employees: {dict(stats)}")
	return mapping


# ------------------------------------------------------------------ attendance + check-ins
def _bulk(doctype, fields, rows, dry_run):
	if rows and not dry_run:
		for i in range(0, len(rows), 5000):
			frappe.db.bulk_insert(doctype, fields, rows[i:i + 5000], ignore_duplicates=True)


def import_attendance(att_rows, mapping, emp_info, dry_run, log, absent=(), leave=(), with_checkins=True):
	"""att_rows: (legacy id, date, in datetime, out datetime, worked, duty, ot) → Attendance + 2 check-ins per day."""
	have = set()
	for r in frappe.db.sql("select employee, attendance_date from tabAttendance where docstatus < 2"):
		have.add((r[0], r[1]))
	now = now_datetime()
	owner = frappe.session.user
	att_fields = ["name", "naming_series", "employee", "employee_name", "company", "department", "attendance_date", "status",
		"in_time", "out_time", "working_hours", "standard_working_hours", "actual_overtime_duration", "leave_type",
		"docstatus", "creation", "modified", "owner", "modified_by"]
	ck_fields = ["name", "employee", "employee_name", "log_type", "time", "device_id", "skip_auto_attendance", "attendance",
		"creation", "modified", "owner", "modified_by"]
	att, ck = [], []
	# continue after the highest number used, so names never collide after a period was replaced
	seq = cint(frappe.db.sql("select ifnull(max(cast(substring_index(name, '-', -1) as unsigned)), 0) from tabAttendance where name like 'ATT-OLD-%%'")[0][0])
	ckseq = cint(frappe.db.sql("select ifnull(max(cast(substring_index(name, '-', -1) as unsigned)), 0) from `tabEmployee Checkin` where name like 'CKIN-OLD-%%'")[0][0])
	stats = defaultdict(int)

	def add(emp, day, status, tin=None, tout=None, worked=0, duty=0, ot=0):
		nonlocal seq, ckseq
		info = emp_info[emp]
		if (emp, day) in have:
			stats["already"] += 1
			return
		if info["doj"] and day < info["doj"]:
			stats["before_joining"] += 1
			return
		have.add((emp, day))
		seq += 1
		name = f"ATT-OLD-{day.year}-{seq:07d}"
		att.append((name, "HR-ATT-.YYYY.-", emp, info["name"], COMPANY, info["department"], day, status, tin, tout,
			flt(worked, 2), flt(duty, 2), flt(ot, 2), None, 1, now, now, owner, owner))
		stats[status] += 1
		for kind, t in (("IN", tin), ("OUT", tout)) if with_checkins else ():
			if t:
				ckseq += 1
				ck.append((f"CKIN-OLD-{ckseq:08d}", emp, info["name"], kind, t, DEVICE, 1, name, now, now, owner, owner))
				stats["checkins"] += 1

	for lid, day, tin, tout, worked, duty, ot in att_rows:
		emp = mapping.get(lid)
		if not emp:
			stats["no_employee"] += 1
			continue
		if tout and tin and tout < tin:
			tout += timedelta(days=1)  # night shift
		add(emp, day, "Half Day" if 0 < flt(worked) < 4 else "Present", tin, tout, worked, duty, ot)
	for lid, day in absent:
		emp = mapping.get(lid)
		if emp:
			add(emp, day, "Absent")
	for lid, day in leave:
		emp = mapping.get(lid)
		if emp:
			add(emp, day, "On Leave")
	_bulk("Attendance", att_fields, att, dry_run)
	_bulk("Employee Checkin", ck_fields, ck, dry_run)
	log.append(f"attendance: {dict(stats)}")


# ------------------------------------------------------------------ salary history → payroll
HALF, FULL = "BGT Half-Monthly", "BGT Monthly"
COMPONENTS = {  # old-sheet field → (component, abbr, type, account)
	"earned": ("Basic", "B", "Earning", "Salary - BGT"),
	"ot": ("Overtime", "OT", "Earning", "Salary - BGT"),
	"advance": ("Advance Recovery", "ADVR", "Deduction", "Employee Advances - BGT"),
	"loan": ("Loan Recovery", "LR", "Deduction", "Employee Advances - BGT"),
	"deduction": ("Other Deductions", "OD", "Deduction", "Salary - BGT"),
	"otAdvance": ("OT Advance Recovery", "OTA", "Deduction", "Employee Advances - BGT"),
}


def _setup_payroll():
	"""Components (with accounts) and the two salary structures the history and future payroll use."""
	for comp, abbr, kind, account in COMPONENTS.values():
		if not frappe.db.exists("Salary Component", comp):
			frappe.get_doc({"doctype": "Salary Component", "salary_component": comp, "salary_component_abbr": abbr,
				"type": kind, "depends_on_payment_days": 0}).insert(ignore_permissions=True)
		if frappe.db.exists("Account", account) and not frappe.db.exists("Salary Component Account", {"parent": comp, "company": COMPANY}):
			c = frappe.get_doc("Salary Component", comp)
			c.append("accounts", {"company": COMPANY, "account": account})
			c.save(ignore_permissions=True)
	for name, freq, formula in ((HALF, "Bimonthly", "base / 2"), (FULL, "Monthly", "base")):
		if frappe.db.exists("Salary Structure", name):
			continue
		ss = frappe.get_doc({"doctype": "Salary Structure", "name": name, "__newname": name, "company": COMPANY,
			"currency": "PKR", "payroll_frequency": freq, "is_active": "Yes",
			"earnings": [{"salary_component": "Basic", "abbr": "B", "amount_based_on_formula": 1, "formula": formula,
				"depends_on_payment_days": 1}]})
		ss.insert(ignore_permissions=True)
		ss.submit()


def import_payroll(sheets, by_code, by_legacy, emp_info, dry_run, log):
	"""Old salary lines → Legacy Salary Sheet (raw) + Payroll Entry per period + submitted Salary Slip per employee,
	plus one Salary Structure Assignment per employee. Bulk-inserted: no accounting entries for past periods."""
	_setup_payroll()
	now, owner = now_datetime(), frappe.session.user
	payable = frappe.db.get_value("Company", COMPANY, "default_payroll_payable_account") or "Payroll Payable - BGT"
	cost_center = frappe.db.get_value("Company", COMPANY, "cost_center") or "Main - BGT"
	have_slip = set(frappe.get_all("Salary Slip", {"name": ["like", "Sal Slip/%/OLD-%"]}, pluck="name"))
	have_ssa = set(frappe.get_all("Salary Structure Assignment", {"docstatus": 1}, pluck="employee"))
	stats = defaultdict(int)
	seen, periods, last_line, first_from = set(), defaultdict(list), {}, {}
	for r in sheets:
		if not r:
			continue
		f, t = _date(r.get("fromDate")), _date(r.get("toDate"))
		key = (cint(r.get("docId")), _s(r.get("code")).upper(), f)
		if key in seen or not f or not t:
			stats["duplicate"] += 1
			continue
		seen.add(key)
		if not any(flt(r.get(k)) for k in ("presents", "earned", "netSalary", "ot", "net", "advance", "loan", "deduction")):
			stats["all_zero"] += 1
			continue
		emp = by_legacy.get(r.get("employeeDetailId")) or by_code.get(_s(r.get("code")).upper())
		if not emp or emp not in emp_info:
			stats["no_employee"] += 1
			continue
		periods[(f, t)].append((emp, r))
		if emp not in last_line or t > _date(last_line[emp].get("toDate")):
			last_line[emp] = r
		first_from[emp] = min(first_from.get(emp, f), f)

	pe_rows, ped_rows, slip_rows, det_rows, sheet_rows, ssa_rows = [], [], [], [], [], []
	for emp, r in last_line.items():  # salary structure assignment: latest basic, frequency of the latest period
		if emp in have_ssa:
			continue
		info = emp_info[emp]
		f, t = _date(r.get("fromDate")), _date(r.get("toDate"))
		ssa_rows.append((f"HR-SSA-OLD-{emp}"[:140], emp, info["name"], info["department"], info["designation"],
			HALF if (t - f).days <= 16 else FULL, min(info["doj"] or first_from[emp], first_from[emp]), COMPANY,
			flt(r.get("basicSalary")), "PKR", payable, 1, now, now, owner, owner))
	for (f, t), lines in sorted(periods.items()):
		freq = "Bimonthly" if (t - f).days <= 16 else "Monthly"
		pe = f"HR-PRUN-OLD-{f:%Y%m%d}-{t:%Y%m%d}"
		posting = max((_date(r.get("date")) or t) for _e, r in lines)
		done = set()
		for emp, r in lines:
			slip = f"Sal Slip/{emp}/OLD-{f:%Y%m%d}-{t:%d}"
			if slip in have_slip or slip in done:
				stats["slip_exists"] += 1
				continue
			done.add(slip)
			info = emp_info[emp]
			sheet = frappe.generate_hash(length=12)
			earn = [(k, flt(r.get(k))) for k in ("earned", "ot") if flt(r.get(k))]
			ded = [(k, flt(r.get(k))) for k in ("advance", "loan", "deduction", "otAdvance") if flt(r.get(k))]
			gross, total_ded = sum(a for _k, a in earn), sum(a for _k, a in ded)
			net = gross - total_ded
			days = (t - f).days + 1
			slip_rows.append((slip, emp, info["name"], info["department"], info["designation"], COMPANY, posting, f, t, freq,
				HALF if freq == "Bimonthly" else FULL, pe, "PKR", 1, days, min(days, flt(r.get("presents")) + flt(r.get("restDays"))),
				gross, gross, total_ded, total_ded, net, net, round(net), round(net), gross, "Submitted", sheet, 1, now, now, owner, owner))
			for field, kind in ((earn, "earnings"), (ded, "deductions")):
				for i, (k, amt) in enumerate(field, 1):
					comp, abbr, _t, _a = COMPONENTS[k]
					det_rows.append((frappe.generate_hash(length=10), slip, "Salary Slip", kind, i, comp, abbr, amt, amt, 1, now, now, owner, owner))
			ped_rows.append((frappe.generate_hash(length=10), pe, "Payroll Entry", "employees", len(done), emp, info["name"],
				info["department"], info["designation"], 1, now, now, owner, owner))
			sheet_rows.append((sheet, emp, _s(r.get("employee")) or info["name"], _s(r.get("code")), _s(r.get("designation")),
				f, t, _date(r.get("date")), cint(r.get("docId")), slip, pe,
				flt(r.get("presents")), flt(r.get("restDays")), flt(r.get("workHours")), flt(r.get("restHours")), flt(r.get("otHours")),
				flt(r.get("basicSalary")), flt(r.get("earned")), flt(r.get("advance")), flt(r.get("loan")), flt(r.get("deduction")),
				flt(r.get("netSalary")), flt(r.get("ot")), flt(r.get("otAdvance")), flt(r.get("netOT")), flt(r.get("net")), 0, now, now, owner, owner))
			stats["slips"] += 1
			stats["gross"] += gross
			stats["advance"] += flt(r.get("advance"))
			stats["loan"] += flt(r.get("loan"))
			stats["ot"] += flt(r.get("ot"))
			stats["net"] += net
		if done and not frappe.db.exists("Payroll Entry", pe):
			pe_rows.append((pe, COMPANY, posting, freq, f, t, len(done), "PKR", 1, payable, cost_center, 1, 1, "Submitted", 0, 1, now, now, owner, owner))
			stats["payroll_runs_" + freq.lower()] += 1
	stats["assignments"] = len(ssa_rows)
	_bulk("Salary Structure Assignment", ["name", "employee", "employee_name", "department", "designation", "salary_structure",
		"from_date", "company", "base", "currency", "payroll_payable_account", "docstatus", "creation", "modified", "owner", "modified_by"],
		ssa_rows, dry_run)
	_bulk("Payroll Entry", ["name", "company", "posting_date", "payroll_frequency", "start_date", "end_date", "number_of_employees",
		"currency", "exchange_rate", "payroll_payable_account", "cost_center", "salary_slips_created", "salary_slips_submitted", "status",
		"validate_attendance", "docstatus", "creation", "modified", "owner", "modified_by"], pe_rows, dry_run)
	_bulk("Payroll Employee Detail", ["name", "parent", "parenttype", "parentfield", "idx", "employee", "employee_name", "department",
		"designation", "docstatus", "creation", "modified", "owner", "modified_by"], ped_rows, dry_run)
	_bulk("Salary Slip", ["name", "employee", "employee_name", "department", "designation", "company", "posting_date", "start_date",
		"end_date", "payroll_frequency", "salary_structure", "payroll_entry", "currency", "exchange_rate", "total_working_days",
		"payment_days", "gross_pay", "base_gross_pay", "total_deduction", "base_total_deduction", "net_pay", "base_net_pay",
		"rounded_total", "base_rounded_total", "total_earnings", "status", "mm_legacy_sheet", "docstatus", "creation", "modified", "owner", "modified_by"],
		slip_rows, dry_run)
	_bulk("Salary Detail", ["name", "parent", "parenttype", "parentfield", "idx", "salary_component", "abbr", "amount", "default_amount",
		"docstatus", "creation", "modified", "owner", "modified_by"], det_rows, dry_run)
	_bulk("Legacy Salary Sheet", ["name", "employee", "employee_name", "employee_code", "designation", "from_date", "to_date",
		"posting_date", "legacy_doc_id", "salary_slip", "payroll_entry", "presents", "rest_days", "work_hours", "rest_hours", "ot_hours",
		"basic_salary", "earned", "advance", "loan", "deduction", "net_salary", "ot", "ot_advance", "net_ot", "net", "docstatus",
		"creation", "modified", "owner", "modified_by"], sheet_rows, dry_run)
	log.append("payroll history: " + str({k: (round(v) if isinstance(v, float) else v) for k, v in stats.items()}))


# ------------------------------------------------------------------ run
def run(folder="~/Downloads", dry_run=1, parts="employees,attendance,payroll"):
	"""dry_run=1 (default) reports what would happen and changes nothing."""
	dry_run, parts = cint(dry_run), {p.strip() for p in parts.split(",")}
	frappe.set_user("Administrator")
	hr = _load(folder, "baogee_legacy_hr.json")
	att_file = _load(folder, "baogee_legacy_attendance.json") if parts & {"attendance", "employees"} else {"rows": []}
	log = [f"{'DRY RUN — nothing saved' if dry_run else 'IMPORT'} · {datetime.now():%Y-%m-%d %H:%M}"]

	# attendance rows, de-duplicated per employee and day (the latest document wins)
	latest = {}
	for doc_id, lid, _name, day, tin, tout, worked, duty, ot in att_file.get("rows", []):
		d = _date(day)
		if not d or not lid:
			continue
		key = (lid, d)
		if key not in latest or doc_id > latest[key][0]:
			latest[key] = (doc_id, _time(tin), _time(tout), worked, duty, ot)
	first_att, last_att = {}, {}
	for (lid, d) in latest:
		first_att[lid] = min(first_att.get(lid, d), d)
		last_att[lid] = max(last_att.get(lid, d), d)
	log.append(f"attendance file: {len(att_file.get('rows', []))} rows → {len(latest)} employee-days")

	plan = {}
	mapping = import_employees(hr, first_att, last_att, _salary_span(hr), dry_run, log, plan) if "employees" in parts else {
		r.mm_legacy_id: r.name for r in frappe.get_all("Employee", {"mm_legacy_id": ["is", "set"]}, ["name", "mm_legacy_id"])}

	emp_info = {r.name: {"name": r.employee_name, "department": r.department, "designation": r.designation,
		"doj": getdate(r.date_of_joining) if r.date_of_joining else None}
		for r in frappe.get_all("Employee", {"company": COMPANY}, ["name", "employee_name", "department", "designation", "date_of_joining"])}
	if dry_run:
		emp_info.update(plan)  # use what the import would set

	if "attendance" in parts:
		rows = [(lid, d, v[1], v[2], v[3], v[4], v[5]) for (lid, d), v in sorted(latest.items(), key=lambda kv: kv[0][1])]
		import_attendance(rows, mapping, emp_info, dry_run, log, _absent_days(hr), _leave_days(hr))

	if "payroll" in parts:
		by_code = {_s(e.employee_number).upper(): e.name for e in frappe.get_all("Employee", {"company": COMPANY}, ["name", "employee_number"])}
		import_payroll(hr.get("Salary", []), by_code, mapping, emp_info, dry_run, log)

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()
	out = "\n".join(log)
	print(out)
	return out


def _absent_days(hr):
	"""Absent documents: the list gives the employee's name per document, the detail its days."""
	names = defaultdict(list)
	for e in hr.get("employeeList", []):
		names[_s(e.get("name")).upper()].append(e["id"])
	doc_emp = {}
	for r in hr.get("absentList", []):
		ids = names.get(_s(r.get("account")).upper(), [])
		if len(ids) == 1:
			doc_emp[r["docId"]] = ids[0]
	out = []
	for r in hr.get("Absent", []):
		lid, d = doc_emp.get(r.get("docId")), _date(r.get("attendanceDate"))
		if lid and d:
			out.append((lid, d))
	return out


def _leave_days(hr):
	out = []
	for r in hr.get("Leave", []):
		f, t, lid = _date(r.get("fromDate")), _date(r.get("toDate")), r.get("employeeId")
		if not (f and t and lid) or (t - f).days > 60:
			continue
		d = f
		while d <= t:
			out.append((lid, d))
			d += timedelta(days=1)
	return out


def undo():
	"""Remove the imported attendance, check-ins, payroll history and salary sheets (employees are kept)."""
	frappe.db.sql("set sql_safe_updates=0")
	frappe.db.sql("delete from `tabEmployee Checkin` where name like 'CKIN-OLD-%%'")
	frappe.db.sql("delete from tabAttendance where name like 'ATT-OLD-%%'")
	frappe.db.sql("delete from `tabSalary Detail` where parenttype='Salary Slip' and parent like 'Sal Slip/%%/OLD-%%'")
	frappe.db.sql("delete from `tabSalary Slip` where name like 'Sal Slip/%%/OLD-%%'")
	frappe.db.sql("delete from `tabPayroll Employee Detail` where parent like 'HR-PRUN-OLD-%%'")
	frappe.db.sql("delete from `tabPayroll Entry` where name like 'HR-PRUN-OLD-%%'")
	frappe.db.sql("delete from `tabSalary Structure Assignment` where name like 'HR-SSA-OLD-%%'")
	frappe.db.sql("delete from `tabLegacy Salary Sheet`")
	frappe.db.commit()
	return "Removed old-site attendance, check-ins, payroll runs, salary slips, assignments and salary sheets."


def run_period(file="~/Desktop/baogee_legacy_nov.json", from_date="2026-11-01", to_date=None, dry_run=1, with_checkins=0, replace=0):
	"""Attendance (and absent / leave days) for a recent period, pulled from the old site into one JSON file:
	{"rows": [...attendance rows...], "Absent": [...], "absentList": [...], "Leave": [...]}.

	Check-ins are not created by default: the gate machine's own punches for the period are already here."""
	dry_run, from_date = cint(dry_run), getdate(from_date)
	to_date = getdate(to_date) if to_date else getdate("2100-12-31")
	frappe.set_user("Administrator")
	data = _load(*os.path.split(os.path.expanduser(file)))
	hr_path = os.path.expanduser("~/Desktop/baogee_legacy_hr.json")
	names = json.load(open(hr_path, encoding="utf-8")) if os.path.exists(hr_path) else {}
	data["employeeList"] = names.get("employeeList", []) + names.get("dailyWagerList", [])
	log = [f"{'DRY RUN — nothing saved' if dry_run else 'IMPORT'} · attendance {from_date} to {to_date} · {datetime.now():%Y-%m-%d %H:%M}"]
	latest = {}
	for doc_id, lid, _name, day, tin, tout, worked, duty, ot in data.get("rows", []):
		d = _date(day)
		if not d or not lid or d < from_date or d > to_date:
			continue
		if (lid, d) not in latest or doc_id > latest[(lid, d)][0]:
			latest[(lid, d)] = (doc_id, _time(tin), _time(tout), worked, duty, ot)
	mapping = {r.mm_legacy_id: r.name for r in frappe.get_all("Employee", {"mm_legacy_id": ["is", "set"]}, ["name", "mm_legacy_id"])}
	unknown = {lid for (lid, _d) in latest if lid not in mapping}
	emp_info = {r.name: {"name": r.employee_name, "department": r.department, "doj": getdate(r.date_of_joining) if r.date_of_joining else None}
		for r in frappe.get_all("Employee", {"company": COMPANY}, ["name", "employee_name", "department", "date_of_joining"])}
	rows = [(lid, d, v[1], v[2], v[3], v[4], v[5]) for (lid, d), v in sorted(latest.items(), key=lambda kv: kv[0][1])]
	if cint(replace):  # drop this period's earlier old-site import (attendance + its punches) first
		old = frappe.db.sql_list("select name from tabAttendance where name like 'ATT-OLD-%%' and attendance_date between %s and %s",
			(from_date, to_date))
		if old:
			frappe.db.sql("delete from `tabEmployee Checkin` where name like 'CKIN-OLD-%%' and attendance in %s", (old,))
			frappe.db.sql("update `tabEmployee Checkin` set attendance = null where attendance in %s", (old,))
			frappe.db.sql("delete from tabAttendance where name in %s", (old,))
		log.append(f"replaced: removed {len(old)} earlier old-site attendance records for the period")
	absent = [(l, d) for l, d in _absent_days(data) if from_date <= d <= to_date]
	# the old site's Absent detail page fails (HTTP 500) for many documents: then the list's employee name and date are used
	detailed = {r.get("__doc") or r.get("docId") for r in data.get("Absent", [])}
	ids_by_name = defaultdict(list)
	for e in data["employeeList"]:
		ids_by_name[_s(e.get("name")).upper()].append(e["id"])
	for r in data.get("absentList", []):
		ids, d = ids_by_name.get(_s(r.get("account")).upper(), []), _date(r.get("transactionDate"))
		if r.get("docId") not in detailed and len(ids) == 1 and d and from_date <= d <= to_date:
			absent.append((ids[0], d))
	leave = [(l, d) for l, d in _leave_days(data) if from_date <= d <= to_date]
	log.append(f"file: {len(data.get('rows', []))} rows → {len(latest)} employee-days; {len(absent)} absent, {len(leave)} leave days; "
		f"{len(unknown)} old-site employees not on this site")
	import_attendance(rows, mapping, emp_info, dry_run, log, absent, leave, with_checkins=cint(with_checkins))
	frappe.db.rollback() if dry_run else frappe.db.commit()
	out = "\n".join(log)
	print(out)
	return out
