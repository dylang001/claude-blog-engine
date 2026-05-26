import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/db';
import { contacts, campaigns, outreachLogs } from '@/db/schema';
import { eq, and, gte } from 'drizzle-orm';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);

    // Emails sent today
    const outboundLogs = await db
      .select()
      .from(outreachLogs)
      .where(
        and(
          eq(outreachLogs.direction, 'outbound'),
          gte(outreachLogs.timestamp, startOfToday)
        )
      );

    // Replies received today
    const inboundLogs = await db
      .select()
      .from(outreachLogs)
      .where(
        and(
          eq(outreachLogs.direction, 'inbound'),
          gte(outreachLogs.timestamp, startOfToday)
        )
      );

    // Count unsubscribes vs normal replies
    let repliesCount = 0;
    let unsubscribesCount = 0;
    const unsubKeywords = ['unsubscribe', 'stop', 'remove me', 'don\'t email', 'dont email', 'remove from list'];

    for (const log of inboundLogs) {
      const bodyLower = log.body.toLowerCase();
      if (unsubKeywords.some((kw) => bodyLower.includes(kw))) {
        unsubscribesCount++;
      } else {
        repliesCount++;
      }
    }

    // Active campaigns count
    const activeCampaigns = await db
      .select()
      .from(campaigns)
      .where(eq(campaigns.status, 'active'));

    // Active prospects currently active in sequences
    const activeProspects = await db
      .select()
      .from(contacts)
      .where(
        and(
          eq(contacts.status, 'queued')
        )
      );

    return NextResponse.json({
      emailsSentToday: outboundLogs.length,
      repliesReceivedToday: repliesCount,
      unsubscribesToday: unsubscribesCount,
      totalActiveCampaigns: activeCampaigns.length,
      activeProspects: activeProspects.length,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 }
    );
  }
}
