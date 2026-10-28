# Airline Booking System ✈️

**English** | [Русский](#русский)

An educational web application for searching flights, choosing seats, managing airline reservations, and exploring flight information. The project combines a **Flask** web interface with a **PostgreSQL** relational database and was developed as a university database systems project.

> **Project status:** Academic / in development. The system demonstrates airline-booking workflows and database design; it is not connected to real airlines or live payment processors.

**Repository:** [IrgaleyevRamil/Airline_project](https://github.com/IrgaleyevRamil/Airline_project)  
**Author:** [IrgaleyevRamil](https://github.com/IrgaleyevRamil)  
**University:** Kazakhstan-British Technical University (KBTU)

---

## English

### 1. Project overview

**Airline Booking System** is a database-driven application designed to model the main processes of an airline reservation service: finding a flight, selecting an available seat, creating a reservation, maintaining passenger and ticket information, and handling cancellations.

The project has two principal perspectives:

- **Passenger-facing interface:** flight search, flight and destination information, a price calendar, seat selection, and booking-related pages.
- **Administrative interface:** overview of flights, passengers, bookings, tickets, and payment records, with analytics-oriented pages.

The interface also includes a dark theme and an interactive **3D globe** for visualizing routes. Some advanced features depend on the version of the application and the database migrations applied.

### 2. Main features

| Area | Functionality |
| --- | --- |
| Flights | Browse and search available flights, routes, and destinations |
| Pricing | View a calendar-style presentation of flight prices |
| Seats | Select seats using an interactive seat map and check availability |
| Reservations | Create bookings and manage booking or ticket statuses |
| Cancellations | Keep cancellation history and make eligible seats available again |
| Passengers | Store passenger records associated with reservations and tickets |
| Tickets & payments | Store ticket details and corresponding payment records (academic simulation) |
| Administration | View operational data and analytics in a dashboard |
| Route visualization | Explore airline routes on a 3D globe |

Depending on the applied migration, additional data structures support temporary seat holds, individual ticket passengers, additional services, QR tokens, and operational logging.

### 3. Technology stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.11+, Flask |
| Database | PostgreSQL 13+ |
| Database administration | pgAdmin 4, SQL, PL/pgSQL |
| Frontend | HTML, CSS, JavaScript, Flask/Jinja templates |
| 3D visualization | Three.js and Globe.gl |
| Version control | Git and GitHub |

### 4. Database design

The core database is named **`airline_booking_system`** and is built around these relational entities:

| Table | Purpose |
| --- | --- |
| `airport` | Airports used as departure and arrival locations |
| `aircraft` | Aircraft information |
| `route` | Connections between airports |
| `seat` | Aircraft seats and their characteristics |
| `flight` | Scheduled flights associated with routes and aircraft |
| `passenger` | Passenger information |
| `booking` | Reservation records and statuses |
| `ticket` | Tickets connecting reservations, flights, and seats |
| `payment` | Payment information associated with reservations or tickets |

Important relationships include:

- An **aircraft** has multiple **seats** and can be assigned to **flights**.
- A **route** connects departure and arrival **airports**; a **flight** follows a route.
- A **passenger** can have **bookings**, and confirmed reservations can have **tickets**.
- A **ticket** is associated with a **flight** and a **seat**.
- A **booking** is associated with its payment information.

The database uses primary and foreign keys, constraints, and booking-related integrity rules. In the extended schema, a partial unique index prevents the same seat on a flight from being assigned to multiple active tickets while allowing cancelled tickets to remain in history.

> Exact columns, relationships, and migration-created tables should be checked against the SQL schema included in the repository. The database can evolve as the project develops.

### 5. Getting started

#### Prerequisites

- Python **3.11** or newer
- PostgreSQL **13** or newer
- `pip`
- pgAdmin 4 (optional, but recommended for importing and inspecting the database)
- A local copy of this repository

#### Step 1 — Get the source code

```bash
git clone https://github.com/IrgaleyevRamil/Airline_project.git
cd Airline_project
```

Alternatively, use GitHub's **Code → Download ZIP** option and extract the project.

#### Step 2 — Create a virtual environment

On **Windows (PowerShell)**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On **macOS / Linux**:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

#### Step 4 — Prepare PostgreSQL

1. Start the PostgreSQL server.
2. Create a database named **`airline_booking_system`** (unless the provided backup already creates it).
3. Restore the database from the SQL backup included with the project.

For a **plain `.sql` file**, open it in **pgAdmin 4 → Query Tool** and execute the script against the appropriate database. You can also use the PostgreSQL command-line tool:

```bash
psql -U postgres -d airline_booking_system -f path/to/backup.sql
```

Replace `path/to/backup.sql` with the actual location of your backup and `postgres` with your PostgreSQL username if different. A custom-format `.backup` / `.dump` file should instead be restored with **pgAdmin Restore** or `pg_restore`.

**Important:** Restore only into a suitable development database. A restore can overwrite or conflict with existing data, depending on how the backup was created.

#### Step 5 — Configure environment variables

Create or update a local **`.env`** file with the PostgreSQL connection settings expected by the application (database name, host, port, username, and password) and the administrator password if used.

The administrator password is read from **`ADMIN_PASSWORD`** in the project's configuration. For example:

```dotenv
ADMIN_PASSWORD=replace_with_a_strong_local_password
```

Check `app.py` and the project's configuration files for the exact database environment-variable names. **Do not commit `.env`, credentials, tokens, or real passenger information to a public repository.**

#### Step 6 — Apply migrations if required

The project has used a migration script named `migrate.py`:

```bash
python migrate.py
```

Run it only when required for your local database version. If you restored an up-to-date full backup, review the migration's purpose before running it again.

#### Step 7 — Run the application

```bash
python app.py
```

Open the local application in your browser:

**http://127.0.0.1:5000**

The administrative login page is located at **`/admin/login`** in versions that include the admin module.

### 6. Typical user workflow

1. Open the application and search for a destination or available flight.
2. Review flight information, schedule, and price.
3. Choose a seat from the seat-selection interface.
4. Enter the required passenger information and create a booking.
5. Review the reservation and related ticket details.
6. If necessary, cancel a reservation according to the implemented booking rules.

Administrators can use the dashboard to inspect flights, passengers, reservations, ticket records, payment records, and available analytics.

### 7. Project structure

The repository may contain the following components; actual paths depend on the current project version:

```text
Airline_project/
├── app.py                 # Flask application entry point
├── migrate.py             # Database migration script, if included
├── requirements.txt       # Python dependencies
├── templates/             # HTML/Jinja page templates
├── static/                # CSS, JavaScript and static assets
├── database/              # SQL scripts or database backup, if organized here
├── .gitignore             # Files excluded from version control
└── README.md              # Project documentation
```

### 8. Notes and limitations

- This is a **university learning project**, not a production-ready airline reservation platform.
- Payment data is represented in the database; **real payment processing is not implied**.
- Flight data may be generated or illustrative rather than live airline inventory.
- Features may differ depending on the uploaded source-code version and applied SQL migrations.
- Credentials, local virtual environments, generated files, and private passenger records should not be published.

### 9. Future improvements

- Automated database and application tests
- Better authentication and role-based access control
- More comprehensive validation and error handling
- Detailed reporting and export functionality
- Deployment instructions and continuous integration

### 10. Author

Developed by **IrgaleyevRamil** as an educational project at **Kazakhstan-British Technical University (KBTU)**.

GitHub: **https://github.com/IrgaleyevRamil**

---

## Русский

### 1. О проекте

**Airline Booking System** — учебное веб-приложение для поиска авиарейсов, выбора мест, оформления бронирований и работы с информацией о пассажирах, билетах и оплатах. Проект сочетает веб-интерфейс на **Flask** с реляционной базой данных **PostgreSQL** и разработан в рамках университетского курса по базам данных.

> **Статус проекта:** учебный, находится в разработке. Система моделирует процессы бронирования авиабилетов и не подключена к реальным авиакомпаниям или платёжным системам.

### 2. Основные возможности

| Раздел | Функциональность |
| --- | --- |
| Рейсы | Просмотр и поиск доступных рейсов, маршрутов и направлений |
| Цены | Календарное отображение стоимости авиабилетов |
| Места | Интерактивная схема салона и выбор свободного места |
| Бронирования | Создание бронирований и работа со статусами заявок и билетов |
| Отмена | Сохранение истории отмен и повторная доступность освобождённых мест |
| Пассажиры | Хранение сведений о пассажирах и связи с бронированиями |
| Билеты и оплаты | Учёт билетов и записей об оплате в учебной модели |
| Администрирование | Панель со сведениями о рейсах, пассажирах, бронированиях и аналитике |
| Визуализация | Интерактивный 3D-глобус с маршрутами авиаперелётов |

В расширенных версиях структуры БД предусмотрены временное удержание мест, данные пассажиров для отдельных билетов, дополнительные услуги, QR-токены и журнал операций. Наличие этих функций в работающем интерфейсе зависит от версии кода и применённых миграций.

### 3. Используемые технологии

| Компонент | Технологии |
| --- | --- |
| Серверная часть | Python 3.11+, Flask |
| База данных | PostgreSQL 13+ |
| Работа с БД | pgAdmin 4, SQL, PL/pgSQL |
| Интерфейс | HTML, CSS, JavaScript, шаблоны Flask/Jinja |
| 3D-визуализация | Three.js, Globe.gl |
| Контроль версий | Git, GitHub |

### 4. Структура базы данных

Основная база данных называется **`airline_booking_system`**. Базовая реляционная схема включает следующие таблицы:

| Таблица | Назначение |
| --- | --- |
| `airport` | Аэропорты отправления и прибытия |
| `aircraft` | Информация о самолётах |
| `route` | Маршруты между аэропортами |
| `seat` | Места в самолётах |
| `flight` | Запланированные рейсы |
| `passenger` | Информация о пассажирах |
| `booking` | Бронирования и их статусы |
| `ticket` | Билеты, связанные с рейсами, бронированиями и местами |
| `payment` | Записи об оплате |

Основные связи:

- У одного **самолёта** множество **мест**, самолёт может использоваться для выполнения **рейсов**.
- **Маршрут** соединяет аэропорты отправления и прибытия, а **рейс** выполняется по маршруту.
- **Пассажир** может иметь несколько **бронирований**; подтверждённые бронирования связаны с **билетами**.
- **Билет** связан с определёнными **рейсом** и **местом**.
- К **бронированию** относится информация об оплате.

Для обеспечения целостности данных применяются первичные и внешние ключи, ограничения и правила бронирования. В расширенной схеме частичный уникальный индекс предотвращает назначение одного места на одном рейсе нескольким активным билетам; отменённые билеты при этом сохраняются для истории.

> Точный состав полей и дополнительных таблиц определяется SQL-схемой и миграциями, находящимися в текущей версии проекта.

### 5. Установка и запуск

#### Необходимое ПО

- Python **3.11** или новее
- PostgreSQL **13** или новее
- `pip`
- pgAdmin 4 (рекомендуется для просмотра БД и импорта резервной копии)
- Локальная копия репозитория

#### Шаг 1 — Скачивание проекта

```bash
git clone https://github.com/IrgaleyevRamil/Airline_project.git
cd Airline_project
```

Также можно нажать **Code → Download ZIP** на странице репозитория и распаковать архив.

#### Шаг 2 — Создание виртуального окружения

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Шаг 3 — Установка зависимостей

```bash
pip install -r requirements.txt
```

#### Шаг 4 — Восстановление базы данных

1. Запустите PostgreSQL.
2. Создайте базу **`airline_booking_system`**, если резервная копия не создаёт её автоматически.
3. Импортируйте SQL-бэкап, предоставленный вместе с проектом.

Если резервная копия — обычный файл **`.sql`**, откройте его в **pgAdmin 4 → Query Tool** и выполните скрипт для нужной базы. Альтернативный вариант через терминал:

```bash
psql -U postgres -d airline_booking_system -f path/to/backup.sql
```

Замените `path/to/backup.sql` на реальный путь к файлу, а `postgres` — на своё имя пользователя PostgreSQL, если оно отличается. Для файлов пользовательского формата **`.backup` / `.dump`** используйте **Restore** в pgAdmin или `pg_restore`.

**Внимание:** восстанавливайте данные в подходящую учебную БД. Импорт может конфликтовать с уже существующими данными или перезаписывать их в зависимости от содержимого бэкапа.

#### Шаг 5 — Настройка окружения

Создайте локальный файл **`.env`** и заполните параметры подключения к PostgreSQL, которые использует приложение: имя БД, адрес сервера, порт, пользователя и пароль.

Для пароля администратора в конфигурации проекта используется переменная **`ADMIN_PASSWORD`**:

```dotenv
ADMIN_PASSWORD=replace_with_a_strong_local_password
```

Точные имена переменных подключения к БД смотрите в `app.py` и конфигурационных файлах проекта. **Не загружайте `.env`, реальные пароли, токены и персональные данные пассажиров в публичный GitHub-репозиторий.**

#### Шаг 6 — Применение миграций (при необходимости)

В проекте использовался файл миграций `migrate.py`:

```bash
python migrate.py
```

Запускайте его, только если этого требует версия вашей БД. После восстановления актуального полного бэкапа сначала проверьте, нужны ли дополнительные изменения схемы.

#### Шаг 7 — Запуск приложения

```bash
python app.py
```

Адрес приложения в браузере:

**http://127.0.0.1:5000**

В версиях с модулем администратора вход доступен по адресу **`/admin/login`**.

### 6. Пример сценария использования

1. Пользователь открывает приложение и выбирает направление или рейс.
2. Просматривает расписание, информацию о рейсе и стоимость.
3. Выбирает свободное место на интерактивной схеме.
4. Вводит необходимые данные пассажира и создаёт бронирование.
5. Просматривает информацию о бронировании и билете.
6. При необходимости отменяет бронь согласно предусмотренным правилам.

Администратор может использовать панель управления для просмотра данных о рейсах, пассажирах, бронированиях, билетах, оплатах и статистике.

### 7. Структура проекта

Пример основных компонентов (реальные пути могут отличаться в зависимости от версии проекта):

```text
Airline_project/
├── app.py                 # Запуск Flask-приложения
├── migrate.py             # Миграции базы данных, если есть
├── requirements.txt       # Зависимости Python
├── templates/             # HTML/Jinja-шаблоны
├── static/                # CSS, JavaScript и статические файлы
├── database/              # SQL-скрипты или бэкап, если хранится здесь
├── .gitignore             # Исключения для Git
└── README.md              # Документация
```

### 8. Ограничения проекта

- Проект создан **в учебных целях** и не предназначен для коммерческого использования в текущем виде.
- Таблицы оплат моделируют учёт платежей; подключение к **реальным платёжным системам не подразумевается**.
- Данные о рейсах могут быть демонстрационными, а не полученными от действующих авиакомпаний.
- Набор работающих функций зависит от версии исходного кода и миграций БД.
- Пароли, виртуальные окружения, временные файлы и персональные данные нельзя публиковать в открытом репозитории.

### 9. Возможные улучшения

- Автоматические тесты приложения и базы данных
- Более надёжная аутентификация и разграничение прав доступа
- Расширенная проверка данных и обработка ошибок
- Подробная отчётность и экспорт данных
- Инструкции по развёртыванию и автоматизация проверок

### 10. Автор

**IrgaleyevRamil**  
Учебный проект, **Казахстанско-Британский технический университет (КБТУ)**.

GitHub: **https://github.com/IrgaleyevRamil**

---

*Airline Booking System — academic database and web application project / учебный проект веб-приложения с реляционной базой данных.*
