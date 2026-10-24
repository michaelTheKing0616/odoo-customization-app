// BV-04: per-version Odoo selector map (17-20). Steps resolve selectors only through here.
const base = {
  login: 'input[name="login"]',
  password: 'input[name="password"]',
  submit: 'form.oe_login_form button[type="submit"]',
  home: '.o_main_navbar',
  list: '.o_list_renderer',
  form: '.o_form_view',
  save: '.o_form_button_save',
  dirty: '.o_form_view .o_form_dirty, .o_form_view.o_form_dirty',
  error: '.o_error_dialog, .o_dialog .o_error_detail, .o_notification.border-danger',
  mask: '.o_data_cell, .o_field_widget, input, textarea',
};

export const SELECTORS = {
  17: { ...base },
  18: { ...base },
  19: { ...base },
  20: { ...base },
};

export function selectorsFor(major) {
  const s = SELECTORS[Number(major)];
  if (!s) throw new Error(`no selector map for Odoo ${major}`);
  return s;
}
