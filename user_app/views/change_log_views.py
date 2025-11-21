from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from user_app.serializers.change_log_serializers import ChangeLogQuerySerializer


class ChangeLogAPIView(APIView):
    """
    Exposes SQL Server CDC logs filtered by the `user_id` path parameter (maps to `modified_by`).
    Works only when the default Django connection targets Azure SQL/SQL Server with CDC enabled.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: int):
        serializer = ChangeLogQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        connection = connections[DEFAULT_DB_ALIAS]
        engine = connection.settings_dict.get("ENGINE", "")
        if "sql_server" not in engine and "mssql" not in engine:
            return Response(
                {
                    "detail": "The CDC log endpoint requires an Azure SQL / SQL Server backend.",
                    "hint": "Switch DATABASES['default'] to the Azure SQL instance in production."
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        source_key = filters.get("source", "all")
        limit = filters.get("limit") or 500

        # If source is "all", query all configured capture instances
        if source_key == "all":
            all_rows = []
            capture_instances = settings.CDC_CAPTURE_INSTANCES
            
            if not capture_instances:
                return Response(
                    {"detail": "No CDC capture instances configured."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Query each capture instance
            for table_key, source_config in capture_instances.items():
                capture_instance = source_config["capture_instance"]
                user_column = source_config.get("user_column", "modified_by")
                select_columns = source_config.get("select_columns", [])
                if isinstance(select_columns, str):
                    select_columns = [select_columns]
                
                try:
                    # Fetch rows for this table (use a higher limit per table, then trim later)
                    table_rows = self._fetch_cdc_rows(
                        connection=connection,
                        capture_instance=capture_instance,
                        user_column=user_column,
                        select_columns=select_columns,
                        limit=limit * 2,  # Get more per table, then trim to total limit
                        user_id=user_id,
                        start_at=filters.get("start_at"),
                        end_at=filters.get("end_at"),
                        operation=filters.get("operation"),
                        table_name=source_config.get("table_name", capture_instance),
                        source_key=table_key,  # Include source key for identification
                    )
                    all_rows.extend(table_rows)
                except (OperationalError, ProgrammingError) as exc:
                    # Log error but continue with other tables
                    continue

            # Sort all rows by changed_at (most recent first) and limit
            all_rows.sort(key=lambda x: x.get("changed_at") or timezone.now(), reverse=True)
            all_rows = all_rows[:limit]

            return Response(
                {
                    "count": len(all_rows),
                    "source": "all",
                    "user_id": user_id,
                    "results": all_rows,
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Single table query (existing logic)
            source_config = settings.CDC_CAPTURE_INSTANCES[source_key]
            capture_instance = source_config["capture_instance"]
            user_column = source_config.get("user_column", "modified_by")
            select_columns = source_config.get("select_columns", [])
            if isinstance(select_columns, str):
                select_columns = [select_columns]

            try:
                rows = self._fetch_cdc_rows(
                    connection=connection,
                    capture_instance=capture_instance,
                    user_column=user_column,
                    select_columns=select_columns,
                    limit=limit,
                    user_id=user_id,
                    start_at=filters.get("start_at"),
                    end_at=filters.get("end_at"),
                    operation=filters.get("operation"),
                    table_name=source_config.get("table_name", capture_instance),
                    source_key=source_key,
                )
            except (OperationalError, ProgrammingError) as exc:
                return Response(
                    {"detail": f"Unable to read CDC logs for '{capture_instance}': {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "count": len(rows),
                    "source": source_key,
                    "user_id": user_id,
                    "results": rows,
                },
                status=status.HTTP_200_OK,
            )

    # ------------------------------------------------------------------ Helpers
    def _fetch_cdc_rows(
        self,
        connection,
        capture_instance: str,
        user_column: str,
        select_columns: List[str],
        limit: int,
        user_id: Optional[int],
        start_at,
        end_at,
        operation: Optional[str],
        table_name: str,
        source_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_lsn = None
        end_lsn = None
        with connection.cursor() as cursor:
            start_lsn = self._resolve_start_lsn(cursor, capture_instance, start_at)
            end_lsn = self._resolve_end_lsn(cursor, end_at)

            params: List[Any] = [start_lsn, end_lsn]
            where_clauses = ["1=1"]

            if user_id is not None:
                where_clauses.append(f"src.[{user_column}] = %s")
                params.append(user_id)

            if operation:
                operation_code = self._operation_code(operation)
                where_clauses.append("src.__$operation = %s")
                params.append(operation_code)

            extra_select = ""
            payload_columns = []
            for column in select_columns:
                extra_select += f", src.[{column}] AS [{column}]"
                payload_columns.append(column)

            sql = f"""
                SELECT
                    sys.fn_cdc_map_lsn_to_time(src.__$start_lsn) AS changed_at,
                    src.__$start_lsn AS start_lsn,
                    src.__$seqval AS sequence_value,
                    src.__$operation AS operation_code,
                    src.[{user_column}] AS modified_by
                    {extra_select}
                FROM cdc.fn_cdc_get_all_changes_{capture_instance} (%s, %s, 'all') AS src
                WHERE {' AND '.join(where_clauses)}
                ORDER BY src.__$start_lsn DESC
            """

            cursor.execute(sql, params)
            records = cursor.fetchmany(limit)

            columns = [meta[0] for meta in cursor.description]

        return [
            self._serialize_row(dict(zip(columns, record)), table_name, payload_columns, source_key)
            for record in records
        ]

    def _serialize_row(self, row: Dict[str, Any], table_name: str, payload_columns: List[str], source_key: Optional[str] = None) -> Dict[str, Any]:
        payload = {col: row.get(col) for col in payload_columns}
        changed_at = row.get("changed_at")
        if changed_at and timezone.is_aware(changed_at):
            changed_at = timezone.make_naive(changed_at)
        result = {
            "table": table_name,
            "changed_at": changed_at,
            "operation": self._operation_label(row["operation_code"]),
            "modified_by": row.get("modified_by"),
            "start_lsn": self._format_lsn(row.get("start_lsn")),
            "sequence_value": self._format_lsn(row.get("sequence_value")),
            "payload": payload,
        }
        if source_key:
            result["source_key"] = source_key
        return result

    def _resolve_start_lsn(self, cursor, capture_instance: str, start_at) -> bytes:
        if start_at:
            cursor.execute(
                "SELECT sys.fn_cdc_map_time_to_lsn(%s, %s)",
                ["smallest greater than or equal", self._as_naive(start_at)],
            )
            mapped = cursor.fetchone()[0]
            if mapped:
                return mapped
        cursor.execute("SELECT sys.fn_cdc_get_min_lsn(%s)", [capture_instance])
        return cursor.fetchone()[0]

    def _resolve_end_lsn(self, cursor, end_at) -> bytes:
        if end_at:
            cursor.execute(
                "SELECT sys.fn_cdc_map_time_to_lsn(%s, %s)",
                ["largest less than or equal", self._as_naive(end_at)],
            )
            mapped = cursor.fetchone()[0]
            if mapped:
                return mapped
        cursor.execute("SELECT sys.fn_cdc_get_max_lsn()")
        return cursor.fetchone()[0]

    def _format_lsn(self, value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytes):
            return value.hex()
        return str(value)

    @staticmethod
    def _operation_code(label: str) -> int:
        mapping = {
            "delete": 1,
            "insert": 2,
            "update_before": 3,
            "update_after": 4,
        }
        return mapping[label]

    @staticmethod
    def _operation_label(code: int) -> str:
        mapping = {
            1: "delete",
            2: "insert",
            3: "update_before",
            4: "update_after",
        }
        return mapping.get(code, "unknown")

    @staticmethod
    def _as_naive(dt):
        if not dt:
            return dt
        return timezone.make_naive(dt) if timezone.is_aware(dt) else dt

