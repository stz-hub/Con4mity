from opensearchpy import OpenSearch
import psycopg2
from datetime import datetime, timezone, timedelta
import time

os_client = OpenSearch(hosts=[{"host": "192.168.0.101", "port": 9200}])

def pg_connect():
    return psycopg2.connect(
        host="192.168.0.104",
        database="con4mity",
        user="con4mity",
        password="Con4mity2024"
    )

def check_ssh_bruteforce():
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=1)).isoformat()

    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"raw_message": "Failed password"}},
                    {"range": {"received_at": {"gte": since}}}
                ]
            }
        },
        "aggs": {
            "by_host": {
                "terms": {"field": "host", "min_doc_count": 10}
            }
        },
        "size": 0
    }

    try:
        resp = os_client.search(index="con4mity-logs-*", body=body)
        buckets = resp.get("aggregations", {}).get("by_host", {}).get("buckets", [])
        for bucket in buckets:
            host = bucket["key"]
            count = bucket["doc_count"]
            insert_alert(
                rule_name="SSH Brute-Force",
                severity="high",
                host=host,
                description=f"{count} tentatives SSH échouées en 1 minute sur {host}"
            )
    except Exception as e:
        print(f"[ERROR] OpenSearch: {e}")

def insert_alert(rule_name, severity, host, description):
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (rule_name, severity, host, description, status, created_at)
                VALUES (%s, %s, %s, %s, 'new', NOW())
                """,
                (rule_name, severity, host, description)
            )
        conn.commit()
        print(f"[ALERT] {rule_name} — {host} — {description}")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] PostgreSQL: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("[INFO] Correlator démarré")
    while True:
        check_ssh_bruteforce()
        time.sleep(60)
