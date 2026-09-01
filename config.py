from decouple import config

class Config:
    SECRET_KEY = config("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = config("DATABASE_URL")

    MAIL_SERVER = config("MAIL_SERVER")
    MAIL_PORT = config("MAIL_PORT", cast=int)
    MAIL_USE_TLS = config("MAIL_USE_TLS", cast=bool)
    MAIL_USE_SSL = config("MAIL_USE_SSL", cast=bool)
    MAIL_USERNAME = config("MAIL_USERNAME")
    MAIL_PASSWORD = config("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER_NAME = config("MAIL_DEFAULT_SENDER_NAME")
    MAIL_DEFAULT_SENDER = f"{MAIL_DEFAULT_SENDER_NAME} <{MAIL_USERNAME}>"