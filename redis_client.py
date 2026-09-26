from upstash_redis import Redis

from config import settings

redis_client = Redis(url=settings.UPSTASH_URL, token=settings.UPSTASH_TOKEN)
