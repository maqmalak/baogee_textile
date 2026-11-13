/**
 * Where the React app lives. Dev server (:5182): at the root (/home, /hr/…). Production: served by the Frappe site at
 * /baogee (www/baogee.html, see hooks.py website_route_rules), so /baogee/home, /baogee/hr/… — Frappe keeps /login,
 * /app and /api for itself.
 */
export const ROUTER_BASE = import.meta.env.PROD ? "/baogee" : "";
