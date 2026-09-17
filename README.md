# BionicPRO: SSO и отчёты по работе протеза

Проектная работа 9 спринта курса "Архитектор программного обеспечения".
Кейс BionicPRO: после утечки через SSO нужно закрыть уязвимость и дать
пользователям отчёт о работе их протеза, не нагружая отчётами боевую базу.

| Задание | Что сделано | Где |
|---|---|---|
| 1.1 Архитектура управления учётными данными | C4-диаграмма: BFF, хранилище сессий, Keycloak с realm на страну, каталог учётных записей в стране представительства, внешние IdP | [Task1](Task1) |
| 1.2 PKCE вместо Code Grant | `pkceMethod: S256` во фронтенде, обязательный S256 у клиента в Keycloak, выключен password grant | [frontend/src/App.tsx](frontend/src/App.tsx), [keycloak/realm-export.json](keycloak/realm-export.json) |
| 2.1 Архитектура отчётов | C4-диаграмма: Airflow, витрина в ClickHouse, сервис отчётов | [Task2](Task2) |
| 2.2 Airflow DAG | Срез CRM и телеметрия в ClickHouse, витрина по пользователю, протезу и дню, запуск раз в сутки | [airflow](airflow), [clickhouse/init](clickhouse/init) |
| 2.3 API /reports | FastAPI, читает готовую витрину из ClickHouse | [reports-api](reports-api) |
| 2.4 Ограничение доступа | Проверка JWT, роль `prothetic_user`, отчёт только по логину из токена | [reports-api/app/auth.py](reports-api/app/auth.py) |
| 2.5 Кнопка в UI | Запрос отчёта с выбором периода, таблица, сохранение в файл | [frontend/src/components/ReportPage.tsx](frontend/src/components/ReportPage.tsx) |

Схемы сделаны в draw.io, рядом с каждым `.drawio` лежит png-экспорт.
Пояснения к решениям и то, как я это проверял, в README внутри Task1 и Task2.

## Запуск

```bash
docker compose up -d --build
```

| Что | Адрес | Доступ |
|---|---|---|
| Фронтенд | http://localhost:3000 | `prothetic1` / `prothetic123` |
| Keycloak | http://localhost:8080 | `admin` / `admin` |
| Airflow | http://localhost:8081 | `admin` / `admin` |
| API отчётов | http://localhost:8000/docs | нужен токен |
| ClickHouse | http://localhost:8123 | `reports_etl` / `reports_etl_password` |

После старта DAG `bionicpro_reports_mart` сам включён и сам отрабатывает первый
запуск, руками ничего заводить не нужно. Минуты через две после
`docker compose up` витрина заполнена, можно логиниться и жать Download Report.
Если хочется не ждать расписания, в Airflow есть кнопка Trigger DAG.

Если Keycloak уже поднимался из исходного репозитория, старый realm останется в
`postgres-keycloak-data` и импорт его не перезапишет. Тогда сначала
`docker compose down -v` и удалить эту директорию.

## Пользователи для проверки

| Логин | Пароль | Что должно быть |
|---|---|---|
| `prothetic1` | `prothetic123` | отчёт по двум протезам |
| `prothetic2` | `prothetic123` | отчёт по одному протезу |
| `prothetic3` | `prothetic123` | 404, сбор телеметрии у него отключён, данных нет |
| `user1` | `password123` | 403, нет роли `prothetic_user` |
