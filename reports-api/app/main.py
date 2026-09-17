from datetime import date, timedelta
from itertools import groupby

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .auth import User, report_user
from .storage import ReportStorage, get_storage

app = FastAPI(title="BionicPRO Reports API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/reports")
def my_report(
    date_from: date | None = Query(None, description="Начало периода, включительно"),
    date_to: date | None = Query(None, description="Конец периода, включительно"),
    user: User = Depends(report_user),
    storage: ReportStorage = Depends(get_storage),
):
    """Отчёт по протезам текущего пользователя. Чей отчёт отдавать, берётся только из токена."""
    return build_report(user.login, date_from, date_to, storage)


@app.get("/reports/{user_login}")
def user_report(
    user_login: str,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: User = Depends(report_user),
    storage: ReportStorage = Depends(get_storage),
):
    # Вариант с явным логином в пути. Чужой логин отсекается до обращения к базе.
    if user_login != user.login:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступен только собственный отчёт")
    return build_report(user.login, date_from, date_to, storage)


def build_report(login: str, date_from: date | None, date_to: date | None, storage: ReportStorage) -> dict:
    processed_until = storage.processed_until()
    if processed_until is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Отчёты ещё не готовы: данные не обработаны, попробуйте позже",
        )

    # Отдаём только то, что Airflow уже обработал. Сегодняшний день и всё, что
    # позже отметки в etl_loads, в отчёт не попадает, даже если его запросили.
    requested_to = date_to or processed_until
    effective_to = min(requested_to, processed_until)
    effective_from = date_from or effective_to - timedelta(days=config.DEFAULT_PERIOD_DAYS - 1)

    if date_from and date_from > processed_until:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"За запрошенный период данные ещё не обработаны. Отчёты доступны по {processed_until} включительно",
        )
    if effective_from > effective_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_from больше date_to")
    if (effective_to - effective_from).days >= config.MAX_PERIOD_DAYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Период не больше {config.MAX_PERIOD_DAYS} дней")

    rows = storage.daily_rows(login, effective_from, effective_to)
    if not rows:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "За выбранный период данных о работе протеза нет",
        )

    return {
        "user": login,
        "period": {
            "date_from": effective_from,
            "date_to": effective_to,
            "requested_to": requested_to,
            "processed_until": processed_until,
            "truncated": requested_to > processed_until,
        },
        "prostheses": [
            prosthesis_block(list(days)) for _, days in groupby(rows, key=lambda r: r["prosthesis_id"])
        ],
    }


def prosthesis_block(days: list[dict]) -> dict:
    first = days[0]
    total = sum(d["movements_total"] for d in days)
    failed = sum(d["movements_failed"] for d in days)
    slow = sum(d["slow_responses"] for d in days)
    return {
        "prosthesis_id": first["prosthesis_id"],
        "serial_number": first["serial_number"],
        "model": first["model"],
        "side": first["side"],
        "summary": {
            "days_with_data": len(days),
            "movements_total": total,
            "movements_failed": failed,
            "recognition_rate": round(1 - failed / total, 4),
            # среднее по периоду взвешиваем числом движений за день
            "avg_response_ms": round(sum(d["avg_response_ms"] * d["movements_total"] for d in days) / total, 1),
            "max_response_ms": max(d["max_response_ms"] for d in days),
            "slow_responses_share": round(slow / total, 4),
            "battery_min": min(d["battery_min"] for d in days),
        },
        "days": [
            {
                "date": d["report_date"],
                "movements_total": d["movements_total"],
                "movements_failed": d["movements_failed"],
                "avg_response_ms": round(d["avg_response_ms"], 1),
                "p95_response_ms": round(d["p95_response_ms"], 1),
                "max_response_ms": d["max_response_ms"],
                "slow_responses": d["slow_responses"],
                "active_hours": d["active_hours"],
                "battery_min": d["battery_min"],
                "battery_avg": round(d["battery_avg"], 1),
                "avg_signal_noise": round(d["avg_signal_noise"], 3),
                "top_movement": d["top_movement"],
            }
            for d in days
        ],
    }
