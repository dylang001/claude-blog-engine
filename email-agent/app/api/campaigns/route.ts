import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/db';
import { campaigns } from '@/db/schema';
import { DEFAULT_SYSTEM_PROMPT } from '@/lib/email/generation';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      name,
      description,
      systemPrompt,
      outreachMode,
      researchEnabled,
      peopleResearchEnabled,
      numberOfFollowUps,
    } = body;

    if (!name) {
      return NextResponse.json(
        { error: 'Missing required field: name' },
        { status: 400 }
      );
    }

    const [created] = await db
      .insert(campaigns)
      .values({
        name,
        description: description || null,
        systemPrompt: systemPrompt || DEFAULT_SYSTEM_PROMPT,
        outreachMode: outreachMode || 'none',
        researchEnabled: researchEnabled !== undefined ? researchEnabled : true,
        peopleResearchEnabled: peopleResearchEnabled !== undefined ? peopleResearchEnabled : false,
        numberOfFollowUps: numberOfFollowUps !== undefined ? numberOfFollowUps : 2,
      })
      .returning();

    return NextResponse.json({ campaign: created }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 }
    );
  }
}
