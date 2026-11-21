from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import duckdb

from src.lpsme.models import (
    InstitutionRecord,
    OrganizationRecord,
    ProfessionalContactRecord,
    RelationshipClaim,
)


class LPSMEStorage:
    """
    Workspace-scoped DuckDB storage for LPSME intelligence.

    Every operation is automatically restricted to the workspace
    supplied when this storage instance is created.
    """

    TABLES: ClassVar[dict[str, str]] = {
    "organizations": "lpsme_organizations",
    "institutions": "lpsme_institutions",
    "relationships": "lpsme_relationships",
    "restricted_contacts": "lpsme_restricted_contacts",
}

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        workspace_id: str,
    ) -> None:
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("A valid workspace_id is required.")

        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("A valid database path is required.")

        self.workspace_id = workspace_id.strip()
        self.db_path = db_path

        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(db_path)

        try:
            self._init_schema()
        except Exception:
            self.conn.close()
            raise

    def _init_schema(self) -> None:
        """
        Create tenant-aware tables.

        Legacy tables without workspace_id are rejected.
        Their records must never be assigned automatically
        to an arbitrary workspace.
        """

        existing_tables = {
            row[0]
            for row in self.conn.execute("SHOW TABLES").fetchall()
        }

        for table_name in self.TABLES.values():
            if table_name not in existing_tables:
                continue

            columns = {
                row[0]
                for row in self.conn.execute(
                    f"DESCRIBE {table_name}"
                ).fetchall()
            }

            if "workspace_id" not in columns:
                raise RuntimeError(
                    f"Legacy LPSME table detected: {table_name}. "
                    "The table has no workspace_id column. "
                    "Automatic migration is blocked to prevent "
                    "cross-workspace data exposure."
                )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lpsme_organizations (
                workspace_id VARCHAR NOT NULL,
                org_id VARCHAR NOT NULL,
                legal_name VARCHAR NOT NULL,
                rc_number VARCHAR,
                nif_number VARCHAR,
                lei_code VARCHAR,
                wilaya VARCHAR,
                country VARCHAR NOT NULL,
                stakeholder_category VARCHAR NOT NULL,
                strategic_level VARCHAR NOT NULL,
                verification_status VARCHAR NOT NULL,
                payload_json VARCHAR NOT NULL,
                PRIMARY KEY (workspace_id, org_id)
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lpsme_institutions (
                workspace_id VARCHAR NOT NULL,
                institution_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                acronym VARCHAR,
                category VARCHAR NOT NULL,
                verification_status VARCHAR NOT NULL,
                payload_json VARCHAR NOT NULL,
                PRIMARY KEY (workspace_id, institution_id)
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lpsme_relationships (
                workspace_id VARCHAR NOT NULL,
                relationship_id VARCHAR NOT NULL,
                source_entity_id VARCHAR NOT NULL,
                target_entity_id VARCHAR NOT NULL,
                relationship_type VARCHAR NOT NULL,
                verification_status VARCHAR NOT NULL,
                payload_json VARCHAR NOT NULL,
                PRIMARY KEY (workspace_id, relationship_id)
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lpsme_restricted_contacts (
                workspace_id VARCHAR NOT NULL,
                contact_id VARCHAR NOT NULL,
                org_id VARCHAR NOT NULL,
                lawful_basis VARCHAR NOT NULL,
                payload_json VARCHAR NOT NULL,
                PRIMARY KEY (workspace_id, contact_id)
            )
            """
        )

    def upsert_organization(
        self,
        org: OrganizationRecord,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO lpsme_organizations (
                workspace_id,
                org_id,
                legal_name,
                rc_number,
                nif_number,
                lei_code,
                wilaya,
                country,
                stakeholder_category,
                strategic_level,
                verification_status,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self.workspace_id,
                org.org_id,
                org.legal_name,
                org.rc_number,
                org.nif_number,
                org.lei_code,
                org.wilaya,
                org.country,
                org.stakeholder_category.value,
                org.strategic_level.value,
                org.verification_status.value,
                org.model_dump_json(),
            ],
        )

    def upsert_institution(
        self,
        inst: InstitutionRecord,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO lpsme_institutions (
                workspace_id,
                institution_id,
                name,
                acronym,
                category,
                verification_status,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self.workspace_id,
                inst.institution_id,
                inst.name,
                inst.acronym,
                inst.category.value,
                inst.verification_status.value,
                inst.model_dump_json(),
            ],
        )

    def upsert_relationship(
        self,
        rel: RelationshipClaim,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO lpsme_relationships (
                workspace_id,
                relationship_id,
                source_entity_id,
                target_entity_id,
                relationship_type,
                verification_status,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self.workspace_id,
                rel.relationship_id,
                rel.source_entity_id,
                rel.target_entity_id,
                rel.relationship_type,
                rel.verification_status.value,
                rel.model_dump_json(),
            ],
        )

    def store_restricted_contact(
        self,
        contact: ProfessionalContactRecord,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO lpsme_restricted_contacts (
                workspace_id,
                contact_id,
                org_id,
                lawful_basis,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                self.workspace_id,
                contact.contact_id,
                contact.org_id,
                contact.lawful_basis,
                contact.model_dump_json(),
            ],
        )

    def get_organization(
        self,
        org_id: str,
    ) -> OrganizationRecord | None:
        row = self.conn.execute(
            """
            SELECT payload_json
            FROM lpsme_organizations
            WHERE workspace_id = ?
              AND org_id = ?
            """,
            [self.workspace_id, org_id],
        ).fetchone()

        if row is None:
            return None

        return OrganizationRecord.model_validate_json(row[0])

    def get_institutions(self) -> list[InstitutionRecord]:
        rows = self.conn.execute(
            """
            SELECT payload_json
            FROM lpsme_institutions
            WHERE workspace_id = ?
            ORDER BY institution_id
            """,
            [self.workspace_id],
        ).fetchall()

        return [
            InstitutionRecord.model_validate_json(row[0])
            for row in rows
        ]

    def get_relationships(self) -> list[RelationshipClaim]:
        rows = self.conn.execute(
            """
            SELECT payload_json
            FROM lpsme_relationships
            WHERE workspace_id = ?
            ORDER BY relationship_id
            """,
            [self.workspace_id],
        ).fetchall()

        return [
            RelationshipClaim.model_validate_json(row[0])
            for row in rows
        ]

    def get_restricted_contact(
        self,
        contact_id: str,
    ) -> ProfessionalContactRecord | None:
        row = self.conn.execute(
            """
            SELECT payload_json
            FROM lpsme_restricted_contacts
            WHERE workspace_id = ?
              AND contact_id = ?
            """,
            [self.workspace_id, contact_id],
        ).fetchone()

        if row is None:
            return None

        return ProfessionalContactRecord.model_validate_json(row[0])

    def count_records(self) -> dict[str, int]:
        counts: dict[str, int] = {}

        for key, table_name in self.TABLES.items():
            row = self.conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE workspace_id = ?
                """,
                [self.workspace_id],
            ).fetchone()

            counts[key] = int(row[0])

        return counts

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> LPSMEStorage:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
