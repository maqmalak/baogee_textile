---
title: Timekeeper — biometric machines and punches
roles: HR User, Timekeeper
order: 30
---
# Timekeeper — biometric machines and punches

## The machines
- Each hall has a ZKTeco machine on the factory network (for example Bleaching Hall and Finishing Hall).
- Every employee is enrolled on the machine with a **user number**. The same number goes in the employee's **Attendance Device ID**.

## The sync PC
- A small PC at the site (Ubuntu, on the same network as the machines, internet 24/7) runs the **Biometric Sync** tool.
- The tool reads new punches from every machine and sends them to the ERP as **Checkins**. Punches already sent are never sent twice.
- On the tool's page: each machine (name, IP, port, serial), **Test** to check it answers, and the history of sync runs (machines read, new punches, pushed, errors).

## Every morning
1. Open **Checkins** and filter yesterday: every employee on duty should have an IN and an OUT.
2. A punch with no employee means the user number is not set on anyone: fix the **Attendance Device ID** on the employee.
3. Machine shown offline in the sync tool: check its power and network cable, then **Test** again.

## From punches to attendance
- With a shift assigned, HRMS marks attendance from the punches: present, half day, absent, **late** after the 30-minute grace, early exit.
- **Roster** shows who works which shift on which day; **Shift Assignments** set it for a period.
- **Attendance** gives the day's and month's picture by department.
