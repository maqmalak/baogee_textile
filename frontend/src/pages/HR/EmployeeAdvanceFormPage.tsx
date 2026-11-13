import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";
import toast from "react-hot-toast";
import {
  Banknote, CalendarRange, Check, CheckCircle2, CircleDashed, ExternalLink, FileText, HandCoins, Landmark, Receipt,
  Send, ShieldCheck, Trash2, UserRound, Wallet, XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FrappeForm } from "@/components/forms/frappe-form";
import type { FormFieldMeta } from "@/components/forms/field-primitives";
import { FormHero, HeroChip, Panel } from "@/components/hr/form-kit";
import { getLinkedValues, useDocMutations, useDocument, type Doc } from "@/hooks/useDoc";
import { useCompanyContext } from "@/hooks/useCompanyContext";
import { notifyDataChanged } from "@/hooks/useRealtime";
import { humanizeError, postCall } from "@/services/frappe";
import { deskUrl } from "@/app/doc-routes";
import { cn } from "@/utils/cn";
import { formatMoney } from "@/utils/currency";
import { formatDate, todayISO } from "@/utils/dates";
import { LoanEligibilityPanel } from "./loan-eligibility";

interface Schedule {
  additional_salary: { name: string; amount: number; from_date?: string; to_date?: string; payroll_date?: string; is_recurring?: number; salary_component: string } | null;
  deductions: { slip: string; start_date: string; end_date: string; docstatus: number; amount: number }[];
  payments: { name: string; posting_date: string; amount: number; mode_of_payment?: string }[];
  outstanding: number;
}
interface Row { n: number; month: string; amount: number; deducted: number; balance: number; slip?: string; state: "Deducted" | "In payroll" | "Scheduled" | "Planned" }

const MONTH_CHOICES = [3, 6, 9, 12];
const n = (v: unknown) => Number(v) || 0;
const firstOfNextMonth = (iso: string) => { const d = new Date(`${iso}T00:00:00`); return new Date(d.getFullYear(), d.getMonth() + 1, 1).toLocaleDateString("en-CA"); };
const addMonths = (iso: string, k: number) => { const d = new Date(`${iso.slice(0, 7)}-01T00:00:00`); return new Date(d.getFullYear(), d.getMonth() + k, 1).toLocaleDateString("en-CA"); };
const monthLabel = (iso: string) => new Date(`${iso.slice(0, 7)}-01T00:00:00`).toLocaleDateString("en-GB", { month: "short", year: "numeric" });

const EMPLOYEE: FormFieldMeta[] = [
  { fieldname: "employee", label: "Employee", fieldtype: "Link", options: "Employee", reqd: true },
  { fieldname: "employee_name", label: "Employee Name", fieldtype: "Data", read_only: true },
  { fieldname: "department", label: "Department", fieldtype: "Link", options: "Department", read_only: true },
  { fieldname: "company", label: "Company", fieldtype: "Link", options: "Company", reqd: true },
  { fieldname: "posting_date", label: "Date", fieldtype: "Date", reqd: true },
  { fieldname: "advance_amount", label: "Amount", fieldtype: "Currency", reqd: true },
  { fieldname: "mode_of_payment", label: "Paid By", fieldtype: "Link", options: "Mode of Payment" },
  { fieldname: "advance_account", label: "Advance Account", fieldtype: "Link", options: "Account", reqd: true },
];
const PURPOSE: FormFieldMeta[] = [{ fieldname: "purpose", label: "Purpose", fieldtype: "Text", reqd: true, placeholder: "Why the employee needs it" }];
const LOAN: FormFieldMeta[] = [
  { fieldname: "mm_installment_months", label: "Instalments (months)", fieldtype: "Int", reqd: true },
  { fieldname: "mm_first_deduction", label: "First Deduction Month", fieldtype: "Date" },
  { fieldname: "mm_guarantor", label: "Guarantor", fieldtype: "Link", options: "Employee" },
  { fieldname: "mm_guarantor_name", label: "Guarantor Name", fieldtype: "Data", read_only: true },
];
const OVERRIDE: FormFieldMeta[] = [
  { fieldname: "mm_override_reason", label: "Override Reason (HR Manager)", fieldtype: "Text", description: "Only to approve a loan that fails the loan policy." },
];

/** Builds the instalment table: planned months from the loan terms (or its recurring Additional Salary), merged with what each salary slip deducted. */
function buildRows(v: Doc, sch?: Schedule): Row[] {
  const isLoan = Boolean(v.mm_is_loan);
  const amount = n(v.advance_amount);
  if (!amount) return [];
  const add = sch?.additional_salary;
  const deducted = new Map<string, Schedule["deductions"][number]>();
  (sch?.deductions ?? []).forEach((d) => deducted.set(d.start_date.slice(0, 7), d));
  let months: number, per: number, start: string;
  if (add && isLoan) {
    start = add.from_date ?? addMonths(todayISO(), 1);
    months = Math.max(1, Math.round((new Date(`${add.to_date}T00:00:00`).getTime() - new Date(`${start}T00:00:00`).getTime()) / (30.44 * 864e5)));
    per = add.amount;
  } else if (add) {
    start = add.payroll_date ?? todayISO(); months = 1; per = add.amount;
  } else if (isLoan) {
    months = Math.max(1, n(v.mm_installment_months) || 1);
    per = Math.round((amount / months) * 100) / 100;
    start = v.mm_first_deduction || firstOfNextMonth(v.posting_date || todayISO());
  } else {
    months = 1; per = amount; start = firstOfNextMonth(v.posting_date || todayISO());
  }
  let balance = amount;
  return Array.from({ length: months }, (_, i) => {
    const month = addMonths(start, i);
    const d = deducted.get(month.slice(0, 7));
    const due = i === months - 1 ? balance : Math.min(per, balance);
    const take = d ? d.amount : 0;
    balance = Math.max(0, Math.round((balance - (d ? take : due)) * 100) / 100);
    return {
      n: i + 1, month, amount: due, deducted: take, balance, slip: d?.slip,
      state: d ? (d.docstatus === 1 ? "Deducted" : "In payroll") : add ? "Scheduled" : "Planned",
    };
  });
}

const STATE_TONE: Record<Row["state"], string> = {
  Deducted: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  "In payroll": "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  Scheduled: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  Planned: "bg-muted text-muted-foreground",
};
const STATUS_TONE: Record<string, string> = {
  Draft: "bg-slate-500/15 text-slate-700 dark:text-slate-300", Unpaid: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  Paid: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300", Returned: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  "Partly Claimed and Returned": "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", Claimed: "bg-teal-500/15 text-teal-700 dark:text-teal-300",
  Cancelled: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
};

function TypeTile({ active, onClick, icon: Icon, title, hint, tone, disabled }: {
  active: boolean; onClick: () => void; icon: typeof Wallet; title: string; hint: string; tone: string; disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={active}
      className={cn("group relative flex flex-1 items-center gap-4 rounded-2xl border p-4 text-left transition disabled:cursor-default",
        active ? `${tone} border-transparent shadow-md ring-2` : "surface-inset hover:border-primary/40", disabled && !active && "opacity-50")}>
      <span className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl", active ? "bg-white/70 dark:bg-white/10" : "bg-muted")}>
        <Icon className="h-6 w-6" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      {active && <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"><Check className="h-3 w-3" /></span>}
    </button>
  );
}

function Stepper({ steps }: { steps: { label: string; done: boolean; hint?: string }[] }) {
  const current = steps.findIndex((s) => !s.done);
  return (
    <ol className="surface flex flex-wrap items-center gap-y-3 rounded-2xl px-5 py-4">
      {steps.map((s, i) => (
        <li key={s.label} className="flex min-w-[140px] flex-1 items-center gap-2.5">
          <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
            s.done ? "bg-emerald-500 text-white" : i === current ? "bg-primary/15 text-primary ring-2 ring-primary/40" : "bg-muted text-muted-foreground")}>
            {s.done ? <Check className="h-4 w-4" /> : i + 1}
          </span>
          <span className="min-w-0">
            <span className={cn("block text-xs font-semibold", !s.done && i !== current && "text-muted-foreground")}>{s.label}</span>
            {s.hint && <span className="block truncate text-[11px] text-muted-foreground">{s.hint}</span>}
          </span>
          {i < steps.length - 1 && <span className={cn("mx-2 hidden h-px flex-1 sm:block", s.done ? "bg-emerald-500/60" : "bg-border")} />}
        </li>
      ))}
    </ol>
  );
}

function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="surface-inset rounded-xl p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-bold tabular-nums", tone)}>{value}</p>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** /hr/advances/new and /hr/advances/:name — a cash advance or salary loan on a full page: terms, live instalment, schedule, eligibility, pay-out and recovery. */
export default function EmployeeAdvanceFormPage() {
  const { name: routeName } = useParams();
  const isNew = !routeName || routeName === "new";
  const name = isNew ? undefined : decodeURIComponent(routeName);
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const presetEmployee = search.get("employee");
  const { company } = useCompanyContext();
  const { data: doc, isLoading, error, mutate } = useDocument("Employee Advance", name);
  const { createDoc, updateDoc, deleteDoc, submitDoc, cancelDoc } = useDocMutations("Employee Advance");
  const { data: schRes, mutate: reloadSchedule } = useFrappeGetCall<{ message: Schedule }>(
    "baogee_textile.loans.get_loan_schedule", { advance: name ?? "" }, name ? `baogee_textile.loans.schedule.${name}` : null,
  );
  const sch = (schRes as unknown as { message?: Schedule })?.message;

  const [values, setValues] = useState<Doc>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<null | "delete" | "cancel" | "submit">(null);
  const [payMode, setPayMode] = useState("Cash");

  useEffect(() => {
    if (isNew) {
      const v: Doc = { company, posting_date: todayISO(), currency: "PKR", exchange_rate: 1, mode_of_payment: "Cash", mm_is_loan: 0 };
      setValues(v);
      if (presetEmployee) {
        v.employee = presetEmployee;
        void getLinkedValues("Employee", presetEmployee, ["employee_name", "department"]).then((e) => setValues((x) => ({ ...x, employee_name: e.employee_name, department: e.department })));
      }
      if (company) void getLinkedValues("Company", company, ["default_employee_advance_account"]).then((c) => setValues((x) => ({ ...x, advance_account: c.default_employee_advance_account })));
    } else if (doc) {
      setValues({ ...doc });
      if (doc.mode_of_payment) setPayMode(doc.mode_of_payment);
    }
    setDirty(false);
  }, [isNew, doc, company, presetEmployee]);

  const docstatus = isNew ? 0 : n(doc?.docstatus);
  const editable = docstatus === 0;
  const isLoan = Boolean(values.mm_is_loan);
  const cur = String(values.currency || "PKR");
  const money = (v: unknown) => formatMoney(n(v), cur);

  const set = (field: string, value: unknown) => {
    setValues((v) => ({ ...v, [field]: value }));
    setErrors((e) => { const { [field]: _, ...rest } = e; return rest; });
    setDirty(true);
    if (field === "employee") {
      void getLinkedValues("Employee", String(value ?? ""), ["employee_name", "department", "company"]).then((e) =>
        setValues((v) => ({ ...v, employee_name: e.employee_name ?? "", department: e.department ?? "", company: e.company || v.company })));
    }
    if (field === "mm_guarantor") {
      void getLinkedValues("Employee", String(value ?? ""), ["employee_name"]).then((e) => setValues((v) => ({ ...v, mm_guarantor_name: e.employee_name ?? "" })));
    }
    if (field === "company" && value) {
      void getLinkedValues("Company", String(value), ["default_employee_advance_account"]).then((c) => setValues((v) => ({ ...v, advance_account: c.default_employee_advance_account })));
    }
  };

  const rows = useMemo(() => buildRows(values, sch), [values, sch]);
  const months = isLoan ? Math.max(1, n(values.mm_installment_months) || 0) : 1;
  const instalment = isLoan && n(values.mm_installment_months) ? Math.round((n(values.advance_amount) / n(values.mm_installment_months)) * 100) / 100 : n(values.advance_amount);
  const paid = n(values.paid_amount), returned = n(values.return_amount) + n(values.claimed_amount);
  const balance = Math.max(0, paid - returned);
  const deductedCount = rows.filter((r) => r.state === "Deducted").length;

  const reload = async () => { await Promise.all([mutate(), reloadSchedule()]); notifyDataChanged(); };
  const run = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key);
    try { await fn(); toast.success(ok); await reload(); } catch (e) { toast.error(humanizeError(e)); } finally { setBusy(null); }
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    [...EMPLOYEE, ...PURPOSE].filter((f) => f.reqd).forEach((f) => { if (!values[f.fieldname]) errs[f.fieldname] = `${f.label} is required`; });
    if (isLoan && !n(values.mm_installment_months)) errs.mm_installment_months = "Number of instalments is required";
    if (isLoan && values.mm_guarantor && values.mm_guarantor === values.employee) errs.mm_guarantor = "The guarantor must be someone else";
    setErrors(errs);
    if (Object.keys(errs).length) toast.error("Please fill in the highlighted fields");
    return !Object.keys(errs).length;
  };

  const payload = () => {
    const keys = ["employee", "company", "posting_date", "advance_amount", "currency", "exchange_rate", "advance_account", "mode_of_payment", "purpose",
      "mm_is_loan", "mm_installment_months", "mm_first_deduction", "mm_guarantor", "mm_override_reason"];
    return Object.fromEntries(keys.map((k) => [k, values[k] ?? (k === "mm_is_loan" ? 0 : null)]).filter(([k, v]) => v !== null || k.startsWith("mm_")));
  };

  const save = async (andSubmit = false) => {
    if (!validate()) return;
    setBusy(andSubmit ? "submit" : "save");
    try {
      let docName = name;
      if (isNew) {
        const created = await createDoc(payload());
        docName = created.name;
      } else if (dirty) {
        await updateDoc(name!, payload());
      }
      if (andSubmit && docName) await submitDoc(docName);
      toast.success(andSubmit ? (isLoan ? "Loan approved" : "Advance approved") : "Saved");
      notifyDataChanged();
      setDirty(false);
      if (isNew && docName) navigate(`/hr/advances/${encodeURIComponent(docName)}`, { replace: true });
      else await reload();
    } catch (e) {
      toast.error(humanizeError(e));
    } finally {
      setBusy(null);
    }
  };

  const payOut = () => run("pay", async () => {
    const r = await postCall<{ message?: { warning?: string } }>("baogee_textile.loans.pay_out", { advance: name, mode_of_payment: payMode });
    const w = (r as { message?: { warning?: string } })?.message?.warning ?? (r as { warning?: string })?.warning;
    if (w) toast(w, { icon: "⚠️", duration: 8000 });
  }, isLoan ? "Loan paid out — instalments set up" : "Advance paid out");
  const setupRecovery = () => run("recover", () => postCall("baogee_textile.loans.recover_from_salary", { advance: name }),
    isLoan ? "Instalments set up — they will be deducted from salary" : "Recovery added to the next salary");

  if (!isNew && isLoading) return <div className="surface h-64 animate-pulse rounded-3xl" />;
  if (!isNew && (error || !doc)) return <div className="surface rounded-2xl p-6 text-sm text-destructive">{error ? humanizeError(error) : "Not found"}</div>;

  const status = isNew ? "New" : String(values.status || "Draft");
  const hasRecovery = Boolean(sch?.additional_salary);
  const steps = [
    { label: "Request", done: !isNew, hint: isNew ? "Fill in and save" : formatDate(values.posting_date) },
    { label: "Approved", done: docstatus === 1, hint: docstatus === 1 ? "Submitted" : "Submit to approve" },
    { label: "Paid out", done: paid > 0, hint: sch?.payments?.[0] ? `${formatDate(sch.payments[0].posting_date)} · ${sch.payments[0].mode_of_payment ?? ""}` : "Cash or bank" },
    { label: isLoan ? "Instalments" : "Recovery set", done: hasRecovery, hint: hasRecovery ? (isLoan ? `${rows.length} × ${money(sch?.additional_salary?.amount)}` : formatDate(sch?.additional_salary?.payroll_date)) : "From salary" },
    { label: "Recovered", done: paid > 0 && balance <= 0.5, hint: paid > 0 ? `${money(returned)} of ${money(paid)}` : undefined },
  ];

  return (
    <div className="space-y-6 pb-4">
      <FormHero
        backTo="/hr/advances" backLabel="Back to advances" icon={isLoan ? HandCoins : Wallet} hue={isLoan ? "indigo" : "amber"}
        kicker={`${isLoan ? "Salary loan" : "Cash advance"}${name ? ` · ${name}` : ""}`}
        title={String(values.employee_name || (isNew ? (isLoan ? "New salary loan" : "New cash advance") : name))}
        chips={<>
          <HeroChip tone={cn("font-medium", STATUS_TONE[status] ?? "border border-border bg-background/60")}>{status}</HeroChip>
          {values.department && <HeroChip>{String(values.department).replace(/ - [A-Z]+$/, "")}</HeroChip>}
          {values.employee && <HeroChip><span className="font-mono">{values.employee}</span></HeroChip>}
          {isLoan && values.mm_guarantor_name && <HeroChip><ShieldCheck className="mr-1 inline h-3 w-3" />Guarantor {values.mm_guarantor_name}</HeroChip>}
        </>}
        figures={[
          { label: "Amount", value: money(values.advance_amount) },
          ...(isLoan ? [{ label: "Per month", value: money(instalment), tone: "text-indigo-600 dark:text-indigo-400" }] : []),
          ...(!isNew ? [{ label: "Recovered", value: money(returned), tone: "text-emerald-600 dark:text-emerald-400" },
            { label: "Balance", value: money(balance), tone: balance > 0 ? "text-amber-600 dark:text-amber-400" : undefined }] : []),
        ]}
      />

      {!isNew && <Stepper steps={steps} />}

      <div className="flex flex-col gap-3 sm:flex-row">
        <TypeTile active={!isLoan} disabled={!editable} onClick={() => set("mm_is_loan", 0)} icon={Wallet} tone="bg-amber-500/10 ring-amber-500/40"
          title="Cash advance" hint="Paid now, recovered in full from the next salary" />
        <TypeTile active={isLoan} disabled={!editable} onClick={() => set("mm_is_loan", 1)} icon={HandCoins} tone="bg-indigo-500/10 ring-indigo-500/40"
          title="Salary loan" hint="Paid now, recovered in equal monthly instalments from salary" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Panel icon={UserRound} title="Employee and amount" description="Who receives it, how much and how it is paid">
            <fieldset disabled={!editable} className="form-flat"><FrappeForm fields={EMPLOYEE} values={values} onChange={set} errors={errors} /></fieldset>
            <fieldset disabled={!editable} className="form-flat form-single mt-4"><FrappeForm fields={PURPOSE} values={values} onChange={set} errors={errors} /></fieldset>
          </Panel>

          {isLoan && (
            <Panel icon={CalendarRange} title="Instalments" description="How many months, from which salary, and who guarantees it">
              {editable && (
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Quick pick</span>
                  {MONTH_CHOICES.map((m) => (
                    <button key={m} type="button" onClick={() => set("mm_installment_months", m)}
                      className={cn("rounded-full border px-3 py-1 text-xs font-medium transition",
                        n(values.mm_installment_months) === m ? "border-transparent bg-indigo-600 text-white shadow" : "border-border hover:border-indigo-400")}>
                      {m} months{n(values.advance_amount) ? ` · ${money(n(values.advance_amount) / m)}` : ""}
                    </button>
                  ))}
                </div>
              )}
              <fieldset disabled={!editable} className="form-flat"><FrappeForm fields={LOAN} values={values} onChange={set} errors={errors} /></fieldset>
              {editable && <fieldset className="form-flat form-single mt-4"><FrappeForm fields={OVERRIDE} values={values} onChange={set} /></fieldset>}
            </Panel>
          )}
        </div>

        <div className="space-y-6">
          <section className={cn("relative overflow-hidden rounded-2xl p-5 text-white shadow-lg bg-gradient-to-br",
            isLoan ? "from-indigo-600 via-violet-600 to-fuchsia-600" : "from-amber-500 via-orange-500 to-rose-500")}>
            <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/15 blur-2xl" />
            <p className="text-xs font-medium uppercase tracking-wider text-white/80">{isLoan ? "Monthly instalment" : "Recovered from salary"}</p>
            <p className="mt-1 text-4xl font-bold tabular-nums">{money(instalment)}</p>
            <p className="mt-1 text-sm text-white/85">
              {isLoan ? `${months} month${months === 1 ? "" : "s"} · total ${money(values.advance_amount)}` : "In one deduction"}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl bg-white/15 p-2.5"><p className="text-white/75">First deduction</p><p className="font-semibold">{rows[0] ? monthLabel(rows[0].month) : "—"}</p></div>
              <div className="rounded-xl bg-white/15 p-2.5"><p className="text-white/75">Last deduction</p><p className="font-semibold">{rows.length ? monthLabel(rows[rows.length - 1].month) : "—"}</p></div>
            </div>
          </section>

          {!isNew && (
            <Panel icon={Landmark} title="Money" description="Paid out, recovered and still owed">
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Paid out" value={money(paid)} hint={paid ? undefined : "Not paid yet"} />
                <Stat label="Recovered" value={money(returned)} tone="text-emerald-600 dark:text-emerald-400" hint={isLoan && rows.length ? `${deductedCount} of ${rows.length} instalments` : undefined} />
                <Stat label="Balance" value={money(balance)} tone={balance > 0 ? "text-amber-600 dark:text-amber-400" : undefined} />
                <Stat label="Status" value={<span className="text-sm">{status}</span>} />
              </div>
              {paid > 0 && (
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400" style={{ width: `${Math.min(100, (returned / paid) * 100)}%` }} />
                </div>
              )}
              {(sch?.payments ?? []).length > 0 && (
                <ul className="mt-4 space-y-1.5 text-xs">
                  {sch!.payments.map((p) => (
                    <li key={p.name} className="flex items-center gap-2">
                      <Receipt className="h-3.5 w-3.5 text-muted-foreground" />
                      <a href={deskUrl("Payment Entry", p.name)} target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">{p.name}</a>
                      <span className="text-muted-foreground">{formatDate(p.posting_date)} · {p.mode_of_payment}</span>
                      <span className="ml-auto tabular-nums">{money(p.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>
      </div>

      {rows.length > 0 && (
        <Panel icon={FileText} title={isLoan ? "Instalment schedule" : "Recovery"}
          description={hasRecovery
            ? `Set up in payroll (${sch!.additional_salary!.name}, ${sch!.additional_salary!.salary_component}) — each salary slip deducts its month`
            : "Preview — the deductions are set up in payroll when it is paid out"}
          bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="surface-inset text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-2.5 text-left">#</th><th className="px-3 py-2.5 text-left">Salary month</th>
                  <th className="px-3 py-2.5 text-right">Instalment</th><th className="px-3 py-2.5 text-right">Deducted</th>
                  <th className="px-3 py-2.5 text-right">Balance after</th><th className="px-3 py-2.5 text-left">Status</th><th className="px-5 py-2.5 text-left">Salary slip</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.n} className="border-t border-border dark:border-white/10">
                    <td className="px-5 py-2 tabular-nums text-muted-foreground">{r.n}</td>
                    <td className="px-3 py-2 font-medium">{monthLabel(r.month)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(r.amount)}</td>
                    <td className={cn("px-3 py-2 text-right tabular-nums", r.deducted ? "font-semibold text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>{r.deducted ? money(r.deducted) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(r.balance)}</td>
                    <td className="px-3 py-2">
                      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium", STATE_TONE[r.state])}>
                        {r.state === "Deducted" ? <CheckCircle2 className="h-3 w-3" /> : <CircleDashed className="h-3 w-3" />}{r.state}
                      </span>
                    </td>
                    <td className="px-5 py-2 text-xs">{r.slip ? <a href={deskUrl("Salary Slip", r.slip)} target="_blank" rel="noreferrer" className="text-primary hover:underline">{r.slip}</a> : "—"}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="surface-inset text-xs font-semibold">
                <tr>
                  <td className="px-5 py-2" colSpan={2}>Total</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(rows.reduce((s, r) => s + r.amount, 0))}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-emerald-600 dark:text-emerald-400">{money(rows.reduce((s, r) => s + r.deducted, 0))}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(rows[rows.length - 1].balance)}</td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </table>
          </div>
        </Panel>
      )}

      {isLoan && <LoanEligibilityPanel values={values} name={name} />}

      {/* sticky action bar — the buttons follow the advance through its life */}
      <div className="sticky bottom-0 z-30 -mx-3 border-t border-border bg-background/90 backdrop-blur sm:-mx-5 lg:-mx-6 dark:border-white/10">
        <div className="flex flex-wrap items-center gap-2 px-6 py-3">
          <span className="mr-auto text-xs text-muted-foreground">
            {isNew ? "Fill in the details, then save as draft or approve"
              : docstatus === 0 ? (dirty ? "Unsaved changes" : "Draft — approve to pay it out")
              : docstatus === 2 ? "Cancelled"
              : paid <= 0 ? "Approved — ready to pay out"
              : !hasRecovery ? (isLoan ? "Paid — set up the instalments" : "Paid — add the recovery to a salary")
              : balance > 0.5 ? "Recovering from salary" : "Fully recovered"}
          </span>
          {name && <a href={deskUrl("Employee Advance", name)} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-xs text-muted-foreground hover:text-foreground"><ExternalLink className="h-3.5 w-3.5" /> Desk</a>}
          {docstatus === 0 && !isNew && <Button variant="outline" onClick={() => setConfirm("delete")} className="text-destructive hover:text-destructive"><Trash2 className="h-4 w-4" /> Delete</Button>}
          {docstatus === 1 && paid <= 0 && <Button variant="outline" onClick={() => setConfirm("cancel")} className="text-destructive hover:text-destructive"><XCircle className="h-4 w-4" /> Cancel</Button>}
          {docstatus === 0 && <Button variant="outline" onClick={() => void save(false)} loading={busy === "save"} disabled={!isNew && !dirty}>Save draft</Button>}
          {docstatus === 0 && <Button variant="create" onClick={() => setConfirm("submit")} loading={busy === "submit"}><Send className="h-4 w-4" /> Approve</Button>}
          {docstatus === 1 && paid <= 0 && (
            <>
              <select value={payMode} onChange={(e) => setPayMode(e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                {["Cash", "Cheque", "Wire Transfer", "Bank Draft"].map((m) => <option key={m}>{m}</option>)}
              </select>
              <Button variant="create" onClick={() => void payOut()} loading={busy === "pay"}><Banknote className="h-4 w-4" /> Pay out {money(values.advance_amount)}</Button>
            </>
          )}
          {docstatus === 1 && paid > 0 && !hasRecovery && (
            <Button variant="create" onClick={() => void setupRecovery()} loading={busy === "recover"}>
              <CalendarRange className="h-4 w-4" /> {isLoan ? "Set up instalments" : "Recover from next salary"}
            </Button>
          )}
          {docstatus === 1 && <Link to="/hr/loans" className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm hover:bg-muted"><HandCoins className="h-4 w-4" /> Loan ledger</Link>}
        </div>
      </div>

      <ConfirmDialog
        open={confirm !== null}
        onClose={() => setConfirm(null)}
        title={confirm === "delete" ? "Delete this draft?" : confirm === "cancel" ? "Cancel this advance?" : isLoan ? "Approve this loan?" : "Approve this advance?"}
        description={confirm === "submit"
          ? `${values.employee_name || "The employee"} · ${money(values.advance_amount)}${isLoan ? ` over ${months} months (${money(instalment)} / month)` : ""}. After approval it can be paid out.`
          : confirm === "delete" ? "The draft is removed." : "The approved advance is cancelled. It has not been paid."}
        confirmLabel={confirm === "delete" ? "Delete" : confirm === "cancel" ? "Cancel advance" : "Approve"}
        destructive={confirm !== "submit"}
        onConfirm={async () => {
          const c = confirm;
          setConfirm(null);
          if (c === "submit") await save(true);
          else if (c === "delete") await run("delete", async () => { await deleteDoc(name!); navigate("/hr/advances", { replace: true }); }, "Draft deleted");
          else if (c === "cancel") await run("cancel", () => cancelDoc(name!), "Advance cancelled");
        }}
      />
    </div>
  );
}
