import { ImapFlow } from 'imapflow';
import { simpleParser } from 'mailparser';

export interface ImapReply {
  fromEmail: string;
  subject: string;
  body: string;
  date: Date;
}

export async function checkInboxReplies(
  activeProspectEmails: string[]
): Promise<ImapReply[]> {
  const host = process.env.IMAP_HOST || 'imap.spacemail.com';
  const port = parseInt(process.env.IMAP_PORT || '993', 10);
  const user = process.env.IMAP_USER || process.env.SMTP_USER || process.env.SMTP_USERNAME;
  const pass = process.env.IMAP_PASSWORD || process.env.SMTP_PASSWORD;

  if (!user || !pass) {
    throw new Error('IMAP credentials (IMAP_USER/IMAP_PASSWORD) are not configured in environment variables');
  }

  const client = new ImapFlow({
    host,
    port,
    secure: port === 993,
    auth: {
      user,
      pass,
    },
    logger: false,
  });

  await client.connect();

  const replies: ImapReply[] = [];
  const activeEmailsSet = new Set(activeProspectEmails.map((e) => e.toLowerCase().trim()));

  if (activeEmailsSet.size === 0) {
    await client.logout();
    return replies;
  }

  const lock = await client.getMailboxLock('INBOX');
  try {
    const mailbox = client.mailbox;
    if (!mailbox) {
      lock.release();
      await client.logout();
      return replies;
    }
    const totalMessages = mailbox.exists;
    if (totalMessages === 0) {
      lock.release();
      await client.logout();
      return replies;
    }

    // We scan the last 100 emails to prevent scanning the entire inbox
    const startSeq = Math.max(1, totalMessages - 100);
    const range = `${startSeq}:${totalMessages}`;

    for await (const message of client.fetch(range, { envelope: true, source: true })) {
      const fromAddress = message.envelope?.from?.[0];
      if (!fromAddress || !fromAddress.address || !message.source) continue;

      const fromEmail = fromAddress.address.toLowerCase().trim();

      if (activeEmailsSet.has(fromEmail)) {
        let bodyText = '';
        try {
          const parsed = (await simpleParser(message.source)) as any;
          bodyText = parsed.text || parsed.html || '';
        } catch (parseError) {
          console.error(`Error parsing raw email source for ${fromEmail}:`, parseError);
          bodyText = 'Error parsing email content';
        }

        replies.push({
          fromEmail,
          subject: message.envelope?.subject || 'No Subject',
          body: bodyText,
          date: message.envelope?.date || new Date(),
        });
      }
    }
  } finally {
    lock.release();
  }

  await client.logout();
  return replies;
}
