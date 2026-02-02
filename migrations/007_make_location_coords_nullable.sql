-- Migration 007: Make location latitude/longitude nullable to allow manual location entries without coordinates

ALTER TABLE location ALTER COLUMN latitude DROP NOT NULL;
ALTER TABLE location ALTER COLUMN longitude DROP NOT NULL;
