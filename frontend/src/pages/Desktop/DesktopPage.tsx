import { Link } from "react-router-dom";
import {
  Banknote, CalendarCheck, Clock3, FileText, HandCoins, Landmark, ListChecks, PlayCircle, Receipt, Users2, Wallet,
  type LucideIcon,
} from "lucide-react";
import { APPS, APP_GROUPS, type AppTile } from "@/app/apps";
import { GlossyIcon, hueOf } from "@/components/ui/app-icon";
import { useAuth } from "@/hooks/useAuth";

/**
 * Baogee Textile desktop (/home): the app icons (HR, Payroll, Settings, My Account) in the same glossy style as the
 * MicroMax desktop, plus one-click icons for the HR and payroll screens used every day.
 * (MicroMax's desktop also reads mm_core.home / system_status, which this site doesn't have.)
 */
interface Shortcut { label: string; sub: string; to: string; icon: LucideIcon; hue: string }

const SHORTCUTS: Shortcut[] = [
  { label: "Employees", sub: "People", to: "/hr/employees", icon: Users2, hue: "violet" },
  { label: "Attendance", sub: "Daily register", to: "/hr/attendance", icon: CalendarCheck, hue: "sky" },
  { label: "Shifts", sub: "Grace periods", to: "/hr/shifts", icon: Clock3, hue: "indigo" },
  { label: "Salary Loans", sub: "Instalments", to: "/hr/loans", icon: Landmark, hue: "amber" },
  { label: "Advances", sub: "Employee advances", to: "/hr/advances", icon: HandCoins, hue: "orange" },
  { label: "Expense Claims", sub: "Reimbursements", to: "/hr/expense-claims", icon: Receipt, hue: "rose" },
  { label: "Run Payroll", sub: "New payroll entry", to: "/payroll/entries/new", icon: PlayCircle, hue: "lime" },
  { label: "Salary Slips", sub: "This month", to: "/payroll/salary-slips", icon: FileText, hue: "emerald" },
  { label: "Salary Structures", sub: "Pay scales", to: "/payroll/salary-structures", icon: Wallet, hue: "teal" },
  { label: "HR Setup", sub: "Checklist", to: "/hr/setup", icon: ListChecks, hue: "slate" },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function IconTile({ to, icon, hue, label, sub, external }: { to: string; icon: LucideIcon; hue: string; label: string; sub?: string; external?: boolean }) {
  const cls = "group flex w-full flex-col items-center gap-1.5 rounded-2xl p-2 text-center outline-none transition focus-visible:ring-2 focus-visible:ring-primary";
  const body = (
    <>
      <GlossyIcon icon={icon} hue={hue} />
      <span className="w-full truncate text-[13px] font-semibold leading-tight">{label}</span>
      {sub && <span className="-mt-1 w-full truncate text-[10px] text-muted-foreground">{sub}</span>}
    </>
  );
  // a page served by the site itself (e.g. the Biometric Sync console) needs a full page load
  return external ? <a href={to} title={label} className={cls}>{body}</a> : <Link to={to} title={label} className={cls}>{body}</Link>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-card/60 p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8">{children}</div>
    </section>
  );
}

export function DesktopPage() {
  const { currentUser, hasRole } = useAuth();
  const visible = (app: AppTile) => !app.roles?.length || hasRole(...app.roles);
  const groups = APP_GROUPS.map((g) => ({ title: g, apps: APPS.filter((a) => a.group === g && visible(a)) })).filter((g) => g.apps.length);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-6">
      <div className="flex items-center gap-3">
        <GlossyIcon icon={Banknote} hue="violet" size="sm" />
        <div>
          <h1 className="text-xl font-bold leading-tight">Baogee Textile</h1>
          <p className="text-sm text-muted-foreground">
            {greeting()}{currentUser && currentUser !== "Guest" ? `, ${currentUser}` : ""} · HR &amp; Payroll
          </p>
        </div>
      </div>

      {groups.map((g) => (
        <Section key={g.title} title={g.title}>
          {g.apps.map((app) => (
            <IconTile key={app.id} to={app.to} icon={app.icon} hue={hueOf(app.colorClass)} label={app.label} sub={app.tagline} external={app.external} />
          ))}
        </Section>
      ))}

      <Section title="Shortcuts">
        {SHORTCUTS.map((s) => <IconTile key={s.to} {...s} />)}
      </Section>
    </div>
  );
}

export default DesktopPage;
