import { sql } from "drizzle-orm";
import { db } from "@workspace/db";

let columnsEnsured = false;

export async function ensureSessionGuardColumns() {
  if (columnsEnsured) return;
  await db.execute(sql`
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_guard_enabled BOOLEAN DEFAULT TRUE;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_start_hour DOUBLE PRECISION DEFAULT 12.0;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_end_hour DOUBLE PRECISION DEFAULT 16.0;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session2_enabled BOOLEAN DEFAULT TRUE;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session2_start_hour DOUBLE PRECISION DEFAULT 18.0;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session2_end_hour DOUBLE PRECISION DEFAULT 22.0;
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS m1_ltf_enabled BOOLEAN DEFAULT TRUE;
  `);
  columnsEnsured = true;
}

export function extractSessionGuardFields(row: any) {
  const enabled = Boolean(row?.sessionGuardEnabled ?? row?.session_guard_enabled ?? false);
  const startHour = Number(row?.sessionStartHour ?? row?.session_start_hour ?? 12.0);
  const endHour = Number(row?.sessionEndHour ?? row?.session_end_hour ?? 16.0);
  const session2Enabled = Boolean(row?.session2Enabled ?? row?.session2_enabled ?? true);
  const session2StartHour = Number(row?.session2StartHour ?? row?.session2_start_hour ?? 18.0);
  const session2EndHour = Number(row?.session2EndHour ?? row?.session2_end_hour ?? 22.0);
  return {
    sessionGuardEnabled: enabled,
    sessionStartHour: startHour,
    sessionEndHour: endHour,
    session2Enabled,
    session2StartHour,
    session2EndHour,
    session_guard_enabled: enabled,
    session_start_hour: startHour,
    session_end_hour: endHour,
    session2_enabled: session2Enabled,
    session2_start_hour: session2StartHour,
    session2_end_hour: session2EndHour,
  };
}
