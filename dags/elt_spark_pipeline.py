from airflow.decorators import dag
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.bash import BashOperator
import pendulum

SPARK_CONN_ID = "spark_default"
SPARK_JOB_FILE = "/opt/airflow/scripts/spark_load_patients.py"

@dag(
    dag_id="elt_spark_pipeline",
    start_date=pendulum.datetime(2023, 1, 1, tz="Asia/Seoul"),
    schedule=None,
    catchup=False,
)
def elt_spark_pipeline():

    load_csv_with_spark = SparkSubmitOperator(
        task_id="load_csv_with_spark",
        conn_id=SPARK_CONN_ID,
        application=SPARK_JOB_FILE,
        verbose=True,
        # PostgreSQL 드라이버
        packages="org.postgresql:postgresql:42.6.0",
        # 🌟 [설정 수정]
        # 1. master: docker-compose의 컨테이너 이름 사용 (de_project_spark_master)
        # 2. driver.host: docker-compose의 컨테이너 이름 사용 (de_project_airflow_scheduler)
        #    -> 이렇게 하면 DNS 문제가 완벽하게 해결됩니다.
        conf={
            "spark.master": "spark://de_project_spark_master:7077",
            "spark.submit.deployMode": "client",
            "spark.driver.host": "de_project_airflow_scheduler",
            "spark.driver.bindAddress": "0.0.0.0"
        }
    )

    run_dbt = BashOperator(
        task_id="run_dbt_after_spark",
        bash_command="cd /opt/airflow/dbt && /opt/dbt_venv/bin/dbt run"
    )

    load_csv_with_spark >> run_dbt

elt_spark_pipeline()