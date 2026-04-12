from src.alerts import run_alert_pipeline


def main() -> None:
    run_alert_pipeline(config_path="config/hackathons_queries.yaml", alert_type="Hackathons India")


if __name__ == "__main__":
    main()
