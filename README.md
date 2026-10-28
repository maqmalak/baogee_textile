# Baogee Textile

Frappe app for the `baogee` site (Baogee Textile). It needs erpnext and hrms.

These HR features were copied from micromaxerp (apps `micromax` and `mm_core`):

- **Shift grace periods and attendance insights** (`baogee_textile.hr_insights`). Late and early marking with a grace period, plus attendance, leave, shift and payroll overviews.
- **Salary loans and advances** (`baogee_textile.loans`). A loan is an Employee Advance with "Salary loan" ticked. The eligibility and guarantor policy lives on the HR Settings → Salary Loans tab, and the loan is recovered in monthly instalments through Additional Salary.
- **Roster** (`baogee_textile.roster`).
- **React HR / Payroll app** in `frontend/`, forked from `erpnext-react/frontend`.
  Dev server: `cd frontend && npm run dev` → http://baogee.localhost:5182/home (proxies to the baogee site on :8009).
  Desktop (/home) shows app icons for HR (/hr), Payroll (/payroll), Settings and My Account, plus shortcut icons.

Custom field names keep the `mm_` prefix, so the copied React pages and the micromaxerp data model stay the same.

## HR masters import

`baogee_masters.xls` (bench folder) → departments (Division → Department → Sub Department), designations and employees,
each with its Urdu name (`mm_urdu_name`):

    bench --site baogee execute baogee_textile.importers.masters.run --kwargs "{'path': 'baogee_masters.xls'}"
    # add 'dry_run': 1 to only report

Re-runnable: departments and designations match by name, employees by CNIC. The sheet has no gender, date of birth or
joining date, so employees get placeholders (Male, 1990-01-01, 2026-10-01) with "not confirmed" (`mm_placeholder_data`)
ticked. A department name used under more than one parent gets its parent added, e.g. `POST (FINISHING)`.
