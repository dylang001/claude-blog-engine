import { db } from '../db';
import { contacts, campaigns } from '../db/schema';
import { desc, eq } from 'drizzle-orm';

async function main() {
  const results = await db
    .select({
      id: contacts.id,
      email: contacts.email,
      firstName: contacts.firstName,
      company: contacts.company,
      notes: contacts.notes,
      subject: contacts.generatedSubject,
      body1: contacts.generatedBody1,
      campaignName: campaigns.name,
      systemPrompt: campaigns.systemPrompt,
    })
    .from(contacts)
    .innerJoin(campaigns, eq(contacts.campaignId, campaigns.id))
    .orderBy(desc(contacts.id))
    .limit(5);

  console.log("=== RECENT GENERATED OUTREACH CONTACTS ===");
  for (const r of results) {
    console.log(`\nContact ID: ${r.id}`);
    console.log(`Campaign: ${r.campaignName}`);
    console.log(`To: ${r.firstName} (${r.email}) at ${r.company}`);
    console.log(`Notes/Strategy: ${r.notes}`);
    console.log(`Subject: ${r.subject}`);
    console.log(`Body 1 excerpt: ${r.body1?.substring(0, 300)}...`);
    console.log("----------------------------------------");
  }
  process.exit(0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
