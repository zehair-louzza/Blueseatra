-- Option C — File durable portée par Supabase (zéro infra en plus).
-- Un worker réclame les jobs avec FOR UPDATE SKIP LOCKED : plusieurs workers
-- peuvent tourner sans se marcher dessus, et rien n'est perdu à un redéploiement.

create table if not exists extraction_jobs (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null,
    request_id  uuid not null,
    status      text not null default 'queued',   -- queued | processing | done | failed
    attempts    int  not null default 0,
    locked_at   timestamptz,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists idx_jobs_claimable
    on extraction_jobs (status, created_at)
    where status = 'queued';

-- Réclamer le prochain job de façon atomique (à appeler par le worker en boucle).
-- SKIP LOCKED : deux workers ne prennent jamais le même job.
create or replace function claim_next_job()
returns extraction_jobs as $$
declare job extraction_jobs;
begin
    select * into job from extraction_jobs
        where status = 'queued'
        order by created_at
        for update skip locked
        limit 1;
    if not found then
        return null;
    end if;
    update extraction_jobs
        set status = 'processing', attempts = attempts + 1,
            locked_at = now(), updated_at = now()
        where id = job.id;
    return job;
end;
$$ language plpgsql;
