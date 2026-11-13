"""The React HR & Payroll app. www/baogee.html is the built index.html (written by frontend/scripts/copy-html.mjs);
every /baogee/* path is sent here by website_route_rules in hooks.py, and the app shows its own login screen."""

no_cache = 1


def get_context(context):
	context.no_cache = 1
	return context
