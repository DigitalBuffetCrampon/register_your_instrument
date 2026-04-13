"""
create_table.py
---------------
Crée la table BigQuery `instrument_registrations` dans le dataset `cdp_marketing`.

Prérequis :
  pip install google-cloud-bigquery
  gcloud auth application-default login  (ou variable GOOGLE_APPLICATION_CREDENTIALS)

Usage :
  python3 create_table.py
  python3 create_table.py --dry-run   # Affiche le DDL sans créer
"""

import argparse
import json
import os
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import Conflict

# ── Configuration ──────────────────────────────────────────────────────────────

PROJECT_ID  = "buffet-crampon-data"
DATASET_ID  = "cdp_marketing"
TABLE_ID    = "instrument_registrations"
LOCATION    = "europe-west9"

SCHEMA_FILE = Path(__file__).parent / "schema_instrument_registrations.json"

# ── Fonctions ──────────────────────────────────────────────────────────────────

def load_schema(schema_path: Path) -> list[bigquery.SchemaField]:
    """Charge le schema JSON et le convertit en liste de SchemaField BQ."""
    with open(schema_path, encoding="utf-8") as f:
        raw = json.load(f)

    fields = []
    for col in raw:
        fields.append(
            bigquery.SchemaField(
                name=col["name"],
                field_type=col["type"],
                mode=col.get("mode", "NULLABLE"),
                description=col.get("description", ""),
            )
        )
    return fields


def create_table(dry_run: bool = False) -> None:
    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    schema    = load_schema(SCHEMA_FILE)

    # Partitionnement sur submitted_at (réduction coûts requêtes)
    time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="submitted_at",
        require_partition_filter=False,
    )

    table = bigquery.Table(table_ref, schema=schema)
    table.time_partitioning = time_partitioning
    table.description = (
        "Enregistrements d'instruments Buffet Crampon soumis via le formulaire web. "
        "Partitionné par submitted_at (journalier). "
        "Ne jamais supprimer les lignes — archivistique RGPD."
    )

    # Affichage récapitulatif
    print(f"\nTable cible   : {table_ref}")
    print(f"Location      : {LOCATION}")
    print(f"Partitionnement: DAY sur submitted_at")
    print(f"Colonnes      : {len(schema)}")
    print(f"Schema source : {SCHEMA_FILE.name}")

    if dry_run:
        print("\n[DRY-RUN] La table N'a PAS été créée. Relancer sans --dry-run pour créer.")
        return

    try:
        created = client.create_table(table)
        print(f"\n✓ Table créée : {created.full_table_id}")
    except Conflict:
        print(f"\n⚠️  La table existe déjà : {table_ref}")
        print("   Pour la recréer : supprimer manuellement via la console GCP puis relancer.")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crée la table BQ instrument_registrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la config sans créer la table",
    )
    args = parser.parse_args()

    create_table(dry_run=args.dry_run)
