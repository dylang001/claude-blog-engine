import nodemailer from 'nodemailer';

export interface SendEmailArgs {
  to: string;
  subject: string;
  text: string;
  html?: string;
}

export async function sendEmail({ to, subject, text, html }: SendEmailArgs) {
  const host = process.env.SMTP_HOST || 'mail.spacemail.com';
  const port = parseInt(process.env.SMTP_PORT || '465', 10);
  const user = process.env.SMTP_USER || process.env.SMTP_USERNAME;
  const pass = process.env.SMTP_PASSWORD;
  const from = process.env.SMTP_FROM || user || 'contact@meetlyra.app';

  if (!user || !pass) {
    throw new Error('SMTP credentials (SMTP_USER/SMTP_PASSWORD) are not configured in environment variables');
  }

  const secure = port === 465;

  const transporter = nodemailer.createTransport({
    host,
    port,
    secure,
    auth: {
      user,
      pass,
    },
    // Spacemail can sometimes require setting TLS parameters for older clients
    tls: {
      rejectUnauthorized: false,
    },
  });

  const mailOptions = {
    from,
    to,
    subject,
    text,
    html: html || text.replace(/\n/g, '<br/>'),
  };

  const info = await transporter.sendMail(mailOptions);
  return info;
}
