"""Import Baogee's HR masters from baogee_masters.xls: departments (Division → Department → Sub Department), designations
and employees, each with its Urdu name.

    bench --site baogee execute baogee_textile.importers.masters.run --kwargs "{'path': 'baogee_masters.xls'}"
    (add 'dry_run': 1 to only report what would change)

Safe to re-run: departments are matched by name, designations by name, employees by CNIC — existing records are
updated, not duplicated.

The sheet has no gender, date of birth or joining date, which ERPNext requires on an Employee; placeholders are used
(PLACEHOLDER below) and the employee's "not confirmed" box (mm_placeholder_data) is ticked so they can be found and
corrected.
"""

import re

import frappe

COMPANY = "Bao Gee Textile"
PLACEHOLDER = {"gender": "Male", "date_of_birth": "1990-01-01", "date_of_joining": "2026-10-01"}
# Placeholder rows in the department sheets, not real departments.
JUNK = {"", "N/AA", "N/AAA", "NULLL", "NULLLL", "NAN"}
URDU = re.compile(r"[؀-ۿ]")


def _s(v) -> str:
	"""Cell → trimmed text with single spaces ('' for empty / NaN)."""
	if v is None or (isinstance(v, float) and v != v):
		return ""
	return re.sub(r"\s+", " ", str(v)).strip()


def _urdu(v) -> str:
	"""Keep a cell only when it is actually Urdu (some 'urdu' cells repeat the English name)."""
	v = _s(v)
	return v if URDU.search(v) else ""


def _read(path):
	import pandas as pd

	from frappe.utils import get_bench_path

	full = path if path.startswith("/") else f"{get_bench_path()}/{path}"  # relative to the bench folder
	sheets = pd.read_excel(full, sheet_name=None, dtype=str)
	return {k.strip().lower(): v for k, v in sheets.items()}


def _canon(key):
	"""A level named like its parent is the same place (division BLEACHING → department BLEACHING): merge it."""
	return tuple(x for i, x in enumerate(key) if i == 0 or x != key[i - 1])


def _department_tree(sheets):
	"""Nodes keyed (division,), (division, department), (division, department, sub) with Urdu name, code and level."""
	nodes = {}

	def node(key, label, level, urdu="", code=""):
		key = _canon(key)
		label = key[-1]
		n = nodes.setdefault(key, {"key": key, "label": label, "level": level, "urdu": "", "code": ""})
		n["urdu"] = n["urdu"] or urdu
		n["code"] = n["code"] or code
		return n

	div_urdu, div_code = {}, {}
	for _, r in sheets["division"].iterrows():
		name = _s(r.get("division name")).upper()
		if name in JUNK:
			continue
		div_urdu[name], div_code[name] = _urdu(r.get("division name in urdu")), _s(r.get("abbr"))
		node((name,), name, "Division", div_urdu[name], div_code[name])

	dept_info = {}  # (division, department) -> (urdu, code)
	for _, r in sheets["department"].iterrows():
		div, dept = _s(r.get("division parent")).upper(), _s(r.get("department")).upper()
		if div in JUNK or dept in JUNK:
			continue
		dept_info[(div, dept)] = (_urdu(r.get("urdu")), _s(r.get("code")))
		node((div,), div, "Division", div_urdu.get(div, ""), div_code.get(div, ""))
		node((div, dept), dept, "Department", *dept_info[(div, dept)])

	sub_info = {}  # (department, sub) -> (urdu, code); the sheet has no division, so a department name can be ambiguous
	for _, r in sheets["sub department"].iterrows():
		dept, sub = _s(r.get("department")).upper(), _s(r.get("sub department")).upper()
		if dept in JUNK or sub in JUNK:
			continue
		sub_info[(dept, sub)] = (_urdu(r.get("urdu name")), _s(r.get("code")))

	# Employees give the real division → department → sub-department paths.
	for _, r in sheets["employee"].iterrows():
		div, dept, sub = (_s(r.get(c)).upper() for c in ("Division", "Department", "SubDepartment"))
		if not (div and dept and sub):
			continue
		node((div,), div, "Division", div_urdu.get(div, ""), div_code.get(div, ""))
		node((div, dept), dept, "Department", *dept_info.get((div, dept), ("", "")))
		node((div, dept, sub), sub, "Sub Department", *sub_info.get((dept, sub), ("", "")))

	# Master sub-departments whose department belongs to exactly one division can be placed too.
	divisions_of = {}
	for key in nodes:
		if len(key) == 2:
			divisions_of.setdefault(key[1], []).append(key[0])
		elif len(key) == 1 and key[0] not in divisions_of:
			divisions_of[key[0]] = [key[0]]  # a department merged into its division (CONTRACTORS → CONTRACTORS)
	skipped = []
	for (dept, sub), info in sub_info.items():
		divs = divisions_of.get(dept, [])
		if len(divs) == 1:
			node((divs[0], dept, sub), sub, "Sub Department", *info)
		elif not any(k[-2:] == (dept, sub) for k in nodes if len(k) >= 2):
			skipped.append(f"{sub} (department {dept}: {'no division' if not divs else 'under ' + ', '.join(divs)})")
	return nodes, skipped


def _unique_names(nodes):
	"""ERPNext department names are unique per company: a label used more than once gets its parent (or division)."""
	used = {}
	for n in nodes.values():
		used[n["label"]] = used.get(n["label"], 0) + 1
	taken = set()
	for key in sorted(nodes, key=len):
		n = nodes[key]
		options = [n["label"]] if len(key) == 1 or used[n["label"]] == 1 else []
		if len(key) >= 2:
			options += [f"{n['label']} ({key[-2]})", f"{n['label']} ({key[0]})", f"{n['label']} ({' / '.join(key[:-1])})"]
		options.append(f"{n['label']} ({' / '.join(key)})")
		n["name"] = next(o for o in options if o not in taken)
		taken.add(n["name"])


def _upsert(doctype, name, values, dry_run, stats):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		changed = {k: v for k, v in values.items() if (doc.get(k) or "") != (v or "")}
		if changed:
			stats["updated"] += 1
			if not dry_run:
				doc.update(changed)
				doc.save(ignore_permissions=True)
		else:
			stats["unchanged"] += 1
		return name
	stats["created"] += 1
	if dry_run:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


def run(path="baogee_masters.xls", dry_run=0, delete_defaults=1):
	dry_run = int(dry_run)
	abbr = frappe.db.get_value("Company", COMPANY, "abbr")
	if not abbr:
		frappe.throw(f"Company {COMPANY} not found")
	sheets = _read(path)
	report = {}

	# ------------------------------------------------------------ departments
	nodes, skipped = _department_tree(sheets)
	_unique_names(nodes)
	has_children = {k[:-1] for k in nodes if len(k) > 1}
	stats = {"created": 0, "updated": 0, "unchanged": 0}
	dept_name = {}
	for key in sorted(nodes, key=len):  # parents first
		n = nodes[key]
		parent = dept_name.get(key[:-1], "All Departments") if len(key) > 1 else "All Departments"
		docname = f"{n['name']} - {abbr}"
		_upsert("Department", docname, {
			"department_name": n["name"], "company": COMPANY, "parent_department": parent,
			"is_group": 1 if key in has_children else 0,
			"mm_urdu_name": n["urdu"], "mm_code": n["code"], "mm_level": n["level"],
		}, dry_run, stats)
		dept_name[key] = docname
	report["departments"] = {**stats, "total": len(nodes),
		"renamed": sorted(n["name"] for n in nodes.values() if n["name"] != n["label"]), "skipped_master_rows": skipped}

	# ------------------------------------------------------------ designations
	stats = {"created": 0, "updated": 0, "unchanged": 0}
	for _, r in sheets["designation"].iterrows():
		name = _s(r.get("designation name")).upper()
		if not name:
			continue
		_upsert("Designation", name, {"designation_name": name, "mm_urdu_name": _urdu(r.get("urdu")), "mm_abbr": _s(r.get("abbr"))}, dry_run, stats)
	report["designations"] = stats

	# ------------------------------------------------------------ employees
	stats = {"created": 0, "updated": 0, "unchanged": 0}
	problems = []
	codes = {}
	for i, r in sheets["employee"].iterrows():
		row = i + 2  # spreadsheet row (header is row 1)
		name, cnic = _s(r.get("Name")), _s(r.get("CNIC"))
		if not name:
			problems.append(f"row {row}: no name — skipped")
			continue
		code = _s(r.get("Code"))
		codes.setdefault(code, []).append(row)
		if not re.fullmatch(r"\d{5}-\d{7}-\d", cnic):
			problems.append(f"row {row} {name}: CNIC '{cnic}' is not in 00000-0000000-0 form — imported as given")
		div, dept, sub = (_s(r.get(c)).upper() for c in ("Division", "Department", "SubDepartment"))
		key = _canon((div, dept, sub) if sub else (div, dept))
		values = {
			"first_name": name, "company": COMPANY, "status": "Active",
			"department": dept_name.get(key),
			"designation": _s(r.get("Designation")).upper() or None,
			"employee_number": code, "cnic": cnic, "mm_urdu_name": _s(r.get("NameUrdu")),
			"mm_basic_salary": float(_s(r.get("BasicSalary")) or 0),
		}
		existing = frappe.db.get_value("Employee", {"cnic": cnic, "company": COMPANY}, "name") if cnic else None
		if existing:
			_upsert("Employee", existing, values, dry_run, stats)
		else:
			_upsert("Employee", "__new__", {**values, **PLACEHOLDER, "mm_placeholder_data": 1}, dry_run, stats)
	dupes = {c: rows for c, rows in codes.items() if len(rows) > 1}
	report["employees"] = {**stats, "problems": problems,
		"shared_codes": {c: len(rows) for c, rows in dupes.items()}}

	# ------------------------------------------------------------ company default + unused ERPNext default departments
	if not dry_run:
		frappe.db.set_single_value("Global Defaults", "default_company", COMPANY)
		frappe.defaults.set_global_default("company", COMPANY)
	if int(delete_defaults):
		ours = set(dept_name.values()) | {"All Departments"}
		deleted, kept = [], []
		for d in frappe.get_all("Department", filters={"name": ["not in", list(ours)]}, pluck="name"):
			if frappe.db.exists("Employee", {"department": d}) or frappe.db.exists("Department", {"parent_department": d}):
				kept.append(d)
				continue
			if dry_run:
				deleted.append(d)
				continue
			try:
				frappe.delete_doc("Department", d, ignore_permissions=True)
				deleted.append(d)
			except Exception as e:
				kept.append(f"{d} ({type(e).__name__})")
		report["default_departments"] = {"deleted": deleted, "kept": kept}

	if not dry_run:
		frappe.db.commit()
	return report
