import { sqliteTable, text, integer, uniqueIndex, index } from "drizzle-orm/sqlite-core";
export const raceSnapshots = sqliteTable("race_snapshots", {
  id: text("id").primaryKey(), owner: text("owner").notNull(), raceKey: text("race_key").notNull(), date: text("date").notNull(),
  stage: text("stage").notNull(), demo: integer("demo").notNull(), payload: text("payload").notNull(), digest: text("digest").notNull(), storedAt: text("stored_at").notNull(),
}, t => [uniqueIndex("snapshots_owner_race_stage").on(t.owner,t.raceKey,t.stage),index("snapshots_owner_date").on(t.owner,t.date)]);
export const raceEvents = sqliteTable("race_events", {
  id: text("id").primaryKey(), owner: text("owner").notNull(), raceKey: text("race_key").notNull(), revision: integer("revision").notNull(), kind: text("kind").notNull(), state: text("state").notNull(), at: text("at").notNull(),
}, t => [uniqueIndex("events_owner_race_revision").on(t.owner,t.raceKey,t.revision)]);
