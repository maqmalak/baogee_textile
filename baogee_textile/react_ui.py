"""Server side of the shared React form kit (field picker, "+" quick create, activity chain) for any site with mm_core.

Same behaviour as the real-estate app's versions, without anything site-specific:

* `form_meta(doctype)` — a DocType's fields (custom fields included) for the connections field picker.
* `quick_entry_meta(doctype)` — the fields for an inline "New <doctype>" dialog behind a Link field's "+", or
  `eligible: false` with the reason when inline creation makes no sense.
* `get_chain(doctype, name)` — the record's history as a hash-chained list of blocks: created, saved changes,
  comments of every kind, emails and the documents later linked to it.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cstr, strip_html

SKIP_TYPES = {"HTML", "Button", "Image", "Fold", "Heading", "Geolocation", "Table MultiSelect", "Signature", "Barcode"}
FIELD_KEYS = ("fieldname", "fieldtype", "label", "options", "reqd", "read_only", "hidden", "depends_on", "mandatory_depends_on",
			  "fetch_from", "fetch_if_empty", "default", "precision", "description", "in_list_view", "in_standard_filter", "bold", "collapsible",
			  "columns")


def _fields(meta):
	out = []
	for df in meta.fields:
		if df.fieldtype in SKIP_TYPES:
			continue
		row = {k: df.get(k) for k in FIELD_KEYS if df.get(k) not in (None, "", 0)}
		row["fieldname"], row["fieldtype"] = df.fieldname, df.fieldtype
		out.append(row)
	return out


@frappe.whitelist(methods=["GET"])
def form_meta(doctype: str) -> dict:
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	meta = frappe.get_meta(doctype)
	children = {df.fieldname: {"doctype": df.options, "fields": _fields(frappe.get_meta(df.options))} for df in meta.get_table_fields()}
	return {
		"doctype": doctype, "issingle": meta.issingle, "is_submittable": meta.is_submittable, "title_field": meta.title_field,
		"search_fields": [f.strip() for f in (meta.search_fields or "").split(",") if f.strip()], "sort_field": meta.sort_field,
		"sort_order": meta.sort_order, "fields": _fields(meta), "children": children, "module": meta.module,
		"can_create": frappe.has_permission(doctype, "create"),
	}


# ---------------------------------------------------------------- "+" quick create
QUICK_DENY = {"User", "Company", "Account", "Role", "Role Profile", "DocType", "Module Def", "Currency", "Fiscal Year", "Cost Center", "Warehouse",
			  "Workflow State", "Print Format", "Letter Head"}
QUICK_EXTRA = {"Customer": ("customer_group", "territory"), "Supplier": ("supplier_group",), "Sales Partner": ("partner_type",)}
QUICK_TYPES = {"Data", "Link", "Select", "Int", "Float", "Currency", "Percent", "Date", "Check", "Small Text", "Text", "Phone", "Dynamic Link"}


@frappe.whitelist(methods=["GET"])
def quick_entry_meta(doctype: str) -> dict:
	meta = frappe.get_meta(doctype)
	reason = None
	if doctype in QUICK_DENY:
		reason = "create on its own page"
	elif not frappe.has_permission(doctype, "create"):
		reason = "no permission"
	elif meta.is_submittable or meta.issingle or meta.istable or meta.is_virtual:
		reason = "not a master"
	elif any(df.reqd for df in meta.get_table_fields()):
		reason = "needs child rows"
	name_field = (meta.autoname or "").split(":", 1)[1] if (meta.autoname or "").startswith("field:") else None
	fields = []
	for df in meta.fields:
		if df.fieldtype not in QUICK_TYPES or df.hidden or df.read_only:
			continue
		if not (df.reqd or df.allow_in_quick_entry or df.fieldname == name_field or df.fieldname == meta.title_field
				or df.fieldname in QUICK_EXTRA.get(doctype, ())):
			continue
		row = {k: df.get(k) for k in FIELD_KEYS if df.get(k) not in (None, "", 0)}
		row["fieldname"], row["fieldtype"] = df.fieldname, df.fieldtype
		fields.append(row)
	first = name_field or meta.title_field
	fields.sort(key=lambda f: 0 if f["fieldname"] == first else 1)
	if not fields and not reason:
		reason = "no quick-entry fields"
	return {"doctype": doctype, "eligible": reason is None, "reason": reason, "label": _(doctype), "fields": fields[:12]}


# ---------------------------------------------------------------- activity chain
LINKED_LIMIT = 80
COMMENT_KIND = {"Comment": "comment", "Info": "info", "Attachment": "file", "Attachment Removed": "file", "Workflow": "workflow",
				"Assigned": "assign", "Assignment Completed": "assign", "Shared": "share", "Unshared": "share", "Like": "like",
				"Label": "info", "Edit": "info", "Deleted": "info"}


def _label(meta, fieldname):
	df = meta.get_field(fieldname)
	return _(df.label) if df and df.label else fieldname.replace("_", " ").title()


def _same(old, new) -> bool:
	if old in (None, "", 0, "0") and new in (None, "", 0, "0", 0.0, "0.0"):
		return True
	try:
		return float(old) == float(new)
	except (TypeError, ValueError):
		return cstr(old) == cstr(new)


def _plain(value):
	"""Values as text: HTML fields (e.g. the tax breakup table) without their markup."""
	text = cstr(value)
	return " ".join(strip_html(text).split()) if "<" in text else text


def _version_block(meta, v):
	try:
		data = json.loads(v.data or "{}")
	except ValueError:
		data = {}
	changes, kind, title = [], "change", _("Updated")
	for field, old, new in data.get("changed") or []:
		if field == "docstatus":
			kind = "submit" if new == 1 else "cancel" if new == 2 else "change"
			title = {1: _("Submitted"), 2: _("Cancelled")}.get(new, _("Reverted to draft"))
			continue
		if field in ("modified", "modified_by") or _same(old, new):
			continue
		changes.append({"field": _label(meta, field), "old": _plain(old)[:140], "new": _plain(new)[:140]})
	for table, rows in data.get("added") or []:
		changes.append({"field": _label(meta, table), "old": "", "new": _("{0} row(s) added").format(len(rows) if isinstance(rows, list) else 1)})
	for table, rows in data.get("removed") or []:
		changes.append({"field": _label(meta, table), "old": _("{0} row(s) removed").format(len(rows) if isinstance(rows, list) else 1), "new": ""})
	for table, _row, _name, rchanges in data.get("row_changed") or []:
		for field, old, new in rchanges or []:
			if not _same(old, new):
				changes.append({"field": f"{_label(meta, table)} · {field.replace('_', ' ')}", "old": cstr(old)[:100], "new": cstr(new)[:100]})
	if kind == "change" and data.get("added") and not data.get("changed"):
		title = _("Rows added")
	return {"kind": kind, "title": title, "at": cstr(v.creation), "by": v.owner, "changes": changes[:30], "ref": v.name}


@frappe.whitelist(methods=["GET"])
def get_chain(doctype: str, name: str, linked: int = 1) -> dict:
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	meta = frappe.get_meta(doctype)
	blocks = [{"kind": "create", "title": _("Created"), "at": cstr(doc.creation), "by": doc.owner, "changes": [], "ref": doc.name}]
	for v in frappe.get_all("Version", {"ref_doctype": doctype, "docname": name}, ["name", "owner", "creation", "data"], order_by="creation asc", limit=200):
		b = _version_block(meta, v)
		if b["changes"] or b["kind"] != "change":
			blocks.append(b)
	for c in frappe.get_all("Comment", {"reference_doctype": doctype, "reference_name": name},
							["name", "comment_type", "content", "comment_email", "owner", "creation"], order_by="creation asc", limit=200):
		blocks.append({"kind": COMMENT_KIND.get(c.comment_type, "info"), "title": _(c.comment_type), "at": cstr(c.creation),
					   "by": c.comment_email or c.owner, "text": strip_html(cstr(c.content)).strip()[:400], "changes": [], "ref": c.name})
	for e in frappe.get_all("Communication", {"reference_doctype": doctype, "reference_name": name, "communication_type": "Communication"},
							["name", "subject", "sender", "recipients", "communication_date", "communication_medium", "sent_or_received"],
							order_by="communication_date asc", limit=100):
		blocks.append({"kind": "email", "title": f"{_(e.communication_medium or 'Email')} {_(e.sent_or_received or '').lower()}".strip(),
					   "at": cstr(e.communication_date), "by": e.sender, "text": cstr(e.subject), "to": e.recipients, "changes": [], "ref": e.name})
	if int(linked):
		# documents linked to this one, from the same groups as the Connections tab
		from baogee_textile.connections import _groups_for

		seen = 0
		for _group, dt, sql, extra in _groups_for(doctype, name):
			if not frappe.has_permission(dt, "read"):
				continue
			try:
				rows = frappe.db.sql(f"""select x.name, x.status, p.creation at, p.owner from ({sql}) x join `tab{dt}` p on p.name = x.name
					order by p.creation desc limit 25""", {"n": name, **extra}, as_dict=True)
			except Exception:
				continue
			submittable = bool(frappe.get_meta(dt).is_submittable)
			for r in rows:
				blocks.append({"kind": "linked", "title": _("{0} linked").format(_(dt)), "at": cstr(r.at), "by": r.owner, "doctype": dt,
							   "docname": r.name, "status": r.get("status"), "text": "", "changes": [], "ref": r.name, "submittable": submittable})
				seen += 1
			if seen >= LINKED_LIMIT:
				break
	genesis, rest = blocks[0], sorted(blocks[1:], key=lambda b: b["at"])
	blocks = [genesis, *rest]
	prev, names = "0" * 64, {}
	for i, b in enumerate(blocks):
		b["index"], b["prev"] = i, prev
		payload = json.dumps({k: b.get(k) for k in ("kind", "title", "at", "by", "changes", "text", "ref")}, sort_keys=True, default=str)
		b["hash"] = prev = hashlib.sha256((b["prev"] + payload).encode()).hexdigest()
		if b.get("by") and b["by"] not in names:
			names[b["by"]] = frappe.utils.get_fullname(b["by"]) if frappe.db.exists("User", b["by"]) else b["by"]
		b["by_name"] = names.get(b.get("by"), b.get("by"))
	counts = {}
	for b in blocks:
		counts[b["kind"]] = counts.get(b["kind"], 0) + 1
	return {"blocks": blocks, "counts": counts, "head": prev}
