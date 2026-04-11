from alerts import run_alert_pipeline


if __name__ == "__main__":
    run_alert_pipeline(config_path="config/jobs_queries.yaml", alert_type="SDE Intern Jobs")
