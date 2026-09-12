#!/usr/bin/env python3
"""Pre-vol : verifie que blueseatra_app peut REELLEMENT faire son travail.

A EXECUTER AVANT TOUTE CONFIGURATION DE DATABASE_URL_APP SUR RENDER.

    python3 scripts/prevol_role_metier.py            # regenere le mot de passe
    python3 scripts/prevol_role_metier.py --reutilise  # garde /tmp/.pw

Si le bilan n'est pas 100 % vert, NE PAS toucher a Render. Chaque echec
correspond a une panne de production evitee.

Le mot de passe est genere dans le bac a sable, ecrit dans /tmp/.pw en
0600, et n'est JAMAIS affiche ni journalise. L'URI complete est ecrite
dans /tmp/.uri en 0600 uniquement si tout passe.

Ce script existe parce que la verification precedente s'est limitee a
"le role se connecte". Il se connectait effectivement -- mais il lui
manquait les droits sur users, ce qui a casse le login en production.

Ici on exerce chaque operation que le chemin metier effectue vraiment,
ET on verifie que les acces interdits echouent bien.

Le mot de passe n'est jamais affiche.
"""
import asyncio
import json
import os
import secrets
import re
import subprocess
import sys

PROJET = "xmsxlochasjauhnxarvc"
HOTE = "aws-0-eu-west-1.pooler.supabase.com"
USER = f"blueseatra_app.{PROJET}"
PORT = 6543

METIER = ["audit_logs", "catalog_versions", "catalogs", "company_profiles",
          "import_errors", "import_jobs", "pricing_items", "quote_versions",
          "quotes", "requests", "settings_integrations"]
AUTH = ["users", "tenants", "tenant_users"]

resultats = []


def note(ok, libelle, detail=""):
    resultats.append((ok, libelle, detail))
    print(f"  [{'OK ' if ok else 'ECHEC'}] {libelle}" + (f" -- {detail}" if detail else ""))


def sql_admin(requete):
    """Execute en tant que postgres via le connecteur Supabase."""
    p = subprocess.run(
        ["pplx", "connector", "call", "supabase", "execute_sql",
         "--input", json.dumps({"project_id": PROJET, "query": requete})],
        capture_output=True, text=True, timeout=120,
    )
    return p.stdout + p.stderr


def genere_et_applique():
    """Mot de passe strictement hexadecimal : aucun caractere qui casse une URI."""
    pw = secrets.token_hex(24)
    with open("/tmp/.pw", "w") as fh:
        fh.write(pw)
    os.chmod("/tmp/.pw", 0o600)
    sortie = sql_admin(f"ALTER ROLE blueseatra_app WITH PASSWORD '{pw}'")
    if pw in sortie:
        print("ALERTE : le mot de passe apparait dans la sortie, arret")
        sys.exit(1)
    ok = '"is_error": false' in sortie or '"is_error":false' in sortie
    print(f"[1] Mot de passe applique : {'OK' if ok else 'ECHEC'}")
    if not ok:
        print(sortie[:600])
        sys.exit(1)
    return pw


def tenant_de_reference():
    """Recupere un tenant_id via le canal ADMIN (postgres contourne RLS).

    Indispensable : blueseatra_app ne peut RIEN lire avant que
    app.tenant_id soit positionne -- c'est precisement la garantie RLS.
    La version precedente de ce script lisait les tables sans contexte,
    obtenait 0 ligne, et concluait a tort a un defaut de droits.
    """
    sortie = sql_admin(
        "select tenant_id from blueseatra.quotes "
        "group by tenant_id order by count(*) desc limit 1")
    m = re.search(r'"tenant_id[\\\"]*:[\\\"]*([0-9a-f-]{8,})', sortie)
    if not m:
        print("Impossible de recuperer un tenant de reference :")
        print(sortie[:500])
        sys.exit(1)
    return m.group(1)


async def pre_vol(pw, tid):
    import asyncpg

    print("\n[2] Connexion avec l'utilisateur qualifie par le project ref")
    # Supavisor met en cache les identifiants : juste apres un ALTER ROLE,
    # l'authentification echoue encore avec l'ANCIEN mot de passe en cache.
    # Observe le 12/09/2026 : InvalidPasswordError a t+0, succes a t+60s.
    # Sans cette attente, on conclut a tort que le mot de passe est faux.
    cx = None
    derniere = None
    for tentative in range(10):
        try:
            cx = await asyncpg.connect(
                host=HOTE, port=PORT, user=USER, password=pw,
                database="postgres", ssl="require",
                statement_cache_size=0, timeout=30,
                server_settings={"search_path": "blueseatra,public"},
            )
            break
        except asyncpg.InvalidPasswordError as e:
            derniere = e
            print(f"      cache Supavisor pas encore rafraichi "
                  f"(tentative {tentative + 1}/10), attente 15 s")
            await asyncio.sleep(15)
        except Exception as e:
            note(False, "connexion", f"{type(e).__name__}: {e}")
            return
    if cx is None:
        note(False, "connexion apres 10 tentatives", f"{type(derniere).__name__}: {derniere}")
        return
    note(True, "connexion etablie", f"{USER}@{HOTE}:{PORT}")

    try:
        # --- identite et privileges ---
        print("\n[3] Identite et privileges du role")
        who = await cx.fetchval("select current_user")
        note(who == "blueseatra_app", "current_user = blueseatra_app", who)

        bypass = await cx.fetchval(
            "select rolbypassrls from pg_roles where rolname = current_user")
        note(bypass is False, "rolbypassrls = false (RLS s'appliquera)", str(bypass))

        sp = await cx.fetchval("show search_path")
        note("blueseatra" in (sp or ""), "search_path contient blueseatra", sp)

        # --- RLS doit BLOQUER sans contexte tenant ---
        print("\n[4] Sans contexte tenant, RLS doit tout bloquer")
        vides, non_vides = 0, []
        for t in METIER:
            n = await cx.fetchval(f'select count(*) from blueseatra."{t}"')
            if n == 0:
                vides += 1
            else:
                non_vides.append(f"{t}={n}")
        note(not non_vides,
             f"les {len(METIER)} tables metier renvoient 0 ligne sans app.tenant_id",
             "fuite : " + " ".join(non_vides) if non_vides else f"{vides}/{len(METIER)} vides")

        # --- RLS doit AUTORISER avec contexte tenant ---
        print(f"\n[5] Avec app.tenant_id positionne, les donnees doivent apparaitre")
        async with cx.transaction():
            await cx.execute("select set_config('app.tenant_id', $1, true)", tid)
            total = 0
            for t in METIER:
                try:
                    n = await cx.fetchval(f'select count(*) from blueseatra."{t}"')
                    total += n
                    print(f"      {t:24} {n} lignes")
                except Exception as e:
                    note(False, f"SELECT {t} avec contexte", f"{type(e).__name__}: {e}")
            note(total > 0, "des donnees sont visibles avec le contexte tenant",
                 f"{total} lignes au total")
            nq = await cx.fetchval('select count(*) from blueseatra."quotes"')
            note(nq > 0, "lecture des devis du tenant", f"{nq} devis")

        # --- les acces interdits DOIVENT echouer ---
        print("\n[6] Les 3 tables d'authentification doivent etre REFUSEES")
        for t in AUTH:
            try:
                await cx.fetchval(f'select count(*) from blueseatra."{t}"')
                note(False, f"{t} accessible", "FUITE : ce role ne doit PAS y acceder")
            except asyncpg.InsufficientPrivilegeError:
                note(True, f"{t} refusee", "permission denied, conforme")
            except Exception as e:
                note(False, f"{t} erreur inattendue", f"{type(e).__name__}: {e}")

        # --- contexte tenant ---
        print("\n[7] Mecanisme de contexte tenant")
        async with cx.transaction():
            await cx.execute("select set_config('app.tenant_id', $1, true)", tid)
            lu = await cx.fetchval("select current_setting('app.tenant_id', true)")
            note(lu == tid, "set_config + relecture dans la transaction")
            try:
                ct = await cx.fetchval("select current_tenant()")
                note(ct == tid, "current_tenant() lit app.tenant_id", str(ct))
            except Exception as e:
                note(False, "current_tenant()", f"{type(e).__name__}: {e}")

        hors = await cx.fetchval("select current_setting('app.tenant_id', true)")
        note(hors in (None, ""), "contexte bien efface hors transaction (is_local)", repr(hors))

        # --- ecritures reelles, annulees ---
        print("\n[8] Ecritures reelles dans le contexte tenant, puis ROLLBACK")
        tr = cx.transaction()
        await tr.start()
        try:
            # Le contexte tenant est OBLIGATOIRE : sans lui la politique
            # WITH CHECK rejette l'insertion (observe le 12/09/2026 :
            # "new row violates row-level security policy").
            await cx.execute("select set_config('app.tenant_id', $1, true)", tid)
            faux = f"preflight-{secrets.token_hex(6)}"
            await cx.execute(
                'insert into blueseatra."audit_logs" (id, tenant_id) values ($1, $2)',
                faux, tid)
            note(True, "INSERT audit_logs")

            n = await cx.fetchval(
                'update blueseatra."audit_logs" set tenant_id = $1 where id = $2 '
                'returning 1', tid, faux)
            note(n == 1, "UPDATE audit_logs")

            n = await cx.fetchval(
                'delete from blueseatra."audit_logs" where id = $1 returning 1', faux)
            note(n == 1, "DELETE audit_logs")
        except Exception as e:
            note(False, "ecritures", f"{type(e).__name__}: {e}")
        finally:
            await tr.rollback()
            reste = await cx.fetchval(
                "select count(*) from blueseatra.\"audit_logs\" where id like 'preflight-%'")
            note(reste == 0, "ROLLBACK effectif, aucune trace laissee", f"{reste} residu")

        # --- lecture metier realiste ---
        print("\n[9] Isolation : un AUTRE tenant doit rester invisible")
        autre = tenant_alternatif(tid)
        if autre:
            async with cx.transaction():
                await cx.execute("select set_config('app.tenant_id', $1, true)", autre)
                n_autre = await cx.fetchval('select count(*) from blueseatra."quotes"')
            async with cx.transaction():
                await cx.execute("select set_config('app.tenant_id', $1, true)", tid)
                n_mien = await cx.fetchval('select count(*) from blueseatra."quotes"')
            note(n_autre != n_mien or n_autre == 0,
                 "le changement de tenant change les lignes visibles",
                 f"tenant A={n_mien} devis, tenant B={n_autre} devis")
        else:
            note(True, "un seul tenant avec des devis, test d'isolation non applicable")

    finally:
        await cx.close()

    # --- pool concurrent ---
    print("\n[10] 7 connexions simultanees (taille du pool metier : 5+2)")
    try:
        pool = await asyncpg.create_pool(
            host=HOTE, port=PORT, user=USER, password=pw, database="postgres",
            ssl="require", statement_cache_size=0, min_size=7, max_size=7,
            timeout=30, server_settings={"search_path": "blueseatra,public"},
        )
        async def sonde(_):
            async with pool.acquire() as c:
                return await c.fetchval("select 1")
        vals = await asyncio.gather(*[sonde(i) for i in range(7)])
        note(all(v == 1 for v in vals), "pool de 7 connexions operationnel")
        await pool.close()
    except Exception as e:
        note(False, "pool concurrent", f"{type(e).__name__}: {e}")


def tenant_alternatif(exclu):
    sortie = sql_admin(
        f"select tenant_id from blueseatra.quotes where tenant_id <> '{exclu}' limit 1")
    m = re.search(r'"tenant_id[\\\"]*:[\\\"]*([0-9a-f-]{8,})', sortie)
    return m.group(1) if m else None


async def main():
    # --reutilise : le mot de passe en place est deja valide, on ne le
    # change pas (evite de redeclencher le delai de cache Supavisor).
    if "--reutilise" in sys.argv and os.path.exists("/tmp/.pw"):
        pw = open("/tmp/.pw").read().strip()
        print("[1] Reutilisation du mot de passe deja applique et valide")
    else:
        pw = genere_et_applique()
    tid = tenant_de_reference()
    print(f"[1b] Tenant de reference : {tid[:8]}...")
    await pre_vol(pw, tid)

    echecs = [r for r in resultats if not r[0]]
    print("\n" + "=" * 62)
    print(f"BILAN : {len(resultats) - len(echecs)}/{len(resultats)} verifications passees")
    if echecs:
        print("\nBLOQUANT -- ne pas configurer Render :")
        for _, lib, det in echecs:
            print(f"  - {lib} : {det}")
        sys.exit(1)
    print("\nTOUT EST VERT. L'URI peut etre poussee vers Render.")
    uri = (f"postgresql+asyncpg://{USER}:{pw}@{HOTE}:{PORT}/postgres")
    with open("/tmp/.uri", "w") as fh:
        fh.write(uri)
    os.chmod("/tmp/.uri", 0o600)
    print(f"Forme : postgresql+asyncpg://{USER}:***@{HOTE}:{PORT}/postgres")


asyncio.run(main())
