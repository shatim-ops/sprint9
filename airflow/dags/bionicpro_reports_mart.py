"""
ETL для витрины отчётов BionicPRO.

Раз в сутки забирает срез клиентов и протезов из CRM и события телеметрии
из PostgreSQL, складывает в ClickHouse и пересобирает витрину
reports.user_prosthesis_daily за обработанные дни.

Окно загрузки считается от журнала reports.etl_loads, а не только от
интервала запуска: первый запуск поднимает всю доступную историю, дальше
грузятся новые дни плюс LATE_DATA_DAYS последних. Протез шлёт данные через 4G
и может досылать их с опозданием, поэтому хвост пересчитывается каждый раз.
Повторный запуск за те же даты ничего не ломает: сырые события
перезаливаются через DROP PARTITION, витрина на ReplacingMergeTree.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import clickhouse_connect
import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException
from airflow.hooks.base import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook

CRM_CONN_ID = "crm_db"
TELEMETRY_CONN_ID = "telemetry_db"
CLICKHOUSE_CONN_ID = "clickhouse_reports"

LATE_DATA_DAYS = 2
BATCH_SIZE = 50_000

log = logging.getLogger(__name__)


def clickhouse_client():
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)
    return clickhouse_connect.get_client(
        host=conn.host,
        port=conn.port or 8123,
        username=conn.login,
        password=conn.password or "",
        database=conn.schema or "reports",
    )


def days(date_from: date, date_to: date):
    current = date_from
    while current < date_to:
        yield current
        current += timedelta(days=1)


@dag(
    dag_id="bionicpro_reports_mart",
    description="CRM + телеметрия -> витрина отчётов в ClickHouse",
    schedule="0 1 * * *",
    start_date=pendulum.datetime(2026, 9, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    default_args={
        "owner": "bionicpro",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bionicpro", "reports"],
)
def bionicpro_reports_mart():
    @task
    def resolve_window(data_interval_end=None) -> dict:
        """Границы загрузки: [date_from, date_to), только полные сутки."""
        date_to = data_interval_end.in_timezone("UTC").date()

        ch = clickhouse_client()
        loads, watermark = ch.query(
            "SELECT count(), max(processed_until) FROM reports.etl_loads"
        ).first_row

        if loads:
            date_from = watermark + timedelta(days=1 - LATE_DATA_DAYS)
        else:
            first_event = PostgresHook(TELEMETRY_CONN_ID).get_first(
                "SELECT min(event_time)::date FROM prosthesis_events"
            )[0]
            if first_event is None:
                raise AirflowSkipException("В источнике телеметрии пока пусто")
            date_from = first_event

        if date_from >= date_to:
            raise AirflowSkipException(f"Нет полных суток для загрузки: {date_from} >= {date_to}")

        log.info("Окно загрузки: %s .. %s (не включая)", date_from, date_to)
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}

    @task
    def load_crm() -> int:
        """Срез CRM. В OLAP уходит только то, что нужно отчёту, без ФИО и контактов."""
        rows = PostgresHook(CRM_CONN_ID).get_records(
            """
            SELECT p.id, c.login, c.country, p.serial_number, p.model, p.side, p.issued_at
            FROM prostheses p
            JOIN customers c ON c.id = p.customer_id
            WHERE p.status = 'active'
            """
        )
        loaded_at = datetime.utcnow().replace(microsecond=0)
        clickhouse_client().insert(
            "reports.crm_prostheses",
            [list(row) + [loaded_at] for row in rows],
            column_names=[
                "prosthesis_id", "user_login", "country", "serial_number",
                "model", "side", "issued_at", "loaded_at",
            ],
        )
        return len(rows)

    @task
    def load_telemetry(window: dict) -> int:
        """Сырые события за окно. Читаем серверным курсором, чтобы не тянуть всё в память."""
        date_from = date.fromisoformat(window["date_from"])
        date_to = date.fromisoformat(window["date_to"])
        ch = clickhouse_client()

        for day in days(date_from, date_to):
            ch.command(f"ALTER TABLE reports.telemetry_events DROP PARTITION '{day.isoformat()}'")

        columns = [
            "event_id", "prosthesis_id", "event_time", "movement",
            "recognized", "response_ms", "battery_level", "signal_noise",
        ]
        total = 0
        with PostgresHook(TELEMETRY_CONN_ID).get_conn() as pg:
            with pg.cursor(name="telemetry_export") as cursor:
                cursor.itersize = BATCH_SIZE
                cursor.execute(
                    """
                    SELECT id, prosthesis_id, event_time, movement,
                           recognized::int, response_ms, battery_level, signal_noise
                    FROM prosthesis_events
                    WHERE event_time >= %s AND event_time < %s
                    """,
                    (date_from, date_to),
                )
                while True:
                    batch = cursor.fetchmany(BATCH_SIZE)
                    if not batch:
                        break
                    ch.insert("reports.telemetry_events", batch, column_names=columns)
                    total += len(batch)

        log.info("Загружено событий: %s", total)
        return total

    @task
    def build_mart(window: dict) -> int:
        """Агрегация по пользователю, протезу и дню. Считается внутри ClickHouse."""
        ch = clickhouse_client()
        params = {"date_from": window["date_from"], "date_to": window["date_to"]}
        ch.command(
            """
            INSERT INTO reports.user_prosthesis_daily
            (
                user_login, prosthesis_id, report_date, country, serial_number, model, side,
                movements_total, movements_failed, avg_response_ms, p95_response_ms,
                max_response_ms, slow_responses, active_hours, battery_min, battery_avg,
                avg_signal_noise, top_movement, loaded_at
            )
            SELECT
                c.user_login,
                e.prosthesis_id,
                toDate(e.event_time) AS report_date,
                any(c.country),
                any(c.serial_number),
                any(c.model),
                any(c.side),
                count(),
                countIf(e.recognized = 0),
                avg(e.response_ms),
                quantile(0.95)(e.response_ms),
                max(e.response_ms),
                countIf(e.response_ms > 100),
                uniqExact(toHour(e.event_time)),
                min(e.battery_level),
                avg(e.battery_level),
                avg(e.signal_noise),
                topK(1)(e.movement)[1],
                now()
            FROM reports.telemetry_events AS e
            INNER JOIN (SELECT * FROM reports.crm_prostheses FINAL) AS c
                ON c.prosthesis_id = e.prosthesis_id
            WHERE e.event_time >= toDate({date_from:String})
              AND e.event_time < toDate({date_to:String})
            GROUP BY c.user_login, e.prosthesis_id, report_date
            """,
            parameters=params,
        )
        return ch.query(
            """
            SELECT count() FROM reports.user_prosthesis_daily FINAL
            WHERE report_date >= toDate({date_from:String}) AND report_date < toDate({date_to:String})
            """,
            parameters=params,
        ).first_row[0]

    @task
    def register_load(window: dict, events_loaded: int, mart_rows: int, run_id=None) -> None:
        """Отметка для API: до какой даты включительно витрина готова."""
        date_from = date.fromisoformat(window["date_from"])
        processed_until = date.fromisoformat(window["date_to"]) - timedelta(days=1)
        clickhouse_client().insert(
            "reports.etl_loads",
            [[run_id, date_from, processed_until, events_loaded, mart_rows,
              datetime.utcnow().replace(microsecond=0)]],
            column_names=[
                "dag_run_id", "date_from", "processed_until",
                "events_loaded", "mart_rows", "finished_at",
            ],
        )

    window = resolve_window()
    crm = load_crm()
    events = load_telemetry(window)
    mart = build_mart(window)
    [crm, events] >> mart
    register_load(window, events, mart)


bionicpro_reports_mart()
