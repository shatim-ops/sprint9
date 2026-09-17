-- Телеметрия протезов, то, что на исходной схеме называется "База данных".
-- В проде сюда пишет API, которому шлёт данные чип. Здесь таблица наполняется
-- синтетикой за последние 10 дней относительно момента первого запуска,
-- чтобы у DAG были свежие данные независимо от даты проверки.

CREATE TABLE prosthesis_events (
    id             BIGSERIAL PRIMARY KEY,
    prosthesis_id  INTEGER     NOT NULL,
    event_time     TIMESTAMP   NOT NULL,
    movement       VARCHAR(16) NOT NULL,
    recognized     BOOLEAN     NOT NULL,
    response_ms    INTEGER     NOT NULL,
    battery_level  SMALLINT    NOT NULL,
    signal_noise   REAL        NOT NULL
);

-- ETL забирает данные окнами по времени
CREATE INDEX idx_events_time ON prosthesis_events (event_time);

-- Протез 4 (клиент prothetic3) телеметрию не шлёт: сбор данных пользователь
-- может отключить, и отчёт для него должен честно вернуть "данных нет".
INSERT INTO prosthesis_events
    (prosthesis_id, event_time, movement, recognized, response_ms, battery_level, signal_noise)
SELECT
    p.id,
    ts,
    (ARRAY['grip', 'pinch', 'point', 'open', 'wrist_rotate'])[1 + floor(random() * 5)::int],
    random() > 0.04 + p.id * 0.01,
    -- старая модель отвечает медленнее, у части событий выброс за 100 мс
    (p.base_ms + random() * 35 + CASE WHEN random() > 0.93 THEN 40 + random() * 60 ELSE 0 END)::int,
    -- разряд в течение дня, зарядка ночью
    greatest(5, 100 - (extract(hour FROM ts)::int - 7) * p.drain - floor(random() * 5)::int)::smallint,
    round((0.05 + random() * 0.25)::numeric, 3)::real
FROM (VALUES (1, 48, 5), (2, 71, 6), (3, 52, 4), (5, 68, 6)) AS p (id, base_ms, drain)
CROSS JOIN generate_series(
    date_trunc('day', now()) - interval '10 days',
    now(),
    interval '4 minutes'
) AS ts
-- ночью протезом не пользуются
WHERE extract(hour FROM ts) BETWEEN 7 AND 22
  AND random() > 0.35;
