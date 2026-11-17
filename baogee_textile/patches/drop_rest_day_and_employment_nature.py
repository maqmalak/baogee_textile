"""Drop Employee.mm_rest_day and Employee.mm_employment_nature (old HR site fields).

- Rest day is the Holiday List's weekly off (company default BGT 2026/2027 = Friday; "BGT 2026 - Sunday rest" for
  Sunday staff), which is what attendance and WO already use.
- Employment nature becomes the standard Employment Type: Daily Wager stays, the two "Permanent" values get their own
  types so the overtime rule is kept.
"""
import frappe

NATURE_TO_TYPE = {
	"Permanent and Over Time is allowed": "Permanent (OT allowed)",
	"Permanent & Overtimes is not allowed": "Permanent (no OT)",
	"Daily Wager": "Daily Wager",
}


def execute():
	cols = frappe.db.get_table_columns("Employee")
	if "mm_employment_nature" in cols:
		for nature, etype in NATURE_TO_TYPE.items():
			if not frappe.db.exists("Employment Type", etype):
				frappe.get_doc({"doctype": "Employment Type", "employee_type_name": etype}).insert(ignore_permissions=True)
			frappe.db.sql("""update tabEmployee set employment_type = %s
				where mm_employment_nature = %s and ifnull(employment_type, '') = ''""", (etype, nature))

	for field in ("mm_employment_nature", "mm_rest_day"):
		# mm_import_remarks was placed after these; keep it in the Old HR Site group
		frappe.db.set_value("Custom Field", {"dt": "Employee", "insert_after": field}, "insert_after", "mm_legacy_id")
		if frappe.db.exists("Custom Field", f"Employee-{field}"):
			frappe.delete_doc("Custom Field", f"Employee-{field}", ignore_permissions=True, force=True)
		if field in frappe.db.get_table_columns("Employee"):
			frappe.db.sql_ddl(f"alter table tabEmployee drop column `{field}`")
	frappe.clear_cache(doctype="Employee")
