from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import requests
import logging

default_args = {
    'owner': 'admin',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

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
    
    CREATE INDEX IF NOT EXISTS idx_air_quality_location ON air_quality_data(latitude, longitude);
    CREATE INDEX IF NOT EXISTS idx_air_quality_timestamp ON air_quality_data(timestamp);
    """
    cursor.execute(create_table_query)
    conn.commit()
    cursor.close()
    conn.close()
    logging.info("Таблица air_quality_data создана")

def get_air_quality_data():
    """Получение данных о качестве воздуха из Open-Meteo API"""
    
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
            
            if 'hourly' in data and 'time' in data['hourly']:
                times = data['hourly']['time']
                
                for i, timestamp in enumerate(times):
                    if i == len(times) - 1: 
                        air_quality_record = {
                            'latitude': location['lat'],
                            'longitude': location['lon'],
                            'location_name': location['name'],
                            'timestamp': timestamp,
                            'pm10': data['hourly']['pm10'][i] if i < len(data['hourly']['pm10']) else None,
                            'pm2_5': data['hourly']['pm2_5'][i] if i < len(data['hourly']['pm2_5']) else None,
                            'carbon_monoxide': data['hourly']['carbon_monoxide'][i] if i < len(data['hourly']['carbon_monoxide']) else None,
                            'nitrogen_dioxide': data['hourly']['nitrogen_dioxide'][i] if i < len(data['hourly']['nitrogen_dioxide']) else None,
                            'sulphur_dioxide': data['hourly']['sulphur_dioxide'][i] if i < len(data['hourly']['sulphur_dioxide']) else None,
                            'ozone': data['hourly']['ozone'][i] if i < len(data['hourly']['ozone']) else None,
                            'aerosol_optical_depth': data['hourly']['aerosol_optical_depth'][i] if i < len(data['hourly']['aerosol_optical_depth']) else None,
                            'dust': data['hourly']['dust'][i] if i < len(data['hourly']['dust']) else None,
                            'uv_index': data['hourly']['uv_index'][i] if i < len(data['hourly']['uv_index']) else None,
                            'us_aqi': data['hourly']['us_aqi'][i] if i < len(data['hourly']['us_aqi']) else None,
                            'european_aqi': data['hourly']['european_aqi'][i] if i < len(data['hourly']['european_aqi']) else None,
                        }
                        all_air_quality_data.append(air_quality_record)
            
            logging.info(f"Получены данные о качестве воздуха для {location['name']}")
            
        except Exception as e:
            logging.error(f"Ошибка для {location['name']}: {str(e)}")
            continue
    
    logging.info(f"Всего получено {len(all_air_quality_data)} записей")
    return all_air_quality_data

def save_air_quality_data(**kwargs):
    """Сохранение данных о качестве воздуха в БД приложения"""
    ti = kwargs['ti']
    air_quality_data = ti.xcom_pull(task_ids='fetch_air_quality')
    
    if not air_quality_data:
        logging.warning("Нет данных для сохранения")
        return
    
    #Используем подключение к БД данных приложения
    hook = PostgresHook(postgres_conn_id='postgres_app')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    inserted_count = 0
    
    for record in air_quality_data:
        check_query = """
        SELECT id FROM air_quality_data 
        WHERE latitude = %s AND longitude = %s AND timestamp = %s
        """
        cursor.execute(check_query, (record['latitude'], record['longitude'], record['timestamp']))
        existing_record = cursor.fetchone()
        
        if not existing_record:
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
            inserted_count += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info(f"Сохранено {inserted_count} новых записей в БД приложения")

def analyze_air_quality():
    """Анализ данных о качестве воздуха из БД приложения"""
    hook = PostgresHook(postgres_conn_id='postgres_app')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    queries = {
        "total_records": "SELECT COUNT(*) FROM air_quality_data",
        "locations_count": "SELECT COUNT(DISTINCT location_name) FROM air_quality_data",
        "latest_data": "SELECT location_name, MAX(timestamp) as latest FROM air_quality_data GROUP BY location_name",
        "avg_pm25_by_city": "SELECT location_name, AVG(pm2_5) as avg_pm25 FROM air_quality_data WHERE timestamp >= NOW() - INTERVAL '24 hours' GROUP BY location_name"
    }
    
    logging.info("=== АНАЛИЗ ДАННЫХ ИЗ БД ПРИЛОЖЕНИЯ ===")
    
    for query_name, query in queries.items():
        cursor.execute(query)
        result = cursor.fetchall()
        logging.info(f"{query_name}: {result}")
    
    cursor.close()
    conn.close()

with DAG(
    'air_quality_monitoring',
    default_args=default_args,
    description='DAG для мониторинга качества воздуха с отдельной БД данных',
    schedule_interval=timedelta(hours=3),
    catchup=False,
    tags=['air-quality', 'open-meteo', 'environment'],
) as dag:

    create_table_task = PythonOperator(
        task_id='create_air_quality_table',
        python_callable=create_air_quality_table,
    )

    fetch_air_quality_task = PythonOperator(
        task_id='fetch_air_quality',
        python_callable=get_air_quality_data,
    )

    save_air_quality_task = PythonOperator(
        task_id='save_air_quality_data',
        python_callable=save_air_quality_data,
        provide_context=True,
    )

    analyze_air_quality_task = PythonOperator(
        task_id='analyze_air_quality',
        python_callable=analyze_air_quality,
    )

    create_table_task >> fetch_air_quality_task >> save_air_quality_task >> analyze_air_quality_task