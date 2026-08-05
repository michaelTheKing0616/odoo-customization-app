# Vertical playbook: School / Education

Expert vertical guidance for building an Odoo **Community** database for schools, training
centers, and academies. Keywords: school, education, student, enrollment, tuition, classroom,
teacher, parent portal, admissions, gradebook, LMS, campus, SIS.

## Summary

Schools rarely fit a single Odoo “Education” app on Community. The practical pattern is:
**Contacts** for people (students, parents, staff), **Website** + **eLearning** for public
content and courses, **CRM** for admissions pipeline, **Sales/Accounting** for fees,
**Events/Calendar** for scheduling, **Survey** for forms, and **custom `x_` models** for
classes, enrollments, grades, and attendance. Use this app's builder or Draft Studio to
scaffold custom models, then sandbox-test before production.

## Stock Odoo apps — recommended install order

1. **`base`**, **`web`**, **`mail`** — platform (always present).
2. **`contacts`** — students, parents, guardians, staff as `res.partner` with tags/categories
   (e.g. Student, Parent, Teacher, Alumni).
3. **`website`** — public site, admission inquiry forms, parent information pages.
4. **`website_slides`** (eLearning) — course content, lessons, quizzes; good for blended
   learning and staff training; not a full gradebook on its own.
5. **`crm`** — admissions leads (inquiry → application → enrolled).
6. **`sale`**, **`account`** — fee products, quotations/invoices, payment tracking.
7. **`event`**, **`calendar`** — open days, parent meetings, exam timetables (with custom links).
8. **`hr`** — staff records if you manage employees in Odoo (attendance via HR optional).
9. **`project`** — internal improvement projects, accreditation tasks (optional).
10. **`survey`** — application forms, feedback, assessments (optional).

Add **`stock`** only if you sell uniforms/books with inventory. Add **`fleet`** only for
transportation. Avoid installing unused apps — each app adds menus and complexity.

## Typical custom models (via Models & Fields or Draft Studio)

| Model | Purpose | Key links |
|-------|---------|-----------|
| `x_school_class` | Class/section (Grade 5A, CS101) | school year, teacher partner |
| `x_student_enrollment` | Student placed in a class for a term | `res.partner`, `x_school_class` |
| `x_attendance_line` | Daily attendance | enrollment, date, status |
| `x_grade_line` | Scores per assignment/exam | enrollment, subject, score |
| `x_academic_year` | Terms/years | start/end dates |
| `x_fee_schedule` | Fee plan per program | links to `product.product` |

Use **`res.partner`** for student identity; store student-specific fields on partner or on
enrollment records depending on reporting needs. Prefer **one partner per person**; parents
as separate contacts linked via partner relations (custom relation or tags).

## Workflows by school function

### Admissions

Use **CRM** stages: Inquiry → Application → Interview → Accepted → Enrolled. Website forms
create CRM leads. On acceptance, create/update **Contact** and an **Enrollment** custom record.
Automations can send email templates via **Mail**.

### Fees and billing

Define fee items as **Products** (service type). Use **Sales Orders** or **Invoices** per term.
For installments, use recurring invoicing patterns supported by your Odoo version or custom
scheduled actions — verify against your instance; do not assume Enterprise subscription billing.

### Academics and grading

Odoo Community does not ship a turnkey **SIS gradebook**. Build `x_grade_line` and views
(filtered by class/term). Publish read-only grades to parents via **Portal** pages only after
access rules are tested.

### Scheduling

**Calendar** for meetings; **Events** for school-wide dates. Timetables usually need a custom
model (`x_timetable_slot`) or spreadsheet export — keep v1 simple (one class, one room field).

## Community vs Enterprise honesty

Odoo marketing may describe **Education** features that are **Enterprise** or **Odoo Online**
only. On Community, assume you are composing Contacts + Website + CRM + custom models.
If a module is not in **Apps → Installed**, Expert should not claim it is available.

Protected areas: do not auto-post accounting entries or payroll from Expert-generated code
without sandbox validation and operator confirmation.

## Phase rollout

**Phase 1:** Contacts tags, one class model, enrollment linking student partners, basic menus.
**Phase 2:** CRM admissions, fee products, invoices, email templates.
**Phase 3:** Attendance/grades, portal pages, automations, module export for reuse.

## Related tools in Odoo Custom

- **Connect** your school Odoo DB, then ask Expert with the connection open (version-aware).
- **App Wizard / Draft Studio** — describe "school enrollment and classes" for a ModuleSpec draft.
- **Import** — CSV of students into Contacts with dry-run first.
- **Snapshots** — before bulk field or view changes.

## Example Expert questions

- "Which stock modules should I install first for a private K-12 school?"
- "How should I model students vs parents in Contacts?"
- "Scaffold enrollment and class models linked to res.partner."
