"""Salary components for Baogee, from micromaxerp's set: the standard Pakistani allowances and deductions, without
micromaxerp's per-amount "Basic 17.5K …" variants, head-office duplicates or its restaurant / fair-price-shop items.

Formulas are not copied: amounts come from Baogee's own salary structures.

    bench --site baogee execute baogee_textile.importers.salary_components.run
"""

import frappe

# name, type, abbr, depends_on_payment_days, is_tax_applicable, description
COMPONENTS = [
	("House Rent Allowance", "Earning", "HRA", 0, 1, "Monthly house rent allowance."),
	("Conveyance Allowance", "Earning", "CA", 1, 1, "Travel to and from work."),
	("Medical Allowance", "Earning", "MA", 0, 0, "Medical allowance (often 10% of basic)."),
	("Medical Allowance (Exempt)", "Earning", "MAE", 0, 0, "Medical allowance exempt from income tax."),
	("Utilities Allowance", "Earning", "UTL", 0, 1, "Electricity, gas and water."),
	("Meal Allowance", "Earning", "MEAL", 0, 0, "Per working day meal allowance."),
	("Other Allowance", "Earning", "OA", 0, 1, "Any other fixed allowance."),
	("Overtime", "Earning", "OT", 0, 1, "Overtime pay (from attendance / overtime slips)."),
	("EOBI", "Deduction", "EOBI", 0, 0, "Employees' Old-Age Benefits Institution — employee share."),
	("Provident Fund", "Deduction", "PF", 0, 0, "Employee provident fund contribution."),
	("Advance Recovery", "Deduction", "ADVR", 0, 0, "Recovery of an employee advance."),
	("Attendance Deduction", "Deduction", "AD", 0, 0, "Short hours / late coming deduction."),
	("Canteen Deduction", "Deduction", "CD", 0, 0, "Canteen bills."),
	("Other Deductions", "Deduction", "OD", 0, 0, "Any other deduction."),
]


def run():
	created, existing = [], []
	for name, typ, abbr, pay_days, taxable, desc in COMPONENTS:
		if frappe.db.exists("Salary Component", name):
			existing.append(name)
			continue
		# an abbreviation already used by another component gets a suffix
		a, n = abbr, 1
		while frappe.db.exists("Salary Component", {"salary_component_abbr": a}):
			n += 1
			a = f"{abbr}{n}"
		frappe.get_doc({
			"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": a, "type": typ,
			"depends_on_payment_days": pay_days, "is_tax_applicable": taxable if typ == "Earning" else 0,
			"description": desc,
		}).insert(ignore_permissions=True)
		created.append(name)
	frappe.db.commit()
	return {"created": created, "already_there": existing}
