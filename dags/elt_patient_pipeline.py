from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
import pendulum
import pandas as pd

# 🌟 1. dbt 프로젝트가 위치한 경로 (Airflow 컨테이너 내부 경로)
DBT_PROJECT_DIR = "/opt/airflow/dbt"
# 🌟 2. CSV 파일이 위치한 경로 (Airflow 컨테이너 내부 경로)
DATA_FILE_PATH = "/opt/airflow/data/patient_treatment.csv"
# 🌟 3. 적재할 DB의 Connection ID (Airflow UI에서 만들 필요 없음. Hook이 직접 연결)
POSTGRES_CONN_ID = "de_project_postgres" # docker-compose.yml의 서비스 이름 사용

@dag(
    dag_id="elt_patient_pipeline",
    start_date=pendulum.datetime(2023, 1, 1, tz="Asia/Seoul"),
    schedule=None,
    catchup=False,
)
def elt_patient_pipeline():
    """
    [2단계] ELT 파이프라인 (Airflow + dbt)
    1. (EL) CSV 파일을 Pandas로 읽어 Postgres(analytics_db)에 적재
    2. (T) dbt를 실행하여 적재된 데이터를 변환
    """

    @task
    def load_csv_to_postgres():
        """
        [E + L] CSV 파일을 Pandas로 읽어 Postgres 'raw.raw_patient_events' 테이블에 적재
        """
        # 1. CSV 파일 읽기
        df = pd.read_csv(DATA_FILE_PATH, header=0)
        
        # 2. PostgresHook을 사용하여 DB 연결 (dbname을 'analytics_db'로 지정)
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID, database="analytics_db")
        
        # 3. 'raw' 스키마가 없으면 생성합니다.
        hook.run("CREATE SCHEMA IF NOT EXISTS raw;")
        
        # 4. 🌟 CASCADE 옵션으로 테이블 및 의존 객체(뷰)를 강제 삭제합니다.
        hook.run("DROP TABLE IF EXISTS raw.raw_patient_events CASCADE;")

        # 5. hook에서 SQLAlchemy 엔진을 가져옵니다.
        engine = hook.get_sqlalchemy_engine()

        # 6. 🌟 pandas.to_sql을 사용합니다.
        #    if_exists='append' : 4번에서 테이블을 확실히 지웠으므로,
        #                       테이블을 새로 생성하고 데이터를 'append' (추가)합니다.
        df.to_sql(
            name="raw_patient_events",  # 테이블 이름
            con=engine,                 # SQLAlchemy 엔진
            schema="raw",               # 스키마 이름
            if_exists="append",         # 🌟 'replace' -> 'append'로 변경
            index=False                 # Pandas의 인덱스는 저장하지 않음
        )
        
        print(f"Successfully loaded {len(df)} rows to raw.raw_patient_events")

    # [T] dbt 실행 (BashOperator 사용)
    run_dbt = BashOperator(
        task_id="run_dbt",
        # 🌟 dbt 프로젝트 폴더로 이동하여 'dbt run'을 실행합니다.
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run"
    )

    # 파이프라인 순서 설정: load 태스크가 성공해야 run_dbt 태스크가 실행됨
    load_csv_to_postgres() >> run_dbt

# DAG 실행
elt_patient_pipeline()