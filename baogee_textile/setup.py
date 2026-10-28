"""Install / migrate: custom fields, the salary loan policy, shift grace periods and payroll settings, as on micromaxerp."""

import frappe

from baogee_textile import custom_fields, loans
from baogee_textile.hr_insights import DEFAULT_GRACE_MINUTES

# micromaxerp's mill shifts: three 8-hour shifts plus the general (office) shift.
SHIFTS = [
	{"name": "General Shift", "start_time": "08:30:00", "end_time": "16:30:00", "before": 420, "after": 420},
	{"name": "Shift A", "start_time": "06:00:00", "end_time": "14:00:00", "before": 60, "after": 60},
	{"name": "Shift B", "start_time": "14:00:00", "end_time": "22:00:00", "before": 60, "after": 60},
	{"name": "Shift C", "start_time": "22:00:00", "end_time": "06:00:00", "before": 60, "after": 60},
]

# micromaxerp's Payroll Settings: pay follows marked attendance, unmarked days count as absent.
PAYROLL_SETTINGS = {
	"payroll_based_on": "Attendance",
	"consider_unmarked_attendance_as": "Absent",
	"include_holidays_in_total_working_days": 1,
	"consider_marked_attendance_on_holidays": 0,
}


def after_install():
	after_migrate()
	ensure_shifts()
	ensure_payroll_settings()


def after_migrate():
	custom_fields.make_custom_fields()
	loans.ensure_policy_defaults()


def ensure_shifts():
	"""Create the mill shifts with micromaxerp's grace rule: late entry / early exit marked after 30 minutes.
	Existing shift types are left as they are (change grace periods from HR → Setup in the React app)."""
	for s in SHIFTS:
		if frappe.db.exists("Shift Type", s["name"]):
			continue
		frappe.get_doc({
			"doctype": "Shift Type", "name": s["name"], "start_time": s["start_time"], "end_time": s["end_time"],
			"begin_check_in_before_shift_start_time": s["before"], "allow_check_out_after_shift_end_time": s["after"],
			"enable_late_entry_marking": 1, "late_entry_grace_period": DEFAULT_GRACE_MINUTES,
			"enable_early_exit_marking": 1, "early_exit_grace_period": DEFAULT_GRACE_MINUTES,
		}).insert(ignore_permissions=True)
	frappe.db.commit()


def ensure_payroll_settings():
	for field, value in PAYROLL_SETTINGS.items():
		frappe.db.set_single_value("Payroll Settings", field, value, update_modified=False)
	frappe.db.commit()
