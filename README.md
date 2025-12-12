# ![Typing SVG](https://readme-typing-svg.herokuapp.com?color=%2336BCF7&lines=AIRFLOW)
Подъём AIRFLOW с помощью Docker и реализация DAG, описывающий сценарий: API-DAG-СУБД
# Структура проекта
```
airflow-docker
├── dags/                                   
│   ├── __pycache__                 #Кеширование
│   └── air_quality_dag.py          #Даг
│
├── init_app_db.sql/
│   └── init_app_db.sql             #Создание пользователя и обновление его прав
│
├── logs/
│   ├── dag_id=<имя dag>            #Логи выполнения конкретных дагов
│   ├── dag_processor_manager       #Логи менеджера по обработке дагов
│   └── scheduler                   #Логи планировщика Airflow
│
├── plugins/                        #Кастомные плагины и операторы     
│
├── venv/
│   └── pyvenv.cfg                  #Конфигурация виртуального окружения
│
├── README.md                       #Документация к проекту
├── docker-compose.yaml             #Файл для развертывания Airflow с помощью Docker
└── requirements.txt                #Установленные зависимости
``` 
# Для чего это нужно?
- Docker гарантирует одинаковую конфигурацию Airflow (версии Python, библиотек, зависимостей) в разработке, тестировании и продакшене. Это исключает проблемы вроде «на моей машине работало».
- Готовые образы Airflow и docker-compose.yaml позволяют запустить кластер (веб-сервер, scheduler) за минуты, без ручной настройки.
- Легко масштабировать воркеры Airflow под нагрузку или интегрировать с другими сервисами (PostgreSQL, Redis, Kafka) через Docker-сети.
# И всё таки "Сценарий API → DAG → СУБД" - Зачем это нужно?
### Этот паттерн описывает классический ETL/ELT-процесс:
1. DAG через задачи запрашивает данные из внешних API (погода, соцсети, CRM-системы). Пример из проекта:
```
def get_air_quality_data():
    
    locations = [
        {"name": "Moscow", "lat": 55.7558, "lon": 37.6173},
        {"name": "Saint Petersburg", "lat": 59.9343, "lon": 30.3351},
        {"name": "Novosibirsk", "lat": 55.0084, "lon": 82.9357},
    ]
    
    all_air_quality_data = []
    
    for location in locations:
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            'latitude': location['lat'],
            'longitude': location['lon'],
            'hourly': 'pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,aerosol_optical_depth,dust,uv_index,us_aqi,european_aqi',
            'timezone': 'Europe/Moscow',
            'past_days': 1
        }
        
        try:
            logging.info(f"Запрос данных для {location['name']}...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
```
2. Airflow преобразовывает данные: очистка, агрегация, джойны с другими источниками. В приведённом примере данные извлекаются через XCom и обрабатываются:
```  
def save_air_quality_data(**kwargs):
    """Сохранение данных о качестве воздуха в БД приложения"""
    ti = kwargs['ti']
    air_quality_data = ti.xcom_pull(task_ids='fetch_air_quality')
    
    if not air_quality_data:
        logging.warning("Нет данных для сохранения")
        return
    
    for record in air_quality_data:
        check_query = """
        SELECT id FROM air_quality_data 
        WHERE latitude = %s AND longitude = %s AND timestamp = %s
        """
        cursor.execute(check_query, (record['latitude'], record['longitude'], record['timestamp']))
        existing_record = cursor.fetchone()
        
        if not existing_record:
            #... логика вставки
```
3. Результаты сохраняются в реляционную базу данных для аналитики, отчетов или ML-моделей. В этом примере используется PostgresHook для работы с БД:
```  
def save_air_quality_data(**kwargs):
    """Сохранение данных о качестве воздуха в БД приложения"""

    hook = PostgresHook(postgres_conn_id='postgres_app')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    for record in air_quality_data:
        insert_query = """
        INSERT INTO air_quality_data (
            latitude, longitude, location_name, timestamp, pm10, pm2_5, 
            carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone,
            aerosol_optical_depth, dust, uv_index, us_aqi, european_aqi
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            record['latitude'],
            record['longitude'],
            record['location_name'],
            record['timestamp'],
            record['pm10'],
            record['pm2_5'],
            record['carbon_monoxide'],
            record['nitrogen_dioxide'],
            record['sulphur_dioxide'],
            record['ozone'],
            record['aerosol_optical_depth'],
            record['dust'],
            record['uv_index'],
            record['us_aqi'],
            record['european_aqi']
        ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info(f"Сохранено {inserted_count} новых записей в БД приложения")
```
Также для создания таблиц можно использовать прямой SQL через PostgresHook, как показано в функции `create_air_quality_table()`:
```
def create_air_quality_table():
    """Создание таблицы для данных о качестве воздуха в БД приложения"""
    hook = PostgresHook(postgres_conn_id='postgres_app')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    create_table_query = """
    CREATE TABLE IF NOT EXISTS air_quality_data (
        id SERIAL PRIMARY KEY,
        latitude DECIMAL(9,6),
        longitude DECIMAL(9,6),
        location_name VARCHAR(255),
        timestamp TIMESTAMP,
        pm10 DECIMAL(8,2),
        pm2_5 DECIMAL(8,2),
        carbon_monoxide DECIMAL(8,2),
        nitrogen_dioxide DECIMAL(8,2),
        sulphur_dioxide DECIMAL(8,2),
        ozone DECIMAL(8,2),
        aerosol_optical_depth DECIMAL(8,2),
        dust DECIMAL(8,2),
        uv_index DECIMAL(6,2),
        us_aqi INTEGER,
        european_aqi INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_table_query)
    conn.commit()
```
### Где это необходимо?
- Data Engineering: Построение надежных пайплайнов для аналитики.
- ML-проекты: Регулярное обновление обучающих данных из API.

# Как работает проект?
### Установка необходимых файлов для Airflow
1. Создать папку для Airflow (Выполнение команд допускается в любом терминале):
```
mkdir airflow-docker
cd airflow-docker
```
2. В ней файл `docker-compose.yaml`:
```
version: '3'
services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  airflow-webserver:
    image: apache/airflow:2.7.1
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
      - AIRFLOW__CORE__LOAD_EXAMPLES=false
      - AIRFLOW__WEBSERVER__EXPOSE_CONFIG=true
      - _AIRFLOW_DB_UPGRADE=true
      - _AIRFLOW_WWW_USER_CREATE=true
      - _AIRFLOW_WWW_USER_USERNAME=admin
      - _AIRFLOW_WWW_USER_PASSWORD=admin
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./requirements.txt:/opt/airflow/requirements.txt
    ports:
      - "8080:8080"
    command: webserver
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
    depends_on:
      postgres:
        condition: service_healthy

  airflow-scheduler:
    image: apache/airflow:2.7.1
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
      - AIRFLOW__CORE__LOAD_EXAMPLES=false
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./requirements.txt:/opt/airflow/requirements.txt
    command: scheduler
    depends_on:
      postgres:
        condition: service_healthy
      airflow-webserver:
        condition: service_healthy

volumes:
  postgres_data:
```
Если нужен `redis` заменить:
```
environment:
  - AIRFLOW__CORE__EXECUTOR=CeleryExecutor
  - AIRFLOW__CELERY__BROKER_URL=redis://redis:6379/0
  - AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres/airflow
```
3. Создание `requirements.txt`:
```
pandas==1.5.3
requests==2.28.2
psycopg2-binary==2.9.5
python-dotenv==0.21.0
```
4. Создание директорий:
```
mkdir dags logs plugins
sudo chown -R 50000:0 ./logs ./plugins ./dags
```
5. Запуск:
```
docker-compose up -d
```
