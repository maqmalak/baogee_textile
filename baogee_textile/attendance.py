"""Automatic attendance from punches (Employee Checkin).

HRMS only marks attendance for punches older than each Shift Type's `last_sync_of_checkin`, which the biometric sync
utility is meant to update (its shift sync is off here). This hourly job moves it to "now" and processes every shift
with auto attendance on, so Present / Half Day / Absent follow the punches without anyone touching the shift types.

Attendance at the first punch: HRMS only marks a day after the shift ends (plus its check-out window), so on_checkin
marks the employee Present at their first punch (a submitted Attendance with mm_provisional = 1 and the in time) and
moves its out time / working hours forward on each OUT punch. When the shift ends HRMS marks the final attendance
(status from the working-hour thresholds, late entry, early exit); adopt_provisional swaps it in under the same name.
"""
from datetime import timedelta

import frappe
from frappe.utils import add_to_date, cint, getdate, now_datetime


def on_checkin(doc, method=None):
	"""Employee Checkin after_insert: provisional attendance for the punch's shift day."""
	try:
		_provisional_for(doc)
	except Exception:
		frappe.log_error(title=f"Provisional attendance failed for check-in {doc.name}")


def _provisional_for(c):
	if not c.employee or not c.shift or not c.shift_start or cint(c.skip_auto_attendance) or cint(c.get("offshift")):
		return
	day = getdate(c.shift_start)
	if day > getdate():
		return
	existing = frappe.db.get_value("Attendance", {"employee": c.employee, "attendance_date": day, "docstatus": ("<", 2)},
		["name", "mm_provisional"], as_dict=True)
	if existing:
		if cint(existing.mm_provisional):
			_refresh(existing.name, c)
		return
	shift = frappe.get_cached_doc("Shift Type", c.shift)
	if not cint(shift.enable_auto_attendance) or not shift.should_mark_attendance(c.employee, day):
		return   # holidays etc.: HRMS will not mark them either
	logs = _shift_logs(c)
	first = logs[0].time if logs else c.time
	late = cint(shift.enable_late_entry_marking) and first > c.shift_start + timedelta(minutes=cint(shift.late_entry_grace_period))
	att = frappe.new_doc("Attendance")
	att.update({"employee": c.employee, "attendance_date": day, "status": "Present", "shift": c.shift,
		"in_time": first, "late_entry": 1 if late else 0, "mm_provisional": 1})
	_set_out(att, logs)
	try:
		frappe.db.savepoint("provisional_attendance")
		att.flags.ignore_permissions = True
		att.insert()
		att.submit()
	except frappe.ValidationError:
		# e.g. on leave that day, or inactive: leave it to HRMS at shift end
		frappe.db.rollback(save_point="provisional_attendance")
		frappe.clear_messages()


def _shift_logs(c):
	return frappe.get_all("Employee Checkin", {"employee": c.employee, "shift": c.shift, "shift_start": c.shift_start,
		"skip_auto_attendance": 0}, ["time", "log_type"], order_by="time")


def _set_out(att, logs):
	"""Out time = the latest OUT punch after the first punch (the machines label punches alternately IN / OUT)."""
	outs = [l.time for l in logs if l.log_type == "OUT"]
	if outs and att.in_time and outs[-1] > att.in_time:
		att.out_time = outs[-1]
		att.working_hours = round((outs[-1] - att.in_time).total_seconds() / 3600, 2)


def _refresh(name, c):
	logs = _shift_logs(c)
	if not logs:
		return
	att = frappe._dict(in_time=logs[0].time, out_time=None, working_hours=0)
	_set_out(att, logs)
	frappe.db.set_value("Attendance", name, {"in_time": att.in_time, "out_time": att.out_time,
		"working_hours": att.working_hours}, update_modified=False)


def adopt_provisional(doc, method=None):
	"""Attendance before_insert: the final attendance for a day (HRMS at shift end, or HR by hand) replaces the
	provisional one and keeps its name, so links to it stay valid."""
	if cint(doc.get("mm_provisional")) or not doc.employee or not doc.attendance_date:
		return
	name = frappe.db.get_value("Attendance", {"employee": doc.employee, "attendance_date": doc.attendance_date,
		"mm_provisional": 1, "docstatus": ("<", 2)}, "name")
	if not name:
		return
	frappe.db.delete("Attendance", {"name": name})
	doc.name = name
	doc.flags.name_set = True


def mark_provisional(day: str | None = None):
	"""Provisional attendance for everyone who punched on `day` (default today) and has none yet, e.g. punches that
	arrived before on_checkin existed. Safe to run again."""
	day = getdate(day)
	rows = frappe.db.sql("""select c.name from `tabEmployee Checkin` c
		where c.shift_start >= %s and c.shift_start < %s + interval 1 day and c.employee is not null
			and c.shift is not null and c.skip_auto_attendance = 0 and c.attendance is null
			and not exists (select 1 from tabAttendance a where a.employee = c.employee
				and a.attendance_date = date(c.shift_start) and a.docstatus < 2)
		order by c.time""", (day, day), pluck=True)
	done = set()
	for name in rows:
		c = frappe.get_doc("Employee Checkin", name)
		if (c.employee, str(getdate(c.shift_start))) in done:
			continue
		done.add((c.employee, str(getdate(c.shift_start))))
		on_checkin(c)
	frappe.db.commit()
	return f"{len(done)} employee-day(s) checked for provisional attendance on {day}"


def process():
	now = now_datetime()
	try:
		mark_provisional()   # catch up punches the hook missed
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Provisional attendance catch-up failed")
	for name in frappe.get_all("Shift Type", {"enable_auto_attendance": 1}, pluck="name"):
		frappe.db.set_value("Shift Type", name, "last_sync_of_checkin", add_to_date(now, minutes=-2), update_modified=False)
		try:
			frappe.get_doc("Shift Type", name).process_auto_attendance()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Auto attendance failed for shift {name}")


def rebuild(from_date: str, to_date: str | None = None):
	"""Redo attendance from punches for a period, e.g. after employees' shifts changed: drop the attendance auto
	attendance made (not the old-site ATT-OLD records or manual ones), re-read each punch's shift, then process."""
	to_date = to_date or str(now_datetime().date())
	auto = frappe.db.sql_list("""select a.name from tabAttendance a where a.attendance_date between %s and %s
		and a.name not like 'ATT-OLD-%%' and (a.status = 'Absent' and ifnull(a.leave_type, '') = '' or a.mm_provisional = 1
		or exists (select 1 from `tabEmployee Checkin` c where c.attendance = a.name))""", (from_date, to_date))
	if auto:
		frappe.db.sql("update `tabEmployee Checkin` set attendance = null where attendance in %s", (auto,))
		frappe.db.sql("delete from tabAttendance where name in %s", (auto,))
	n = 0
	for name in frappe.get_all("Employee Checkin", {"time": ["between", [from_date, f"{to_date} 23:59:59"]],
			"attendance": ["is", "not set"], "skip_auto_attendance": 0}, pluck="name"):
		c = frappe.get_doc("Employee Checkin", name)
		c.fetch_shift()
		c.db_update()
		n += 1
	for name in frappe.get_all("Shift Type", {"enable_auto_attendance": 1}, pluck="name"):
		frappe.db.set_value("Shift Type", name, "process_attendance_after", from_date, update_modified=False)
	frappe.db.commit()
	process()
	return f"removed {len(auto)} auto attendance records, re-read shift on {n} punches, processed shifts"


def switch_machines_to_frappe(sync_from: str | None = None):
	"""Let biometric_sync pull the gate machines (after the local sync tool is stopped): Auto Sync on, every
	15 minutes, starting from `sync_from` (default today 07:00). Punches already here are skipped as duplicates."""
	from frappe.utils import getdate, nowdate

	start = sync_from or f"{getdate(nowdate())} 07:00:00"
	names = frappe.get_all("Biometric Device", {"enabled": 1}, pluck="name")
	for name in names:
		frappe.db.set_value("Biometric Device", name, {"auto_sync": 1, "sync_interval": 15, "sync_from": start}, update_modified=False)
	frappe.db.set_single_value("Biometric Sync Settings", "enable_scheduled_sync", 1)
	frappe.db.commit()
	return f"Auto Sync on for {len(names)} machine(s) from {start}: {', '.join(names)}"


def relabel_checkins(from_date: str, to_date: str | None = None, dry_run: int = 0):
	"""The gate machines send one key for every punch (MAIN_GATE always 3, MAIN_GATE2 always 0), so every check-in was
	stored as IN. Relabel by order instead: per employee and day, 1st punch IN, 2nd OUT, 3rd IN… (the same rule as the
	machines' "Alternate IN/OUT" mode). Attendance is not affected: the shifts already read punches alternately."""
	from frappe.utils import cint, getdate

	to_date = to_date or str(now_datetime().date())
	rows = frappe.db.sql("""select name, employee, date(time) d, log_type from `tabEmployee Checkin`
		where time >= %s and time < %s + interval 1 day and employee is not null order by employee, time, name""",
		(getdate(from_date), getdate(to_date)), as_dict=True)
	changed, seen = 0, {}
	for r in rows:
		key = (r.employee, r.d)
		n = seen.get(key, 0)
		seen[key] = n + 1
		want = "IN" if n % 2 == 0 else "OUT"
		if r.log_type != want:
			changed += 1
			if not cint(dry_run):
				frappe.db.set_value("Employee Checkin", r.name, "log_type", want, update_modified=False)
				frappe.db.sql("update `tabBiometric Log` set log_type = %s where employee_checkin = %s", (want, r.name))
	if not cint(dry_run):
		frappe.db.commit()
	return f"{len(rows)} check-ins from {from_date} to {to_date}: {changed} relabelled{' (dry run)' if cint(dry_run) else ''}"


def set_machines_alternate():
	"""Both gate machines: log type by order (1st IN, 2nd OUT…), since nobody presses the IN/OUT keys."""
	names = frappe.get_all("Biometric Device", pluck="name")
	for n in names:
		frappe.db.set_value("Biometric Device", n, "log_type_mode", "Alternate IN/OUT")
	frappe.db.set_single_value("Biometric Sync Settings", "default_log_type_mode", "Alternate IN/OUT")
	frappe.db.commit()
	return f"Alternate IN/OUT on {len(names)} machine(s)"
