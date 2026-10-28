import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ExternalLink, LayoutGrid } from "lucide-react";
import { APP_NAVIGATION } from "@/app/navigation";
import { GlossyIcon } from "@/components/ui/app-icon";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/utils/cn";

/** One hue per sidebar section, so each section's icons read as a group. */
const SECTION_HUES = ["violet", "sky", "indigo", "teal", "amber", "rose", "emerald", "orange", "fuchsia", "cyan", "lime", "slate"];
const STORE_KEY = "baogee.workspace-icons.";

/**
 * Workspace icons for an app's home page (HR, Payroll): every page of the app's sidebar as a glossy icon, grouped by
 * sidebar section, like the Desktop. ERPNext desk tools (/desk/…) open in a new tab, as in the sidebar.
 */
export function WorkspaceIcons({ segment, title }: { segment: string; title: string }) {
  const { hasRole } = useAuth();
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(STORE_KEY + segment) !== "0"; } catch { return true; }
  });
  const toggle = () => {
    setOpen((v) => {
      try { localStorage.setItem(STORE_KEY + segment, v ? "0" : "1"); } catch { /* storage blocked */ }
      return !v;
    });
  };

  const home = `/${segment}`;
  const seen = new Set<string>([home]);
  const sections = (APP_NAVIGATION[segment] ?? [])
    .map((group, i) => ({
      title: group.title || "Start",
      hue: SECTION_HUES[i % SECTION_HUES.length],
      items: group.items.filter((item) => {
        if (seen.has(item.to) || (item.roles?.length && !hasRole(...item.roles))) return false;
        seen.add(item.to);
        return true;
      }),
    }))
    .filter((s) => s.items.length > 0);
  const count = sections.reduce((n, s) => n + s.items.length, 0);

  return (
    <section className="rounded-2xl border border-border bg-card/60">
      <button type="button" onClick={toggle} aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left">
        <LayoutGrid className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted-foreground">{count} pages</span>
        <ChevronDown className={cn("ml-auto h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-4 border-t border-border px-4 pb-4 pt-3">
          {sections.map((s) => (
            <div key={s.title}>
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{s.title}</h3>
              <div className="grid grid-cols-3 gap-1 sm:grid-cols-5 md:grid-cols-7 lg:grid-cols-9">
                {s.items.map((item) => {
                  const desk = item.to.startsWith("/desk/");
                  const body = (
                    <>
                      <GlossyIcon icon={item.icon ?? LayoutGrid} hue={s.hue}
                        badge={desk ? <span className="flex h-5 w-5 items-center justify-center rounded-full bg-background shadow ring-1 ring-border"><ExternalLink className="h-3 w-3 text-muted-foreground" /></span> : undefined} />
                      <span className="line-clamp-2 w-full text-[12px] font-medium leading-tight">{item.label}</span>
                    </>
                  );
                  const cls = "group flex w-full flex-col items-center gap-1.5 rounded-2xl p-2 text-center outline-none transition focus-visible:ring-2 focus-visible:ring-primary";
                  return desk ? (
                    <a key={item.to} href={item.to} target="_blank" rel="noreferrer" className={cls} title="Opens in a new tab (ERPNext desk)">{body}</a>
                  ) : (
                    <Link key={item.to} to={item.to} className={cls} title={item.label}>{body}</Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
