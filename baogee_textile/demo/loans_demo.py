"""Demo salary loans and cash advances for Bao Gee Textile, with October 2026 payroll run so the deductions show.

    bench --site baogee execute baogee_textile.demo.loans_demo.run
    bench --site baogee execute baogee_textile.demo.loans_demo.remove     # before go-live: cancels and deletes it all

What run() creates (every record is listed in the manifest, a JSON file in the site's private files):
- holiday list "BGT 2026" (Sundays off) as the company default, if the company has none;
- salary component accounts: Basic → Salary, Loan / Advance Recovery → Employee Advances;
- salary structure "[DEMO] Basic Pay" (Basic = base) assigned from 1 Oct 2026 to the demo employees, base = basic salary;
- October attendance (Present on working days) for them, because payroll is based on attendance;
- 6 salary loans (3–12 instalments, deducted from October) and 4 cash advances (recovered in full from October), all paid out;
- 2 drafts (a loan request and an advance) waiting for approval;
- the October 2026 payroll for the demo employees: salary slips submitted and posted, so the loans' balances drop.
November's payroll is not run: the Salary Loans page shows November's instalments as scheduled.
"""
import json
import os

import frappe
from frappe.utils import add_days, flt, getdate

from baogee_textile import loans

COMPANY = "Bao Gee Textile"
TAG = "[DEMO]"
MONTH_START, MONTH_END = "2026-10-01", "2026-10-31"
STRUCTURE = f"{TAG} Basic Pay"

LOANS = [  # (amount, months, purpose)
    (60000, 6, "Daughter's wedding"), (36000, 12, "House repair after rain"), (24000, 3, "Motorcycle repair"),
    (90000, 12, "Mother's medical treatment"), (45000, 9, "Children's school admission"), (18000, 6, "Electricity bill arrears"),
]
ADVANCES = [(8000, "Eid expenses"), (5000, "Medical emergency"), (12000, "House rent advance"), (6000, "Travel to village")]


def _manifest_path():
    return frappe.get_site_path("private", "files", "baogee_loans_demo.json")


def _employees(n):
    # Active employees with a basic salary, not on the biometric mock machines, not already borrowing
    taken = {r.employee for r in frappe.get_all("Employee Advance", ["employee"])}
    rows = frappe.get_all("Employee", {"company": COMPANY, "status": "Active", "mm_basic_salary": [">", 0], "attendance_device_id": ["is", "not set"]},
                          ["name", "employee_name", "mm_basic_salary", "date_of_joining"], order_by="name", limit=200)
    return [r for r in rows if r.name not in taken][:n]


def run(dry: int = 0):
    """dry=1: do everything, print the result, then roll it all back."""
    if os.path.exists(_manifest_path()):
        return "Demo loans already generated — run remove() first to regenerate."
    frappe.set_user("Administrator")
    m = {"created": []}
    note = lambda dt, name: m["created"].append([dt, name])  # noqa: E731
    cur = frappe.get_cached_value("Company", COMPANY, "default_currency") or "PKR"
    adv_account = frappe.get_cached_value("Company", COMPANY, "default_employee_advance_account")
    salary_account = frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Salary", "is_group": 0}, "name")
    payable = frappe.get_cached_value("Company", COMPANY, "default_payroll_payable_account")
    cash = frappe.db.get_value("Mode of Payment Account", {"parent": "Cash", "company": COMPANY}, "default_account")

    # holiday list (company default) — real setup, kept by remove()
    if not frappe.db.get_value("Company", COMPANY, "default_holiday_list"):
        name = "BGT 2026"
        if not frappe.db.exists("Holiday List", name):
            hl = frappe.get_doc({"doctype": "Holiday List", "holiday_list_name": name, "from_date": "2026-01-01", "to_date": "2026-12-31",
                                 "weekly_off": "Sunday"})
            hl.get_weekly_off_dates()
            hl.insert()
        frappe.db.set_value("Company", COMPANY, "default_holiday_list", name)
        if frappe.db.exists("DocType", "Holiday List Assignment") and not frappe.db.exists("Holiday List Assignment", {"assigned_to": COMPANY, "docstatus": 1}):
            frappe.get_doc({"doctype": "Holiday List Assignment", "applicable_for": "Company", "assigned_to": COMPANY,
                            "holiday_list": name, "from_date": "2026-01-01"}).insert().submit()
    holidays = {getdate(h.holiday_date) for h in frappe.get_all("Holiday", {"parent": frappe.db.get_value("Company", COMPANY, "default_holiday_list")}, ["holiday_date"])}

    # component accounts — real setup, kept by remove()
    loans._ensure_component_account("Basic", COMPANY, salary_account)
    loans._ensure_component_account("Loan Recovery", COMPANY, adv_account)
    loans._ensure_component_account("Advance Recovery", COMPANY, adv_account)

    # salary structure + assignments
    ss = frappe.get_doc({"doctype": "Salary Structure", "name": STRUCTURE, "company": COMPANY, "currency": cur, "payroll_frequency": "Monthly",
                         "earnings": [{"salary_component": "Basic", "abbr": "B", "amount_based_on_formula": 1, "formula": "base"}]})
    ss.insert()
    ss.submit()
    note("Salary Structure", ss.name)

    people = _employees(len(LOANS) * 2 + len(ADVANCES) + 2)  # borrowers + guarantors + advance takers + drafts
    borrowers, guarantors = people[:len(LOANS)], people[len(LOANS):len(LOANS) * 2]
    takers, drafts = people[len(LOANS) * 2:len(LOANS) * 2 + len(ADVANCES)], people[-2:]
    paid_staff = borrowers + takers

    for e in paid_staff:
        a = frappe.get_doc({"doctype": "Salary Structure Assignment", "employee": e.name, "salary_structure": ss.name, "company": COMPANY,
                            "currency": cur, "from_date": MONTH_START, "base": e.mm_basic_salary, "payroll_payable_account": payable})
        a.insert()
        a.submit()
        note("Salary Structure Assignment", a.name)
        d = getdate(MONTH_START)
        while d <= getdate(MONTH_END):
            if d not in holidays and d >= getdate(e.date_of_joining) and not frappe.db.exists("Attendance", {"employee": e.name, "attendance_date": d, "docstatus": 1}):
                att = frappe.get_doc({"doctype": "Attendance", "employee": e.name, "attendance_date": d, "status": "Present", "company": COMPANY})
                att.insert()
                att.submit()
                note("Attendance", att.name)
            d = add_days(d, 1)

    def advance(e, amount, purpose, posting, loan=None, guarantor=None):
        doc = frappe.get_doc({
            "doctype": "Employee Advance", "employee": e.name, "company": COMPANY, "posting_date": posting, "currency": cur, "exchange_rate": 1,
            "advance_amount": amount, "purpose": f"{TAG} {purpose}", "advance_account": adv_account, "mode_of_payment": "Cash",
            **({"mm_is_loan": 1, "mm_installment_months": loan, "mm_first_deduction": MONTH_START, "mm_guarantor": guarantor.name,
                "mm_override_reason": f"{TAG} demo data (placeholder joining dates)"} if loan else {}),
        })
        doc.insert()
        note("Employee Advance", doc.name)
        return doc

    for i, (e, (amount, months, purpose)) in enumerate(zip(borrowers, LOANS)):
        doc = advance(e, amount, purpose, add_days(MONTH_START, 2 + i), loan=months, guarantor=guarantors[i])
        doc.submit()
        r = loans.pay_out(doc.name, "Cash", posting_date=doc.posting_date)
        note("Payment Entry", r["payment_entry"])
        if r["installments"]:
            note("Additional Salary", r["installments"])
    for i, (e, (amount, purpose)) in enumerate(zip(takers, ADVANCES)):
        doc = advance(e, amount, purpose, add_days(MONTH_START, 8 + i))
        doc.submit()
        r = loans.pay_out(doc.name, "Cash", posting_date=doc.posting_date)
        note("Payment Entry", r["payment_entry"])
        note("Additional Salary", loans.recover_from_salary(doc.name, MONTH_END))
    advance(drafts[0], 30000, "Roof repair (awaiting approval)", "2026-11-03", loan=6, guarantor=guarantors[0])
    advance(drafts[1], 4000, "School fee (awaiting approval)", "2026-11-03")

    # October payroll for the demo staff
    pe = frappe.get_doc({"doctype": "Payroll Entry", "company": COMPANY, "posting_date": MONTH_END, "currency": cur, "exchange_rate": 1,
                         "payroll_frequency": "Monthly", "start_date": MONTH_START, "end_date": MONTH_END, "payroll_payable_account": payable,
                         "cost_center": frappe.get_cached_value("Company", COMPANY, "cost_center"), "payment_account": cash,
                         "salary_slip_based_on_timesheet": 0,
                         "employees": [{"employee": e.name} for e in paid_staff]})
    pe.insert()
    note("Payroll Entry", pe.name)
    # HRMS commits / rolls back inside slip creation and submission unless in_test; keep it in our transaction
    was = frappe.in_test
    frappe.in_test = True
    try:
        pe.submit()  # creates the salary slips
        pe.reload()
        if not pe.salary_slips_created:
            frappe.throw(f"Salary slips not created: {pe.error_message}")
        pe.submit_salary_slips()
        pe.reload()
        if pe.error_message:
            frappe.throw(f"Salary slips not submitted: {pe.error_message}")
    finally:
        frappe.in_test = was
    for s in frappe.get_all("Salary Slip", {"payroll_entry": pe.name}, pluck="name"):
        note("Salary Slip", s)

    if int(dry):
        out = summary()
        frappe.db.rollback()
        frappe.clear_document_cache("Company", COMPANY)
        return "DRY RUN (rolled back)\n" + out
    with open(_manifest_path(), "w") as f:
        json.dump(m, f, indent=1)
    frappe.db.commit()
    return summary()


def summary():
    rows = frappe.get_all("Employee Advance", {"company": COMPANY, "purpose": ["like", f"{TAG}%"]},
                          ["name", "employee_name", "mm_is_loan", "advance_amount", "paid_amount", "return_amount", "status", "docstatus"],
                          order_by="name")
    out = []
    for r in rows:
        out.append(f"{r.name} {'LOAN' if r.mm_is_loan else 'ADV '} {r.employee_name[:28]:28} amount {r.advance_amount:>8,.0f} paid {r.paid_amount:>8,.0f} "
                   f"repaid {r.return_amount:>8,.0f} {r.status}{' (draft)' if r.docstatus == 0 else ''}")
    slips = frappe.get_all("Salary Slip", {"company": COMPANY, "start_date": MONTH_START, "docstatus": 1}, ["name"])
    out.append(f"October salary slips submitted: {len(slips)}")
    return "\n".join(out)


def remove():
    """Cancel and delete everything run() created (newest first). Holiday list and component accounts are kept."""
    path = _manifest_path()
    if not os.path.exists(path):
        return "No demo manifest found."
    frappe.set_user("Administrator")
    m = json.load(open(path))
    order = ["Payroll Entry", "Salary Slip", "Additional Salary", "Payment Entry", "Employee Advance", "Attendance",
             "Salary Structure Assignment", "Salary Structure"]
    for dt in order:
        names = [n for d, n in m["created"] if d == dt]
        if dt == "Payroll Entry":  # its journal entry first
            for je in frappe.get_all("Journal Entry Account", {"reference_type": "Payroll Entry", "reference_name": ["in", names or [""]]}, pluck="parent"):
                j = frappe.get_doc("Journal Entry", je)
                if j.docstatus == 1:
                    j.cancel()
                frappe.delete_doc("Journal Entry", je, force=1)
        for n in reversed(names):
            if not frappe.db.exists(dt, n):
                continue
            d = frappe.get_doc(dt, n)
            if d.docstatus == 1:
                d.flags.ignore_links = True
                d.cancel()
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
    os.remove(path)
    frappe.db.commit()
    return "Demo loans, advances and October demo payroll removed."
