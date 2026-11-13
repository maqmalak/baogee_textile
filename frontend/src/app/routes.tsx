import { Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { LoginPage } from "@/pages/Auth/LoginPage";
import { ComingSoonPage, FullPageLoader } from "@/pages/common/ComingSoonPage";

// Baogee Textile: the HR and Payroll apps forked from micromaxerp (erpnext-react/frontend), plus account and settings.
const DesktopPage = lazy(() => import("@/pages/Desktop/DesktopPage"));
const HrSalaryLoansPage = lazy(() => import("@/pages/HR/SalaryLoansPage"));
const HrRosterPage = lazy(() => import("@/pages/HR/RosterPage"));
const HrEmployeesPage = lazy(() => import("@/pages/HR/EmployeesPage").then((m) => ({ default: m.default })));
const HrEmployeeDetailPage = lazy(() => import("@/pages/HR/EmployeeDetailPage").then((m) => ({ default: m.default })));
const HrDepartmentsPage = lazy(() => import("@/pages/HR/DepartmentsPage").then((m) => ({ default: m.default })));
const HrDesignationsPage = lazy(() => import("@/pages/HR/DesignationsPage").then((m) => ({ default: m.default })));
const HrBranchesPage = lazy(() => import("@/pages/HR/BranchesPage").then((m) => ({ default: m.default })));
const HrAttendancePage = lazy(() => import("@/pages/HR/AttendancePage").then((m) => ({ default: m.default })));
const HrLeaveApplicationsPage = lazy(() => import("@/pages/HR/LeaveApplicationsPage").then((m) => ({ default: m.default })));
const HrLeaveAllocationsPage = lazy(() => import("@/pages/HR/LeaveAllocationsPage").then((m) => ({ default: m.default })));
const HrHolidayListsPage = lazy(() => import("@/pages/HR/HolidayListsPage").then((m) => ({ default: m.default })));
const HrExpenseClaimsPage = lazy(() => import("@/pages/HR/ExpenseClaimsPage").then((m) => ({ default: m.default })));
const HrEmployeeAdvancesPage = lazy(() => import("@/pages/HR/EmployeeAdvancesPage").then((m) => ({ default: m.default })));
const HrGratuityPage = lazy(() => import("@/pages/HR/GratuityPage").then((m) => ({ default: m.default })));
const PayrollSalaryComponentsPage = lazy(() => import("@/pages/Payroll/SalaryComponentsPage").then((m) => ({ default: m.default })));
const PayrollSalaryStructuresPage = lazy(() => import("@/pages/Payroll/SalaryStructuresPage").then((m) => ({ default: m.default })));
const PayrollSalaryStructureAssignmentsPage = lazy(() => import("@/pages/Payroll/SalaryStructureAssignmentsPage").then((m) => ({ default: m.default })));
const PayrollSalarySlipsPage = lazy(() => import("@/pages/Payroll/SalarySlipsPage").then((m) => ({ default: m.default })));
const PayrollSalarySlipDetailPage = lazy(() => import("@/pages/Payroll/SalarySlipDetailPage").then((m) => ({ default: m.default })));
const HrDepartmentFormPage = lazy(() => import("@/pages/HR/DepartmentFormPage"));
const HrDesignationFormPage = lazy(() => import("@/pages/HR/DesignationFormPage"));
const HrEmployeeNewPage = lazy(() => import("@/pages/HR/EmployeeNewPage"));
const HelpPage = lazy(() => import("@/pages/Help/HelpPage").then((m) => ({ default: m.HelpPage })));
const HrEmployeeAdvanceFormPage = lazy(() => import("@/pages/HR/EmployeeAdvanceFormPage"));
const HrDocPage = lazy(() => import("@/pages/HR/HrDocPage"));
const HrShiftsOverviewPage = lazy(() => import("@/pages/HR/ShiftsOverviewPage"));
const HrSetupPage = lazy(() => import("@/pages/HR/HRSetupPage"));
const HrHomePage = lazy(() => import("@/pages/HR/HRHomePage"));
const PayrollHomePage = lazy(() => import("@/pages/Payroll/PayrollHomePage"));
const AccountProfilePage = lazy(() => import("@/pages/Account/AccountProfilePage").then((m) => ({ default: m.AccountProfilePage })));
const NotificationsPage = lazy(() => import("@/pages/Settings/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const GeneralSettingsPage = lazy(() => import("@/pages/Settings/GeneralSettingsPage").then((m) => ({ default: m.GeneralSettingsPage })));
const CompanyPage = lazy(() => import("@/pages/Settings/CompanyPage").then((m) => ({ default: m.CompanyPage })));

/** Config-driven HR / payroll screens: path → HrDocPage key (each gets a list and a `:name` form route). */
const HR_DOC_ROUTES: [string, import("@/pages/HR/HrDocPage").HrDocKey][] = [
  ["hr/leave-types", "leaveTypes"],
  ["hr/shift-types", "shiftTypes"],
  ["hr/shift-assignments", "shiftAssignments"],
  ["hr/shift-requests", "shiftRequests"],
  ["hr/shift-locations", "shiftLocations"],
  ["hr/shift-schedules", "shiftSchedules"],
  ["hr/shift-schedule-assignments", "shiftScheduleAssignments"],
  ["hr/attendance-requests", "attendanceRequests"],
  ["hr/checkins", "checkins"],
  ["hr/leave-policies", "leavePolicies"],
  ["hr/leave-policy-assignments", "leavePolicyAssignments"],
  ["hr/leave-periods", "leavePeriods"],
  ["hr/compensatory-leave", "compensatoryLeave"],
  ["hr/leave-encashment", "leaveEncashment"],
  ["hr/holiday-list-assignments", "holidayListAssignments"],
  ["hr/employment-types", "employmentTypes"],
  ["hr/employee-grades", "employeeGrades"],
  ["hr/promotions", "promotions"],
  ["hr/transfers", "transfers"],
  ["hr/separations", "separations"],
  ["hr/expense-claim-types", "expenseClaimTypes"],
  ["payroll/entries", "entries"],
  ["payroll/old-salary-sheets", "legacySalary"],
  ["payroll/additional-salary", "additionalSalary"],
  ["payroll/periods", "periods"],
  ["payroll/income-tax-slabs", "taxSlabs"],
  ["payroll/gratuity-rules", "gratuityRules"],
  ["payroll/incentives", "incentives"],
  ["payroll/retention-bonus", "retentionBonus"],
  ["payroll/salary-withholding", "salaryWithholding"],
  ["payroll/tax-declarations", "taxDeclarations"],
  ["payroll/overtime-types", "overtimeTypes"],
  ["payroll/overtime-slips", "overtimeSlips"],
];

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Navigate to="/home" replace />} />

      <Route element={<AppShell />}>
        <Route path="home" element={<Suspense fallback={<FullPageLoader />}><DesktopPage /></Suspense>} />
        <Route path="hr" element={<Suspense fallback={<FullPageLoader />}><HrHomePage /></Suspense>} />
        <Route path="hr/settings" element={<Suspense fallback={<FullPageLoader />}><HrDocPage which="hrSettings" /></Suspense>} />
        <Route path="hr/shifts" element={<Suspense fallback={<FullPageLoader />}><HrShiftsOverviewPage /></Suspense>} />
        <Route path="hr/setup" element={<Suspense fallback={<FullPageLoader />}><HrSetupPage /></Suspense>} />
        {HR_DOC_ROUTES.flatMap(([path, which]) => [
          <Route key={path} path={path} element={<Suspense fallback={<FullPageLoader />}><HrDocPage which={which} /></Suspense>} />,
          <Route key={`${path}/:name`} path={`${path}/:name`} element={<Suspense fallback={<FullPageLoader />}><HrDocPage which={which} form /></Suspense>} />,
        ])}
        <Route path="hr/employees" element={<Suspense fallback={<FullPageLoader />}><HrEmployeesPage /></Suspense>} />
        <Route path="hr/employees/new" element={<Suspense fallback={<FullPageLoader />}><HrEmployeeNewPage /></Suspense>} />
        <Route path="hr/employees/:name" element={<Suspense fallback={<FullPageLoader />}><HrEmployeeDetailPage /></Suspense>} />
        <Route path="hr/departments" element={<Suspense fallback={<FullPageLoader />}><HrDepartmentsPage /></Suspense>} />
        <Route path="hr/departments/:name" element={<Suspense fallback={<FullPageLoader />}><HrDepartmentFormPage /></Suspense>} />
        <Route path="hr/designations" element={<Suspense fallback={<FullPageLoader />}><HrDesignationsPage /></Suspense>} />
        <Route path="hr/designations/:name" element={<Suspense fallback={<FullPageLoader />}><HrDesignationFormPage /></Suspense>} />
        <Route path="hr/branches" element={<Suspense fallback={<FullPageLoader />}><HrBranchesPage /></Suspense>} />
        <Route path="hr/attendance" element={<Suspense fallback={<FullPageLoader />}><HrAttendancePage /></Suspense>} />
        <Route path="hr/roster" element={<Suspense fallback={<FullPageLoader />}><HrRosterPage /></Suspense>} />
        <Route path="hr/leave-applications" element={<Suspense fallback={<FullPageLoader />}><HrLeaveApplicationsPage /></Suspense>} />
        <Route path="hr/leave-applications/:name" element={<Suspense fallback={<FullPageLoader />}><HrDocPage which="leaveApplication" form /></Suspense>} />
        <Route path="hr/leave-allocations" element={<Suspense fallback={<FullPageLoader />}><HrLeaveAllocationsPage /></Suspense>} />
        <Route path="hr/holiday-lists" element={<Suspense fallback={<FullPageLoader />}><HrHolidayListsPage /></Suspense>} />
        <Route path="hr/expense-claims" element={<Suspense fallback={<FullPageLoader />}><HrExpenseClaimsPage /></Suspense>} />
        <Route path="hr/expense-claims/:name" element={<Suspense fallback={<FullPageLoader />}><HrDocPage which="expenseClaim" form /></Suspense>} />
        <Route path="hr/advances" element={<Suspense fallback={<FullPageLoader />}><HrEmployeeAdvancesPage /></Suspense>} />
        <Route path="hr/loans" element={<Suspense fallback={<FullPageLoader />}><HrSalaryLoansPage /></Suspense>} />
        <Route path="hr/advances/:name" element={<Suspense fallback={<FullPageLoader />}><HrEmployeeAdvanceFormPage /></Suspense>} />
        <Route path="hr/gratuity" element={<Suspense fallback={<FullPageLoader />}><HrGratuityPage /></Suspense>} />

        <Route path="help" element={<Suspense fallback={<FullPageLoader />}><HelpPage /></Suspense>} />
        <Route path="help/guides" element={<Suspense fallback={<FullPageLoader />}><HelpPage /></Suspense>} />

        {/* Payroll */}
        <Route path="payroll" element={<Suspense fallback={<FullPageLoader />}><PayrollHomePage /></Suspense>} />
        <Route path="payroll/settings" element={<Suspense fallback={<FullPageLoader />}><HrDocPage which="payrollSettings" /></Suspense>} />
        <Route path="payroll/salary-components" element={<Suspense fallback={<FullPageLoader />}><PayrollSalaryComponentsPage /></Suspense>} />
        <Route path="payroll/salary-structures" element={<Suspense fallback={<FullPageLoader />}><PayrollSalaryStructuresPage /></Suspense>} />
        <Route path="payroll/salary-structure-assignments" element={<Suspense fallback={<FullPageLoader />}><PayrollSalaryStructureAssignmentsPage /></Suspense>} />
        <Route path="payroll/salary-slips" element={<Suspense fallback={<FullPageLoader />}><PayrollSalarySlipsPage /></Suspense>} />
        <Route path="payroll/salary-slips/:name" element={<Suspense fallback={<FullPageLoader />}><PayrollSalarySlipDetailPage /></Suspense>} />

        {/* Settings */}
        <Route path="settings" element={<Suspense fallback={<FullPageLoader />}><GeneralSettingsPage /></Suspense>} />
        <Route path="settings/company" element={<Suspense fallback={<FullPageLoader />}><CompanyPage /></Suspense>} />
        <Route path="settings/notifications" element={<Suspense fallback={<FullPageLoader />}><NotificationsPage /></Suspense>} />

        {/* My Account */}
        <Route path="account" element={<Suspense fallback={<FullPageLoader />}><AccountProfilePage /></Suspense>} />
        <Route path="account/security" element={<ComingSoonPage title="Security" description="Password and two-factor authentication" />} />

        <Route path="*" element={<Navigate to="/home" replace />} />
      </Route>
    </Routes>
  );
}
