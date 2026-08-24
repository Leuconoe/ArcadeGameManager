import logging

from bsm.paths import PortablePaths
from bsm.ui import run


def configure_logging(paths: PortablePaths) -> None:
    log_directory = paths.root / "data" / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_directory / "manager.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


if __name__ == "__main__":
    portable_paths = PortablePaths.discover()
    configure_logging(portable_paths)
    logging.info("Arcade Game Manager starting; root=%s", portable_paths.root)
    try:
        run(portable_paths)
    except Exception:
        logging.exception("Arcade Game Manager terminated by an unhandled error")
        raise
