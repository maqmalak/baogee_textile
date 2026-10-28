"""Custom Fields for the HR features copied from micromaxerp (mm_core): salary loans on Employee Advance, the loan
policy tab in HR Settings, and the branch type.

Field names keep the mm_ prefix so the copied React pages and the data model match micromaxerp. They are applied on
install and on every migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Baogee Textile"


def _build_custom_fields():
    """Returns a dict keyed by doctype with a list of field dicts."""
    data = {}

    def add(dt, fieldname, label, fieldtype, options, insert_after, section=None, description=None, **props):
        field = {
            "fieldname": fieldname,
            "label": label,
            "fieldtype": fieldtype,
            "options": options,
            "insert_after": insert_after,
            "module": MODULE,
        }
        if description:
            field["description"] = description
        field.update(props)
        data.setdefault(dt, []).append(field)

    # ---------------------------------------------------------- Salary loans (baogee_textile.loans)
    # Loan = an Employee Advance repaid in monthly instalments from salary. The policy lives in HR Settings;
    # the eligibility check (service, salary limits, guarantor, history) runs before submit.
    add("Employee Advance", "mm_loan_section", "Salary Loan", "Section Break", None, "repay_unclaimed_amount_from_salary")
    add("Employee Advance", "mm_is_loan", "Salary loan (repay in instalments from salary)", "Check", None, "mm_loan_section", default="0")
    add("Employee Advance", "mm_installment_months", "Instalments (months)", "Int", None, "mm_is_loan", depends_on="mm_is_loan")
    add("Employee Advance", "mm_monthly_installment", "Monthly Instalment", "Currency", "currency", "mm_installment_months",
        depends_on="mm_is_loan", read_only=1)
    add("Employee Advance", "mm_first_deduction", "First Deduction Month", "Date", None, "mm_monthly_installment",
        depends_on="mm_is_loan", description="Payroll month the first instalment is deducted in (default: next month).")
    add("Employee Advance", "mm_loan_column", None, "Column Break", None, "mm_first_deduction")
    add("Employee Advance", "mm_guarantor", "Guarantor", "Link", "Employee", "mm_loan_column", depends_on="mm_is_loan")
    add("Employee Advance", "mm_guarantor_name", "Guarantor Name", "Data", None, "mm_guarantor", depends_on="mm_is_loan",
        fetch_from="mm_guarantor.employee_name", read_only=1)
    add("Employee Advance", "mm_eligibility", "Eligibility Check", "Small Text", None, "mm_guarantor_name", depends_on="mm_is_loan",
        read_only=1, no_copy=1)
    add("Employee Advance", "mm_override_reason", "Override Reason", "Small Text", None, "mm_eligibility", depends_on="mm_is_loan",
        no_copy=1, description="HR Manager only: why a loan that fails the policy is approved anyway.")

    add("HR Settings", "mm_loan_tab", "Salary Loans", "Tab Break", None, "hiring_sender_email")
    add("HR Settings", "mm_loan_policy_section", "Salary Loan Policy", "Section Break", None, "mm_loan_tab")
    add("HR Settings", "mm_loan_employment_types", "Eligible Employment Types", "Small Text", None, "mm_loan_policy_section",
        default="Full-time", description="One per line.")
    add("HR Settings", "mm_loan_min_service_months", "Minimum Service (months)", "Int", None, "mm_loan_employment_types", default="12")
    add("HR Settings", "mm_loan_salary_multiple", "Maximum Loan (× average gross salary)", "Float", None, "mm_loan_min_service_months", default="3")
    add("HR Settings", "mm_loan_max_installment_pct", "Maximum Instalment (% of average net pay)", "Percent", None,
        "mm_loan_salary_multiple", default="30")
    add("HR Settings", "mm_loan_max_months", "Maximum Tenure (months)", "Int", None, "mm_loan_max_installment_pct", default="12")
    add("HR Settings", "mm_loan_max_active", "Other Loans Allowed While One Is Outstanding", "Int", None, "mm_loan_max_months", default="0")
    add("HR Settings", "mm_loan_policy_column", None, "Column Break", None, "mm_loan_max_active")
    add("HR Settings", "mm_loan_guarantor_required", "Guarantor Required", "Select", "Always\nAbove one month's gross salary\nNever",
        "mm_loan_policy_column", default="Always")
    add("HR Settings", "mm_loan_guarantor_min_service_months", "Guarantor Minimum Service (months)", "Int", None,
        "mm_loan_guarantor_required", default="24")
    add("HR Settings", "mm_loan_guarantor_max_guarantees", "Loans One Guarantor May Back", "Int", None,
        "mm_loan_guarantor_min_service_months", default="2")
    add("HR Settings", "mm_loan_component", "Recovery Salary Component", "Link", "Salary Component", "mm_loan_guarantor_max_guarantees",
        description="Deduction used for instalments (default: Loan Recovery, created automatically).")

    # ---------------------------------------------------------- Branch: what kind of site it is (icon on the Branches page / map)
    add("Branch", "mm_branch_type", "Branch Type", "Select", "\nHead Office\nFactory\nWarehouse\nShop / Outlet\nOffice",
        "branch", description="Shown as the branch's icon in the list and on the map.")

    # ---------------------------------------------------------- Item: POS quantity presets (e.g. Roti starts at 2)
    add("Item", "mm_pos_section", "POS", "Section Break", None, "description", collapsible=1)
    add("Item", "mm_pos_default_qty", "POS Default Qty", "Float", None, "mm_pos_section",
        description="Quantity a sale starts at when this item is added at the counter (blank = 1).")
    add("Item", "mm_pos_qty_options", "POS Quick Quantities", "Data", None, "mm_pos_default_qty",
        description="Comma-separated quantities shown as one-tap buttons on the cart line, e.g. 4,5,6,8,10,15,20.")

    # ---------------------------------------------------------- POS Invoice: offline sales synced from the React terminal
    add("POS Invoice", "mm_offline_id", "Offline ID", "Data", None, "pos_profile", read_only=1, no_copy=1, search_index=1,
        description="Set when the sale was rung up offline in the React POS and synced later (prevents double posting).")
    add("POS Invoice", "mm_offline_at", "Rung Up Offline At", "Datetime", None, "mm_offline_id", read_only=1, no_copy=1,
        depends_on="mm_offline_id")

    # ---------------------------------------------------------- Branch location (from micromax.install)
    # Address and map coordinates, read by the React HR Branches page to pin every branch on a map.
    add("Branch", "location_section", "Location", "Section Break", None, "branch")
    add("Branch", "branch_address", "Address", "Small Text", None, "location_section")
    add("Branch", "city", "City", "Data", None, "branch_address", in_list_view=1)
    add("Branch", "location_column", None, "Column Break", None, "city")
    add("Branch", "latitude", "Latitude", "Float", None, "location_column", precision="6")
    add("Branch", "longitude", "Longitude", "Float", None, "latitude", precision="6")

    # ---------------------------------------------------------- Urdu names and mill codes (baogee_masters.xls)
    # Every master that has a name also has its Urdu name, shown next to it on the form (and on the New form).
    add("Department", "mm_urdu_name", "Department Name (Urdu)", "Data", None, "department_name", in_standard_filter=1)
    add("Department", "mm_code", "Code", "Data", None, "mm_urdu_name")
    add("Department", "mm_level", "Level", "Select", "\nDivision\nDepartment\nSub Department", "mm_code",
        description="Division → Department → Sub Department; employees sit in a Sub Department.")
    add("Designation", "mm_urdu_name", "Designation (Urdu)", "Data", None, "designation_name")
    add("Designation", "mm_abbr", "Abbreviation", "Data", None, "mm_urdu_name")
    add("Employee", "mm_urdu_name", "Full Name (Urdu)", "Data", None, "employee_name")
    add("Employee", "cnic", "CNIC", "Data", None, "mm_urdu_name", description="National identity card number, 00000-0000000-0.")
    add("Employee", "mm_basic_salary", "Basic Salary", "Currency", None, "ctc")
    add("Employee", "mm_placeholder_data", "Gender / date of birth / joining date not confirmed", "Check", None, "date_of_joining",
        default="0", description="Set by the masters import, which had no gender, date of birth or joining date. Untick once corrected.")

    return data


def _applicable(data):
    """Keep only the fields this site can hold.

    - doctype not installed on this site (e.g. CRM Lead without the crm app) -> skip it
    - Link to a doctype that doesn't exist here (e.g. a MicroMax-only doctype) -> skip the field
    - a native field of the same name already exists (ERPNext added it later) -> skip, or the doctype
      ends up with a duplicate fieldname
    """
    kept = {}
    for dt, fields in data.items():
        if not frappe.db.exists("DocType", dt):
            continue
        meta = frappe.get_meta(dt)
        for field in fields:
            if field["fieldtype"] == "Link" and not frappe.db.exists("DocType", field["options"]):
                continue
            if meta.has_field(field["fieldname"]) and not frappe.db.exists(
                "Custom Field", f"{dt}-{field['fieldname']}"
            ):
                continue
            kept.setdefault(dt, []).append(field)
    return kept


def make_custom_fields():
    if not frappe.db.table_exists("Custom Field"):
        return
    data = _applicable(_build_custom_fields())
    if data:
        create_custom_fields(data, ignore_validate=True)
