#!/bin/bash
set -e

echo "#################################################"
echo "Starting ${GITHUB_WORKFLOW}:${GITHUB_ACTION}"
echo ${DEFAULT_TARGET_BRANCH}
echo $env

pylint_git --ignore-patterns=".*_pb2\.py",".*template\.py","(.*_)?test(_.*)?\.py","(.*_)?mock.*\.py","^\d{4}_.*\.py" --indent-string="    " --disable=C0122 --output-format=colorized --reports=no --msg-template="{abspath} ({line}:{column}) {obj} [{msg_id}:{symbol}] {msg}" --target-branch=$env:DEFAULT_TARGET_BRANCH

echo "#################################################"
echo "Completed ${GITHUB_WORKFLOW}:${GITHUB_ACTION}"