import { Pool } from 'pg';
import { drizzle, type NodePgDatabase } from 'drizzle-orm/node-postgres';
import * as schema from './schema';

let _db: NodePgDatabase<typeof schema> | null = null;

function getDb() {
  if (!_db) {
    const pool = new Pool({
      connectionString: process.env.DATABASE_URL!,
    });
    _db = drizzle({ client: pool, schema });
  }
  return _db;
}

// Lazy proxy so db is usable as an import but doesn't initialize until first use
export const db = new Proxy({} as NodePgDatabase<typeof schema>, {
  get(_target, prop) {
    return (getDb() as unknown as Record<string | symbol, unknown>)[prop];
  },
});

