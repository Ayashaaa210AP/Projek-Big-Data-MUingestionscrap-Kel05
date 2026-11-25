from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# ==========================================
# DEFAULT ARGS
# ==========================================
default_args = {
    'owner': 'kelompok_05',
    'depends_on_past': False,
    'start_date': datetime(2026, 11, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# ==========================================
# FUNGSI PEMBUNGKUS (LAZY IMPORT)
# ==========================================
# Kita pindahkan import ke dalam fungsi agar Airflow tidak timeout
# saat sedang membaca file dags.py.
def run_scraping():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from script.main import main as scrape_and_ingest
    scrape_and_ingest()

def run_preprocessing():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from script.preprocessing import process_data
    process_data()

# ==========================================
# DAG 1: INGESTION PIPELINE
# ==========================================
with DAG(
    dag_id='dag_mu_news_ingestion',
    default_args=default_args,
    description='Pipeline 1: Scrape ANTARA Liga Inggris & Load ke Bronze',
    schedule='0 */3 * * *', 
    catchup=False,
    tags=['MU', 'Ingestion', 'Bronze'],
) as dag1:

    task_scrape_and_load = PythonOperator(
        task_id='task_fetch_parse_load_staging',
        python_callable=run_scraping, # <-- Memanggil fungsi pembungkus
    )

    trigger_dag2 = TriggerDagRunOperator(
        task_id='trigger_dag_dw_transformation',
        trigger_dag_id='dag_mu_dw_transformation',
        wait_for_completion=False,
    )

    task_scrape_and_load >> trigger_dag2

# ==========================================
# DAG 2: TRANSFORMATION & NLP (DATA WAREHOUSE)
# ==========================================
with DAG(
    dag_id='dag_mu_dw_transformation',
    default_args=default_args,
    description='Pipeline 2: NLP Sentimen & Load ke Data Warehouse (Star Schema)',
    schedule=None, 
    catchup=False,
    tags=['MU', 'NLP', 'DataWarehouse'],
) as dag2:

    task_transform_and_load_dw = PythonOperator(
        task_id='task_nlp_sentiment_and_load_dw',
        python_callable=run_preprocessing, # <-- Memanggil fungsi pembungkus
    )

    task_transform_and_load_dw