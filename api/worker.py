from api.settings import settings


class WorkerSettings:
    redis_settings = settings.redis_url
    functions = []
