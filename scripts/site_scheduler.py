"""Scheduler for chosen sites only (instead of `bench schedule`, which ticks every site on the bench).

    cd ~/erpnext-react/sites && ../env/bin/python ../apps/baogee_textile/scripts/site_scheduler.py baogee

Every minute it queues the due Scheduled Job Types of the given sites; a `bench worker` runs them."""
import sys
import time

from frappe.utils.scheduler import enqueue_events_for_site

sites = sys.argv[1:] or ["baogee"]
while True:
	for site in sites:
		try:
			enqueue_events_for_site(site=site)
		except Exception as e:  # never stop the loop
			print(f"{site}: {e}", flush=True)
	time.sleep(60 - time.time() % 60 + 1)
