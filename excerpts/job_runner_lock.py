"""Excerpt: never run the same scheduled job twice at once.

Context: the scheduler ticks every minute. A slow job could still be running when
the next tick fires, so it would start a second copy. A Postgres advisory lock,
held on its own connection for the length of the run, makes the second tick skip.
"""


def run_locked(oid):
    conn = db.connect_write()          # dedicated connection: the lock lives as long as it does
    try:
        cur = conn.cursor()
        # hashtext gives a stable bigint key from the orchestration id
        cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (oid,))
        if not cur.fetchone()[0]:
            return                     # already running, skip this tick
        try:
            run_orchestration(oid)
        finally:
            cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (oid,))
    except Exception:
        pass
    finally:
        conn.close()                   # closing also drops the lock if we crashed
