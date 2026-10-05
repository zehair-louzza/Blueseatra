"""Transitions atomiques et tenant-scopées des devis, sans changement de schéma."""
import copy
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from database import tenant_session
from models_sql import Quote, QuoteVersion
from pg_adapter import _to_dict
import tce_v4


async def transition(tenant_id, quote_id, actor, target, expected_digest=None, review_tce=False):
    async with tenant_session() as session:
        # La lecture, la validation, le snapshot et l'écriture partagent la
        # transaction. Une édition concurrente ne peut être approuvée à l'insu.
        row = (await session.execute(
            select(Quote).where(Quote.id == quote_id, Quote.tenant_id == tenant_id).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Quote not found")
        q = _to_dict(Quote, row)
        errors = tce_v4.blockers(q)
        if errors:
            raise HTTPException(409, "Devis incomplet : " + " ".join(errors[:8]))
        now = datetime.now(timezone.utc).isoformat()
        if target == "validated":
            if q.get("status") != "draft":
                raise HTTPException(409, "Seul un brouillon peut être validé.")
            digest = tce_v4.review_digest(q)
            if not expected_digest or expected_digest != digest:
                raise HTTPException(409, "Le devis a changé depuis sa revue. Rechargez-le et vérifiez les modifications.")
            if (q.get("meta") or {}).get("tce_version") and review_tce is not True:
                raise HTTPException(409, "Confirmez la revue TCE avant validation.")
            meta = dict(q.get("meta") or {})
            meta.update(tce_review_digest=digest, tce_reviewed_by=actor, tce_reviewed_at=now)
            q["meta"] = meta
            session.add(QuoteVersion(
                id=str(uuid.uuid4()), tenant_id=tenant_id, quote_id=quote_id,
                version=q.get("version") or 1, snapshot=copy.deepcopy(q), created_at=now,
            ))
            row.meta = meta
            row.validated_at = now
        elif target == "sent":
            if q.get("status") != "validated" or not tce_v4.reviewed(q):
                raise HTTPException(409, "Le devis doit être complet et revalidé avant envoi.")
            row.sent_at = now
        else:
            raise ValueError("Transition inconnue")
        row.status = target
        await session.commit()
    return {"ok": True, "status": target}
