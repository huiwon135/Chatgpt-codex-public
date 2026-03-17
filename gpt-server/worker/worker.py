import os
import time
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.from_url(REDIS_URL, decode_responses=True)


def main():
    while True:
        _ = r.ping()
        time.sleep(30)


if __name__ == "__main__":
    main()
