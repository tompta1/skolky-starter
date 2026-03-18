-- Add contact fields: email (populated from registry "emaily" field)
-- and phone (reserved column, no source data yet).
alter table school_places add column if not exists email text;
alter table school_places add column if not exists phone text;
