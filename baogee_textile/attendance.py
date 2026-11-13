"""Automatic attendance from punches (Employee Checkin).

HRMS only marks attendance for punches older than each Shift Type's `last_sync_of_checkin`, which the biometric sync
utility is meant to update (its shift sync is off here). This hourly job moves it to "now" and processes every shift
with auto attendance on, so Present / Half Day / Absent follow the punches without anyone touching the shift types.
"""
import frappe
from frappe.utils import add_to_date, now_datetime


def process():
	now = now_datetime()
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
		and a.name not like 'ATT-OLD-%%' and (a.status = 'Absent' and ifnull(a.leave_type, '') = ''
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
