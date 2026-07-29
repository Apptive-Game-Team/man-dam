from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    upstage_api_key: str = ""  # Backend A가 사용, Backend B 로컬 개발엔 필수 아님

    class Config:
        env_file = ".env"


settings = Settings()
