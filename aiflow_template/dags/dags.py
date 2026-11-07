from airflow import DAG
from airflow.operators.python import PythonOperator

# script to crawl
# script to insert 

from script.main import main

with DAG(
    "dags_scraping",
    description="Scraping data...",
    schedule="*/5 * * * *"
) as dag:    
    task = PythonOperator(
        task_id="airflow_scraping",
        python_callable=main
    )
    
    task