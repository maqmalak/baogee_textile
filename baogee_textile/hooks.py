app_name = "baogee_textile"
app_title = "Baogee Textile"
app_publisher = "Baogee Textile"
app_description = "Baogee Textile ERP: HR (shift grace periods, attendance insights), salary loans and employee advances, React HR app"
app_email = "maqmalak@gmail.com"
app_license = "mit"

required_apps = ["erpnext", "hrms"]

after_install = "baogee_textile.setup.after_install"
after_migrate = "baogee_textile.setup.after_migrate"

# The React HR & Payroll app in production: one page (www/baogee.html) for every /baogee/* route.
website_route_rules = [{"from_route": "/baogee/<path:app_path>", "to_route": "baogee"}]

# Salary loans (baogee_textile.loans): eligibility on save, policy enforced on submit, instalments when paid out.
doc_events = {
	"Employee Advance": {
		"validate": "baogee_textile.loans.validate",
		"before_submit": "baogee_textile.loans.before_submit",
	},
	"Payment Entry": {
		"on_submit": "baogee_textile.loans.on_payment_submit",
	},
}

# Attendance from punches every hour (baogee_textile.attendance)
scheduler_events = {
	"hourly_long": ["baogee_textile.attendance.process"],
}
