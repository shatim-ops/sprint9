CREATE DATABASE IF NOT EXISTS reports;

-- Срез CRM: только то, что нужно отчёту. ФИО, телефон, email и дата рождения
-- в OLAP не попадают, после утечки лишние копии персональных данных ни к чему.
CREATE TABLE IF NOT EXISTS reports.crm_prostheses
(
    prosthesis_id  UInt32,
    user_login     String,
    country        FixedString(2),
    serial_number  String,
    model          LowCardinality(String),
    side           LowCardinality(String),
    issued_at      Date,
    loaded_at      DateTime
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY prosthesis_id;

-- Сырые события за последние дни. Партиция на день, чтобы повторная загрузка
-- дня сводилась к DROP PARTITION + INSERT. История здесь не копится, TTL 35 дней:
-- дольше хранится только агрегат в витрине.
CREATE TABLE IF NOT EXISTS reports.telemetry_events
(
    event_id       UInt64,
    prosthesis_id  UInt32,
    event_time     DateTime,
    movement       LowCardinality(String),
    recognized     UInt8,
    response_ms    UInt16,
    battery_level  UInt8,
    signal_noise   Float32
)
ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (prosthesis_id, event_time)
TTL event_time + INTERVAL 35 DAY;

-- Витрина для сервиса отчётов: строка на пользователя, протез и день.
-- Ключ сортировки начинается с user_login, поэтому отчёт по одному
-- пользователю читает несколько гранул, а не всю таблицу.
-- ReplacingMergeTree по loaded_at делает перезапуск DAG за тот же день безопасным.
CREATE TABLE IF NOT EXISTS reports.user_prosthesis_daily
(
    user_login           String,
    prosthesis_id        UInt32,
    report_date          Date,
    country              FixedString(2),
    serial_number        String,
    model                LowCardinality(String),
    side                 LowCardinality(String),
    movements_total      UInt32,
    movements_failed     UInt32,
    avg_response_ms      Float32,
    p95_response_ms      Float32,
    max_response_ms      UInt16,
    slow_responses       UInt32,
    active_hours         UInt8,
    battery_min          UInt8,
    battery_avg          Float32,
    avg_signal_noise     Float32,
    top_movement         LowCardinality(String),
    loaded_at            DateTime
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_login, prosthesis_id, report_date);

-- Журнал загрузок. По нему API понимает, до какой даты витрина готова.
CREATE TABLE IF NOT EXISTS reports.etl_loads
(
    dag_run_id       String,
    date_from        Date,
    processed_until  Date,
    events_loaded    UInt64,
    mart_rows        UInt64,
    finished_at      DateTime
)
ENGINE = MergeTree
ORDER BY finished_at;

-- Сервису отчётов запись не нужна, у него отдельный пользователь
-- с SELECT только на витрину и журнал загрузок.
CREATE USER IF NOT EXISTS reports_api IDENTIFIED WITH sha256_password BY 'reports_api_password';
GRANT SELECT ON reports.user_prosthesis_daily TO reports_api;
GRANT SELECT ON reports.etl_loads TO reports_api;
