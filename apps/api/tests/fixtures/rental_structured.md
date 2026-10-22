Create an Odoo app called **Equipment Rental & Asset Lifecycle** for a company that rents out construction and event equipment to business customers.

Everything must work on Odoo Online without custom Python: use models, fields, views, menus, automated actions, scheduled actions, security groups and record rules only.

## Records
1. **Equipment Category**: name, description, default daily rate, maintenance interval (days), active.
2. **Equipment Asset**: name, internal reference, category, serial number, purchase date, purchase cost, daily rate, current customer (contact), location (Warehouse / On site / In repair / Retired), condition (New / Good / Fair / Needs repair), last maintenance date, next maintenance due date, notes, photo, active. Status pipeline: Available → Reserved → Rented → Returned → In Maintenance → Retired.
3. **Rental Booking**: reference, customer (contact), customer contact person, related sales order, project (optional, for site jobs), start date, end date, delivery address, deposit amount, currency, responsible user, notes. Stages: Draft → Confirmed → Out → Returned → Invoiced → Cancelled.
4. **Booking Line**: booking, asset, quantity days, daily rate, discount %, line notes.
5. **Inspection**: asset, booking, inspection type (Check-out / Check-in), inspector (user), date, condition found, damage noted (yes/no), damage description, photos, follow-up needed.
6. **Maintenance Log**: asset, maintenance type (Preventive / Repair / Safety certification), date, technician (user), cost, vendor (contact), description, next due date.

## Existing apps
- On Contacts, add a "Rentals" tab showing the customer's bookings, a rental credit limit, a "preferred customer" checkbox and a default delivery address note.
- On Sales orders, add a link to the rental booking.

## Views
- Asset kanban grouped by status with condition badges, plus list, form and search (filters: Available, Needs repair, Maintenance overdue; group by category and location).
- Booking kanban by stage, a calendar view of bookings by start/end date coloured by customer, plus list, form, pivot and graph by month and customer.
- Inspection and maintenance list and form views; maintenance calendar by next due date.
- Menus: Rentals → Bookings, Assets, Inspections, Maintenance; Configuration → Categories.

## Automations
1. When a booking moves to Confirmed, schedule a "Prepare equipment" activity for the responsible user, due one day before the start date.
2. When a booking moves to Out, set each booked asset's status to Rented and its current customer to the booking customer.
3. When a booking moves to Returned, set the assets to Returned and create a "Check-in inspection" activity for the responsible user.
4. When an inspection is saved with Damage noted = yes, set the asset condition to Needs repair, its status to In Maintenance, and schedule a "Repair assessment" activity for the Rental Manager group.
5. When a maintenance log is created, update the asset's last maintenance date and next maintenance due date.
6. Daily scheduled action: flag bookings past their end date that are still Out (set an "Overdue" tag and schedule a follow-up call activity), and schedule a maintenance activity for assets whose next maintenance due date is within 7 days.

## Security
- **Rental User**: create and edit bookings, inspections and maintenance logs; sees only bookings where they are the responsible user.
- **Rental Manager** (includes Rental User): sees everything, manages assets and categories, can cancel bookings.
- Respect multi-company: each asset and booking belongs to one company.

## Principles
Don't duplicate standard Odoo data: use Contacts for customers and vendors, Users for staff, Sales for orders and Project for site jobs. Keep labels clear and professional.
