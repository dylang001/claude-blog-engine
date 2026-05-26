import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/db';
import { contacts, campaigns, outreachLogs } from '@/db/schema';
import { eq, and, lte, or, inArray } from 'drizzle-orm';
import { sendEmail } from '@/lib/email/smtp';
import { checkInboxReplies } from '@/lib/email/imap';
import { pushOutreachLog } from '@/lib/supermemory';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  return handleCron();
}

export async function POST(request: NextRequest) {
  return handleCron();
}

async function handleCron() {
  try {
    const now = new Date();
    console.log(`[Cron Outreach] Starting cycle at ${now.toISOString()}`);

    // =========================================================================
    // Part 1: Check Inbox for Replies (IMAP)
    // =========================================================================
    console.log('[Cron Outreach] Checking IMAP inbox for replies...');
    
    // Fetch all active contacts that could reply
    const activeContacts = await db
      .select({
        id: contacts.id,
        email: contacts.email,
        status: contacts.status,
      })
      .from(contacts)
      .where(
        inArray(contacts.status, ['sent_initial', 'sent_followup1', 'sent_followup2'])
      );

    const activeEmails = activeContacts.map((c) => c.email);
    let repliesCount = 0;

    if (activeEmails.length > 0) {
      try {
        const replies = await checkInboxReplies(activeEmails);
        console.log(`[Cron Outreach] IMAP check finished. Found ${replies.length} matching emails.`);

        for (const reply of replies) {
          // Find the corresponding contact
          const contact = activeContacts.find(
            (c) => c.email.toLowerCase() === reply.fromEmail.toLowerCase()
          );
          if (!contact) continue;

          // Deduplicate: check if this reply is already logged
          const [existingLog] = await db
            .select({ id: outreachLogs.id })
            .from(outreachLogs)
            .where(
              and(
                eq(outreachLogs.contactId, contact.id),
                eq(outreachLogs.direction, 'inbound'),
                eq(outreachLogs.subject, reply.subject)
              )
            )
            .limit(1);

          if (existingLog) {
            console.log(`[Cron Outreach] Reply from ${reply.fromEmail} already logged. Skipping.`);
            continue;
          }

          // Detect unsubscribe
          const unsubKeywords = ['unsubscribe', 'stop', 'remove me', 'don\'t email', 'dont email', 'remove from list'];
          const bodyLower = reply.body.toLowerCase();
          const isUnsubscribe = unsubKeywords.some((kw) => bodyLower.includes(kw));
          const newStatus = isUnsubscribe ? 'unsubscribed' : 'replied';

          console.log(`[Cron Outreach] Processing reply from ${reply.fromEmail}. New status: ${newStatus}`);

          // Update contact status and clear nextActionDueAt to halt future follow-ups
          await db
            .update(contacts)
            .set({
              status: newStatus,
              nextActionDueAt: null,
              updatedAt: new Date(),
            })
            .where(eq(contacts.id, contact.id));

          // Log the reply
          await db.insert(outreachLogs).values({
            contactId: contact.id,
            direction: 'inbound',
            subject: reply.subject,
            body: reply.body,
            timestamp: reply.date,
          });

          try {
            await pushOutreachLog(reply.fromEmail, reply.subject, reply.body, 'inbound', newStatus);
          } catch (smErr) {
            console.error('[Cron Outreach] Failed to push inbound reply to SuperMemory:', smErr);
          }

          repliesCount++;
        }
      } catch (imapErr) {
        console.error('[Cron Outreach] IMAP scanning failed:', imapErr);
      }
    } else {
      console.log('[Cron Outreach] No active contacts to check for replies.');
    }

    // =========================================================================
    // Part 2: Send Outbound Emails (SMTP)
    // =========================================================================
    console.log('[Cron Outreach] Checking for due outbound emails...');

    // Fetch all contacts due for outreach
    const dueContacts = await db
      .select({
        contact: contacts,
        campaign: campaigns,
      })
      .from(contacts)
      .innerJoin(campaigns, eq(contacts.campaignId, campaigns.id))
      .where(
        and(
          inArray(contacts.status, ['queued', 'sent_initial', 'sent_followup1']),
          lte(contacts.nextActionDueAt, now)
        )
      );

    console.log(`[Cron Outreach] Found ${dueContacts.length} contacts due for sending.`);
    let sentCount = 0;

    for (const item of dueContacts) {
      const contact = item.contact;
      const campaign = item.campaign;

      let subject = contact.generatedSubject || '';
      let body = '';
      let nextStatus: typeof contacts.$inferSelect.status = 'completed';
      let delayDays = 0;

      if (contact.status === 'queued') {
        body = contact.generatedBody1 || '';
        nextStatus = 'sent_initial';
        delayDays = 4; // Step 2 (Follow-up 1) sent 4 days later
      } else if (contact.status === 'sent_initial') {
        body = contact.generatedBody2 || '';
        nextStatus = 'sent_followup1';
        delayDays = 5; // Step 3 (Follow-up 2) sent 5 days later (9 days total)
      } else if (contact.status === 'sent_followup1') {
        body = contact.generatedBody3 || '';
        nextStatus = 'sent_followup2';
        delayDays = 0; // End of sequence
      }

      if (!subject || !body) {
        console.error(`[Cron Outreach] Missing generated subject or body for contact ${contact.email} (ID: ${contact.id}). Skipping.`);
        await db
          .update(contacts)
          .set({
            status: 'failed',
            errorMessage: 'Missing generated subject or body template',
            updatedAt: new Date(),
          })
          .where(eq(contacts.id, contact.id));
        continue;
      }

      try {
        console.log(`[Cron Outreach] Sending SMTP email to ${contact.email} (Status: ${contact.status} -> ${nextStatus})...`);

        const genericKeywords = [
          'content', 'editorial', 'press', 'editor', 'support', 'info', 
          'hello', 'team', 'media', 'contact', 'webmaster', 'sales', 
          'marketing', 'admin', 'staff', 'news', 'feedback', 'partner', 
          'outreach', 'advertise', 'inquiry', 'general', 'web', 'dept', 
          'department', 'office', 'help', 'service'
        ];
        const firstNameClean = (contact.firstName || '').trim();
        const firstNameLower = firstNameClean.toLowerCase();
        
        const isGeneric = !firstNameClean || 
          genericKeywords.some(kw => firstNameLower.includes(kw));
          
        const companyClean = contact.company 
          ? contact.company.replace(/(Inc\.|Ltd\.|LLC|Limited|Co\.|Corporation|Corp\.)/gi, '').trim() 
          : 'Company';
          
        const greetingName = isGeneric ? `${companyClean} team` : firstNameClean;
        const greeting = `Hi ${greetingName},<br><br>`;
        const signoff = `<br><br>Best,<br>Dylan<br>Founder, Lyra<br><a href="https://meetlyra.app">meetlyra.app</a>`;
        
        const originalTo = contact.email;
        const testMode = process.env.OUTBOUND_TEST_MODE !== 'false';
        const testRecipient = "dylanangloher@gmail.com";
        const postTitle = campaign.name.replace("Backlinks: ", "");
        const pitchContext = contact.notes || "Relevance outreach based on beat";

        let recipient = originalTo;
        let mailSubject = subject;
        let mailHtml = `
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; padding: 20px;">
            ${greeting}
            ${body}
            ${signoff}
          </body>
          </html>
        `;
        let mailText = `${greeting.replace(/<br>/g, '\n')}${body.replace(/<p>/g, '').replace(/<\/p>/g, '\n').replace(/<br>/g, '\n')}${signoff.replace(/<br>/g, '\n').replace(/<[^>]+>/g, '')}`;

        if (testMode) {
          recipient = testRecipient;
          mailSubject = `[Test Outbound] ${subject}`;
          
          const testInfoBanner = `
            <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #1e3a8a; font-family: sans-serif;">
              <strong style="color: #1d4ed8;">[TEST MODE - OUTBOUND CAMPAIGN REDIRECT]</strong><br/>
              <strong>Blog Post:</strong> ${postTitle}<br/>
              <strong>Original Target Email:</strong> ${originalTo} (Name: ${contact.firstName} ${contact.lastName || ""})<br/>
              <strong>Author / Publisher:</strong> MeetLyra AI Agent<br/>
              <strong>Beat / Pitch Context:</strong> ${pitchContext}<br/>
              <strong>Backlink Strategy:</strong> Personal relationship outreach based on their specific writing beat (Edward Sturm strategy).
            </div>
          `;
          
          mailHtml = `
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; padding: 20px;">
              ${testInfoBanner}
              ${greeting}
              ${body}
              ${signoff}
            </body>
            </html>
          `;
          
          mailText = `[TEST REDIRECT TO YOU - Original Target: ${originalTo}]\nBlog Post: ${postTitle}\n\n${mailText}`;
        }

        await sendEmail({
          to: recipient,
          subject: mailSubject,
          text: mailText,
          html: mailHtml,
        });

        // Calculate next action due date
        const nextActionDueAt = delayDays > 0 
          ? new Date(now.getTime() + delayDays * 24 * 60 * 60 * 1000) 
          : null;

        // Update database
        await db
          .update(contacts)
          .set({
            status: nextStatus,
            lastSentAt: now,
            nextActionDueAt,
            updatedAt: now,
          })
          .where(eq(contacts.id, contact.id));

        // Log outreach message
        await db.insert(outreachLogs).values({
          contactId: contact.id,
          direction: 'outbound',
          subject,
          body: mailText,
          timestamp: now,
        });

        try {
          await pushOutreachLog(contact.email, subject, body, 'outbound', nextStatus);
        } catch (smErr) {
          console.error(`[Cron Outreach] Failed to push outbound email to SuperMemory for ${contact.email}:`, smErr);
        }

        sentCount++;
      } catch (sendErr) {
        console.error(`[Cron Outreach] Failed to send email to ${contact.email}:`, sendErr);
        await db
          .update(contacts)
          .set({
            status: 'failed',
            errorMessage: sendErr instanceof Error ? sendErr.message : 'SMTP send failed',
            updatedAt: now,
          })
          .where(eq(contacts.id, contact.id));
      }
    }

    console.log(`[Cron Outreach] Finished. Sent: ${sentCount}, Replies Logged: ${repliesCount}`);
    return NextResponse.json({
      success: true,
      sentCount,
      repliesCount,
      timestamp: now.toISOString(),
    });
  } catch (error) {
    console.error('[Cron Outreach] Fatal error in cron job:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal Server Error' },
      { status: 500 }
    );
  }
}
