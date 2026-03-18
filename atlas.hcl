env "local" {
  src = "file://backend/schema.sql"
  url = getenv("DATABASE_URL")
  dev = "docker://postgres/16/dev"
  migration {
    dir = "file://backend/migrations"
  }
}
