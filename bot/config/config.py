from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int = 1
    API_HASH: str = "1"
   
    AUTO_TASK: bool = True
    API_CHANGE_DETECTION: bool = True

    REF_ID: str = ''
    USE_PROXY_FROM_FILE: bool = False
    

settings = Settings()


