import {
  pgTable,
  pgEnum,
  text,
  timestamp,
  integer,
  boolean,
  serial,
  jsonb,
} from 'drizzle-orm/pg-core';
import type { InferSelectModel } from 'drizzle-orm';

// =============================================================================
// Enums
// =============================================================================

export const campaignStatus = pgEnum('campaign_status', [
  'draft',
  'active',
  'paused',
  'archived',
]);

export const outreachMode = pgEnum('outreach_mode', [
  'none',
  'upsert_only',
  'full',
  'local',
]);

export const contactStatus = pgEnum('contact_status', [
  'pending',
  'researching',
  'generating',
  'sending',
  'completed',
  'failed',
  'queued',
  'sent_initial',
  'sent_followup1',
  'sent_followup2',
  'replied',
  'unsubscribed',
]);

// =============================================================================
// Types
// =============================================================================

export interface CompanyResearch {
  companySummary: string;
  existingAIFeatures: string[];
}

export interface PeopleResearch {
  title: string;
  contactSummary: string;
  recentActivity: string[];
}

// =============================================================================
// Campaigns
// =============================================================================

export const campaigns = pgTable('campaigns', {
  id: serial('id').primaryKey(),
  name: text('name').notNull(),
  description: text('description'),
  status: campaignStatus('status').default('draft').notNull(),
  systemPrompt: text('system_prompt').notNull(),
  researchEnabled: boolean('research_enabled').default(true).notNull(),
  peopleResearchEnabled: boolean('people_research_enabled')
    .default(false)
    .notNull(),
  numberOfFollowUps: integer('number_of_follow_ups').default(2).notNull(),
  outreachMode: outreachMode('outreach_mode').default('none').notNull(),
  outreachSequenceId: integer('outreach_sequence_id'),
  mailboxId: integer('mailbox_id'),
  createdAt: timestamp('created_at', { withTimezone: true })
    .defaultNow()
    .notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true })
    .defaultNow()
    .notNull()
    .$onUpdate(() => new Date()),
});

export type Campaign = InferSelectModel<typeof campaigns>;
export type CampaignInsert = typeof campaigns.$inferInsert;

// =============================================================================
// Contacts
// =============================================================================

export const contacts = pgTable('contacts', {
  id: serial('id').primaryKey(),
  campaignId: integer('campaign_id')
    .references(() => campaigns.id, { onDelete: 'cascade' })
    .notNull(),
  status: contactStatus('status').default('pending').notNull(),
  email: text('email').notNull(),
  firstName: text('first_name').notNull(),
  lastName: text('last_name'),
  title: text('title'),
  company: text('company').notNull(),
  notes: text('notes'),
  companyResearch: jsonb('company_research').$type<CompanyResearch>(),
  peopleResearch: jsonb('people_research').$type<PeopleResearch>(),
  generatedSubject: text('generated_subject'),
  generatedBody1: text('generated_body_1'),
  generatedBody2: text('generated_body_2'),
  generatedBody3: text('generated_body_3'),
  outreachProspectId: integer('outreach_prospect_id'),
  errorMessage: text('error_message'),
  data: jsonb('data').$type<Record<string, unknown>>(),
  nextActionDueAt: timestamp('next_action_due_at', { withTimezone: true }),
  lastSentAt: timestamp('last_sent_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true })
    .defaultNow()
    .notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true })
    .defaultNow()
    .notNull()
    .$onUpdate(() => new Date()),
});

export type Contact = InferSelectModel<typeof contacts>;
export type ContactInsert = typeof contacts.$inferInsert;

// =============================================================================
// OAuth Tokens
// =============================================================================

export const oauthTokens = pgTable('oauth_tokens', {
  id: serial('id').primaryKey(),
  provider: text('provider').notNull().unique(),
  accessToken: text('access_token').notNull(),
  refreshToken: text('refresh_token').notNull(),
  scope: text('scope'),
  expiresAt: timestamp('expires_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true })
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type OAuthToken = InferSelectModel<typeof oauthTokens>;

// =============================================================================
// Settings
// =============================================================================

export const settings = pgTable('settings', {
  id: serial('id').primaryKey(),
  key: text('key').notNull().unique(),
  value: text('value'),
});

export type Setting = InferSelectModel<typeof settings>;

// =============================================================================
// Outreach Logs
// =============================================================================

export const outreachLogs = pgTable('outreach_logs', {
  id: serial('id').primaryKey(),
  contactId: integer('contact_id')
    .references(() => contacts.id, { onDelete: 'cascade' })
    .notNull(),
  direction: text('direction').notNull(), // 'outbound' | 'inbound'
  subject: text('subject').notNull(),
  body: text('body').notNull(),
  timestamp: timestamp('timestamp', { withTimezone: true }).defaultNow().notNull(),
});

export type OutreachLog = InferSelectModel<typeof outreachLogs>;
