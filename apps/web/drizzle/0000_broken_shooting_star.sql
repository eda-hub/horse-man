CREATE TABLE `race_events` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`race_key` text NOT NULL,
	`revision` integer NOT NULL,
	`kind` text NOT NULL,
	`state` text NOT NULL,
	`at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `events_owner_race_revision` ON `race_events` (`owner`,`race_key`,`revision`);--> statement-breakpoint
CREATE TABLE `race_snapshots` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`race_key` text NOT NULL,
	`date` text NOT NULL,
	`stage` text NOT NULL,
	`demo` integer NOT NULL,
	`payload` text NOT NULL,
	`digest` text NOT NULL,
	`stored_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `snapshots_owner_race_stage` ON `race_snapshots` (`owner`,`race_key`,`stage`);--> statement-breakpoint
CREATE INDEX `snapshots_owner_date` ON `race_snapshots` (`owner`,`date`);