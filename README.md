# ![Typing SVG](https://readme-typing-svg.herokuapp.com?color=%2336BCF7&lines=AIRFLOW)
Подъём AIRFLOW с помощью Docker и реализация DAG, описывающий сценарий: API-DAG-СУБД
# Структура проекта
```
airflow-docker
├── dags/                                   
│   ├── __pycache__                 #Кеширование
│   └── air_quality_dag.py          #Даг
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
1. DAG через задачи (например, PythonOperator с библиотекой requests) запрашивает данные из внешних API (погода, соцсети, CRM-системы).
2. Airflow преобразовывает данные: очистка, агрегация, джойны с другими источниками. Например:
```  
def process_data(**kwargs):
    data = kwargs['ti'].xcom_pull(task_ids='fetch_api_data')
    return cleaned_data
```
3. Результаты сохраняются в реляционную базу данных для аналитики, отчетов или ML-моделей. Например, с помощью PostgresOperator:
```  
load_to_db = PostgresOperator(
    task_id='load_data',
    sql="INSERT INTO table VALUES (...)",
    postgres_conn_id='my_postgres'
)
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
3. Создание requirements.txt
```
pandas==1.5.3
requests==2.28.2
psycopg2-binary==2.9.5
python-dotenv==0.21.0
```
4. Создание директорий
```
mkdir dags logs plugins
sudo chown -R 50000:0 ./logs ./plugins ./dags
```
5. Запуск
```
docker-compose up -d
```
