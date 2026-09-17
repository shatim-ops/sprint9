from datetime import date

import clickhouse_connect

from . import config

# Клиент один на процесс, а эндпоинты FastAPI выполняются в пуле потоков.
# С общей сессией ClickHouse параллельные запросы падают, поэтому сессию не заводим.
clickhouse_connect.common.set_setting("autogenerate_session_id", False)


class ReportStorage:
    """Чтение витрины. Вся агрегация уже сделана в Airflow, здесь только выборка по ключу."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        # подключение ленивое: сервис не должен падать на старте, если ClickHouse ещё поднимается
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=config.CLICKHOUSE_HOST,
                port=config.CLICKHOUSE_PORT,
                username=config.CLICKHOUSE_USER,
                password=config.CLICKHOUSE_PASSWORD,
                database=config.CLICKHOUSE_DB,
            )
        return self._client

    def processed_until(self) -> date | None:
        loads, until = self.client.query(
            "SELECT count(), max(processed_until) FROM reports.etl_loads"
        ).first_row
        return until if loads else None

    def daily_rows(self, user_login: str, date_from: date, date_to: date) -> list[dict]:
        result = self.client.query(
            """
            SELECT prosthesis_id, serial_number, model, side, report_date,
                   movements_total, movements_failed, avg_response_ms, p95_response_ms,
                   max_response_ms, slow_responses, active_hours,
                   battery_min, battery_avg, avg_signal_noise, top_movement
            FROM reports.user_prosthesis_daily FINAL
            WHERE user_login = {login:String}
              AND report_date BETWEEN {date_from:Date} AND {date_to:Date}
            ORDER BY prosthesis_id, report_date
            """,
            parameters={"login": user_login, "date_from": date_from, "date_to": date_to},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]


storage = ReportStorage()


def get_storage() -> ReportStorage:
    return storage
