const SUPERMEMORY_API_KEY = process.env.SUPERMEMORY_API_KEY;
const CONTAINER_TAG = 'meetlyra';
const BASE_URL = 'https://api.supermemory.ai/v3';

/**
 * Pushes a sent cold pitch or received reply email log into SuperMemory.
 */
export async function pushOutreachLog(
  contactEmail: string,
  subject: string,
  body: string,
  direction: 'outbound' | 'inbound',
  status?: string
): Promise<boolean> {
  if (!SUPERMEMORY_API_KEY) {
    console.warn('SUPERMEMORY_API_KEY is not defined. Skipping SuperMemory push.');
    return false;
  }

  const cleanBody = body.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  const content = `Outreach Log [${direction.toUpperCase()}]
Email: ${contactEmail}
Subject: ${subject}
Status: ${status || 'logged'}

Body:
${cleanBody}`;

  try {
    const response = await fetch(`${BASE_URL}/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${SUPERMEMORY_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content,
        containerTag: CONTAINER_TAG,
      }),
    });

    if (response.ok) {
      console.log(`Successfully pushed outreach log for ${contactEmail} to SuperMemory.`);
      return true;
    } else {
      const text = await response.text();
      console.error(`Failed to push outreach log to SuperMemory: ${response.status} ${text}`);
      return false;
    }
  } catch (error) {
    console.error('Error pushing outreach log to SuperMemory:', error);
    return false;
  }
}

/**
 * Searches SuperMemory for historically successful templates or snippets matching a topic.
 */
export async function searchOutreachTemplates(topic: string, limit = 3): Promise<any[]> {
  if (!SUPERMEMORY_API_KEY) {
    console.warn('SUPERMEMORY_API_KEY is not defined. Skipping SuperMemory search.');
    return [];
  }

  try {
    const response = await fetch(`${BASE_URL}/search`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${SUPERMEMORY_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        q: `${topic} successful email outreach templates`,
        limit,
        rewriteQuery: true,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      return Array.isArray(data) ? data : (data.results || []);
    } else {
      console.error(`Failed to search SuperMemory templates: ${response.status}`);
      return [];
    }
  } catch (error) {
    console.error('Error searching SuperMemory templates:', error);
    return [];
  }
}
