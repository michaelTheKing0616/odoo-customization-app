Create a complete custom Odoo application called **Customer Health & Retention Intelligence**.

### Domain
**B2B Customer Success / Account Management / Customer Retention**

### Why this module is needed
Odoo provides CRM, Sales, Subscriptions, Helpdesk, Project, Invoicing, and other modules, but it does not natively provide a unified customer-health system that continuously evaluates the overall health of an account across these different business signals.

The goal of this application is to give companies a centralized **Customer Health Score**, identify customers at risk of churn, identify expansion opportunities, and automatically create proactive customer-success actions.

The module should integrate with standard Odoo objects where possible rather than duplicating existing functionality.

---

## 1. Core concept

Create a **Customer Health Score** for each B2B customer.

The score should be configurable and calculated from multiple signals, such as:

- Recent sales activity
- Revenue trend
- Subscription status
- Invoice/payment behavior
- Support ticket volume
- Support ticket severity
- Ticket resolution time
- Project activity
- Last customer interaction
- CRM opportunity activity
- Product/service usage where available
- Contract renewal proximity
- Number of unresolved issues
- Customer satisfaction/NPS data if available

The administrator must be able to configure which signals contribute to the score and how heavily each signal is weighted.

Example:

- Revenue trend: 20%
- Support health: 20%
- Payment health: 15%
- Engagement: 20%
- Renewal risk: 15%
- Customer satisfaction: 10%

Calculate a score from **0–100**.

Classify customers automatically:

- 80–100: Healthy
- 60–79: Stable
- 40–59: At Risk
- 0–39: Critical

Make these thresholds configurable.

---

## 2. Customer Health Dashboard

Create a management dashboard showing:

- Total customers
- Healthy customers
- Stable customers
- At-risk customers
- Critical customers
- Customers whose health score is declining
- Customers whose health score improved
- Customers approaching renewal
- Customers with unresolved critical issues
- Customers with unusual revenue declines
- Customers requiring immediate action

Include charts for:

- Customer health distribution
- Health score over time
- At-risk customers by account manager
- Churn-risk trend
- Revenue at risk
- Renewals at risk
- Health score by customer segment

Allow filtering by:

- Salesperson
- Customer success manager
- Sales team
- Customer industry
- Customer country
- Subscription
- Product/service
- Health status
- Score range
- Renewal date

---

## 3. Customer 360 Health View

Add a dedicated **Health** section to the customer form.

Display:

- Current health score
- Previous health score
- Score change
- Health status
- Risk level
- Renewal date
- Estimated revenue at risk
- Last meaningful interaction
- Open support tickets
- Critical tickets
- Recent sales activity
- Payment status
- Active subscriptions
- Recent opportunities
- Customer-success tasks
- Active risks
- Recommended actions

Show a visual timeline of important customer events.

The user should be able to understand the customer's overall relationship with the company without opening multiple Odoo applications.

---

## 4. Health Score Rules Engine

Create a no-code rules configuration interface.

Administrators should be able to create rules such as:

"If customer has more than 3 unresolved support tickets, subtract 10 points."

"If revenue decreases by more than 20% over the previous 90 days, subtract 15 points."

"If the customer has not interacted with us for 60 days, subtract 10 points."

"If subscription renewal is within 30 days and there are unresolved critical tickets, subtract 20 points."

"If customer has purchased an additional product within the last 90 days, add 10 points."

Rules should support:

- Conditions
- Operators
- Thresholds
- Weight/points
- Time windows
- Positive or negative scoring
- Rule activation/deactivation

Do not hard-code the scoring logic where possible.

---

## 5. Risk Detection

Automatically identify common customer risks:

- Churn risk
- Revenue decline
- Low engagement
- Support dissatisfaction
- Payment risk
- Renewal risk
- Product adoption risk
- Relationship risk
- Contract risk

Create a **Customer Risk** model containing:

- Customer
- Risk type
- Severity
- Description
- Detection date
- Source
- Status
- Owner
- Recommended action
- Resolution date

Allow users to mark risks as:

- Open
- Monitoring
- Resolved
- Dismissed

---

## 6. Proactive Actions

The system should automatically recommend or create actions based on health signals.

Examples:

- Create a call task for the account manager
- Create a customer-success activity
- Schedule a customer review
- Create a support escalation
- Notify the account owner
- Create a renewal preparation task
- Create an executive escalation
- Recommend an upsell opportunity

Each recommended action should explain **why it was generated**.

For example:

"Customer health dropped from 76 to 48 because revenue declined 24%, two high-priority support tickets remain unresolved, and the customer has had no meaningful interaction in 47 days."

---

## 7. Customer Success Plans

Allow account managers to create a success plan for important customers.

A success plan should contain:

- Objectives
- Milestones
- Tasks
- Target dates
- Owners
- KPIs
- Notes
- Risks
- Success criteria

Show progress visually.

---

## 8. Renewal Management

Create a renewal workspace showing upcoming renewals.

For each renewal display:

- Customer
- Contract/subscription
- Renewal date
- Contract value
- Current health score
- Revenue at risk
- Open risks
- Open critical tickets
- Account owner
- Renewal stage
- Recommended next action

Automatically flag renewals with poor health scores.

---

## 9. Expansion Opportunities

Identify customers that may be good candidates for expansion.

Examples:

- Increasing usage/activity
- Strong health score
- Increasing purchasing frequency
- Products/services not yet purchased
- Successful completion of projects
- High engagement

Create an "Expansion Opportunity" recommendation that can optionally create an Odoo CRM opportunity.

---

## 10. Automated Alerts

Create configurable automated alerts.

Examples:

- Health score drops by more than 15 points
- Customer becomes "At Risk"
- Customer becomes "Critical"
- Renewal is within 60 days
- Revenue drops significantly
- Critical support issue remains unresolved
- Customer has been inactive for a configurable period

Alerts can be delivered through standard Odoo activities and notifications where possible.

---

## 11. Configuration

Create a dedicated configuration section for administrators.

Include:

- Health score rules
- Score thresholds
- Risk types
- Risk severity
- Alert rules
- Customer segments
- Health-score calculation frequency
- Renewal warning periods
- Default action templates

Avoid requiring Python/code changes for normal configuration.

---

## 12. Odoo Integration

Use existing Odoo models whenever possible.

Potential integrations include:

- `res.partner`
- CRM opportunities
- Sales orders
- Subscriptions
- Invoices
- Payments
- Helpdesk tickets
- Projects
- Activities
- Calendar
- Products
- Users/sales teams

Do not unnecessarily duplicate standard Odoo data.

The application should gracefully handle cases where an optional Odoo module is not installed.

---

## 13. Security

Create appropriate access rights for:

### Customer Success User
- View assigned customers
- View health information
- Manage customer risks
- Create actions

### Customer Success Manager
- View all customer health information
- Configure success plans
- Manage team risks
- View dashboards

### Sales Manager
- View health and expansion information
- View customers owned by their team

### Administrator
- Full configuration access

Respect Odoo's existing multi-company and record-rule mechanisms.

---

## 14. Views

Create polished Odoo-native views for:

- Customer Health dashboard
- Customer Health list
- Customer Health kanban
- Customer Health form
- Risk list
- Risk kanban
- Renewal dashboard
- Success plans
- Health rule configuration
- Health score history
- Expansion opportunities

Use appropriate colors/badges for health states, but maintain a professional Odoo UI.

---

## 15. Health Score History

Never overwrite historical scores without retaining the history.

Store:

- Customer
- Score
- Previous score
- Score change
- Status
- Calculation timestamp
- Major contributing factors

Allow users to view the customer's health-score trend over time.

---

## 16. Explainability

An important requirement is that health scores must be explainable.

Whenever a score changes, show the major factors responsible.

Example:

**Health Score: 42 — At Risk**

Factors:

- Revenue declined 22%: **−12**
- 3 unresolved high-priority tickets: **−10**
- No customer interaction for 45 days: **−8**
- Successful project completion: **+5**
- Active subscription: **+8**

This should make the system useful to humans rather than behaving like an unexplained black box.

---

## 17. No-Code Philosophy

This application is intended for a **no-code Odoo customization platform**.

Therefore:

- Prefer Odoo models, fields, views, actions, automated actions, scheduled actions, and configuration records.
- Avoid unnecessary custom code.
- Make business rules configurable.
- Make labels configurable where practical.
- Avoid hard-coded IDs.
- Avoid hard-coded company-specific assumptions.
- Use standard Odoo relationships whenever possible.
- Make optional integrations fail gracefully.
- Ensure generated modules can be installed/uninstalled cleanly.

---

## 18. Deliverable

Generate a complete, production-quality Odoo custom module.

The generated application must include:

1. Module manifest
2. Python models
3. XML views
4. Menus
5. Actions
6. Security groups
7. Access control lists
8. Record rules where required
9. Scheduled actions for health-score recalculation
10. Configuration models
11. Demo/sample data where appropriate
12. Proper dependencies
13. Odoo-native UI
14. Clear model and field names
15. Clean module structure

Before generating the module, validate that:

- Models have correct relationships.
- Views reference valid fields.
- Security rules do not prevent legitimate access.
- Dependencies are declared correctly.
- Optional Odoo modules are handled safely.
- Scheduled actions cannot create duplicate records.
- Health scores are deterministic and explainable.
- Uninstalling the module does not corrupt standard Odoo data.

### Product principle

Do not build another CRM, helpdesk, sales, project-management, or subscription application.

Build the **missing intelligence layer between those applications**: a system that answers the question:

> **"Which customers need our attention right now, why, and what should we do about them?"**

The final result should feel like a native Odoo application that a mid-sized B2B company could install and immediately use to proactively reduce churn and increase customer retention.
