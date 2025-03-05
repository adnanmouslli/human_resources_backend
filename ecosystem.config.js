module.exports = {
  apps: [{
    name: "flask-app",
    script: "/root/human_resources_backend/venv/bin/python3",
    args: "-m gunicorn --bind 0.0.0.0:4000 'run:app'",
    cwd: "/root/human_resources_backend",
    env: {
      "FLASK_APP": "run.py",
      "FLASK_ENV": "production",
      "CORS_ALLOWED_ORIGINS": "*"
    }
  }]
}