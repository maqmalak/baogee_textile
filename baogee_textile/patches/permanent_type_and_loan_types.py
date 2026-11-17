"""Employees without an Employment Type are Permanent (OT allowed); salary loans/advances are open to permanent staff."""
import frappe

PERMANENT = ("Permanent (OT allowed)", "Permanent (no OT)")


def execute():
	for etype in PERMANENT:
		if not frappe.db.exists("Employment Type", etype):
			frappe.get_doc({"doctype": "Employment Type", "employee_type_name": etype}).insert(ignore_permissions=True)
	frappe.db.sql("update tabEmployee set employment_type = %s where ifnull(employment_type, '') = ''", PERMANENT[0])

	if frappe.get_meta("HR Settings").has_field("mm_loan_employment_types"):
		cur = [t.strip() for t in (frappe.db.get_single_value("HR Settings", "mm_loan_employment_types") or "").splitlines() if t.strip()]
		new = cur + [t for t in PERMANENT if t not in cur]
		if new != cur:
			frappe.db.set_single_value("HR Settings", "mm_loan_employment_types", "\n".join(new))
