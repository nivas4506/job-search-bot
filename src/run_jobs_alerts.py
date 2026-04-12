from src.alerts import run_alert_pipeline


def main() -> None:
    run_alert_pipeline(config_path="config/jobs_queries.yaml", alert_type="SDE Intern Jobs")


if __name__ == "__main__":
    main()
