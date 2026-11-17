"""Upsert employees from the owner's master sheet (baogee-emp-list.xls) and remove duplicate employees.

The sheet is the current master: its values win. Each row is matched by CNIC (preferring the employee with the same code).
Where a CNIC belongs to two employees, the second is the person's earlier record that the old-site import created under
another code: its old-site id, leaving date and blank-filling data are merged into the sheet's record, its punches
(Employee Checkin) are moved over, and it is deleted.

    bench --site baogee execute baogee_textile.importers.master_sheet.run --kwargs "{'path': '…/baogee-emp-list.xls', 'dry_run': 1}"

Columns used: Division / Department / Sub Department, Code, Name, Name Urdu, CNIC, Designation, Basic Salary, Device Code
("LEFT" there = the employee has left), Date Of Birth, Date Of Joining. The salary columns are not employee data and are skipped.
"""
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime

import frappe
from frappe.utils import cint, flt, getdate

from baogee_textile.importers.legacy import (
	COMPANY, _department_lookup, _designation, _month_end, _years_before,
)

# Employee fields filled from a duplicate when blank on the sheet's record
MERGE_FIELDS = ["mm_legacy_id", "mm_father_name", "mm_father_name_urdu", "date_of_birth", "cell_number", "current_address",
	"permanent_address", "emergency_phone_number", "blood_group", "mm_city", "mm_province", "mm_qualification", "mm_experience",
	"employment_type", "mm_gross_salary", "salary_mode", "default_shift", "gender"]


def _s(v):
	if v is None or (isinstance(v, float) and v != v):
		return ""
	return " ".join(str(v).split())


def _code(v):
	return _s(v).upper()


def _sheet_date(v):
	"""datetime from Excel, or '21-02-2005' / '06.05.1989' / '5/11/2002' (day first)."""
	if isinstance(v, (datetime, date)):
		d = v.date() if isinstance(v, datetime) else v
	else:
		t = _s(v).replace("..", ".")
		d = None
		for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
			try:
				d = datetime.strptime(t, fmt).date()
				break
			except ValueError:
				continue
	return d if d and 1920 < d.year <= 2030 else None


def _device(v):
	if isinstance(v, (int, float)) and v == v:
		return str(int(v))
	return _code(v)


def _load(path):
	import pandas as pd
	x = pd.read_excel(os.path.expanduser(path))
	x.columns = [" ".join(str(c).split()) for c in x.columns]
	return [r for r in x.to_dict("records") if _s(r.get("CNIC")) or _s(r.get("Code"))]


def _last_salary_end(folder="~/Desktop"):
	"""legacy id → last salary period end, from the old-site file (for leaving dates)."""
	path = os.path.join(os.path.expanduser(folder), "baogee_legacy_hr.json")
	if not os.path.exists(path):
		return {}
	out = {}
	for r in json.load(open(path, encoding="utf-8")).get("Salary", []):
		lid, t = (r or {}).get("employeeDetailId"), (r or {}).get("toDate")
		if lid and t:
			d = getdate(t[:10])
			out[lid] = max(out.get(lid, d), d)
	return out


def run(path="~/Desktop/uploads/baogee-emp-list.xls", dry_run=1):
	dry_run = cint(dry_run)
	frappe.set_user("Administrator")
	rows = _load(path)
	log = [f"{'DRY RUN — nothing saved' if dry_run else 'UPDATE'} · {datetime.now():%Y-%m-%d %H:%M} · {len(rows)} sheet rows"]
	emps = frappe.get_all("Employee", {"company": COMPANY}, ["name", "employee_number", "cnic", "attendance_device_id"])
	by_cnic = defaultdict(list)
	for e in emps:
		if _s(e.cnic):
			by_cnic[_s(e.cnic)].append(e)
	device_owner = {_s(e.attendance_device_id): e.name for e in emps if _s(e.attendance_device_id)}
	sheet_devices = Counter(_device(r.get("Device Code")) for r in rows if _device(r.get("Device Code")).isdigit())
	clash = {d for d, n in sheet_devices.items() if n > 1}
	by_path, find_dept = _department_lookup()
	desig_cache, last_sal = {}, _last_salary_end()
	stats, problems = defaultdict(int), []

	for r in rows:
		cnic, code = _s(r.get("CNIC")), _code(r.get("Code"))
		hits = by_cnic.get(cnic, [])
		master = next((h for h in hits if _code(h.employee_number) == code), None) or (hits[0] if len(hits) == 1 else None)
		if not master:
			stats["not_found"] += 1
			problems.append(f"no employee for {code} {_s(r.get('Name'))} (CNIC {cnic})")
			continue
		doc = frappe.get_doc("Employee", master.name)
		remarks = []

		# ---- duplicates: same CNIC, other record → merge into the sheet's record, move punches, delete
		for dup_row in [h for h in hits if h.name != master.name]:
			dup = frappe.get_doc("Employee", dup_row.name)
			for f in MERGE_FIELDS:
				if dup.get(f) and not doc.get(f):
					doc.set(f, dup.get(f))
			if dup.relieving_date and not doc.relieving_date:
				doc.relieving_date = dup.relieving_date
			remarks.append(f"Merged duplicate {dup.name} (old-site code {dup.employee_number}, {dup.status}).")
			stats["duplicates_removed"] += 1
			n = frappe.db.count("Employee Checkin", {"employee": dup.name})
			stats["punches_moved"] += n
			if dup.attendance_device_id:
				device_owner.pop(_s(dup.attendance_device_id), None)
			if not dry_run:
				frappe.db.sql("update `tabEmployee Checkin` set employee=%s, employee_name=%s where employee=%s",
					(doc.name, doc.employee_name, dup.name))
				frappe.db.set_value("Employee", dup.name, "attendance_device_id", None, update_modified=False)
				frappe.delete_doc("Employee", dup.name, ignore_permissions=True, force=True)

		# ---- sheet values win
		full = _s(r.get("Name"))
		if full and _code(doc.employee_name) != _code(full):
			first, _sp, rest = full.partition(" ")
			doc.first_name, doc.middle_name, doc.last_name = first, None, rest or None
		doc.employee_number = code or doc.employee_number
		if _s(r.get("Name Urdu")):
			doc.mm_urdu_name = _s(r.get("Name Urdu"))
		doc.cnic = cnic
		if _s(r.get("Designation")):
			doc.designation = _designation(r.get("Designation"), desig_cache)
		dept = find_dept(r.get("Division"), r.get("Department"), r.get("Sub Department"))
		if dept:
			doc.department = dept
		if flt(r.get("Basic Salary")):
			doc.mm_basic_salary = flt(r.get("Basic Salary"))
		doj = _sheet_date(r.get("Date Of Joining"))
		if doj:
			doc.date_of_joining = doj
		dob = _sheet_date(r.get("Date Of Birth"))
		if dob and doc.date_of_joining and dob > _years_before(getdate(doc.date_of_joining), 14):
			remarks.append(f"Sheet date of birth {_s(r.get('Date Of Birth'))} is not possible: kept {doc.date_of_birth}.")
			dob = None
		elif not dob and _s(r.get("Date Of Birth")):
			remarks.append(f"Sheet date of birth '{_s(r.get('Date Of Birth'))}' unreadable: kept {doc.date_of_birth}.")
		if dob:
			doc.date_of_birth = dob

		dev = _device(r.get("Device Code"))
		if dev == "LEFT":
			doc.status = "Left"
			if not doc.relieving_date:
				end = last_sal.get(cint(doc.mm_legacy_id))
				doc.relieving_date = _month_end(end) if end else _month_end(getdate(doc.date_of_joining))
				remarks.append("Marked Left by the master sheet; leaving date set to last day of "
					+ ("last salary month." if end else "joining month (no salary found)."))
			else:
				remarks.append("Marked Left by the master sheet.")
			stats["marked_left"] += 1
		elif dev.isdigit():
			if dev in clash:
				if _s(doc.attendance_device_id) == dev:
					doc.attendance_device_id = None
				remarks.append(f"Device code {dev} appears twice in the master sheet: left blank, please confirm.")
				problems.append(f"device {dev} is on two rows of the sheet ({code} {full})")
				stats["device_clash"] += 1
			elif _s(doc.attendance_device_id) != dev:
				other = device_owner.get(dev)
				if other and other != doc.name:
					stats["device_taken_from_other"] += 1
					if not dry_run:
						frappe.db.set_value("Employee", other, "attendance_device_id", None, update_modified=False)
						_note(other, f"Device code {dev} moved to {doc.name} by the master sheet.")
				device_owner.pop(_s(doc.attendance_device_id), None)
				stats["device_set" if not doc.attendance_device_id else "device_changed"] += 1
				doc.attendance_device_id = dev
				device_owner[dev] = doc.name
			else:
				stats["device_same"] += 1
		if doc.relieving_date and getdate(doc.relieving_date) < getdate(doc.date_of_joining):
			doc.relieving_date = doc.date_of_joining
		if remarks:
			old = _s(doc.mm_import_remarks)
			doc.mm_import_remarks = "\n".join(([doc.mm_import_remarks] if old else []) + [m for m in remarks if m not in old])
		stats["updated"] += 1
		if not dry_run:
			doc.flags.ignore_mandatory = True
			doc.flags.ignore_links = True
			try:
				doc.save(ignore_permissions=True)
			except Exception as exc:
				frappe.clear_messages()
				stats["failed"] += 1
				problems.append(f"{doc.name} {code}: {exc}")
	log.append(str(dict(stats)))
	log += [f"  - {p}" for p in problems]
	frappe.db.rollback() if dry_run else frappe.db.commit()
	out = "\n".join(log)
	print(out)
	return out


def _note(name, text):
	old = frappe.db.get_value("Employee", name, "mm_import_remarks") or ""
	if text not in old:
		frappe.db.set_value("Employee", name, "mm_import_remarks", (old + "\n" if old else "") + text, update_modified=False)
