FROM vcoder/git_pylint:0.0.1

LABEL "com.github.actions.name"="Git Pylint GitHub Action"
LABEL "com.github.actions.description"="Run Pylint on PR change files only"
LABEL "com.github.actions.icon"="code"
LABEL "com.github.actions.color"="black"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]