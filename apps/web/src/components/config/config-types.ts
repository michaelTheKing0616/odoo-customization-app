export const CONFIRM_PHRASE = "I understand the risks";

export type CronRow = {
  id: number;
  name: string;
  model_name: string | null;
  interval_number: number | null;
  interval_type: string | null;
  active: boolean;
};

export type MailTemplateRow = {
  id: number;
  name: string;
  model: string | null;
  subject: string | null;
  email_to: string | null;
};

export type ActivityTypeRow = {
  id: number;
  name: string;
  summary: string | null;
};

export type PaperformatRow = {
  id: number;
  name: string;
  format: string | null;
  margin_top: number | null;
};

export type IrDefaultRow = {
  id: number;
  field_name: string | null;
  json_value: string | null;
};

export type MailForm = {
  name: string;
  model: string;
  subject: string;
  body_html: string;
  email_to: string;
};

export type SeqForm = {
  name: string;
  code: string;
  prefix: string;
  padding: number;
};

export type PaperForm = {
  name: string;
  format: string;
  margin_top: number;
};

export type I18nProbe = {
  ok: boolean;
  method: string;
  message: string;
  major: number | null;
};

export type MailHealth = {
  smtp_servers: number;
  alias_domains: number;
  ok: boolean;
  warnings: string[];
};
