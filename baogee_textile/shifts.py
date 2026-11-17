"""Day / Night shifts.

- Day 08:00–18:00 and Night 18:00–08:00 (overnight). Weekly rest is Friday through the holiday lists (BGT 2026 / 2027,
  assigned to the company), so the shifts carry no holiday list of their own.
- The weekly Day ↔ Night change is done with HRMS Shift Schedule / Shift Schedule Assignment, not here.
- assign_from_last_punch() puts each Day / Night employee on the shift their recent check-ins / check-outs show.
"""
from datetime import timedelta

import frappe
from frappe.utils import cint, getdate, now_datetime, nowdate

DAY, NIGHT = "Day", "Night"
OLD_DAY = "10 Hours (08:00-18:00)"   # same hours as Day: its employees move to Day
SHIFTS = {
	DAY: {"start_time": "08:00:00", "end_time": "18:00:00"},
	NIGHT: {"start_time": "18:00:00", "end_time": "08:00:00"},
}


def ensure_shift_types():
	for name, times in SHIFTS.items():
		doc = frappe.get_doc("Shift Type", name) if frappe.db.exists("Shift Type", name) else frappe.new_doc("Shift Type")
		if doc.is_new():
			doc.name = doc.__newname = name
		doc.update(times)
		doc.enable_auto_attendance = 1
		doc.process_attendance_after = doc.process_attendance_after or nowdate()
		doc.determine_check_in_and_check_out = "Alternating entries as IN and OUT during the same shift"
		doc.working_hours_calculation_based_on = "First Check-in and Last Check-out"
		doc.begin_check_in_before_shift_start_time = 120   # early arrivals still count for this shift
		doc.allow_check_out_after_shift_end_time = 240     # overtime: check-out up to 4 h after the end
		doc.working_hours_threshold_for_half_day = doc.working_hours_threshold_for_half_day or 4
		doc.holiday_list = None   # Friday rest from the employee's / company's holiday list assignment
		doc.save(ignore_permissions=True)
	return list(SHIFTS)


def move_old_day_shift():
	"""Employees on the old 10 Hours (08:00-18:00) shift → Day."""
	names = frappe.get_all("Employee", {"default_shift": OLD_DAY}, pluck="name")
	for n in names:
		frappe.db.set_value("Employee", n, "default_shift", DAY, update_modified=False)
	return len(names)


def count_day_night(punches):
	"""(day shifts, night shifts) worked: a Day shift is a morning punch (05–12 h) and an evening punch (15–23 h) on the
	same date; a Night shift is an evening punch (16–23 h) with no morning punch that date and a punch the next
	morning (04–11 h). Stray single punches (a Friday visit, a forgotten check-in) count as neither."""
	by_day = {}
	for t in punches:
		by_day.setdefault(t.date(), []).append(t.hour)
	day = night = 0
	for d, hours in by_day.items():
		morning = any(5 <= h <= 12 for h in hours)
		evening = any(15 <= h <= 23 for h in hours)
		if morning and evening:
			day += 1
		elif any(16 <= h <= 23 for h in hours) and not morning and any(4 <= h <= 11 for h in by_day.get(d + timedelta(days=1), [])):
			night += 1
	return day, night


def assign_from_last_punch(days=14, dry_run=0):
	"""Day / Night from each employee's recent check-ins / check-outs (last `days` days).

	Every shift worked counts as a Day or a Night (see count_day_night). Employees on Day / Night get Night when
	night periods are the majority (at least 2), else Day. Employees on another shift (General, 12 Hours) move to Night
	only with at least 3 night periods and a night majority; a stray evening punch (e.g. a Friday visit) changes nothing."""
	since = now_datetime() - timedelta(days=cint(days))
	rows = frappe.db.sql("""select c.employee, c.time from `tabEmployee Checkin` c join tabEmployee e on e.name = c.employee
		where c.time >= %s and e.status = 'Active' order by c.employee, c.time""", since)
	by_emp = {}
	for emp, t in rows:
		by_emp.setdefault(emp, []).append(t)
	current = frappe.get_all("Employee", {"status": "Active"}, ["name", "default_shift"])
	changes = {"to_day": [], "to_night": [], "unchanged": 0, "no_punches": 0}
	for e in current:
		days_, nights = count_day_night(by_emp.get(e.name, []))
		in_rotation = e.default_shift in (DAY, NIGHT) or (cint(dry_run) and e.default_shift == OLD_DAY)
		if not (days_ or nights):
			changes["no_punches"] += in_rotation
			continue
		if in_rotation:
			want = NIGHT if nights >= 2 and nights > days_ else DAY
		elif nights >= 3 and nights > days_:
			want = NIGHT
		else:
			continue   # General / 12 Hours employees stay unless they clearly work nights
		have = DAY if e.default_shift == OLD_DAY else e.default_shift
		if have == want:
			changes["unchanged"] += 1
			continue
		changes["to_night" if want == NIGHT else "to_day"].append(e.name)
		if not cint(dry_run):
			frappe.db.set_value("Employee", e.name, "default_shift", want, update_modified=False)
	return {k: (len(v) if isinstance(v, list) else v) for k, v in changes.items()} | {"night": changes["to_night"][:50]}


def setup(dry_run=0):
	"""One-time: shift types, 10 Hours → Day, then Day / Night by the last punches."""
	ensure_shift_types()
	moved = 0 if cint(dry_run) else move_old_day_shift()
	result = assign_from_last_punch(dry_run=dry_run)
	if not cint(dry_run):
		frappe.db.commit()
	return {"moved_10_hours_to_day": moved, **result}


def assign_default_shifts(start_date: str = "2026-11-01", dry_run: int = 0):
	"""An active Shift Assignment for every active employee who has none, on the shift already set as their default
	shift (HR → Shifts counts assignments, so without one everybody shows as "No shift assigned"). Attendance does not
	change: HRMS falls back to the default shift when there is no assignment. Starts on `start_date`, or the joining
	date if later. Safe to run again (e.g. for new joiners)."""
	rows = frappe.db.sql("""select e.name, e.company, e.default_shift, e.date_of_joining from tabEmployee e
		where e.status = 'Active' and ifnull(e.default_shift, '') != '' and not exists (select 1 from `tabShift Assignment` sa
			where sa.employee = e.name and sa.docstatus = 1 and sa.status = 'Active'
			and (sa.end_date is null or sa.end_date >= curdate()))""", as_dict=True)
	made, failed = {}, []
	for r in rows:
		start = max(getdate(start_date), getdate(r.date_of_joining)) if r.date_of_joining else getdate(start_date)
		if cint(dry_run):
			made[r.default_shift] = made.get(r.default_shift, 0) + 1
			continue
		try:
			frappe.db.savepoint("shift_assignment")
			sa = frappe.get_doc({"doctype": "Shift Assignment", "employee": r.name, "company": r.company,
				"shift_type": r.default_shift, "start_date": start, "status": "Active"})
			sa.flags.ignore_permissions = True
			sa.insert()
			sa.submit()
			made[r.default_shift] = made.get(r.default_shift, 0) + 1
		except Exception as e:
			frappe.db.rollback(save_point="shift_assignment")
			frappe.clear_messages()
			failed.append(f"{r.name}: {frappe.utils.strip_html(str(e))[:120]}")
	if not cint(dry_run):
		frappe.db.commit()
	return {"assigned": made, "failed": failed[:20], "failed_count": len(failed), "dry_run": cint(dry_run)}
