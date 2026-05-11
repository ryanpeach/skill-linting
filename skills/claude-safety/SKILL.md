Check ~/.claude/settings.json. Make sure that the agent can not do any of the following automatically:

1. Run any arbitrary code (e.g. via `python` or `bash` commands)
2. Delete any files or directories
3. Access any files outside of the project directory (e.g. via `cat /etc/passwd` or `ls ~`)
4. Make any network requests (e.g. via `curl` or `requests` library)
5. Install any new software on the system itself (e.g. via `apt install` or `pip install` or `brew install`)
6. Access any sensitive environment variables (e.g. `AWS_SECRET_KEY` or `DATABASE_URL`), or read or source the .env file