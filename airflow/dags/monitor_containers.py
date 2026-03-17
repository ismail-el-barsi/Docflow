import json
import subprocess
from datetime import datetime, timedelta

from airflow.operators.python import PythonOperator

from airflow import DAG

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'monitor_and_restart_containers',
    default_args=default_args,
    description='A DAG to monitor and restart docker containers if they are down',
    schedule_interval=timedelta(minutes=1),
    catchup=False
)

def check_and_restart():
    try:
        # Fetch all containers via Docker socket using curl
        cmd = ["curl", "-s", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/json?all=1"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        containers = json.loads(result.stdout)
        
        services_to_monitor = ["backend", "frontend"]
        
        for container in containers:
            labels = container.get("Labels", {})
            service_name = labels.get("com.docker.compose.service")
            project_name = labels.get("com.docker.compose.project")
            
            if service_name in services_to_monitor:
                state = container.get("State")
                container_id = container.get("Id")
                
                if state != "running":
                    print(f"Container {service_name} (Project: {project_name}) is currently {state}. Sending restart command...")
                    restart_cmd = ["curl", "-X", "POST", "-s", "--unix-socket", "/var/run/docker.sock", f"http://localhost/containers/{container_id}/restart"]
                    subprocess.run(restart_cmd)
                    print(f"Restart command sent for {service_name}.")
                else:
                    print(f"Container {service_name} is running normally.")
                    
    except Exception as e:
        print(f"An error occurred while monitoring containers: {e}")

monitor_task = PythonOperator(
    task_id='check_container_status',
    python_callable=check_and_restart,
    dag=dag,
)
